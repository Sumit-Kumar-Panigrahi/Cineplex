# 🎬 CINEPLEX — Evaluator Demonstration Guide (5–10 Minutes)
**Project Name:** CINEPLEX — Movie Ticket Booking System  
**Tagline:** *Your Movies. Your Moments.*  
**Developer:** Sumit Kumar Panigrahi  
**Subject:** Database Management Systems (DBMS)  
**Architecture:** Python Flask, SQLite 3 (3NF Relational Schema), HTML5, CSS3, ES6 JavaScript  

---

## 🚀 1. Application Startup Commands

### Option A: 1-Click Startup (Recommended)
Double-click `run.bat` or run in terminal:
```powershell
.\run.bat
```
This automatically launches the Flask application and opens your browser at:
👉 **`http://127.0.0.1:5000`**

### Option B: Manual Command Line Startup
```powershell
# Ensure working directory is the project folder
cd C:\Users\sumit\OneDrive\Desktop\TRS

# Run the Flask backend server
python.bat app.py
# or
& "C:\Users\sumit\AppData\Local\Programs\Python\Python314\python.exe" app.py
```

---

## 🔑 2. Demo Credentials

| Role | Name | Email | Password | Phone |
| :--- | :--- | :--- | :--- | :--- |
| **Demo Customer** | Sumit Kumar Panigrahi | `sumit@example.com` | `password123` | `8984378785` |
| **Cineplex Administrator** | Cineplex Admin | `admin@cineplex.com` | `admin123` | `9999999999` |

> 💡 **Tip:** On the Sign In page, use the **`⚡ Demo (Sumit)`** and **`🛡️ Admin Demo`** quick buttons to auto-populate credentials in 1 click!

---

## 📋 3. 5–10 Minute Demonstration Script for Evaluators

### Step 1: Branding & Movie Catalogue Discovery (1 Minute)
1. Open `http://127.0.0.1:5000`.
2. Notice the **CINEPLEX** identity (*"Your Movies. Your Moments."*).
3. Point out the city selector defaulting to **Bhubaneswar** (with options for Cuttack, Puri, Rourkela, Mumbai, etc.).
4. Showcase the catalogue with **24 titles**:
   - Filter by **Status**: `Now Showing`, `Upcoming`, `Popular & Classics`.
   - Filter by **Language**: `Hindi`, `Odia (ଓଡ଼ିଆ)`, `English`, `Telugu`, `Tamil`.
   - Filter by **Genre**: `Action`, `Sci-Fi`, `Drama`, `Thriller`, etc.
   - Live Search: Type *"Ramayan"*, *"Jadi"*, or *"Interstellar"*.

### Step 2: Showtimes & Date Selection (1 Minute)
1. Click **"Book Tickets"** on a movie card (e.g., *Ramayan*, *Pushpa 2*, or *Jadi*).
2. The Movie Details modal opens showing synopsis, runtime, certification, and official trailer option.
3. Switch between **Show Dates** on the horizontal date picker.
4. Review available multiplexes in Bhubaneswar:
   - *Cinepolis: Esplanade One Mall*
   - *INOX: BMC Bhawani Mall*
   - *Maharaja Picture Palace*
5. Click any showtime pill (e.g. `10:00 AM`, `04:30 PM`, or `08:15 PM`).

### Step 3: Curved Auditorium Seat Map & Hold Timer (1.5 Minutes)
1. The curved amphitheater seat map opens with 3 normalized tiers:
   - **Recliner (Luxe Comfort):** Rows A, B (₹420)
   - **Prime (Optimal View):** Rows C, D, E (₹280)
   - **Classic (Standard):** Rows F, G, H (₹180)
2. Tap 2 seats (e.g., `C5`, `C6`). Notice live subtotal recalculation and seat pill badges.
3. Click **"Pay & Checkout"**.
4. Point out the **5-Minute Hold Timer** (`5:00 min`) preventing race conditions and double bookings.

### Step 4: Snacks, Simulated Payment & Digital Pass (1.5 Minutes)
1. Add concession items (e.g., *Cineplex Deluxe Combo* or *Caramel Popcorn*).
2. Review the transparent billing breakdown:
   - Ticket Price Subtotal
   - Food & Beverages
   - Integrated Convenience Fee (5%)
   - GST (18% on convenience fee)
   - Total Amount Payable
3. Select payment mode (**UPI** / **Card**).
4. Click **"Pay & Confirm"**.
5. The digital **CINEPLEX M-TICKET PASS** generates instantly with:
   - Unique reference: `CPX-YYMMDD-XXXXXX`
   - Verified offline QR verification code
   - Seat numbers, cinema auditorium, date/time, total paid
   - Options to **"Print Pass"** or **"Download Pass"** (`.txt` formatted receipt).

