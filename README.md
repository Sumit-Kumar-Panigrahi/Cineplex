# CINEPLEX — Movie Ticket Booking System

**Your Movies. Your Moments.**

A fully functional, production-level movie ticket booking platform built with Python Flask, SQLite (3NF Relational), HTML5, CSS3, and ES6 JavaScript.

> **Developer:** Sumit Kumar Panigrahi  
> **Stack:** Python 3 · Flask · SQLite 3 · HTML5 · CSS3 · JavaScript (ES6)  
> **Database:** 3NF Normalized Relational Schema · 11 Tables · 2,100 Scheduled Shows

---

## Features

- **24-movie catalogue** filterable by language, genre, and show status (Now Showing / Upcoming / Classics)
- **City-aware showtimes** across 10 multiplexes (Bhubaneswar, Mumbai, Delhi-NCR, and more)
- **Curved auditorium seat map** with 3 pricing tiers: Recliner (₹420), Prime (₹280), Classic (₹180)
- **5-minute ACID seat hold** — atomic SQLite transactions prevent double-booking
- **Digital M-Ticket Pass** with offline QR code, 1-click print, PDF download
- **Concessions (F&B)** — popcorn, nachos, samosas, combo meals
- **Transparent cancellation** — ₹30/seat fee, instant seat liberation and refund ledger
- **UPI / Card payment simulation** with confirmation reference
- **TMDB API integration** — live movie poster and backdrop sync
- **Live Search autocomplete** — instant dropdown across movies, languages, and theatres
- **Management Portal** — Admin dashboard with real-time stats
- **Interactive SQL Query Showcase** — Execute live SQL queries (JOINs, GROUP BY, subqueries, aggregates)
- **Responsive design** — desktop, tablet, and mobile ready

---

## Project Structure

```
cineplex/
├── app.py                  # Flask backend: REST APIs, SQLite engine, admin routes
├── cinema.db               # SQLite database (seeded: 24 movies, 10 theatres, 2100 shows)
├── templates/
│   └── index.html          # Single-page frontend: all views, modals, seat map
├── static/
│   ├── style.css           # Cineplex brand theme, curved screen, print styles
│   ├── app.js              # Frontend controller: booking flow, live search, SQL console
│   └── posters/            # SVG movie artwork & vector food/snack icons
├── test_cineplex_system.py # Unit test suite (8 backend tests)
├── run.bat                 # Windows 1-click launcher
├── python.bat              # Python runner helper
├── DEMO_GUIDE.md           # 5–10 min demonstration guide for evaluators
└── README.md               # This file
```

---

## Relational Database Schema (3NF)

| Table | Description |
|---|---|
| `movies` | Catalogue with TMDB integration |
| `theaters` | Multiplex network across cities |
| `screens` | Auditorium screens per theatre |
| `shows` | Scheduled showtimes with pricing |
| `show_seats` | Per-seat status & reservation tokens |
| `bookings` | Customer booking records |
| `booking_seats` | Seat-level booking detail |
| `booking_snacks` | F&B per booking |
| `payments` | Payment transactions |
| `cancellations` | Cancellation & refund ledger |
| `users` | Registered accounts |

---

## Running Locally

### Prerequisites

| Requirement | Minimum Version |
|---|---|
| Python | 3.9+ |
| pip | (bundled with Python) |
| Git | Any recent version |

