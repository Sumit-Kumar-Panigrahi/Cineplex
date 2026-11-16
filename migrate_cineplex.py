import sqlite3
import json
import uuid
import datetime
from pathlib import Path

DB_PATH = Path("cinema.db").resolve()

def run_migration():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    # 1. Update user 1: Soumya Ranjan -> Sumit Kumar Panigrahi
    print("Updating user references...")
    c.execute("""
        UPDATE users 
        SET name = 'Sumit Kumar Panigrahi', email = 'sumit@example.com', phone = '8984378785'
        WHERE email IN ('soumya@example.com', 'soumya.r@example.com') OR name LIKE '%Soumya%'
    """)

    # Update demo bookings and cancellations
    c.execute("""
        UPDATE bookings 
        SET customer_name = 'Sumit Kumar Panigrahi', customer_email = 'sumit@example.com'
        WHERE customer_email IN ('soumya@example.com', 'soumya.r@example.com') OR customer_name LIKE '%Soumya%'
    """)

    # 2. Add is_admin column to users if not present
    c.execute("PRAGMA table_info(users)")
    cols = [col["name"] for col in c.fetchall()]
    if "is_admin" not in cols:
        print("Adding is_admin column to users...")
        c.execute("ALTER TABLE users ADD COLUMN is_admin INTEGER DEFAULT 0")

    # Add admin user if not present (admin@cineplex.com / admin123 -> base64 'YWRtaW4xMjM=')
    import base64
    admin_hash = base64.b64encode(b"admin123").decode()
    c.execute("SELECT id FROM users WHERE email = 'admin@cineplex.com'")
    if not c.fetchone():
        print("Seeding admin user...")
        c.execute("""
            INSERT INTO users (name, email, phone, password_hash, is_admin)
            VALUES (?, ?, ?, ?, 1)
        """, ("Cineplex Admin", "admin@cineplex.com", "9999999999", admin_hash))

    # 3. Create relational tables: booking_seats, booking_snacks, payments
    print("Creating relational tables: booking_seats, booking_snacks, payments...")
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
        payment_method TEXT NOT NULL CHECK (payment_method IN ('UPI', 'CARD', 'NETBANKING', 'WALLET')),
        payment_status TEXT NOT NULL DEFAULT 'SUCCESS' CHECK (payment_status IN ('SUCCESS', 'PENDING', 'FAILED', 'REFUNDED')),
        transaction_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (booking_id) REFERENCES bookings(id) ON DELETE CASCADE
    )
    """)

    # 4. Backfill booking_seats and payments for existing bookings
    print("Backfilling booking_seats and payments for existing bookings...")
    c.execute("SELECT b.id, b.booking_ref, b.show_id, b.seat_numbers, b.total_amount, b.payment_method, b.status, b.created_at, s.price_vip, s.price_premium, s.price_executive FROM bookings b JOIN shows s ON b.show_id = s.id")
    existing_bookings = c.fetchall()

    for bk in existing_bookings:
        b_id = bk["id"]
        # Check if already backfilled
        c.execute("SELECT COUNT(*) FROM booking_seats WHERE booking_id = ?", (b_id,))
        if c.fetchone()[0] == 0:
            seats = [s.strip() for s in (bk["seat_numbers"] or "").split(",") if s.strip()]
            for seat in seats:
                row_letter = seat[0].upper() if seat else "C"
                tier = "RECLINER" if row_letter in ["A", "B"] else ("PRIME" if row_letter in ["C", "D", "E"] else "CLASSIC")
                price = bk["price_vip"] if tier == "RECLINER" else (bk["price_premium"] if tier == "PRIME" else bk["price_executive"])
                c.execute("""
                    INSERT INTO booking_seats (booking_id, show_id, seat_label, tier, price)
                    VALUES (?, ?, ?, ?, ?)
                """, (b_id, bk["show_id"], seat, tier, price))

        c.execute("SELECT COUNT(*) FROM payments WHERE booking_id = ?", (b_id,))
        if c.fetchone()[0] == 0:
            pay_ref = f"PAY-{bk['booking_ref']}"
            p_status = "REFUNDED" if bk["status"] == "CANCELLED" else "SUCCESS"
            method = bk["payment_method"] or "UPI"
            if "CARD" in method.upper(): method = "CARD"
            elif "NET" in method.upper(): method = "NETBANKING"
            elif "WALLET" in method.upper(): method = "WALLET"
            else: method = "UPI"
            c.execute("""
                INSERT OR IGNORE INTO payments (booking_id, payment_ref, amount, payment_method, payment_status, transaction_time)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (b_id, pay_ref, bk["total_amount"], method, p_status, bk["created_at"]))

    # 5. Add database indexes
    print("Creating DBMS indexes...")
    indexes = [
        ("idx_shows_movie_date", "CREATE INDEX IF NOT EXISTS idx_shows_movie_date ON shows(movie_id, show_date)"),
        ("idx_shows_theater", "CREATE INDEX IF NOT EXISTS idx_shows_theater ON shows(theater_id, show_date)"),
        ("idx_seats_show_status", "CREATE INDEX IF NOT EXISTS idx_seats_show_status ON show_seats(show_id, status)"),
        ("idx_bookings_user_email", "CREATE INDEX IF NOT EXISTS idx_bookings_user_email ON bookings(customer_email)"),
        ("idx_bookings_ref", "CREATE INDEX IF NOT EXISTS idx_bookings_ref ON bookings(booking_ref)"),
        ("idx_booking_seats_bk", "CREATE INDEX IF NOT EXISTS idx_booking_seats_bk ON booking_seats(booking_id)"),
        ("idx_payments_bk", "CREATE INDEX IF NOT EXISTS idx_payments_bk ON payments(booking_id)"),
        ("idx_movies_status", "CREATE INDEX IF NOT EXISTS idx_movies_status ON movies(is_now_showing, featured)")
    ]
    for idx_name, idx_sql in indexes:
        c.execute(idx_sql)

    # 6. Add Expanded Movie Catalogue (Indian & International Movies)
    print("Populating Expanded Movie Catalogue...")
    # Check existing titles
    c.execute("SELECT title FROM movies")
    existing_titles = set(r["title"].lower().strip() for r in c.fetchall())

    new_movies = [
        # Indian Movies
        {
            "tmdb_id": 945961,
            "title": "Pushpa 2: The Rule",
            "overview": "The clash intensifies as Pushpa Raj expands his sandalwood empire against formidable enemies, including fearless SP Bhanwar Singh Shekhawat. Starring Allu Arjun, Rashmika Mandanna, and Fahadh Faasil.",
            "poster_path": "https://image.tmdb.org/t/p/w500/vQ5x2kO21f0O5K3Qc1y9Q9M0Q0o.jpg",
            "offline_poster_path": "/static/posters/ramayan.jpg",
            "backdrop_path": "https://image.tmdb.org/t/p/w1280/tElnmtQ6yz1PjN1kePNl8yMSb59.jpg",
            "release_date": "2024-12-05",
            "rating": 9.1,
            "votes_count": 98400,
            "runtime": 195,
            "genres": json.dumps(["Action", "Crime", "Thriller"]),
            "language": "Hindi, Telugu",
            "certification": "UA 16+",
            "trailer_url": "https://www.youtube.com/embed/g3JUbgFBZno",
            "is_now_showing": 1,
            "featured": 1
        },
        {
            "tmdb_id": 1022789,
            "title": "Kalki 2898 AD",
            "overview": "A modern mythology-infused science fiction epic set in a post-apocalyptic dystopian world, where an avatar descends to protect unborn hope. Starring Prabhas, Amitabh Bachchan, and Deepika Padukone.",
            "poster_path": "https://image.tmdb.org/t/p/w500/3bsxZp7i8Q2kR5bQp9z9g1z3s3.jpg",
            "offline_poster_path": "/static/posters/scene.jpg",
            "backdrop_path": "https://image.tmdb.org/t/p/w1280/8b8r8W80Qz1g7Z8s0Qz1g7Z8s0.jpg",
            "release_date": "2024-06-27",
            "rating": 8.9,
            "votes_count": 112000,
            "runtime": 180,
            "genres": json.dumps(["Sci-Fi", "Action", "Mythology"]),
            "language": "Hindi, Telugu",
            "certification": "UA 13+",
            "trailer_url": "https://www.youtube.com/embed/kQDd1AhGIHk",
            "is_now_showing": 1,
            "featured": 1
        },
        {
            "tmdb_id": 1111873,
            "title": "Stree 2",
            "overview": "The town of Chanderi is haunted once more, this time by a terrifying headless entity named Sarkata. The eccentric gang reunites with Stree's spirit to save their loved ones. Starring Rajkummar Rao and Shraddha Kapoor.",
            "poster_path": "https://image.tmdb.org/t/p/w500/m2zW6a4Qv0h1kF8G1q8z9b0.jpg",
            "offline_poster_path": "/static/posters/jailer2.jpg",
            "backdrop_path": "https://image.tmdb.org/t/p/w1280/9l1Qz1g7Z8s0Qz1g7Z8s0.jpg",
            "release_date": "2024-08-15",
            "rating": 8.5,
            "votes_count": 87000,
            "runtime": 147,
            "genres": json.dumps(["Comedy", "Horror"]),
            "language": "Hindi",
            "certification": "UA 16+",
            "trailer_url": "https://www.youtube.com/embed/kv14pXjK_Uo",
            "is_now_showing": 1,
            "featured": 0
        },
        {
            "tmdb_id": 1197830,
            "title": "Chhaava",
            "overview": "A grand historical biographical war drama chronicling the extraordinary valour and leadership of Chhatrapati Sambhaji Maharaj, the second ruler of the Maratha Empire. Starring Vicky Kaushal and Rashmika Mandanna.",
            "poster_path": "https://image.tmdb.org/t/p/w500/k2zW6a4Qv0h1kF8G1q8z9b1.jpg",
            "offline_poster_path": "/static/posters/udta_teer.jpg",
            "backdrop_path": "https://image.tmdb.org/t/p/w1280/4z9Qz1g7Z8s0Qz1g7Z8s0.jpg",
            "release_date": "2025-02-14",
            "rating": 8.7,
            "votes_count": 45000,
            "runtime": 160,
            "genres": json.dumps(["Historical", "Action", "Drama"]),
            "language": "Hindi",
            "certification": "UA 16+",
            "trailer_url": "https://www.youtube.com/embed/hB8w6s4vQ8A",
            "is_now_showing": 1,
            "featured": 0
        },
        {
            "tmdb_id": 872585,
            "title": "Jawan",
            "overview": "A high-octane emotional action thriller outlining the journey of a man driven by a personal vendetta to rectify the social corruptions in society, kept together by an old promise. Starring Shah Rukh Khan and Nayanthara.",
            "poster_path": "https://image.tmdb.org/t/p/w500/jJw9K0R3H0g0Z9F2v3s3k1y.jpg",
            "offline_poster_path": "/static/posters/ramayan.jpg",
            "backdrop_path": "https://image.tmdb.org/t/p/w1280/7I6VUdPj6tQtheET8cuNXveDTe5.jpg",
            "release_date": "2023-09-07",
            "rating": 8.6,
            "votes_count": 142000,
            "runtime": 169,
            "genres": json.dumps(["Action", "Thriller"]),
            "language": "Hindi, Tamil",
            "certification": "UA 16+",
            "trailer_url": "https://www.youtube.com/embed/MWOlnZSnXpc",
            "is_now_showing": 0,
            "featured": 1
        },
        {
            "tmdb_id": 1289345,
            "title": "Drishyam: The Conclusion",
            "overview": "The ultimate concluding chapter of Vijay Salgaonkar's masterclass in deception and family protection as new forensic technology reopens the case.",
            "poster_path": "https://image.tmdb.org/t/p/w500/gIClWRv5OSe8rl5Koi0AeUcCZ9Z.jpg",
            "offline_poster_path": "/static/posters/drishyam.jpg",
            "backdrop_path": "https://image.tmdb.org/t/p/w1280/5jxesZtbjNtsDitSBvK1amtd7o2.jpg",
            "release_date": "2026-11-20",
            "rating": 9.0,
            "votes_count": 15000,
            "runtime": 155,
            "genres": json.dumps(["Crime", "Thriller", "Suspense"]),
            "language": "Hindi",
            "certification": "UA 16+",
            "trailer_url": "https://www.youtube.com/embed/cxA2y9Tgl7o",
            "is_now_showing": 0,
            "featured": 0
        },
        {
            "tmdb_id": 1334521,
            "title": "Dhurandhar",
            "overview": "Ranveer Singh headlines an electrifying high-stakes geopolitical espionage thriller directed by Aditya Dhar, tracking elite undercover operatives deep behind enemy lines.",
            "poster_path": "https://image.tmdb.org/t/p/w500/q3zW6a4Qv0h1kF8G1q8z9b2.jpg",
            "offline_poster_path": "/static/posters/scene.jpg",
            "backdrop_path": "https://image.tmdb.org/t/p/w1280/2z9Qz1g7Z8s0Qz1g7Z8s0.jpg",
            "release_date": "2025-10-02",
            "rating": 8.4,
            "votes_count": 12000,
            "runtime": 150,
            "genres": json.dumps(["Action", "Thriller", "Spy"]),
            "language": "Hindi",
            "certification": "UA 16+",
            "trailer_url": "https://www.youtube.com/embed/ROI2ilgRSPk",
            "is_now_showing": 0,
            "featured": 0
        },
        {
            "tmdb_id": 1221345,
            "title": "Mookuthi Amman 2",
            "overview": "RJ Balaji and Nayanthara return in this satirical fantasy comedy highlighting devotion, modern miracles, and humorous exposés of false seers.",
            "poster_path": "https://image.tmdb.org/t/p/w500/y3zW6a4Qv0h1kF8G1q8z9b3.jpg",
            "offline_poster_path": "/static/posters/jadi.jpg",
            "backdrop_path": "https://image.tmdb.org/t/p/w1280/3z9Qz1g7Z8s0Qz1g7Z8s0.jpg",
            "release_date": "2025-11-14",
            "rating": 8.2,
            "votes_count": 18000,
            "runtime": 138,
            "genres": json.dumps(["Comedy", "Fantasy", "Satire"]),
            "language": "Tamil, Hindi",
            "certification": "U",
            "trailer_url": "https://www.youtube.com/embed/dKIi5HuXXS8",
            "is_now_showing": 0,
            "featured": 0
        },
        {
            "tmdb_id": 1354321,
            "title": "Bouma",
            "overview": "A rich Bengali cultural drama depicting generational matriarchy, warmth, and culinary tradition in a heritage Kolkata mansion.",
            "poster_path": "https://image.tmdb.org/t/p/w500/p4zW6a4Qv0h1kF8G1q8z9b4.jpg",
            "offline_poster_path": "/static/posters/tum_mere_ho.jpg",
            "backdrop_path": "https://image.tmdb.org/t/p/w1280/5z9Qz1g7Z8s0Qz1g7Z8s0.jpg",
            "release_date": "2025-09-12",
            "rating": 8.0,
            "votes_count": 9200,
            "runtime": 132,
            "genres": json.dumps(["Drama", "Family"]),
            "language": "Bengali, Hindi",
            "certification": "U",
            "trailer_url": "https://www.youtube.com/embed/qJ-sICWNOKo",
            "is_now_showing": 0,
            "featured": 0
        },
        {
            "tmdb_id": 1365432,
            "title": "DNK",
            "overview": "An intense detective mystery thriller unearthing buried secrets across coastal Odisha through sharp investigative deduction.",
            "poster_path": "https://image.tmdb.org/t/p/w500/r5zW6a4Qv0h1kF8G1q8z9b5.jpg",
            "offline_poster_path": "/static/posters/scene.jpg",
            "backdrop_path": "https://image.tmdb.org/t/p/w1280/6z9Qz1g7Z8s0Qz1g7Z8s0.jpg",
            "release_date": "2025-12-19",
            "rating": 8.1,
            "votes_count": 14500,
            "runtime": 135,
            "genres": json.dumps(["Thriller", "Mystery", "Crime"]),
            "language": "Odia, Hindi",
            "certification": "UA 16+",
            "trailer_url": "https://www.youtube.com/embed/ho4ACWs1hwc",
            "is_now_showing": 0,
            "featured": 0
        },
        {
            "tmdb_id": 1376543,
            "title": "Itllu Arjuna",
            "overview": "A wholesome family entertainer and romantic comedy exploring modern love and traditional joint family bonds.",
            "poster_path": "https://image.tmdb.org/t/p/w500/s6zW6a4Qv0h1kF8G1q8z9b6.jpg",
            "offline_poster_path": "/static/posters/udta_teer.jpg",
            "backdrop_path": "https://image.tmdb.org/t/p/w1280/7z9Qz1g7Z8s0Qz1g7Z8s0.jpg",
            "release_date": "2026-01-14",
            "rating": 8.3,
            "votes_count": 11000,
            "runtime": 142,
            "genres": json.dumps(["Family", "Romance", "Comedy"]),
            "language": "Telugu, Hindi",
            "certification": "U",
            "trailer_url": "https://www.youtube.com/embed/8yjkWn-pKAA",
            "is_now_showing": 0,
            "featured": 0
        },
        # International Movies requested
        {
            "tmdb_id": 157336,
            "title": "Interstellar",
            "overview": "When Earth becomes uninhabitable, a team of explorers travel through a wormhole across space and time in an attempt to ensure humanity's survival. Directed by Christopher Nolan, starring Matthew McConaughey and Anne Hathaway.",
            "poster_path": "https://image.tmdb.org/t/p/w500/gEU2QniE6E77NI6lCU6MxlNBvIx.jpg",
            "offline_poster_path": "/static/posters/ramayan.jpg",
            "backdrop_path": "https://image.tmdb.org/t/p/w1280/xJHokMbljvjADYDit5fK5VQsXEG.jpg",
            "release_date": "2014-11-05",
            "rating": 9.4,
            "votes_count": 210000,
            "runtime": 169,
            "genres": json.dumps(["Sci-Fi", "Adventure", "Drama"]),
            "language": "English, Hindi",
            "certification": "UA 13+",
            "trailer_url": "https://www.youtube.com/embed/zSWdZVtXT7E",
            "is_now_showing": 1,
            "featured": 1
        },
        {
            "tmdb_id": 27205,
            "title": "Inception",
            "overview": "Cobb steals information from targets by entering their dreams. He is offered a chance at having his criminal history erased as payment for the implantation of an idea into a CEO's mind. Starring Leonardo DiCaprio.",
            "poster_path": "https://image.tmdb.org/t/p/w500/oYuLEt3zVCKq57qu2F8dT7NIa6f.jpg",
            "offline_poster_path": "/static/posters/scene.jpg",
            "backdrop_path": "https://image.tmdb.org/t/p/w1280/s3TBrRGB1iav7gFOCNx3H31MoES.jpg",
            "release_date": "2010-07-15",
            "rating": 9.3,
            "votes_count": 195000,
            "runtime": 148,
            "genres": json.dumps(["Sci-Fi", "Action", "Thriller"]),
            "language": "English, Hindi",
            "certification": "UA 16+",
            "trailer_url": "https://www.youtube.com/embed/YoHD9XEInc0",
            "is_now_showing": 1,
            "featured": 1
        },
        {
            "tmdb_id": 299534,
            "title": "Avengers: Endgame",
            "overview": "After the devastating events of Infinity War, the universe is in ruins. With the help of remaining allies, the Avengers assemble once more to reverse Thanos' actions and restore balance. Starring Robert Downey Jr. and Chris Evans.",
            "poster_path": "https://image.tmdb.org/t/p/w500/or06FN3Dka5tukK1e9sl16pB3iy.jpg",
            "offline_poster_path": "/static/posters/jailer2.jpg",
            "backdrop_path": "https://image.tmdb.org/t/p/w1280/7RyHsO4yDXtBv1zJW8ACSLmw0kf.jpg",
            "release_date": "2019-04-24",
            "rating": 9.2,
            "votes_count": 240000,
            "runtime": 181,
            "genres": json.dumps(["Action", "Adventure", "Sci-Fi"]),
            "language": "English, Hindi",
            "certification": "UA 13+",
            "trailer_url": "https://www.youtube.com/embed/TcMBFSGVi1c",
            "is_now_showing": 1,
            "featured": 1
        },
        {
            "tmdb_id": 597,
            "title": "Titanic",
            "overview": "A seventeen-year-old aristocrat falls in love with a kind but poor artist aboard the luxurious, ill-fated R.M.S. Titanic. Directed by James Cameron, starring Leonardo DiCaprio and Kate Winslet.",
            "poster_path": "https://image.tmdb.org/t/p/w500/9xjZS2rlVxm8SFx8kPC3aIGCOYQ.jpg",
            "offline_poster_path": "/static/posters/tum_mere_ho.jpg",
            "backdrop_path": "https://image.tmdb.org/t/p/w1280/6VmF2397ISUFs67Zzh7Y352n9as.jpg",
            "release_date": "1997-12-18",
            "rating": 9.0,
            "votes_count": 180000,
            "runtime": 194,
            "genres": json.dumps(["Drama", "Romance"]),
            "language": "English, Hindi",
            "certification": "UA 16+",
            "trailer_url": "https://www.youtube.com/embed/2e-eXJ6HgkQ",
            "is_now_showing": 0,
            "featured": 0
        },
        {
            "tmdb_id": 10588,
            "title": "The Cat in the Hat",
            "overview": "Two bored children have their lives turned upside down when a talking cat in a red-and-white striped hat arrives with whimsical mayhem. Starring Mike Myers.",
            "poster_path": "https://image.tmdb.org/t/p/w500/5k70iH2gR7vU2x9kF8g1q8z9b7.jpg",
            "offline_poster_path": "/static/posters/udta_teer.jpg",
            "backdrop_path": "https://image.tmdb.org/t/p/w1280/8k70iH2gR7vU2x9kF8g1q8z9b7.jpg",
            "release_date": "2026-03-06",
            "rating": 7.8,
            "votes_count": 12500,
            "runtime": 102,
            "genres": json.dumps(["Animation", "Family", "Comedy"]),
            "language": "English, Hindi",
            "certification": "U",
            "trailer_url": "https://www.youtube.com/embed/8yjkWn-pKAA",
            "is_now_showing": 0,
            "featured": 0
        },
        {
            "tmdb_id": 1184918,
            "title": "Clayface",
            "overview": "A dark psychological body-horror thriller delving into the tragic transformation of actor Matt Hagen into the iconic Gotham shapeshifter Clayface.",
            "poster_path": "https://image.tmdb.org/t/p/w500/9k70iH2gR7vU2x9kF8g1q8z9b8.jpg",
            "offline_poster_path": "/static/posters/scene.jpg",
            "backdrop_path": "https://image.tmdb.org/t/p/w1280/1k70iH2gR7vU2x9kF8g1q8z9b8.jpg",
            "release_date": "2026-10-09",
            "rating": 8.3,
            "votes_count": 8900,
            "runtime": 130,
            "genres": json.dumps(["Horror", "Action", "Crime"]),
            "language": "English, Hindi",
            "certification": "A",
            "trailer_url": "https://www.youtube.com/embed/ho4ACWs1hwc",
            "is_now_showing": 0,
            "featured": 0
        }
    ]

    added_movies = 0
    for m in new_movies:
        if m["title"].lower().strip() not in existing_titles:
            c.execute("""
            INSERT INTO movies (tmdb_id, title, overview, poster_path, offline_poster_path, backdrop_path, release_date, rating, votes_count, runtime, genres, language, certification, trailer_url, is_now_showing, featured)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (m["tmdb_id"], m["title"], m["overview"], m["poster_path"], m["offline_poster_path"], m["backdrop_path"], m["release_date"], m["rating"], m["votes_count"], m["runtime"], m["genres"], m["language"], m["certification"], m["trailer_url"], m["is_now_showing"], m["featured"]))
            added_movies += 1

    print(f"Added {added_movies} new movies to catalogue.")

    # 7. Seed shows for newly added Now Showing movies
    print("Scheduling shows & generating seats for Now Showing movies...")
    c.execute("SELECT id, title FROM movies WHERE is_now_showing = 1")
    now_showing_movies = c.fetchall()

    c.execute("SELECT id, theater_id FROM screens ORDER BY theater_id ASC, id ASC")
    screens = c.fetchall()
    screens_by_theater = {}
    for sc in screens:
        screens_by_theater.setdefault(sc["theater_id"], []).append(sc["id"])

    today = datetime.date.today()
    shows_added = 0
    time_slots = [
        ["09:45 AM", "01:15 PM", "06:45 PM"],
        ["10:15 AM", "02:30 PM", "07:30 PM", "10:15 PM"],
        ["11:00 AM", "03:15 PM", "08:00 PM"],
        ["12:30 PM", "04:45 PM", "09:15 PM"]
    ]

    for m_idx, m in enumerate(now_showing_movies):
        m_id = m["id"]
        # Check if movie already has shows
        c.execute("SELECT COUNT(*) FROM shows WHERE movie_id = ?", (m_id,))
        if c.fetchone()[0] == 0:
            slots = time_slots[m_idx % len(time_slots)]
            for day_offset in range(5):
                show_date = (today + datetime.timedelta(days=day_offset)).strftime("%Y-%m-%d")
                for tid, sc_list in screens_by_theater.items():
                    sc_id = sc_list[m_idx % len(sc_list)]
                    for st in slots:
                        c.execute("""
                        INSERT INTO shows (movie_id, theater_id, screen_id, show_date, show_time, price_vip, price_premium, price_executive)
                        VALUES (?, ?, ?, ?, ?, 450.0, 300.0, 200.0)
                        """, (m_id, tid, sc_id, show_date, st))
                        show_id = c.lastrowid
                        shows_added += 1

                        # Generate seats for show
                        seats = []
                        for r in ["A", "B"]:
                            for col in range(1, 11): seats.append((show_id, f"{r}{col}", "RECLINER", "AVAILABLE"))
                        for r in ["C", "D", "E"]:
                            for col in range(1, 13): seats.append((show_id, f"{r}{col}", "PRIME", "AVAILABLE"))
                        for r in ["F", "G", "H"]:
                            for col in range(1, 13): seats.append((show_id, f"{r}{col}", "CLASSIC", "AVAILABLE"))
                        c.executemany("INSERT OR IGNORE INTO show_seats (show_id, seat_label, tier, status) VALUES (?, ?, ?, ?)", seats)

    print(f"Scheduled {shows_added} new shows.")
    conn.commit()

    # Final summary
    c.execute("SELECT COUNT(*) FROM movies")
    total_m = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM movies WHERE is_now_showing = 1")
    ns_m = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM shows")
    total_shows = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM users")
    total_users = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM bookings")
    total_bk = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM booking_seats")
    total_bs = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM payments")
    total_pay = c.fetchone()[0]

    print("\n--- MIGRATION COMPLETE ---")
    print(f"Total Movies: {total_m} ({ns_m} Now Showing, {total_m - ns_m} Upcoming/Classics)")
    print(f"Total Shows: {total_shows}")
    print(f"Total Users: {total_users}")
    print(f"Total Bookings: {total_bk}")
    print(f"Relational booking_seats rows: {total_bs}")
    print(f"Relational payments rows: {total_pay}")

    conn.close()

if __name__ == "__main__":
    run_migration()

