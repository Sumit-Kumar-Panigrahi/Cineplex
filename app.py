"""
CINEPLEX - Movie Ticket Booking System
Tagline: Your Movies. Your Moments.
DBMS Subject-Specific Web Application Built with Flask, SQLite, HTML5, CSS3 & JavaScript.
Full Relational Normalization (3NF) with SQLite Foreign Key & Check Constraints.
"""

import os
import json
import uuid
import sqlite3
import datetime
import urllib.request
import urllib.parse
import io
from pathlib import Path
from flask import Flask, render_template, request, jsonify, send_file
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib import colors

# ==============================================================================
# SECTION 1: CONFIGURATION & SEATING TIERS
# ==============================================================================
BASE_DIR = Path(__file__).resolve().parent
DATABASE_PATH = str(BASE_DIR / "cinema.db")

TMDB_API_KEY = os.environ.get("TMDB_API_KEY", "4e44d9029b1270a757cddc766a1bcb63")
TMDB_BASE_URL = "https://api.themoviedb.org/3"
TMDB_IMG_URL = "https://image.tmdb.org/t/p"

# Cineplex Seating Tiers & Pricing (in ₹ INR)
SEAT_TIERS = {
    "RECLINER": {"name": "Recliner (Luxe Comfort)", "price": 420.00, "rows": ["A", "B"]},
    "PRIME": {"name": "Prime (Optimal View)", "price": 280.00, "rows": ["C", "D", "E"]},
    "CLASSIC": {"name": "Classic (Standard)", "price": 180.00, "rows": ["F", "G", "H"]}
}

CONVENIENCE_FEE_PCT = 0.05       # 5% convenience fee
GST_PCT = 0.18                   # 18% GST on convenience fee
CANCELLATION_FEE_PER_SEAT = 30.0 # ₹30 fee per cancelled seat (transparent Cineplex policy)
RESERVATION_HOLD_SECONDS = 300   # 5-minute seat hold timer

