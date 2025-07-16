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

        self.client.post('/auth/login', data={
            'username_or_email': self.test_email,
            'password': self.test_password
        }, follow_redirects=True)

    def get_logged_in_user_id(self):
        """Get user ID from the session by checking profile"""
        supabase = self.app.supabase
        result = supabase.table('users').select('id').eq('email', self.test_email).execute()
        return result.data[0]['id']

    def test_index_route(self):
        response = self.client.get('/business/')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Localate', response.data)  

    def test_dashboard_route_requires_login(self):
        response = self.client.get('/business/dashboard', follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Dashboard', response.data)

    def test_create_business_get(self):
        response = self.client.get('/business/create_business', follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Create Your Business', response.data)

    def test_create_business_post_minimal_valid(self):
        form_data = {
            'name': 'Testing3789078690',
            'category': 'Testing',
            'city': 'Testville',
            'state': 'TS',
            'description': 'Test business description',
            'start_time': '09:00',
            'end_time': '17:00',
            'timezone': 'America/Los_Angeles',
            'interval': '30',
            'weekdays': ['Monday', 'Wednesday']
        }

        response = self.client.post('/business/create_business', data=form_data, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Dashboard', response.data)

        supabase = self.app.supabase
        supabase.table('businesses').delete().eq('name', 'Testing3789078690').execute()

    def test_create_business_error_city(self):
        form_data = {
            'name': 'Testing3789078690s',
            'category': 'Testing',
            'city': '',
            'state': 'TS',
            'description': 'Test business description',
            'start_time': '09:00',
            'timezone': 'America/Los_Angeles',
            'end_time': '17:00',
            'interval': '30',
            'weekdays': ['Monday', 'Wednesday']
        }

        response = self.client.post('/business/create_business', data=form_data, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Please select a city.', response.data)

    def test_create_business_error_name(self):
        form_data = {
            'name': '',
            'category': 'Testing',
            'city': '',
            'state': 'TS',
            'description': 'Test business description',
            'start_time': '09:00',
            'timezone': 'America/Los_Angeles',
            'end_time': '17:00',
            'interval': '30',
            'weekdays': ['Monday', 'Wednesday']
        }

        response = self.client.post('/business/create_business', data=form_data, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Business name is required', response.data)

    def test_create_business_error_open_days(self):
        form_data = {
            'name': 'asdf',
            'category': 'Testing',
            'city': 'asdf',
            'state': 'TS',
            'description': 'Test business description',
            'start_time': '09:00',
            'timezone': 'America/Los_Angeles',
            'end_time': '17:00',
            'interval': '30',
            'weekdays': []
        }

        response = self.client.post('/business/create_business', data=form_data, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Please select at least one open day', response.data)

    def test_create_business_error_state(self):
        form_data = {
            'name': 'asdf',
            'category': 'Testing',
            'city': 'asdf',
            'state': '',
            'description': 'Test business description',
            'start_time': '09:00',
            'timezone': 'America/Los_Angeles',
            'end_time': '17:00',
            'interval': '30',
            'weekdays': ['Monday']
        }

        response = self.client.post('/business/create_business', data=form_data, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Please select a state', response.data)

    def test_create_business_error_opening_time(self):
        
        form_data = {
            'name': 'asdf',
            'category': 'Testing',
            'city': 'asdf',
            'state': 'CA',
            'description': 'Test business description',
            'start_time': '18:00',
            'timezone': 'America/Los_Angeles',
            'end_time': '17:00',
            'interval': '30',
            'weekdays': ['Monday']
        }

        response = self.client.post('/business/create_business', data=form_data, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Opening time must be earlier than closing time', response.data)


    def test_view_existing_business(self):

        business_id = 5

        response = self.client.get(f'/business/view_business/{business_id}')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Threading yuba', response.data)

    def test_editing_exisiting_business(self):

        form_data = {
            'name': 'TEST: Original Business',
            'category': 'Salon',
            'city': 'Starter City',
            'state': 'CA',
            'description': 'A business to be edited',
            'start_time': '09:00',
            'timezone': 'America/Los_Angeles',
            'end_time': '17:00',
            'interval': '30',
            'weekdays': ['Monday', 'Tuesday']
        }

        create_response = self.client.post('/business/create_business', data=form_data, follow_redirects=True)
        self.assertEqual(create_response.status_code, 200)
        self.assertIn(b'Dashboard', create_response.data)

        supabase = self.app.supabase
        businesses = supabase.table('businesses').select('*').eq('name', 'TEST: Original Business').execute()
        self.assertTrue(businesses.data)
        business = businesses.data[0]
        business_id = business['id']

        updated_data = {
            'name': 'TEST: Updated Business Name',
            'category': 'Barbershop',
            'city': 'Updated City',
            'state': 'CA',
            'description': 'Updated description',
            'start_time': '10:00',
            'end_time': '18:00',
            'timezone': 'America/Los_Angeles',
            'interval': '60',
            'weekdays': ['Wednesday', 'Thursday']
        }

        edit_response = self.client.post(f'/business/edit_business/{business_id}', data=updated_data, follow_redirects=True)
        self.assertEqual(edit_response.status_code, 200)
        self.assertIn(b'Dashboard', edit_response.data)

        if business['name'].startswith('TEST:'):
            supabase.table('businesses').delete().eq('id', business_id).execute()

    def test_confirm_appointment_success(self):
        """POST /confirm_appointment confirms the appointment if user owns the business"""

        supabase = self.app.supabase

        # First, create a test business
        business_data = {
            'name': 'TEST: Confirm Appt Biz',
            'category': 'Testing',
            'city': 'ConfirmCity',
            'state': 'CA',
            'description': 'To test confirming appt',
            'opening_time': '09:00',
            'closing_time': '17:00',
            'timezone': 'America/Los_Angeles',
            'interval': 30,
            'open_days': ['Monday', 'Tuesday'],
            'user_id': self.get_logged_in_user_id()  # you’ll define this helper below
        }

        business = supabase.table('businesses').insert(business_data).execute().data[0]
        business_id = business['id']

        # Then, create an appointment under that business
        appointment_data = {
            'user_id': business_data['user_id'],
            'business_id': business_id,
            'date': '2099-12-31',
            'time': '13:00:00',
            'email': self.test_email,
            'name': 'Test User',
            'phone': '1234567890',
            'age': 30,
            'profile_image_url': None,
            'confirmed': False
        }

        appt = supabase.table('appointments').insert(appointment_data).execute().data[0]
        appt_id = appt['id']

        # Confirm the appointment
        response = self.client.post('/business/confirm_appointment', data={
            'id': appt_id
        })

        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Appointment confirmed', response.data)

        # Cleanup
        supabase.table('appointments').delete().eq('id', appt_id).execute()
        supabase.table('businesses').delete().eq('id', business_id).execute()