Python 3.9+ must be installed. Download from [python.org](https://www.python.org/downloads/).

---

### Step 1 — Clone the Repository

```bash
git clone https://github.com/YOUR_USERNAME/cineplex.git
cd cineplex
```

---

### Step 2 — Create a Virtual Environment (Recommended)

**macOS / Linux:**
```bash
python3 -m venv venv
source venv/bin/activate
```

**Windows (Command Prompt):**
```bat
python -m venv venv
venv\Scripts\activate.bat
```

**Windows (PowerShell):**
```powershell
python -m venv venv
venv\Scripts\Activate.ps1
```

---

### Step 3 — Install Dependencies

```bash
pip install flask requests
```

That's it. The app uses only the standard library plus Flask and Requests.

---

### Step 4 — (Optional) Configure TMDB API Key

For live movie poster syncing from [The Movie Database](https://www.themoviedb.org/):

1. Register a free account at [themoviedb.org](https://www.themoviedb.org/)
2. Go to **Settings → API** and copy your **API Key (v3)**
3. Set it as an environment variable:

**macOS / Linux:**
```bash
export TMDB_API_KEY=your_api_key_here
```

**Windows (Command Prompt):**
```bat
set TMDB_API_KEY=your_api_key_here
```

**Windows (PowerShell):**
```powershell
$env:TMDB_API_KEY="your_api_key_here"
```

> **Without a TMDB key:** The app works fully with the included local SVG posters and seeded database. The key only enables the "TMDB Sync" button to refresh posters from the live API.

---

### Step 5 — Run the Server

```bash
python app.py
```

You should see:

```
==================================================================
 CINEPLEX - Movie Ticket Booking System
 Tagline: Your Movies. Your Moments.
 Server running at: http://127.0.0.1:5000
==================================================================
 * Running on http://127.0.0.1:5000
 * Running on http://0.0.0.0:5000
```

Open your browser and go to: **[http://127.0.0.1:5000](http://127.0.0.1:5000)**

---

### Step 6 — Demo Accounts

| Account | Email | Password | Role |
|---|---|---|---|
| Sumit (Demo User) | `sumit@example.com` | `password123` | Customer |
| Admin | `admin@cineplex.com` | `admin123` | Administrator |

---

### Windows Quick Start

Double-click `run.bat` — it auto-detects Python and launches the server.

---

### Running the Test Suite

```bash
python -m unittest test_cineplex_system.py -v
```

Expected output: **8 tests, OK**.

---

## Deployment

### Option A — Deploy to Render (Free, Recommended)

**Render** offers a free web service tier that runs Python Flask apps with zero credit card required.

#### Step 1 — Create a `requirements.txt`

```bash
pip freeze > requirements.txt
```

Or create it manually:

```
flask>=3.0.0
requests>=2.31.0
```

#### Step 2 — Create a `Procfile`

Create a file named `Procfile` (no extension) in the project root:

```
web: gunicorn app:app
```

Install gunicorn:
```bash
pip install gunicorn
pip freeze > requirements.txt
```

#### Step 3 — Push to GitHub

```bash
git add .
git commit -m "Add Render deployment files"
git push origin main
```

#### Step 4 — Deploy on Render

1. Go to [render.com](https://render.com) and sign up with GitHub
2. Click **New → Web Service**
3. Connect your **cineplex** GitHub repository
4. Configure:
   - **Name:** `cineplex`
   - **Region:** Singapore (or closest to you)
   - **Branch:** `main`
   - **Runtime:** `Python 3`
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `gunicorn app:app`
5. Add Environment Variable (optional): `TMDB_API_KEY` → your key
6. Click **Create Web Service**

Your app will be live at `https://cineplex.onrender.com` within 2–3 minutes.

> **Note:** On Render's free tier, the SQLite `cinema.db` file is **ephemeral** (resets on redeploy). For persistent storage, use a persistent disk (paid) or migrate to PostgreSQL.

---

### Option B — Deploy to Railway

**Railway** offers \$5 free credit per month, enough for a demo project.

#### Step 1 — Prepare files

Same as Render: create `requirements.txt` and `Procfile`.

#### Step 2 — Deploy

1. Go to [railway.app](https://railway.app) and sign in with GitHub
2. Click **New Project → Deploy from GitHub repo**
3. Select your **cineplex** repository
4. Railway auto-detects Python and starts deployment
5. Go to **Settings → Networking → Generate Domain** to get a public URL

---

### Option C — Deploy to PythonAnywhere (Free Tier)

Good for demos — persistent filesystem, always-on free tier.

#### Step 1 — Upload files

1. Go to [pythonanywhere.com](https://www.pythonanywhere.com) and create a free account
2. Open a **Bash Console** and clone your repo:
   ```bash
   git clone https://github.com/YOUR_USERNAME/cineplex.git
   ```

#### Step 2 — Install dependencies

```bash
cd cineplex
pip3 install --user flask requests
```

#### Step 3 — Configure Web App

1. Go to the **Web** tab → **Add a new web app**
2. Choose **Manual configuration** → **Python 3.10**
3. Set **Source code:** `/home/YOUR_USERNAME/cineplex`
4. Set **Working directory:** `/home/YOUR_USERNAME/cineplex`
5. Edit the **WSGI configuration file** (link provided on the Web tab):

```python
import sys
path = '/home/YOUR_USERNAME/cineplex'
if path not in sys.path:
    sys.path.append(path)

from app import app as application
```

6. Click **Reload**

Your app will be live at `https://YOUR_USERNAME.pythonanywhere.com`

> **PythonAnywhere free tier advantage:** `cinema.db` persists on disk — bookings and data survive restarts!

---

### Option D — Deploy to a Linux VPS (DigitalOcean / AWS / Linode)

For production or persistent deployments.

#### Step 1 — Server setup

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install python3 python3-pip python3-venv git nginx -y
```

#### Step 2 — Clone and install

```bash
git clone https://github.com/YOUR_USERNAME/cineplex.git /var/www/cineplex
cd /var/www/cineplex
python3 -m venv venv
source venv/bin/activate
pip install flask requests gunicorn
```

#### Step 3 — Create a Gunicorn systemd service

```bash
sudo nano /etc/systemd/system/cineplex.service
```

Paste:

```ini
[Unit]
Description=Cineplex Flask App
After=network.target

[Service]
User=www-data
WorkingDirectory=/var/www/cineplex
Environment="PATH=/var/www/cineplex/venv/bin"
ExecStart=/var/www/cineplex/venv/bin/gunicorn --workers 3 --bind unix:cineplex.sock -m 007 app:app

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable cineplex
sudo systemctl start cineplex
```

#### Step 4 — Nginx reverse proxy

```bash
sudo nano /etc/nginx/sites-available/cineplex
```

Paste:

```nginx
server {
    listen 80;
    server_name yourdomain.com;

    location / {
        include proxy_params;
        proxy_pass http://unix:/var/www/cineplex/cineplex.sock;
    }

    location /static/ {
        alias /var/www/cineplex/static/;
    }
}
```

```bash
sudo ln -s /etc/nginx/sites-available/cineplex /etc/nginx/sites-enabled
sudo nginx -t
sudo systemctl restart nginx
```

#### Step 5 — HTTPS with Let's Encrypt (optional)

```bash
sudo apt install certbot python3-certbot-nginx -y
sudo certbot --nginx -d yourdomain.com
```

---

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/movies` | List movies (supports `?status`, `?language`, `?genre`, `?search`) |
| GET | `/api/movies/:id` | Single movie detail |
| GET | `/api/search?q=` | Instant search across movies & theatres |
| GET | `/api/shows/:id/seats` | Seat map for a show |
| POST | `/api/reserve` | Hold seats (5-minute ACID lock) |
| POST | `/api/book` | Confirm booking + payment |
| GET | `/api/bookings` | All bookings |
| GET | `/api/bookings/:ref/pdf` | Download ticket PDF |
| POST | `/api/cancel` | Cancel booking + refund |
| POST | `/api/admin/sql-console` | Execute read-only SQL (admin) |
| POST | `/api/admin/movies` | Add new movie (admin) |
| GET | `/api/admin/stats` | Dashboard metrics |
| POST | `/api/tmdb/sync` | Trigger TMDB poster sync |

---

## Screenshots

> Run the server and visit [http://127.0.0.1:5000](http://127.0.0.1:5000)

- **Homepage** — Hero movie carousel with filter chips by language and genre
- **Seat Map** — Curved auditorium layout with real-time availability
- **Checkout** — F&B concessions + payment simulation + bill breakdown
- **Digital M-Ticket** — QR code pass ready to print or download
- **Management Portal** — Live SQL console + admin tabs

---

## License

This project is built for educational and demonstration purposes.  
&copy; 2026 CINEPLEX — Sumit Kumar Panigrahi