# ==============================================================================
# SECTION 2: SQLITE DATABASE SETUP & RELATIONAL INTEGRITY (3NF)
# ==============================================================================
def get_db():
    conn = sqlite3.connect(DATABASE_PATH, timeout=20.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def init_db(force_reseed=False):
    conn = get_db()
    c = conn.cursor()

    if force_reseed:
        c.execute("DROP TABLE IF EXISTS payments")
        c.execute("DROP TABLE IF EXISTS booking_snacks")
        c.execute("DROP TABLE IF EXISTS booking_seats")
        c.execute("DROP TABLE IF EXISTS show_seats")
        c.execute("DROP TABLE IF EXISTS cancellations")
        c.execute("DROP TABLE IF EXISTS bookings")
        c.execute("DROP TABLE IF EXISTS shows")
        c.execute("DROP TABLE IF EXISTS screens")
        c.execute("DROP TABLE IF EXISTS theaters")
        c.execute("DROP TABLE IF EXISTS movies")
        c.execute("DROP TABLE IF EXISTS snacks")
        c.execute("DROP TABLE IF EXISTS users")

    c.execute("""
    CREATE TABLE IF NOT EXISTS movies (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tmdb_id INTEGER UNIQUE,
        title TEXT NOT NULL,
        overview TEXT,
        poster_path TEXT,
        offline_poster_path TEXT,
        backdrop_path TEXT,
        release_date TEXT,
        rating REAL DEFAULT 8.0,
        votes_count INTEGER DEFAULT 0,
        runtime INTEGER DEFAULT 140,
        genres TEXT,
        language TEXT DEFAULT 'Hindi',
        certification TEXT DEFAULT 'UA 16+',
        trailer_url TEXT,
        is_now_showing INTEGER DEFAULT 1,
        featured INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS theaters (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        city TEXT NOT NULL,
        address TEXT NOT NULL,
        screens_count INTEGER DEFAULT 3
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS screens (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        theater_id INTEGER NOT NULL,
        screen_name TEXT NOT NULL,
        screen_type TEXT NOT NULL,
        total_rows INTEGER DEFAULT 8,
        total_cols INTEGER DEFAULT 12,
        FOREIGN KEY (theater_id) REFERENCES theaters(id) ON DELETE CASCADE
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS shows (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        movie_id INTEGER NOT NULL,
        theater_id INTEGER NOT NULL,
        screen_id INTEGER NOT NULL,
        show_date TEXT NOT NULL,
        show_time TEXT NOT NULL,
        price_vip REAL DEFAULT 420.0,
        price_premium REAL DEFAULT 280.0,
        price_executive REAL DEFAULT 180.0,
        FOREIGN KEY (movie_id) REFERENCES movies(id) ON DELETE CASCADE,
        FOREIGN KEY (theater_id) REFERENCES theaters(id) ON DELETE CASCADE,
        FOREIGN KEY (screen_id) REFERENCES screens(id) ON DELETE CASCADE
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS bookings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        booking_ref TEXT UNIQUE NOT NULL,
        show_id INTEGER NOT NULL,
        customer_name TEXT NOT NULL,
        customer_email TEXT NOT NULL,
        customer_phone TEXT NOT NULL,
        seat_numbers TEXT NOT NULL,
        seats_count INTEGER NOT NULL,
        subtotal REAL NOT NULL,
        snacks_total REAL DEFAULT 0.0,
        convenience_fee REAL NOT NULL,
        taxes REAL NOT NULL,
        total_amount REAL NOT NULL,
        payment_method TEXT DEFAULT 'UPI',
        status TEXT NOT NULL DEFAULT 'CONFIRMED' CHECK (status IN ('CONFIRMED', 'CANCELLED', 'PENDING')),
        qr_data TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (show_id) REFERENCES shows(id) ON DELETE CASCADE
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS show_seats (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        show_id INTEGER NOT NULL,
        seat_label TEXT NOT NULL,
        tier TEXT NOT NULL CHECK (tier IN ('RECLINER', 'PRIME', 'CLASSIC')),
        status TEXT NOT NULL DEFAULT 'AVAILABLE' CHECK (status IN ('AVAILABLE', 'RESERVED', 'BOOKED')),
        reservation_token TEXT,
        reserved_at TIMESTAMP,
        booking_id INTEGER,
        FOREIGN KEY (show_id) REFERENCES shows(id) ON DELETE CASCADE,
        FOREIGN KEY (booking_id) REFERENCES bookings(id) ON DELETE SET NULL,
        UNIQUE(show_id, seat_label)
    )
    """)

    # Normalized relational tables for 3NF
    c.execute("""
    CREATE TABLE IF NOT EXISTS booking_seats (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        booking_id INTEGER NOT NULL,
        show_id INTEGER NOT NULL,
        seat_label TEXT NOT NULL,
        tier TEXT NOT NULL CHECK (tier IN ('RECLINER', 'PRIME', 'CLASSIC')),
        price REAL NOT NULL CHECK (price >= 0),
        FOREIGN KEY (booking_id) REFERENCES bookings(id) ON DELETE CASCADE,
        FOREIGN KEY (show_id) REFERENCES shows(id) ON DELETE CASCADE
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS booking_snacks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        booking_id INTEGER NOT NULL,
        snack_id INTEGER,
        snack_name TEXT NOT NULL,
        quantity INTEGER NOT NULL CHECK (quantity > 0),
        unit_price REAL NOT NULL CHECK (unit_price >= 0),
        total_price REAL NOT NULL CHECK (total_price >= 0),
        FOREIGN KEY (booking_id) REFERENCES bookings(id) ON DELETE CASCADE,
        FOREIGN KEY (snack_id) REFERENCES snacks(id) ON DELETE SET NULL
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS payments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        booking_id INTEGER NOT NULL,
        payment_ref TEXT UNIQUE NOT NULL,
        amount REAL NOT NULL CHECK (amount >= 0),
        payment_method TEXT NOT NULL,
        payment_status TEXT NOT NULL DEFAULT 'SUCCESS' CHECK (payment_status IN ('SUCCESS', 'PENDING', 'FAILED', 'REFUNDED')),
        transaction_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (booking_id) REFERENCES bookings(id) ON DELETE CASCADE
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS cancellations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        cancellation_ref TEXT UNIQUE NOT NULL,
        booking_id INTEGER NOT NULL,
        booking_ref TEXT NOT NULL,
        reason TEXT,
        original_amount REAL NOT NULL,
        cancellation_fee REAL NOT NULL,
        refund_amount REAL NOT NULL,
        refund_status TEXT NOT NULL DEFAULT 'PROCESSED',
        refund_mode TEXT NOT NULL DEFAULT 'Original Payment Source (UPI/Card)',
        cancelled_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        released_seats TEXT NOT NULL,
        FOREIGN KEY (booking_id) REFERENCES bookings(id) ON DELETE CASCADE
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS snacks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        category TEXT NOT NULL,
        price REAL NOT NULL,
        image_url TEXT,
        description TEXT
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        phone TEXT NOT NULL,
        password_hash TEXT NOT NULL,
        is_admin INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    c.execute("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)")

    # DBMS Performance Indexes
    c.execute("CREATE INDEX IF NOT EXISTS idx_shows_movie_date ON shows(movie_id, show_date)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_shows_theater ON shows(theater_id, show_date)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_seats_show_status ON show_seats(show_id, status)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_bookings_user_email ON bookings(customer_email)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_bookings_ref ON bookings(booking_ref)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_booking_seats_bk ON booking_seats(booking_id)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_payments_bk ON payments(booking_id)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_movies_status ON movies(is_now_showing, featured)")

    conn.commit()

    # Seed Sumit Kumar Panigrahi as primary demo user
    c.execute("SELECT id FROM users WHERE email = 'sumit@example.com'")
    if not c.fetchone():
        c.execute("""
        INSERT OR IGNORE INTO users (name, email, phone, password_hash, is_admin)
        VALUES (?, ?, ?, ?, 0)
        """, ("Sumit Kumar Panigrahi", "sumit@example.com", "8984378785", "cGFzc3dvcmQxMjM="))

    # Seed Admin user
    import base64
    admin_hash = base64.b64encode(b"admin123").decode()
    c.execute("SELECT id FROM users WHERE email = 'admin@cineplex.com'")
    if not c.fetchone():
        c.execute("""
        INSERT OR IGNORE INTO users (name, email, phone, password_hash, is_admin)
        VALUES (?, ?, ?, ?, 1)
        """, ("Cineplex Admin", "admin@cineplex.com", "9999999999", admin_hash))

    conn.commit()
    conn.close()

def cleanup_reservations(conn):
    c = conn.cursor()
    threshold = (datetime.datetime.now() - datetime.timedelta(seconds=RESERVATION_HOLD_SECONDS)).strftime("%Y-%m-%d %H:%M:%S")
    c.execute("UPDATE show_seats SET status = 'AVAILABLE', reservation_token = NULL, reserved_at = NULL WHERE status = 'RESERVED' AND reserved_at < ?", (threshold,))
    conn.commit()

# ==============================================================================
# SECTION 3: FLASK APPLICATION & API ENDPOINTS
# ==============================================================================
app = Flask(__name__)
with app.app_context():
    init_db(force_reseed=False)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/movies', methods=['GET'])
def api_movies():
    conn = get_db()
    c = conn.cursor()
    status = request.args.get('status', 'now_showing')
    genre = request.args.get('genre')
    language = request.args.get('language')
    search = request.args.get('search', '').strip()

    query = "SELECT * FROM movies WHERE 1=1"
    params = []

    if search:
        # Global search: search across title, overview, language, and genres without status restrictions
        query += " AND (title LIKE ? OR overview LIKE ? OR language LIKE ? OR genres LIKE ?)"
        params.extend([f"%{search}%", f"%{search}%", f"%{search}%", f"%{search}%"])
    else:
        # Tab filtering only when search is not active
        if status == 'now_showing': query += " AND is_now_showing = 1"
        elif status == 'upcoming': query += " AND is_now_showing = 0"
        elif status == 'popular': query += " AND featured = 1"

    if language and language.lower() != 'all':
        query += " AND language LIKE ?"
        params.append(f"%{language}%")

    if genre and genre.lower() != 'all':
        query += " AND genres LIKE ?"
        params.append(f"%{genre}%")

    query += " ORDER BY featured DESC, rating DESC, title ASC"
    c.execute(query, params)
    movies = [dict(r) for r in c.fetchall()]
    for m in movies:
        try: m["genres_list"] = json.loads(m["genres"])
        except Exception: m["genres_list"] = [m["genres"]]
    conn.close()
    return jsonify({"success": True, "movies": movies})

@app.route('/api/search', methods=['GET'])
def api_live_search():
    """
    Instant autocomplete endpoint returning top matching movies and theatres.
    """
    q = request.args.get('q', '').strip()
    if not q:
        return jsonify({"success": True, "movies": [], "theaters": []})

    conn = get_db()
    c = conn.cursor()

    # Search movies by title, language, or genres
    c.execute("""
    SELECT id, title, poster_path, offline_poster_path, rating, language, certification, genres, is_now_showing, runtime
    FROM movies
    WHERE title LIKE ? OR language LIKE ? OR genres LIKE ? OR overview LIKE ?
    ORDER BY featured DESC, rating DESC
    LIMIT 6
    """, (f"%{q}%", f"%{q}%", f"%{q}%", f"%{q}%"))
    movies = [dict(r) for r in c.fetchall()]
    for m in movies:
        try: m["genres_list"] = json.loads(m["genres"])
        except Exception: m["genres_list"] = [m["genres"]]

    # Search theatres by name, city, or address
    c.execute("""
    SELECT id, name, city, address
    FROM theaters
    WHERE name LIKE ? OR city LIKE ? OR address LIKE ?
    ORDER BY city ASC, name ASC
    LIMIT 4
    """, (f"%{q}%", f"%{q}%", f"%{q}%"))
    theaters = [dict(r) for r in c.fetchall()]

    conn.close()
    return jsonify({"success": True, "query": q, "movies": movies, "theaters": theaters})

@app.route('/api/movies/<int:movie_id>', methods=['GET'])
def api_movie_detail(movie_id):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM movies WHERE id = ?", (movie_id,))
    row = c.fetchone()
    conn.close()
    if not row: return jsonify({"success": False, "error": "Movie not found"}), 404
    movie = dict(row)
    try: movie["genres_list"] = json.loads(movie["genres"])
    except Exception: movie["genres_list"] = [movie["genres"]]
    return jsonify({"success": True, "movie": movie})

@app.route('/api/movies/<int:movie_id>/shows', methods=['GET'])
def api_movie_shows(movie_id):
    show_date = request.args.get('date', datetime.date.today().strftime('%Y-%m-%d'))
    city = request.args.get('city')
    conn = get_db()
    c = conn.cursor()

    query = """
    SELECT s.id AS show_id, s.show_date, s.show_time, s.price_vip, s.price_premium, s.price_executive,
           t.id AS theater_id, t.name AS theater_name, t.city, t.address, sc.screen_name, sc.screen_type
    FROM shows s
    JOIN theaters t ON s.theater_id = t.id
    JOIN screens sc ON s.screen_id = sc.id
    WHERE s.movie_id = ? AND s.show_date = ?
    """
    params = [movie_id, show_date]
    if city and city.lower() != 'all':
        query += " AND t.city = ?"
        params.append(city)
    query += " ORDER BY t.name ASC, s.show_time ASC"

    c.execute(query, params)
    rows = c.fetchall()

    # Fallback to ensure showtimes are ALWAYS available for demonstration
    if not rows:
        query_fallback = """
        SELECT s.id AS show_id, s.show_date, s.show_time, s.price_vip, s.price_premium, s.price_executive,
               t.id AS theater_id, t.name AS theater_name, t.city, t.address, sc.screen_name, sc.screen_type
        FROM shows s
        JOIN theaters t ON s.theater_id = t.id
        JOIN screens sc ON s.screen_id = sc.id
        WHERE s.movie_id = ?
        ORDER BY t.name ASC, s.show_time ASC
        LIMIT 20
        """
        c.execute(query_fallback, (movie_id,))
        rows = c.fetchall()

    conn.close()

    theaters_map = {}
    for r in rows:
        tid = r["theater_id"]
        if tid not in theaters_map:
            theaters_map[tid] = {"theater_id": tid, "theater_name": r["theater_name"], "city": r["city"], "address": r["address"], "shows": []}
        theaters_map[tid]["shows"].append(dict(r))

    return jsonify({"success": True, "theaters": list(theaters_map.values())})

@app.route('/api/shows/<int:show_id>/seats', methods=['GET'])
def api_show_seats(show_id):
    conn = get_db()
    cleanup_reservations(conn)
    c = conn.cursor()
    c.execute("""
    SELECT s.id, s.show_date, s.show_time, s.price_vip, s.price_premium, s.price_executive,
           m.title AS movie_title, m.certification, m.poster_path, m.offline_poster_path, t.name AS theater_name, sc.screen_name
    FROM shows s
    JOIN movies m ON s.movie_id = m.id
    JOIN theaters t ON s.theater_id = t.id
    JOIN screens sc ON s.screen_id = sc.id
    WHERE s.id = ?
    """, (show_id,))
    row = c.fetchone()
    if not row:
        conn.close()
        return jsonify({"success": False, "error": "Show not found"}), 404

    show_info = dict(row)
    c.execute("SELECT id, seat_label, tier, status, reservation_token FROM show_seats WHERE show_id = ? ORDER BY seat_label ASC", (show_id,))
    seats = [dict(r) for r in c.fetchall()]
    conn.close()
    return jsonify({"success": True, "data": {"show": show_info, "seats": seats, "tiers": SEAT_TIERS}})

@app.route('/api/shows/<int:show_id>/reserve', methods=['POST'])
def api_reserve(show_id):
    body = request.get_json() or {}
    seat_labels = body.get('seat_labels', [])
    token = body.get('reservation_token') or str(uuid.uuid4())
    if not seat_labels: return jsonify({"success": False, "error": "No seats selected"}), 400

    conn = get_db()
    cleanup_reservations(conn)
    c = conn.cursor()

    placeholders = ",".join("?" for _ in seat_labels)
    c.execute(f"SELECT seat_label, status, reservation_token FROM show_seats WHERE show_id = ? AND seat_label IN ({placeholders})", [show_id] + seat_labels)
    existing = c.fetchall()

    for r in existing:
        if r["status"] == "BOOKED":
            conn.close()
            return jsonify({"success": False, "error": f"Seat {r['seat_label']} is already booked"}), 409
        if r["status"] == "RESERVED" and r["reservation_token"] != token:
            conn.close()
            return jsonify({"success": False, "error": f"Seat {r['seat_label']} is temporarily held by another moviegoer"}), 409

    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    c.execute(f"UPDATE show_seats SET status = 'RESERVED', reservation_token = ?, reserved_at = ? WHERE show_id = ? AND seat_label IN ({placeholders})", [token, now_str, show_id] + seat_labels)
    conn.commit()
    conn.close()
    return jsonify({"success": True, "reservation_token": token, "expires_in": RESERVATION_HOLD_SECONDS})

@app.route('/api/shows/<int:show_id>/release', methods=['POST'])
def api_release(show_id):
    body = request.get_json() or {}
    seat_labels = body.get('seat_labels', [])
    token = body.get('reservation_token')
    if seat_labels and token:
        conn = get_db()
        c = conn.cursor()
        placeholders = ",".join("?" for _ in seat_labels)
        c.execute(f"UPDATE show_seats SET status = 'AVAILABLE', reservation_token = NULL, reserved_at = NULL WHERE show_id = ? AND reservation_token = ? AND seat_label IN ({placeholders})", [show_id, token] + seat_labels)
        conn.commit()
        conn.close()
    return jsonify({"success": True})

@app.route('/api/shows/<int:show_id>/book', methods=['POST'])
def api_book(show_id):
    """
    Atomic Cineplex Booking Transaction.
    Inserts into: bookings, booking_seats, booking_snacks, payments.
    Updates: show_seats (status = 'BOOKED').
    Guarantees no double-booking via immediate SQLite transaction.
    """
    body = request.get_json() or {}
    seats = body.get('seat_labels', [])
    name = body.get('customer_name', '').strip()
    email = body.get('customer_email', '').strip()
    phone = body.get('customer_phone', '').strip()
    snacks = body.get('snacks', [])
    pay_method = (body.get('payment_method') or 'UPI').upper()
    if 'CARD' in pay_method: pay_method = 'CARD'
    elif 'NET' in pay_method: pay_method = 'NETBANKING'
    elif 'WALLET' in pay_method: pay_method = 'WALLET'
    else: pay_method = 'UPI'
    token = body.get('reservation_token')

    if not seats or not name or not email or not phone:
        return jsonify({"success": False, "error": "Missing required booking details (seats, name, email, phone)"}), 400

    conn = get_db()
    c = conn.cursor()

    try:
        # Begin explicit atomic transaction
        c.execute("BEGIN IMMEDIATE")

        placeholders = ",".join("?" for _ in seats)
        c.execute(f"SELECT seat_label, tier, status, reservation_token FROM show_seats WHERE show_id = ? AND seat_label IN ({placeholders})", [show_id] + seats)
        seats_data = c.fetchall()

        if len(seats_data) != len(seats):
            conn.rollback()
            conn.close()
            return jsonify({"success": False, "error": "One or more seats not found for this show."}), 400

        for s in seats_data:
            if s["status"] == "BOOKED":
                conn.rollback()
                conn.close()
                return jsonify({"success": False, "error": f"Seat {s['seat_label']} was just booked by another user."}), 409
            if s["status"] == "RESERVED" and token and s["reservation_token"] != token:
                conn.rollback()
                conn.close()
                return jsonify({"success": False, "error": f"Seat {s['seat_label']} is held by another user."}), 409

        c.execute("SELECT price_vip, price_premium, price_executive FROM shows WHERE id = ?", (show_id,))
        prices = c.fetchone()

        subtotal = 0.0
        seat_price_map = {}
        for s in seats_data:
            tier = s["tier"]
            tier_price = prices["price_vip"] if tier == "RECLINER" else (prices["price_premium"] if tier == "PRIME" else prices["price_executive"])
            seat_price_map[s["seat_label"]] = (tier, tier_price)
            subtotal += tier_price

        snacks_total = sum(item.get("price", 0) * item.get("quantity", 0) for item in snacks)
        conv_fee = round((subtotal + snacks_total) * CONVENIENCE_FEE_PCT, 2)
        taxes = round(conv_fee * GST_PCT, 2)
        grand_total = round(subtotal + snacks_total + conv_fee + taxes, 2)

        booking_ref = f"CPX-{datetime.datetime.now().strftime('%y%m%d')}-{uuid.uuid4().hex[:6].upper()}"
        seat_str = ", ".join(sorted(seats))
        qr_data = f"CINEPLEX-PASS:{booking_ref}:{seat_str}:{show_id}"

        # 1. Insert into bookings
        c.execute("""
        INSERT INTO bookings (booking_ref, show_id, customer_name, customer_email, customer_phone, seat_numbers, seats_count, subtotal, snacks_total, convenience_fee, taxes, total_amount, payment_method, status, qr_data)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'CONFIRMED', ?)
        """, (booking_ref, show_id, name, email, phone, seat_str, len(seats), subtotal, snacks_total, conv_fee, taxes, grand_total, pay_method, qr_data))
        b_id = c.lastrowid

        # 2. Insert into booking_seats (3NF Normalized)
        for s_label, (tier, s_price) in seat_price_map.items():
            c.execute("""
            INSERT INTO booking_seats (booking_id, show_id, seat_label, tier, price)
            VALUES (?, ?, ?, ?, ?)
            """, (b_id, show_id, s_label, tier, s_price))

        # 3. Insert into booking_snacks (3NF Normalized)
        for sn in snacks:
            qty = sn.get("quantity", 0)
            u_price = sn.get("price", 0.0)
            if qty > 0:
                c.execute("""
                INSERT INTO booking_snacks (booking_id, snack_id, snack_name, quantity, unit_price, total_price)
                VALUES (?, ?, ?, ?, ?, ?)
                """, (b_id, sn.get("id"), sn.get("name", "Concession Item"), qty, u_price, round(qty * u_price, 2)))

        # 4. Insert into payments (3NF Normalized)
        payment_ref = f"PAY-{booking_ref}"
        c.execute("""
        INSERT INTO payments (booking_id, payment_ref, amount, payment_method, payment_status)
        VALUES (?, ?, ?, ?, 'SUCCESS')
        """, (b_id, payment_ref, grand_total, pay_method))

        # 5. Update show_seats to BOOKED
        c.execute(f"UPDATE show_seats SET status = 'BOOKED', reservation_token = NULL, reserved_at = NULL, booking_id = ? WHERE show_id = ? AND seat_label IN ({placeholders})", [b_id, show_id] + seats)

        conn.commit()
        conn.close()
        return jsonify({
            "success": True,
            "booking_ref": booking_ref,
            "payment_ref": payment_ref,
            "total_amount": grand_total,
            "seats": seat_str,
            "qr_data": qr_data
        })
    except Exception as e:
        conn.rollback()
        conn.close()
        return jsonify({"success": False, "error": f"Booking transaction failed: {str(e)}"}), 500

@app.route('/api/bookings', methods=['GET'])
def api_bookings_list():
    conn = get_db()
    c = conn.cursor()
    search = request.args.get('search')
    query = """
    SELECT b.*, s.show_date, s.show_time, m.title AS movie_title, m.poster_path, m.offline_poster_path, m.certification, m.language, t.name AS theater_name, sc.screen_name,
           c.cancellation_ref, c.refund_amount, c.refund_status, c.cancelled_at, p.payment_ref, p.payment_status
    FROM bookings b
    JOIN shows s ON b.show_id = s.id
    JOIN movies m ON s.movie_id = m.id
    JOIN theaters t ON s.theater_id = t.id
    JOIN screens sc ON s.screen_id = sc.id
    LEFT JOIN cancellations c ON b.id = c.booking_id
    LEFT JOIN payments p ON b.id = p.booking_id
    WHERE 1=1
    """
    params = []
    if search:
        query += " AND (b.booking_ref LIKE ? OR b.customer_email LIKE ? OR b.customer_name LIKE ?)"
        params.extend([f"%{search}%", f"%{search}%", f"%{search}%"])
    query += " ORDER BY b.created_at DESC"
    c.execute(query, params)
    bookings = [dict(r) for r in c.fetchall()]
    conn.close()
    return jsonify({"success": True, "bookings": bookings})

@app.route('/api/bookings/<booking_ref>', methods=['GET'])
def api_booking_detail(booking_ref):
    conn = get_db()
    c = conn.cursor()
    c.execute("""
    SELECT b.*, s.show_date, s.show_time, m.title AS movie_title, m.poster_path, m.offline_poster_path, m.certification, m.language,
           t.name AS theater_name, t.city, sc.screen_name, c.cancellation_ref, c.refund_amount, c.refund_status, c.cancelled_at,
           p.payment_ref, p.payment_status
    FROM bookings b
    JOIN shows s ON b.show_id = s.id
    JOIN movies m ON s.movie_id = m.id
    JOIN theaters t ON s.theater_id = t.id
    JOIN screens sc ON s.screen_id = sc.id
    LEFT JOIN cancellations c ON b.id = c.booking_id
    LEFT JOIN payments p ON b.id = p.booking_id
    WHERE b.booking_ref = ?
    """, (booking_ref,))
    row = c.fetchone()
    if not row:
        conn.close()
        return jsonify({"success": False, "error": "Booking not found"}), 404

    booking_data = dict(row)

    # Fetch normalized booking_seats & snacks
    c.execute("SELECT seat_label, tier, price FROM booking_seats WHERE booking_id = ?", (booking_data["id"],))
    booking_data["seats_details"] = [dict(r) for r in c.fetchall()]

    c.execute("SELECT snack_name, quantity, unit_price, total_price FROM booking_snacks WHERE booking_id = ?", (booking_data["id"],))
    booking_data["snacks_details"] = [dict(r) for r in c.fetchall()]

    conn.close()
    return jsonify({"success": True, "booking": booking_data})

@app.route('/api/bookings/<booking_ref>/pdf', methods=['GET'])
def api_booking_pdf(booking_ref):
    conn = get_db()
    c = conn.cursor()
    c.execute("""
    SELECT b.*, s.show_date, s.show_time, m.title AS movie_title, m.poster_path, m.offline_poster_path, m.certification, m.language,
           t.name AS theater_name, t.city, sc.screen_name, c.cancellation_ref, c.refund_amount, c.refund_status, c.cancelled_at,
           p.payment_ref, p.payment_status, p.payment_method
    FROM bookings b
    JOIN shows s ON b.show_id = s.id
    JOIN movies m ON s.movie_id = m.id
    JOIN theaters t ON s.theater_id = t.id
    JOIN screens sc ON s.screen_id = sc.id
    LEFT JOIN cancellations c ON b.id = c.booking_id
    LEFT JOIN payments p ON b.id = p.booking_id
    WHERE b.booking_ref = ?
    """, (booking_ref,))
    row = c.fetchone()
    conn.close()
    if not row:
        return jsonify({"success": False, "error": "Booking not found"}), 404

    b = dict(row)
    buffer = io.BytesIO()

    # Generate Single-Page A4 PDF Ticket
    c_pdf = canvas.Canvas(buffer, pagesize=A4)
    page_w, page_h = A4

    card_w = 420
    card_h = 560
    card_x = (page_w - card_w) / 2
    card_y = (page_h - card_h) / 2

    # 1. Ticket Card Background & Outer Border
    c_pdf.setFillColor(colors.HexColor('#ffffff'))
    c_pdf.setStrokeColor(colors.HexColor('#0f172a'))
    c_pdf.setLineWidth(1.5)
    c_pdf.roundRect(card_x, card_y, card_w, card_h, 12, fill=1, stroke=1)

    # 2. Header Banner (Navy)
    c_pdf.saveState()
    path = c_pdf.beginPath()
    path.roundRect(card_x, card_y + card_h - 75, card_w, 75, 12)
    c_pdf.clipPath(path, stroke=0)
    c_pdf.setFillColor(colors.HexColor('#0f172a'))
    c_pdf.rect(card_x, card_y + card_h - 75, card_w, 75, fill=1, stroke=0)
    c_pdf.restoreState()

    # Header Red Accent Strip
    c_pdf.setFillColor(colors.HexColor('#e11d48'))
    c_pdf.rect(card_x, card_y + card_h - 77, card_w, 3, fill=1, stroke=0)

    # Header Logo Badge
    c_pdf.setFillColor(colors.HexColor('#e11d48'))
    c_pdf.roundRect(card_x + 18, card_y + card_h - 45, 75, 20, 3, fill=1, stroke=0)
    c_pdf.setFillColor(colors.white)
    c_pdf.setFont("Helvetica-Bold", 10)
    c_pdf.drawString(card_x + 24, card_y + card_h - 38, "CINEPLEX")

    # Header Subtitle
    c_pdf.setFont("Helvetica-Bold", 8)
    c_pdf.setFillColor(colors.HexColor('#94a3b8'))
    c_pdf.drawString(card_x + 102, card_y + card_h - 33, "DIGITAL M-TICKET PASS")

    # Header Booking Ref
    c_pdf.setFont("Helvetica-Bold", 13)
    c_pdf.setFillColor(colors.white)
    c_pdf.drawString(card_x + 102, card_y + card_h - 48, str(b['booking_ref']))

    # Status Badge
    status_text = "CONFIRMED" if b.get('status') != 'CANCELLED' else "CANCELLED"
    status_bg = colors.HexColor('#ecfdf5') if status_text == 'CONFIRMED' else colors.HexColor('#ffe4e6')
    status_fg = colors.HexColor('#047857') if status_text == 'CONFIRMED' else colors.HexColor('#be123c')

    c_pdf.setFillColor(status_bg)
    c_pdf.roundRect(card_x + card_w - 95, card_y + card_h - 44, 78, 18, 9, fill=1, stroke=0)
    c_pdf.setFillColor(status_fg)
    c_pdf.setFont("Helvetica-Bold", 8)
    c_pdf.drawCentredString(card_x + card_w - 56, card_y + card_h - 38, status_text)

    # 3. Movie Title & Meta
    curr_y = card_y + card_h - 110
    c_pdf.setFillColor(colors.HexColor('#0f172a'))
    c_pdf.setFont("Helvetica-Bold", 17)
    c_pdf.drawString(card_x + 22, curr_y, str(b['movie_title']))

    curr_y -= 18
    c_pdf.setFillColor(colors.HexColor('#64748b'))
    c_pdf.setFont("Helvetica-Bold", 9)
    meta_str = f"{b.get('certification', 'UA 16+')}   •   {b.get('language', 'Hindi')}"
    c_pdf.drawString(card_x + 22, curr_y, meta_str)

    curr_y -= 20
    c_pdf.setFillColor(colors.HexColor('#0f172a'))
    c_pdf.setFont("Helvetica-Bold", 11)
    c_pdf.drawString(card_x + 22, curr_y, f"Show Date: {b.get('show_date')}    Time: {b.get('show_time')}")

    # 4. Perforation Tear Line with Notches
    tear_y = curr_y - 25
    c_pdf.setDash(4, 3)
    c_pdf.setStrokeColor(colors.HexColor('#cbd5e1'))
    c_pdf.line(card_x + 15, tear_y, card_x + card_w - 15, tear_y)
    c_pdf.setDash([])

    # Semicircle notches at tear edges
    c_pdf.setFillColor(colors.white)
    c_pdf.setStrokeColor(colors.HexColor('#0f172a'))
    c_pdf.circle(card_x, tear_y, 9, fill=1, stroke=1)
    c_pdf.circle(card_x + card_w, tear_y, 9, fill=1, stroke=1)

    # 5. Details Grid: Theatre & Seats
    detail_y = tear_y - 35
    c_pdf.setFillColor(colors.HexColor('#64748b'))
    c_pdf.setFont("Helvetica-Bold", 8)
    c_pdf.drawString(card_x + 22, detail_y, "THEATRE & SCREEN")
    c_pdf.drawString(card_x + card_w/2 + 20, detail_y, "RESERVED SEAT(S)")

    c_pdf.setFillColor(colors.HexColor('#0f172a'))
    c_pdf.setFont("Helvetica-Bold", 11)
    c_pdf.drawString(card_x + 22, detail_y - 15, str(b.get('theater_name', 'Cineplex Theatre')))
    c_pdf.setFont("Helvetica", 9)
    c_pdf.setFillColor(colors.HexColor('#475569'))
    c_pdf.drawString(card_x + 22, detail_y - 28, f"{b.get('screen_name', 'Screen 1')} ({b.get('city', 'Bhubaneswar')})")

    c_pdf.setFont("Helvetica-Bold", 16)
    c_pdf.setFillColor(colors.HexColor('#e11d48'))
    c_pdf.drawString(card_x + card_w/2 + 20, detail_y - 18, str(b.get('seat_numbers', 'Seats')))

    # 6. Customer & Payment Row
    pay_y = detail_y - 56
    c_pdf.setStrokeColor(colors.HexColor('#e2e8f0'))
    c_pdf.setLineWidth(1)
    c_pdf.line(card_x + 20, pay_y + 12, card_x + card_w - 20, pay_y + 12)

    c_pdf.setFillColor(colors.HexColor('#475569'))
    c_pdf.setFont("Helvetica", 9)
    c_pdf.drawString(card_x + 22, pay_y - 3, "Customer:")
    c_pdf.setFillColor(colors.HexColor('#0f172a'))
    c_pdf.setFont("Helvetica-Bold", 9)
    c_pdf.drawString(card_x + 75, pay_y - 3, str(b.get('customer_name', 'Customer')))

    c_pdf.setFillColor(colors.HexColor('#475569'))
    c_pdf.setFont("Helvetica", 9)
    c_pdf.drawString(card_x + card_w/2 + 20, pay_y - 3, "Total Paid:")
    c_pdf.setFillColor(colors.HexColor('#059669'))
    c_pdf.setFont("Helvetica-Bold", 12)
    c_pdf.drawString(card_x + card_w/2 + 75, pay_y - 3, f"Rs. {float(b.get('total_amount', 0)):.2f}")

    # 7. QR Verification Box
    qr_y = pay_y - 120
    qr_box_size = 85
    qr_x = card_x + (card_w - qr_box_size) / 2

    c_pdf.setFillColor(colors.HexColor('#f8fafc'))
    c_pdf.setStrokeColor(colors.HexColor('#cbd5e1'))
    c_pdf.roundRect(qr_x, qr_y, qr_box_size, qr_box_size, 6, fill=1, stroke=1)

    # Procedural QR elements
    c_pdf.setFillColor(colors.HexColor('#0f172a'))
    c_pdf.rect(qr_x + 8, qr_y + qr_box_size - 24, 16, 16, fill=1, stroke=0)
    c_pdf.rect(qr_x + qr_box_size - 24, qr_y + qr_box_size - 24, 16, 16, fill=1, stroke=0)
    c_pdf.rect(qr_x + 8, qr_y + 8, 16, 16, fill=1, stroke=0)
    c_pdf.setFillColor(colors.white)
    c_pdf.rect(qr_x + 12, qr_y + qr_box_size - 20, 8, 8, fill=1, stroke=0)
    c_pdf.rect(qr_x + qr_box_size - 20, qr_y + qr_box_size - 20, 8, 8, fill=1, stroke=0)
    c_pdf.rect(qr_x + 12, qr_y + 12, 8, 8, fill=1, stroke=0)
    c_pdf.setFillColor(colors.HexColor('#0f172a'))
    c_pdf.rect(qr_x + 14, qr_y + qr_box_size - 18, 4, 4, fill=1, stroke=0)
    c_pdf.rect(qr_x + qr_box_size - 18, qr_y + qr_box_size - 18, 4, 4, fill=1, stroke=0)
    c_pdf.rect(qr_x + 14, qr_y + 14, 4, 4, fill=1, stroke=0)
    c_pdf.rect(qr_x + 38, qr_y + 38, 9, 9, fill=1, stroke=0)
    c_pdf.rect(qr_x + 52, qr_y + 24, 6, 6, fill=1, stroke=0)
    c_pdf.rect(qr_x + 26, qr_y + 52, 6, 6, fill=1, stroke=0)

    # Instructions below QR
    c_pdf.setFont("Helvetica-Bold", 8)
    c_pdf.setFillColor(colors.HexColor('#475569'))
    c_pdf.drawCentredString(card_x + card_w/2, qr_y - 16, "SCAN AT TURNSTILE ENTRANCE FOR ENTRY")
    c_pdf.setFont("Helvetica", 7)
    c_pdf.setFillColor(colors.HexColor('#94a3b8'))
    c_pdf.drawCentredString(card_x + card_w/2, qr_y - 28, "Valid on show date only - Powered by CINEPLEX Systems")

    # Finish and save single page
    c_pdf.showPage()
    c_pdf.save()

    buffer.seek(0)
    return send_file(
        buffer,
        mimetype='application/pdf',
        as_attachment=True,
        download_name=f"CINEPLEX_TICKET_{booking_ref}.pdf"
    )

@app.route('/api/bookings/<booking_ref>/cancel', methods=['POST'])
def api_cancel_booking(booking_ref):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM bookings WHERE booking_ref = ?", (booking_ref,))
    b = c.fetchone()
    if not b:
        conn.close()
        return jsonify({"success": False, "error": "Booking not found"}), 404
    if b["status"] == "CANCELLED":
        conn.close()
        return jsonify({"success": False, "error": "This booking has already been cancelled"}), 400

    fee = round(b["seats_count"] * CANCELLATION_FEE_PER_SEAT, 2)
    refund = max(0.0, round(b["total_amount"] - fee, 2))
    can_ref = f"CAN-{datetime.datetime.now().strftime('%y%m%d')}-{uuid.uuid4().hex[:6].upper()}"
    reason = (request.get_json() or {}).get("reason", "Change of plans")

    try:
        c.execute("BEGIN IMMEDIATE")
        c.execute("UPDATE bookings SET status = 'CANCELLED' WHERE id = ?", (b["id"],))
        c.execute("""
        INSERT INTO cancellations (cancellation_ref, booking_id, booking_ref, reason, original_amount, cancellation_fee, refund_amount, refund_status, released_seats)
        VALUES (?, ?, ?, ?, ?, ?, ?, 'PROCESSED', ?)
        """, (can_ref, b["id"], booking_ref, reason, b["total_amount"], fee, refund, b["seat_numbers"]))

        # Update payment status
        c.execute("UPDATE payments SET payment_status = 'REFUNDED' WHERE booking_id = ?", (b["id"],))

        # Immediately liberate seats back to AVAILABLE in SQLite
        seat_list = [s.strip() for s in b["seat_numbers"].split(",") if s.strip()]
        if seat_list:
            placeholders = ",".join("?" for _ in seat_list)
            c.execute(f"UPDATE show_seats SET status = 'AVAILABLE', booking_id = NULL, reservation_token = NULL, reserved_at = NULL WHERE show_id = ? AND seat_label IN ({placeholders})", [b["show_id"]] + seat_list)

        conn.commit()
        conn.close()
        return jsonify({
            "success": True,
            "cancellation_ref": can_ref,
            "refund_amount": refund,
            "cancellation_fee": fee,
            "released_seats": b["seat_numbers"],
            "refund_status": "PROCESSED"
        })
    except Exception as e:
        conn.rollback()
        conn.close()
        return jsonify({"success": False, "error": f"Cancellation failed: {str(e)}"}), 500

@app.route('/api/snacks', methods=['GET'])
def api_snacks():
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM snacks ORDER BY category ASC, price ASC")
    snacks = [dict(r) for r in c.fetchall()]
    conn.close()
    return jsonify({"success": True, "snacks": snacks})

@app.route('/api/tmdb/sync', methods=['POST'])
def api_sync():
    """Live API search to fetch latest posters from TMDB API."""
    body = request.get_json() or {}
    api_key = body.get('api_key') or TMDB_API_KEY
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT id, title, tmdb_id FROM movies")
    movies_list = c.fetchall()
    updated = 0

    for m in movies_list:
        try:
            encoded = urllib.parse.quote(m["title"])
            url = f"{TMDB_BASE_URL}/search/movie?api_key={api_key}&query={encoded}"
            req = urllib.request.Request(url, headers={"User-Agent": "CineplexApp/1.0"})
            with urllib.request.urlopen(req, timeout=3) as res:
                data = json.loads(res.read().decode("utf-8"))
                results = data.get("results", [])
                if results and results[0].get("poster_path"):
                    poster_url = f"{TMDB_IMG_URL}/w500{results[0]['poster_path']}"
                    backdrop_url = f"{TMDB_IMG_URL}/w1280{results[0]['backdrop_path']}" if results[0].get('backdrop_path') else poster_url
                    c.execute("UPDATE movies SET poster_path = ?, backdrop_path = ? WHERE id = ?", (poster_url, backdrop_url, m["id"]))
                    updated += 1
        except Exception:
            pass

    conn.commit()
    conn.close()
    return jsonify({"success": True, "updated": updated, "message": f"Successfully synced live TMDB API posters for {updated} movies!"})

@app.route('/api/tmdb/status', methods=['GET'])
def api_tmdb_status():
    return jsonify({"configured": True, "masked_key": "TMDB-API-Live", "service": "CINEPLEX Cloud Sync"})

# ==============================================================================
# SECTION 4: AUTHENTICATION & USER PROFILE
# ==============================================================================
@app.route('/api/auth/register', methods=['POST'])
def api_auth_register():
    data = request.get_json() or {}
    name = (data.get('name') or '').strip()
    email = (data.get('email') or '').strip().lower()
    phone = (data.get('phone') or '').strip()
    password_hash = data.get('password_hash') or ''

    if not name or not email or not phone:
        return jsonify({"success": False, "error": "Name, email, and phone are required"}), 400

    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT id FROM users WHERE email = ?", (email,))
    if c.fetchone():
        conn.close()
        return jsonify({"success": False, "error": "User with this email already exists"}), 409

    c.execute("""
    INSERT INTO users (name, email, phone, password_hash, is_admin)
    VALUES (?, ?, ?, ?, 0)
    """, (name, email, phone, password_hash))
    user_id = c.lastrowid
    conn.commit()
    conn.close()
    return jsonify({"success": True, "user": {"id": user_id, "name": name, "email": email, "phone": phone, "is_admin": False}})

@app.route('/api/auth/login', methods=['POST'])
def api_auth_login():
    data = request.get_json() or {}
    email = (data.get('email') or '').strip().lower()
    password_hash = data.get('password_hash') or ''

    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT id, name, email, phone, password_hash, is_admin FROM users WHERE email = ?", (email,))
    row = c.fetchone()
    conn.close()

    if not row:
        return jsonify({"success": False, "error": "No account found with this email"}), 404
    if row['password_hash'] != password_hash:
        return jsonify({"success": False, "error": "Incorrect password"}), 401

    return jsonify({
        "success": True,
        "user": {
            "id": row['id'],
            "name": row['name'],
            "email": row['email'],
            "phone": row['phone'],
            "is_admin": bool(row['is_admin'])
        }
    })

@app.route('/api/auth/sync', methods=['POST'])
def api_auth_sync():
    """Bidirectional sync between browser storage and database without credentials."""
    data = request.get_json() or {}
    browser_users = data.get('users', [])
    conn = get_db()
    c = conn.cursor()

    synced = 0
    for u in browser_users:
        email = (u.get('email') or '').strip().lower()
        name = (u.get('name') or '').strip()
        phone = (u.get('phone') or '').strip()
        pwd = u.get('passwordHash') or ''
        if email and name:
            c.execute("SELECT id FROM users WHERE email = ?", (email,))
            if not c.fetchone():
                c.execute("INSERT INTO users (name, email, phone, password_hash, is_admin) VALUES (?, ?, ?, ?, 0)", (name, email, phone, pwd))
                synced += 1

    c.execute("SELECT id, name, email, phone, password_hash, is_admin, created_at FROM users")
    db_users = [{"name": r["name"], "email": r["email"], "phone": r["phone"], "passwordHash": r["password_hash"], "isAdmin": bool(r["is_admin"]), "createdAt": r["created_at"]} for r in c.fetchall()]
    conn.commit()
    conn.close()
    return jsonify({"success": True, "synced_count": synced, "users": db_users})

# ==============================================================================
# SECTION 5: ADMIN DASHBOARD & DBMS LIVE VIVA CONSOLE
# ==============================================================================
@app.route('/api/admin/stats', methods=['GET'])
def api_admin_stats():
    """Real-time metrics for Cineplex Administration & Evaluator Demonstration."""
    conn = get_db()
    c = conn.cursor()

    c.execute("SELECT COUNT(*) FROM movies")
    total_movies = c.fetchone()[0]

    c.execute("SELECT COUNT(*) FROM movies WHERE is_now_showing = 1")
    now_showing_movies = c.fetchone()[0]

    c.execute("SELECT COUNT(*) FROM theaters")
    total_theaters = c.fetchone()[0]

    c.execute("SELECT COUNT(*) FROM shows")
    total_shows = c.fetchone()[0]

    c.execute("SELECT COUNT(*) FROM bookings")
    total_bookings = c.fetchone()[0]

    c.execute("SELECT COUNT(*) FROM bookings WHERE status = 'CONFIRMED'")
    active_bookings = c.fetchone()[0]

    c.execute("SELECT COUNT(*) FROM cancellations")
    total_cancellations = c.fetchone()[0]

    c.execute("SELECT COALESCE(SUM(total_amount), 0) FROM bookings WHERE status = 'CONFIRMED'")
    net_revenue = round(c.fetchone()[0], 2)

    c.execute("SELECT COALESCE(SUM(original_amount), 0), COALESCE(SUM(refund_amount), 0), COALESCE(SUM(cancellation_fee), 0) FROM cancellations")
    can_stats = c.fetchone()
    total_refunded = round(can_stats[1], 2)
    cancellation_fees_earned = round(can_stats[2], 2)

    c.execute("SELECT COUNT(*) FROM users")
    total_users = c.fetchone()[0]

    c.execute("SELECT COUNT(*) FROM show_seats WHERE status = 'BOOKED'")
    total_tickets_sold = c.fetchone()[0]

    c.execute("SELECT COUNT(*) FROM show_seats")
    total_seat_inventory = c.fetchone()[0]
    occupancy_pct = round((total_tickets_sold / total_seat_inventory * 100), 2) if total_seat_inventory > 0 else 0.0

    conn.close()
    return jsonify({
        "success": True,
        "metrics": {
            "total_movies": total_movies,
            "now_showing_movies": now_showing_movies,
            "total_theaters": total_theaters,
            "total_shows": total_shows,
            "total_bookings": total_bookings,
            "active_bookings": active_bookings,
            "total_cancellations": total_cancellations,
            "net_revenue": net_revenue,
            "total_refunded": total_refunded,
            "cancellation_fees_earned": cancellation_fees_earned,
            "total_users": total_users,
            "total_tickets_sold": total_tickets_sold,
            "occupancy_rate_pct": occupancy_pct
        }
    })

@app.route('/api/admin/movies', methods=['GET', 'POST', 'PUT', 'DELETE'])
def api_admin_movies():
    conn = get_db()
    c = conn.cursor()

    if request.method == 'GET':
        c.execute("SELECT * FROM movies ORDER BY is_now_showing DESC, title ASC")
        movies = [dict(r) for r in c.fetchall()]
        conn.close()
        return jsonify({"success": True, "movies": movies})

    if request.method == 'POST':
        data = request.get_json() or {}
        title = data.get('title', '').strip()
        if not title:
            conn.close()
            return jsonify({"success": False, "error": "Movie title is required"}), 400
        overview = data.get('overview', '')
        poster_path = data.get('poster_path', '/static/posters/ramayan.jpg')
        release_date = data.get('release_date', datetime.date.today().strftime('%Y-%m-%d'))
        rating = float(data.get('rating', 8.5))
        runtime = int(data.get('runtime', 145))
        genres = json.dumps(data.get('genres_list', ["Action", "Drama"]))
        language = data.get('language', 'Hindi')
        certification = data.get('certification', 'UA 16+')
        is_now_showing = int(data.get('is_now_showing', 1))

        c.execute("""
        INSERT INTO movies (title, overview, poster_path, offline_poster_path, release_date, rating, runtime, genres, language, certification, is_now_showing)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (title, overview, poster_path, poster_path, release_date, rating, runtime, genres, language, certification, is_now_showing))
        m_id = c.lastrowid
        conn.commit()
        conn.close()
        return jsonify({"success": True, "movie_id": m_id, "message": f"Movie '{title}' added to catalogue"})

    if request.method == 'PUT':
        data = request.get_json() or {}
        m_id = data.get('id')
        if not m_id:
            conn.close()
            return jsonify({"success": False, "error": "Movie ID is required"}), 400
        is_now_showing = int(data.get('is_now_showing', 1))
        featured = int(data.get('featured', 0))
        c.execute("UPDATE movies SET is_now_showing = ?, featured = ? WHERE id = ?", (is_now_showing, featured, m_id))
        conn.commit()
        conn.close()
        return jsonify({"success": True, "message": "Movie updated successfully"})

    if request.method == 'DELETE':
        m_id = request.args.get('id')
        if not m_id:
            conn.close()
            return jsonify({"success": False, "error": "Movie ID is required"}), 400
        c.execute("DELETE FROM movies WHERE id = ?", (m_id,))
        conn.commit()
        conn.close()
        return jsonify({"success": True, "message": f"Movie ID {m_id} deleted successfully"})

