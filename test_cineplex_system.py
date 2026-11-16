import unittest
import json
import sqlite3
import base64
from app import app, get_db

class CineplexSystemTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        app.config['TESTING'] = True
        cls.client = app.test_client()

    def test_01_sqlite_integrity(self):
        """Verify SQLite database integrity and foreign key constraints."""
        conn = get_db()
        c = conn.cursor()
        c.execute("PRAGMA integrity_check;")
        res = c.fetchone()[0]
        self.assertEqual(res, "ok", f"Integrity check failed: {res}")

        c.execute("PRAGMA foreign_key_check;")
        fk_violations = c.fetchall()
        self.assertEqual(len(fk_violations), 0, f"Foreign key violations found: {fk_violations}")
        conn.close()

    def test_02_homepage_loads_and_branding(self):
        """Verify homepage renders with CINEPLEX branding and no old developer references."""
        res = self.client.get('/')
        self.assertEqual(res.status_code, 200)
        html = res.data.decode('utf-8')
        self.assertIn("CINEPLEX", html)
        self.assertIn("Your Movies. Your Moments.", html)
        self.assertIn("Sumit Kumar Panigrahi", html)
        self.assertNotIn("Soumya", html)
        self.assertNotIn("soumya@example.com", html)

    def test_03_movie_catalogue_and_filters(self):
        """Verify expanded movie catalogue (20+ titles) and filter routes."""
        res = self.client.get('/api/movies?status=now_showing')
        self.assertEqual(res.status_code, 200)
        data = json.loads(res.data)
        self.assertTrue(data['success'])
        self.assertGreaterEqual(len(data['movies']), 10)

        # Test upcoming filter
        res_up = self.client.get('/api/movies?status=upcoming')
        data_up = json.loads(res_up.data)
        self.assertTrue(data_up['success'])
        self.assertGreaterEqual(len(data_up['movies']), 5)

        # Test search
        res_search = self.client.get('/api/movies?search=Ramayan')
        data_search = json.loads(res_search.data)
        self.assertTrue(data_search['success'])
        self.assertTrue(any("Ramayan" in m['title'] for m in data_search['movies']))

        # Test live search endpoint
        res_live = self.client.get('/api/search?q=Pushpa')
        self.assertEqual(res_live.status_code, 200)
        data_live = json.loads(res_live.data)
        self.assertTrue(data_live['success'])
        self.assertTrue(any("Pushpa" in m['title'] for m in data_live['movies']))

        # Test language filter
        res_lang = self.client.get('/api/movies?language=Odia')
        data_lang = json.loads(res_lang.data)
        self.assertTrue(data_lang['success'])
        self.assertTrue(any("Odia" in m['language'] for m in data_lang['movies']))

    def test_04_theaters_and_showtimes(self):
        """Verify showtimes endpoint with Bhubaneswar default."""
        res = self.client.get('/api/movies/1/shows?city=Bhubaneswar')
        self.assertEqual(res.status_code, 200)
        data = json.loads(res.data)
        self.assertTrue(data['success'])
        self.assertGreater(len(data['theaters']), 0)
        self.assertTrue(any(t['city'] == 'Bhubaneswar' for t in data['theaters']))

    def test_05_auditorium_seats_and_tiers(self):
        """Verify seat map returns Recliner, Prime, Classic tiers and seats."""
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT id FROM shows LIMIT 1")
        show_id = c.fetchone()[0]
        conn.close()

        res = self.client.get(f'/api/shows/{show_id}/seats')
        self.assertEqual(res.status_code, 200)
        data = json.loads(res.data)['data']
        self.assertEqual(len(data['seats']), 92) # 20 recliner + 36 prime + 36 classic
        self.assertIn("RECLINER", data['tiers'])
        self.assertIn("PRIME", data['tiers'])
        self.assertIn("CLASSIC", data['tiers'])

    def test_06_booking_workflow_and_transactions(self):
        """Verify complete atomic booking workflow communication and 3NF persistence."""
        conn = get_db()
        c = conn.cursor()
        # Find a show with available seats
        c.execute("""
            SELECT s.id FROM shows s
            JOIN show_seats ss ON s.id = ss.show_id
            WHERE ss.seat_label = 'F1' AND ss.status = 'AVAILABLE'
            LIMIT 1
        """)
        show_id = c.fetchone()[0]
        conn.close()

        # Step A: Reserve
        res_res = self.client.post(f'/api/shows/{show_id}/reserve', json={
            "seat_labels": ["F1", "F2"]
        })
        self.assertEqual(res_res.status_code, 200)
        token = json.loads(res_res.data)['reservation_token']

        # Step B: Duplicate reserve attempt by another user should fail with 409
        res_conflict = self.client.post(f'/api/shows/{show_id}/reserve', json={
            "seat_labels": ["F1"],
            "reservation_token": "different-token-123"
        })
        self.assertEqual(res_conflict.status_code, 409)

        # Step C: Book with simulated payment
        book_payload = {
            "seat_labels": ["F1", "F2"],
            "customer_name": "Sumit Kumar Panigrahi",
            "customer_email": "sumit@example.com",
            "customer_phone": "8984378785",
            "payment_method": "UPI",
            "reservation_token": token,
            "snacks": [{"id": 1, "name": "Regular Popcorn", "quantity": 1, "price": 180.0}]
        }
        res_book = self.client.post(f'/api/shows/{show_id}/book', json=book_payload)
        self.assertEqual(res_book.status_code, 200)
        book_data = json.loads(res_book.data)
        booking_ref = book_data['booking_ref']
        self.assertTrue(booking_ref.startswith("CPX-"))

        # Verify 3NF relational rows exist
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT id FROM bookings WHERE booking_ref = ?", (booking_ref,))
        b_id = c.fetchone()[0]

        c.execute("SELECT COUNT(*) FROM booking_seats WHERE booking_id = ?", (b_id,))
        self.assertEqual(c.fetchone()[0], 2)

        c.execute("SELECT COUNT(*) FROM booking_snacks WHERE booking_id = ?", (b_id,))
        self.assertEqual(c.fetchone()[0], 1)

        c.execute("SELECT payment_status FROM payments WHERE booking_id = ?", (b_id,))
        self.assertEqual(c.fetchone()[0], "SUCCESS")

        # Step D: Duplicate booking of same seats must fail with 409
        res_dup_book = self.client.post(f'/api/shows/{show_id}/book', json=book_payload)
        self.assertEqual(res_dup_book.status_code, 409)

        # Step E: Fetch booking detail & PDF ticket
        res_detail = self.client.get(f'/api/bookings/{booking_ref}')
        self.assertEqual(res_detail.status_code, 200)
        detail_data = json.loads(res_detail.data)['booking']
        self.assertEqual(len(detail_data['seats_details']), 2)

        res_pdf = self.client.get(f'/api/bookings/{booking_ref}/pdf')
        self.assertEqual(res_pdf.status_code, 200)
        self.assertEqual(res_pdf.mimetype, 'application/pdf')
        self.assertTrue(res_pdf.data.startswith(b'%PDF'))

        # Step F: Cancel booking & verify seat release
        res_cancel = self.client.post(f'/api/bookings/{booking_ref}/cancel', json={"reason": "Evaluator test"})
        self.assertEqual(res_cancel.status_code, 200)
        cancel_data = json.loads(res_cancel.data)
        self.assertTrue(cancel_data['cancellation_ref'].startswith("CAN-"))

        # Verify seats returned to AVAILABLE in SQLite
        c.execute("SELECT status FROM show_seats WHERE show_id = ? AND seat_label IN ('F1', 'F2')", (show_id,))
        statuses = [r[0] for r in c.fetchall()]
        self.assertTrue(all(s == 'AVAILABLE' for s in statuses))

        # Verify payments table marked as REFUNDED
        c.execute("SELECT payment_status FROM payments WHERE booking_id = ?", (b_id,))
        self.assertEqual(c.fetchone()[0], "REFUNDED")

        # Step G: Double cancellation must fail with 400
        res_double_cancel = self.client.post(f'/api/bookings/{booking_ref}/cancel', json={})
        self.assertEqual(res_double_cancel.status_code, 400)
        conn.close()

    def test_07_authentication_endpoints(self):
        """Verify registration, login, and profile sync."""
        # Test Login
        pwd_hash = base64.b64encode(b"password123").decode()
        res_login = self.client.post('/api/auth/login', json={
            "email": "sumit@example.com",
            "password_hash": pwd_hash
        })
        self.assertEqual(res_login.status_code, 200)
        user_info = json.loads(res_login.data)['user']
        self.assertEqual(user_info['name'], "Sumit Kumar Panigrahi")

        # Test Admin Login
        adm_pwd_hash = base64.b64encode(b"admin123").decode()
        res_adm_login = self.client.post('/api/auth/login', json={
            "email": "admin@cineplex.com",
            "password_hash": adm_pwd_hash
        })
        self.assertEqual(res_adm_login.status_code, 200)
        adm_user = json.loads(res_adm_login.data)['user']
        self.assertTrue(adm_user['is_admin'])

    def test_08_admin_metrics_and_viva_sql_console(self):
        """Verify admin metrics and evaluator live DBMS SQL execution."""
        res_stats = self.client.get('/api/admin/stats')
        self.assertEqual(res_stats.status_code, 200)
        metrics = json.loads(res_stats.data)['metrics']
        self.assertGreater(metrics['total_movies'], 20)
        self.assertGreater(metrics['total_shows'], 1000)

        # Test 7 Pre-curated DBMS demonstration queries
        res_demos = self.client.get('/api/dbms/demonstrations')
        self.assertEqual(res_demos.status_code, 200)
        demos = json.loads(res_demos.data)['demonstrations']
        self.assertEqual(len(demos), 7)

        # Execute each of the 7 queries live via SQL console
        for d in demos:
            res_exec = self.client.post('/api/admin/sql-console', json={"query": d['sql']})
            self.assertEqual(res_exec.status_code, 200, f"Demo query '{d['title']}' failed: {res_exec.data}")
            result = json.loads(res_exec.data)
            self.assertTrue(result['success'])
            self.assertIn("columns", result)
            self.assertIn("rows", result)

if __name__ == '__main__':
    unittest.main()