### Step 5: User History & Real-Time Cancellation (1 Minute)
1. Click **"My Bookings"** in the top navigation.
2. View your newly created booking alongside past history.
3. Click **"Cancel"** on a booking:
   - Review transparent policy: ₹30 fee per seat deducted.
   - Confirm cancellation.
4. View the **Cancellation Summary** showing net refund credited and **immediate seat release** back to the auditorium inventory.

### Step 6: Admin Portal & Evaluator DBMS Viva Console (3 Minutes)
1. Click **"🛡️ Admin & DBMS"** in the top header.
2. Review the real-time operational dashboard:
   - **Gross Net Revenue**
   - **Tickets Sold**
   - **Active Theaters** (10)
   - **Total Shows** (2,100)
   - **Occupancy Rate**
3. Navigate to the **"⚡ Evaluator Live SQL Console (Viva)"** tab:
   - Click each pre-curated query button to execute live against the database:
     1. **Multi-Table Relational INNER JOIN (3NF Compliance):** Joins `bookings`, `booking_seats`, `shows`, `movies`, `theaters`, `payments`.
     2. **GROUP BY and HAVING Clause:** Aggregates ticket sales and gross revenue per theater.
     3. **Correlated Subquery:** Queries high-value bookings exceeding the platform average ticket value.
     4. **Aggregate Statistical Functions:** `COUNT()`, `SUM()`, `AVG()`, `MIN()`, `MAX()` across seating tiers.
     5. **LEFT OUTER JOIN:** Identifies unscheduled or empty show inventories.
     6. **Cancellation & Refund Audit:** Tracks retained fees vs refunded amounts.
     7. **Schema Catalog Verification:** Inspects foreign keys and check constraints.

---

## 🗄️ 4. Key DBMS Viva Concepts Demonstrated

### 1. 3NF Relational Normalization
The database schema separates entities to eliminate insertion, update, and deletion anomalies:
- `movies` (Movie catalogue & metadata)
- `theaters` (Multiplexes and locations)
- `screens` (Auditoriums with FK to `theaters`)
- `shows` (Schedule with composite FKs to `movies`, `theaters`, `screens`)
- `show_seats` (Granular seat state per show)
- `bookings` (Customer order header)
- `booking_seats` (3NF Normalized table linking each seat to booking & show)
- `booking_snacks` (3NF Normalized concessions breakdown)
- `payments` (3NF Normalized payment ledger with transaction refs)
- `cancellations` (Audit log of refunds and seat liberations)
- `users` (User accounts with hashed passwords and admin roles)

### 2. Constraints Demonstrated
- **PRIMARY KEY:** Unique identification on all tables.
- **FOREIGN KEY:** `ON DELETE CASCADE` and `ON DELETE SET NULL` preserving referential integrity.
- **NOT NULL:** Enforced on required attributes (titles, emails, prices).
- **UNIQUE:** Enforced on `bookings.booking_ref`, `payments.payment_ref`, `users.email`, and composite `show_seats(show_id, seat_label)`.
- **CHECK Constraints:** `tier IN ('RECLINER', 'PRIME', 'CLASSIC')`, `status IN ('AVAILABLE', 'RESERVED', 'BOOKED')`, `price >= 0`.

### 3. Concurrency & ACID Transactions
- Seat reservation hold expires automatically after 300 seconds.
- `api_book` uses an **atomic immediate SQLite transaction** (`BEGIN IMMEDIATE`) to prevent double-booking race conditions when two customers tap the same seat simultaneously.

---

## 🛠️ 5. Important SQL Queries for Viva Reference

```sql
-- 1. Multi-Table Relational Audit Trail
SELECT b.booking_ref, b.customer_name, m.title AS movie, t.name AS theater,
       bs.seat_label, bs.tier, bs.price, p.payment_method, p.payment_status
FROM bookings b
INNER JOIN booking_seats bs ON b.id = bs.booking_id
INNER JOIN shows s ON b.show_id = s.id
INNER JOIN movies m ON s.movie_id = m.id
INNER JOIN theaters t ON s.theater_id = t.id
INNER JOIN payments p ON b.id = p.booking_id
ORDER BY b.created_at DESC;

-- 2. Revenue & Ticket Distribution (GROUP BY + HAVING)
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

-- 3. High-Value Customer Subquery
SELECT b.booking_ref, b.customer_name, b.customer_email, b.total_amount
FROM bookings b
WHERE b.status = 'CONFIRMED'
  AND b.total_amount > (
      SELECT AVG(total_amount) FROM bookings WHERE status = 'CONFIRMED'
  )
ORDER BY b.total_amount DESC;
```