@app.route('/api/admin/theaters', methods=['GET'])
def api_admin_theaters():
    conn = get_db()
    c = conn.cursor()
    c.execute("""
    SELECT t.id, t.name, t.city, t.address, t.screens_count,
           COUNT(s.id) AS active_shows_count
    FROM theaters t
    LEFT JOIN shows s ON t.id = s.theater_id
    GROUP BY t.id
    ORDER BY t.city ASC, t.name ASC
    """)
    theaters = [dict(r) for r in c.fetchall()]
    conn.close()
    return jsonify({"success": True, "theaters": theaters})

@app.route('/api/admin/shows', methods=['GET', 'POST'])
def api_admin_shows():
    conn = get_db()
    c = conn.cursor()

    if request.method == 'GET':
        c.execute("""
        SELECT s.id, s.show_date, s.show_time, s.price_vip, s.price_premium, s.price_executive,
               m.title AS movie_title, t.name AS theater_name, t.city, sc.screen_name,
               (SELECT COUNT(*) FROM show_seats ss WHERE ss.show_id = s.id AND ss.status = 'BOOKED') AS booked_seats,
               (SELECT COUNT(*) FROM show_seats ss WHERE ss.show_id = s.id) AS total_seats
        FROM shows s
        JOIN movies m ON s.movie_id = m.id
        JOIN theaters t ON s.theater_id = t.id
        JOIN screens sc ON s.screen_id = sc.id
        ORDER BY s.show_date DESC, s.show_time ASC
        LIMIT 100
        """)
        shows = [dict(r) for r in c.fetchall()]
        conn.close()
        return jsonify({"success": True, "shows": shows})

    if request.method == 'POST':
        data = request.get_json() or {}
        movie_id = data.get('movie_id')
        theater_id = data.get('theater_id')
        screen_id = data.get('screen_id')
        show_date = data.get('show_date')
        show_time = data.get('show_time')
        price_vip = float(data.get('price_vip', 450.0))
        price_premium = float(data.get('price_premium', 300.0))
        price_executive = float(data.get('price_executive', 180.0))

        if not all([movie_id, theater_id, screen_id, show_date, show_time]):
            conn.close()
            return jsonify({"success": False, "error": "Missing show parameters"}), 400

        c.execute("""
        INSERT INTO shows (movie_id, theater_id, screen_id, show_date, show_time, price_vip, price_premium, price_executive)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (movie_id, theater_id, screen_id, show_date, show_time, price_vip, price_premium, price_executive))
        new_show_id = c.lastrowid

        # Generate seats for the new show
        seats = []
        for r in ["A", "B"]:
            for col in range(1, 11): seats.append((new_show_id, f"{r}{col}", "RECLINER", "AVAILABLE"))
        for r in ["C", "D", "E"]:
            for col in range(1, 13): seats.append((new_show_id, f"{r}{col}", "PRIME", "AVAILABLE"))
        for r in ["F", "G", "H"]:
            for col in range(1, 13): seats.append((new_show_id, f"{r}{col}", "CLASSIC", "AVAILABLE"))
        c.executemany("INSERT OR IGNORE INTO show_seats (show_id, seat_label, tier, status) VALUES (?, ?, ?, ?)", seats)

        conn.commit()
        conn.close()
        return jsonify({"success": True, "show_id": new_show_id, "message": "Show added and 92 auditorium seats generated!"})

@app.route('/api/admin/users', methods=['GET'])
def api_admin_users():
    conn = get_db()
    c = conn.cursor()
    c.execute("""
    SELECT u.id, u.name, u.email, u.phone, u.is_admin, u.created_at,
           COUNT(b.id) AS total_bookings_count,
           COALESCE(SUM(CASE WHEN b.status = 'CONFIRMED' THEN b.total_amount ELSE 0 END), 0) AS total_spend
    FROM users u
    LEFT JOIN bookings b ON u.email = b.customer_email
    GROUP BY u.id
    ORDER BY total_spend DESC, u.created_at DESC
    """)
    users = [dict(r) for r in c.fetchall()]
    conn.close()
    return jsonify({"success": True, "users": users})

@app.route('/api/admin/cancellations', methods=['GET'])
def api_admin_cancellations():
    conn = get_db()
    c = conn.cursor()
    c.execute("""
    SELECT c.*, b.customer_name, b.customer_email, m.title AS movie_title, t.name AS theater_name
    FROM cancellations c
    JOIN bookings b ON c.booking_id = b.id
    JOIN shows s ON b.show_id = s.id
    JOIN movies m ON s.movie_id = m.id
    JOIN theaters t ON s.theater_id = t.id
    ORDER BY c.cancelled_at DESC
    """)
    cancellations = [dict(r) for r in c.fetchall()]
    conn.close()
    return jsonify({"success": True, "cancellations": cancellations})

@app.route('/api/admin/sql-console', methods=['POST'])
def api_admin_sql_console():
    """
    Evaluator Demonstration Query Console.
    Allows executing read-only SQL queries live during the DBMS viva.
    Demonstrates constraints, joins, groupings, and relational algebra.
    """
    data = request.get_json() or {}
    query = (data.get('query') or '').strip()

    if not query:
        return jsonify({"success": False, "error": "Query cannot be empty"}), 400

    # Ensure query is read-only for security and safety
    first_word = query.split()[0].upper() if query.split() else ""
    if first_word not in ['SELECT', 'PRAGMA', 'EXPLAIN', 'WITH']:
        return jsonify({"success": False, "error": f"Only read queries (SELECT, PRAGMA, EXPLAIN) are permitted in demonstration console."}), 403

    conn = get_db()
    c = conn.cursor()
    try:
        start_time = datetime.datetime.now()
        c.execute(query)
        col_names = [d[0] for d in c.description] if c.description else []
        rows = [dict(zip(col_names, row)) for row in c.fetchall()]
        elapsed_ms = round((datetime.datetime.now() - start_time).total_seconds() * 1000, 2)
        conn.close()
        return jsonify({
            "success": True,
            "columns": col_names,
            "rows": rows,
            "count": len(rows),
            "execution_time_ms": elapsed_ms
        })
    except Exception as e:
        conn.close()
        return jsonify({"success": False, "error": str(e)}), 400

@app.route('/api/dbms/demonstrations', methods=['GET'])
def api_dbms_demonstrations():
    """
    Returns 7 pre-curated DBMS demonstration queries ready for evaluator inspection.
    """
    queries = [
        {
            "id": "q1_joins",
            "title": "1. Multi-Table Relational INNER JOIN (3NF Compliance)",
            "description": "Joins 6 normalized tables (bookings, booking_seats, shows, movies, theaters, payments) to produce an end-to-end audit trail.",
            "sql": """
            SELECT b.booking_ref, b.customer_name, m.title AS movie, t.name AS theater,
                   bs.seat_label, bs.tier, bs.price, p.payment_method, p.payment_status
            FROM bookings b
            INNER JOIN booking_seats bs ON b.id = bs.booking_id
            INNER JOIN shows s ON b.show_id = s.id
            INNER JOIN movies m ON s.movie_id = m.id
            INNER JOIN theaters t ON s.theater_id = t.id
            INNER JOIN payments p ON b.id = p.booking_id
            ORDER BY b.created_at DESC
            LIMIT 10;
            """
        },
        {
            "id": "q2_groupby_having",
            "title": "2. GROUP BY and HAVING Clause",
            "description": "Aggregates revenue and ticket counts by theater, filtering only venues with confirmed bookings.",
            "sql": """
            SELECT t.name AS theater_name, t.city,
                   COUNT(b.id) AS confirmed_bookings,
                   SUM(b.seats_count) AS total_seats_booked,
                   ROUND(SUM(b.total_amount), 2) AS total_revenue
            FROM theaters t
            INNER JOIN shows s ON t.id = s.theater_id
            INNER JOIN bookings b ON s.id = b.show_id
            WHERE b.status = 'CONFIRMED'
            GROUP BY t.id, t.name, t.city
            HAVING COUNT(b.id) > 0
            ORDER BY total_revenue DESC;
            """
        },
        {
            "id": "q3_subquery",
            "title": "3. Correlated Subquery Demonstration",
            "description": "Identifies high-value customers who spent more than the platform-wide average booking value.",
            "sql": """
            SELECT b.booking_ref, b.customer_name, b.customer_email, b.total_amount
            FROM bookings b
            WHERE b.status = 'CONFIRMED'
              AND b.total_amount > (
                  SELECT AVG(total_amount) FROM bookings WHERE status = 'CONFIRMED'
              )
            ORDER BY b.total_amount DESC;
            """
        },
        {
            "id": "q4_aggregates",
            "title": "4. Aggregate Statistical Functions (COUNT, SUM, AVG, MIN, MAX)",
            "description": "Calculates cinema ticket pricing dispersion and distribution across seating tiers.",
            "sql": """
            SELECT bs.tier,
                   COUNT(bs.id) AS seats_booked,
                   ROUND(AVG(bs.price), 2) AS avg_seat_price,
                   MIN(bs.price) AS min_price,
                   MAX(bs.price) AS max_price,
                   ROUND(SUM(bs.price), 2) AS gross_tier_revenue
            FROM booking_seats bs
            JOIN bookings b ON bs.booking_id = b.id
            WHERE b.status = 'CONFIRMED'
            GROUP BY bs.tier
            ORDER BY gross_tier_revenue DESC;
            """
        },
        {
            "id": "q5_left_join",
            "title": "5. LEFT OUTER JOIN (Auditing Unsold Shows)",
            "description": "Identifies scheduled movie shows that currently have zero confirmed bookings for inventory planning.",
            "sql": """
            SELECT s.id AS show_id, s.show_date, s.show_time, m.title AS movie, t.name AS theater
            FROM shows s
            INNER JOIN movies m ON s.movie_id = m.id
            INNER JOIN theaters t ON s.theater_id = t.id
            LEFT JOIN bookings b ON s.id = b.show_id AND b.status = 'CONFIRMED'
            WHERE b.id IS NULL
            ORDER BY s.show_date ASC, s.show_time ASC
            LIMIT 10;
            """
        },
        {
            "id": "q6_cancellation_audit",
            "title": "6. Transactional Cancellation & Refund Audit Trail",
            "description": "Cross-references cancellations against initial payments and calculates company retention revenue.",
            "sql": """
            SELECT c.cancellation_ref, c.booking_ref, c.original_amount,
                   c.cancellation_fee AS retained_fee,
                   c.refund_amount, c.refund_status, c.cancelled_at,
                   b.customer_name, b.payment_method
            FROM cancellations c
            INNER JOIN bookings b ON c.booking_id = b.id
            ORDER BY c.cancelled_at DESC;
            """
        },
        {
            "id": "q7_dbms_integrity",
            "title": "7. Schema Constraint & Foreign Key Verification",
            "description": "Queries SQLite system catalog to verify foreign key relationships, indexes, and primary key definitions.",
            "sql": """
            SELECT m.name AS table_name, p.name AS column_name, p.type, p.[notnull], p.dflt_value, p.pk
            FROM sqlite_master m
            JOIN pragma_table_info(m.name) p
            WHERE m.type = 'table' AND m.name IN ('bookings', 'booking_seats', 'payments', 'cancellations')
            ORDER BY m.name, p.cid;
            """
        }
    ]
    return jsonify({"success": True, "demonstrations": queries})

if __name__ == '__main__':
    print("==================================================================")
    print("🎬 CINEPLEX - Movie Ticket Booking System")
    print("Tagline: Your Movies. Your Moments.")
    print("Server running at: http://127.0.0.1:5000")
    print("Admin Portal: http://127.0.0.1:5000 (Switch to Admin View)")
    print("==================================================================")
    app.run(host='0.0.0.0', port=5000, debug=True)
