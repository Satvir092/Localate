import os
import unittest
from localate import create_app
from dotenv import load_dotenv
from datetime import datetime, timedelta

load_dotenv()

class TestSearch(unittest.TestCase):
    def setUp(self):
        supabase_url = os.getenv('SUPABASE_URL')
        supabase_key = os.getenv('SECRET_KEY')
        test_email = os.getenv('TEST_EMAIL')
        test_password = os.getenv('TEST_PASSWORD')

        if not supabase_url or not supabase_key:
            raise RuntimeError("SUPABASE_URL and SUPABASE_KEY must be set in environment")
        if not test_email or not test_password:
            raise RuntimeError("TEST_EMAIL and TEST_PASSWORD must be set in environment")

        os.environ['SUPABASE_URL'] = supabase_url
        os.environ['SUPABASE_KEY'] = supabase_key

        self.test_email = test_email
        self.test_password = test_password

        self.app = create_app()
        self.app.config['TESTING'] = True
        self.app.config['WTF_CSRF_ENABLED'] = False
        self.client = self.app.test_client()

        self.client.post('/auth/login', data={
            'username_or_email': self.test_email,
            'password': self.test_password
        }, follow_redirects=True)

    def test_search_no_results(self):
        """GET /search/ with a query that yields no results shows 'No businesses found.'"""
        response = self.client.get('/search/?q=nonexistentbusiness')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'No businesses found.', response.data)

    def test_search_with_query(self):
        """GET /search/ with a query should return matching businesses"""
        response = self.client.get('/search/', query_string={'q': 'yuba'})
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'yuba', response.data.lower())

    def test_customer_view_requires_login(self):
        """GET /search/customer_view/<id> redirects if not logged in"""
        self.client.get('/auth/logout', follow_redirects=True)
        response = self.client.get('/search/customer_view/1', follow_redirects=False)
        self.assertIn(response.status_code, (302, 301))  

    def test_customer_view_logged_in(self):
        """GET /search/customer_view/<id> shows business details when logged in"""
        response = self.client.get('/search/customer_view/5')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Business', response.data)  

    def test_book_appointment_success(self):
        """POST /book_appointment should book a new appointment if slot is available"""
        future_date = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
        test_time = "10:00"  

        response = self.client.post('/search/book_appointment', data={
            'business_id': 5,
            'selected_date': future_date,
            'selected_time': test_time
        }, follow_redirects=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Appointment booked successfully', response.data)

    def test_book_appointment_slot_taken(self):
        """Booking the same slot twice should show 'already booked' error"""

        future_date = (datetime.now() + timedelta(days=2)).strftime("%Y-%m-%d")
        test_time = "11:00"

        self.client.post('/search/book_appointment', data={
            'business_id': 5,
            'selected_date': future_date,
            'selected_time': test_time
        }, follow_redirects=True)

        response = self.client.post('/search/book_appointment', data={
            'business_id': 5,
            'selected_date': future_date,
            'selected_time': test_time
        }, follow_redirects=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn(b'This time slot is already booked', response.data)

    def test_autocomplete_results(self):
        """GET /autocomplete?q=partial should return matching business names as JSON"""
        response = self.client.get('/search/autocomplete', query_string={'q': 'yu'})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.is_json)
        data = response.get_json()
        self.assertIsInstance(data, list)
        self.assertTrue(any('yuba' in name.lower() for name in data))



if __name__ == '__main__':
    unittest.main()