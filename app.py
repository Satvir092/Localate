from flask import Flask, render_template, redirect, url_for, request, flash
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from flask_mail import Mail, Message
from itsdangerous import URLSafeTimedSerializer
from datetime import datetime
from postgrest.exceptions import APIError
import os
from dotenv import load_dotenv
from supabase import create_client, Client

# Load environment variables from .env
load_dotenv()

app = Flask(__name__)

# Flask app config
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')

# Mail configuration
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = os.getenv('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.getenv('MAIL_PASSWORD')
app.config['MAIL_DEFAULT_SENDER'] = os.getenv('MAIL_DEFAULT_SENDER')

# Initialize Flask extensions
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
mail = Mail(app)

# Initialize Supabase client
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_SERVICE_ROLE_KEY = os.getenv('SUPABASE_SERVICE_ROLE_KEY')  
supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)


# User class for Flask-Login
class User(UserMixin):
    def __init__(self, id, username, email, password_hash, confirmed, confirmed_on):
        self.id = id
        self.username = username
        self.email = email
        self.password_hash = password_hash
        self.confirmed = confirmed
        self.confirmed_on = confirmed_on

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


# Helper functions for user data via Supabase


def get_user_by_id(user_id):
    try:
        response = supabase.table('users').select('*').eq('id', user_id).execute()
    except APIError:
        # The query returned 0 or multiple rows or other API error
        return None

    data = response.data
    if isinstance(data, list) and len(data) == 1:
        return User(**data[0])
    return None

def get_user_by_username_or_email(username_or_email):
    response = supabase.table('users').select('*').or_(
        f"username.eq.{username_or_email},email.eq.{username_or_email}"
    ).limit(1).execute()
    data = response.data
    if data:
        return User(**data[0])
    return None


def create_user(username, email, password_hash):
    response = supabase.table('users').insert({
        "username": username,
        "email": email,
        "password_hash": password_hash,
        "confirmed": False,
        "confirmed_on": None
    }).execute()
    data = response.data
    if data:
        return User(**data[0])
    return None


def confirm_user_email(email):
    response = supabase.table('users').update({
        "confirmed": True,
        "confirmed_on": datetime.utcnow().isoformat()
    }).eq('email', email).execute()
    data = response.data
    if data:
        return User(**data[0])
    return None


# Flask-Login user loader
@login_manager.user_loader
def load_user(user_id):
    return get_user_by_id(int(user_id))


# Token helpers for email confirmation
def generate_confirmation_token(email):
    serializer = URLSafeTimedSerializer(app.config['SECRET_KEY'])
    return serializer.dumps(email, salt='email-confirm-salt')


def confirm_token(token, expiration=3600):
    serializer = URLSafeTimedSerializer(app.config['SECRET_KEY'])
    try:
        email = serializer.loads(token, salt='email-confirm-salt', max_age=expiration)
    except Exception:
        return False
    return email


# Send confirmation email
def send_confirmation_email(user_email):
    token = generate_confirmation_token(user_email)
    confirm_url = url_for('confirm_email', token=token, _external=True)
    html = render_template('confirm.html', confirm_url=confirm_url)
    subject = "Please confirm your email"
    msg = Message(subject, recipients=[user_email], html=html)
    mail.send(msg)


# Routes

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/about')
def about():
    return render_template('about.html')


@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')

        # Check if user exists by username or email
        if get_user_by_username_or_email(username):
            flash('Username already exists.')
            return redirect(url_for('signup'))

        if get_user_by_username_or_email(email):
            flash('Email already registered.')
            return redirect(url_for('signup'))

        password_hash = generate_password_hash(password)
        new_user = create_user(username, email, password_hash)

        if new_user is None:
            flash('Error creating user. Please try again.')
            return redirect(url_for('signup'))

        send_confirmation_email(new_user.email)
        flash('Signup successful! A confirmation email has been sent. Please check your inbox.')
        return redirect(url_for('signup'))

    return render_template('signup.html')


@app.route('/confirm/<token>')
def confirm_email(token):
    email = confirm_token(token)
    if not email:
        return render_template('confirm_result.html', message="The confirmation link is invalid or has expired.")

    user = get_user_by_username_or_email(email)
    if not user:
        return render_template('confirm_result.html', message="User not found.")

    if user.confirmed:
        message = "Account already confirmed. Please login."
    else:
        confirm_user_email(email)
        message = "You have confirmed your account and may now login."

    return render_template('confirm_result.html', message=message)


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username_or_email = request.form.get('username_or_email')
        password = request.form.get('password')

        user = get_user_by_username_or_email(username_or_email)

        if user and user.check_password(password):
            if not user.confirmed:
                flash('Please confirm your email before logging in.', 'warning')
                return redirect(url_for('login'))

            login_user(user)
            flash('Logged in successfully.')
            return redirect(url_for('dashboard'))

        flash('Invalid credentials, please try again.')
        return redirect(url_for('login'))

    return render_template('login.html')


@app.route('/dashboard', methods=['GET', 'POST'])
@login_required
def dashboard():

    if request.method == 'POST':

        pass


    return render_template('dashboard.html', user=current_user)

@app.route('/create_business', methods=['GET', 'POST'])
@login_required
def create_business():
    if request.method == 'POST':
        name = request.form.get('name')
        category = request.form.get('category')
        city = request.form.get('city')
        description = request.form.get('description')
        opening_time = request.form.get('start_time')
        closing_time = request.form.get('end_time')
        interval = request.form.get('interval')
        days_list = request.form.getlist('weekdays')

        if not name:
            flash("Business name is required.", "error")
            return redirect(url_for('create_business'))
        
        if opening_time and closing_time and opening_time >= closing_time:
            flash("Opening time must be earlier than closing time.", "error")
            return redirect(url_for('create_business'))

        response = supabase.table('businesses').insert({
            "user_id": str(current_user.id),
            "name": name,
            "category": category,
            "city": city,
            "description": description,
            "open_days" : days_list,
            "opening_time": opening_time,
            "interval": interval,
            "closing_time": closing_time
        }).execute()

        if response.data:
            flash("Business created successfully!", "success")
            return redirect(url_for('dashboard'))
        else:
            flash("Failed to create business. Please try again.", "error")
            return redirect(url_for('create_business'))

    return render_template('create_business.html')
        

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.')
    return redirect(url_for('index'))


if __name__ == '__main__':
    app.run(debug=True)