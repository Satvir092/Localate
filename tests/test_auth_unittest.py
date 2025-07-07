import os
import unittest
from app import create_app
from dotenv import load_dotenv
import time

load_dotenv()

class TestAuth(unittest.TestCase):
    def setUp(self):
        supabase_url = os.getenv('SUPABASE_URL')
        supabase_key = os.getenv('SECRET_KEY')
        test_email = os.getenv('TEST_EMAIL')
        test_password = os.getenv('TEST_PASSWORD')
        test_username = os.getenv('TEST_USERNAME')

        if not supabase_url or not supabase_key:
            raise RuntimeError("SUPABASE_URL and SUPABASE_KEY must be set in environment")
        if not test_email or not test_password:
            raise RuntimeError("TEST_EMAIL and TEST_PASSWORD must be set in environment")

        os.environ['SUPABASE_URL'] = supabase_url
        os.environ['SUPABASE_KEY'] = supabase_key

        self.test_email = test_email
        self.username = test_username
        self.test_password = test_password

        self.app = create_app()
        self.app.config['TESTING'] = True
        self.app.config['WTF_CSRF_ENABLED'] = False
        self.client = self.app.test_client()

    def test_login_page_loads(self):
        response = self.client.get('/auth/login')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'<form', response.data, "Login page should contain a form")

    def test_login_success_real_user(self):
        login_data = {
            'username_or_email': self.test_email,
            'password': self.test_password,
        }
        response = self.client.post('/auth/login', data=login_data, follow_redirects=True)
        html = response.data.decode()

        self.assertEqual(response.status_code, 200)
        self.assertIn("<title>Dashboard</title>", html)
        self.assertNotIn("Invalid credentials, please try again.", html, "Should not show login error on success")

    def test_login_fail_wrong_user(self):
        login_data = {
            'username_or_email': 'nonexistent@example.com',
            'password': 'wrongpass'
        }
        response = self.client.post('/auth/login', data=login_data, follow_redirects=True)
        html = response.data.decode()

        self.assertEqual(response.status_code, 200)
        self.assertIn("Invalid credentials", html)
        self.assertNotIn("Welcome", html)

    def test_signup_and_cleanup(self):
        timestamp = int(time.time())
        test_email = f"testuser_{timestamp}@example.com"
        test_username = f"testuser_{timestamp}"
        test_password = "TestPass123!"

        signup_data = {
            'username': test_username,
            'email': test_email,
            'password': test_password
        }

        try:
            response = self.client.post('/auth/signup', data=signup_data, follow_redirects=True)
            self.assertEqual(response.status_code, 200)
            self.assertIn("confirmation email", response.data.decode().lower())

            user_check = self.app.supabase.table("users").select("*").eq("email", test_email).execute()
            self.assertTrue(user_check.data, "User was not created")

        finally:

            self.app.supabase.table("users").delete().eq("email", test_email).execute()

    def test_signup_same_email(self):

        timestamp = int(time.time())
        test_email = self.test_email
        test_username = self.test_email
        test_password = self.test_password
                  
        signup_data = {
            'username': test_username,
            'email': test_email,
            'password': test_password
        }

        response = self.client.post('/auth/signup', data=signup_data, follow_redirects=True)
        html = response.data.decode()

        self.assertEqual(response.status_code, 200)
        self.assertIn("Username already exists.", html)
        self.assertNotIn("Welcome", html)

    def test_signup_same_user(self):

        test_email = self.test_email
        test_password = self.test_password
                  
        signup_data = {
            'username': 'blahblah',
            'email': test_email,
            'password': test_password
        }

        response = self.client.post('/auth/signup', data=signup_data, follow_redirects=True)
        html = response.data.decode()

        self.assertEqual(response.status_code, 200)
        self.assertIn("Email already registered.", html)
        self.assertNotIn("Welcome", html)




if __name__ == '__main__':
    unittest.main()