from flask import Blueprint, render_template, redirect, url_for, request, flash, current_app
from werkzeug.security import generate_password_hash
from flask_login import login_user, logout_user, login_required
from models import get_user_by_username_or_email
from utils import generate_confirmation_token, confirm_token
from itsdangerous import URLSafeTimedSerializer
from extensions import mail
from flask_mail import Message
from datetime import datetime
import requests

auth_bp = Blueprint('auth', __name__)

def send_confirmation_email(user_email):
    token = generate_confirmation_token(user_email)
    confirm_url = url_for('auth.confirm_email', token=token, _external=True)
    html = render_template('confirm.html', confirm_url=confirm_url)
    subject = "Please confirm your email"
    msg = Message(subject, recipients=[user_email], html=html)
    mail.send(msg)

def generate_reset_token(email):
    serializer = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
    return serializer.dumps(email, salt='password-reset-salt')

def confirm_reset_token(token, expiration=3600):
    serializer = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
    try:
        email = serializer.loads(token, salt='password-reset-salt', max_age=expiration)
    except Exception:
        return False
    return email

def verify_recaptcha(token):
    secret_key = "6LeECIwrAAAAABgwlcfrq1rr3CFJKTmOs-qJRmhc"  
    url = "https://www.google.com/recaptcha/api/siteverify"
    data = {
        'secret': secret_key,
        'response': token
    }
    try:
        response = requests.post(url, data=data)
        result = response.json()
        print("reCAPTCHA result:", result)  
        return result.get("success", False) and result.get("score", 0) >= 0.5
    except Exception as e:
        print("reCAPTCHA error:", e)
        return False

@auth_bp.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':

        recaptcha_token = request.form.get('g-recaptcha-response', '')
        if not recaptcha_token or not verify_recaptcha(recaptcha_token):
            flash('reCAPTCHA verification failed. Please try again.', 'error')
            return redirect(url_for('auth.signup'))
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')

        if not (3 <= len(username) <= 30):
            flash('Username must be between 3 and 30 characters.')
            return redirect(url_for('auth.signup'))

        if len(email) > 100:
            flash('Email must be less than 100 characters.')
            return redirect(url_for('auth.signup'))

        if len(password) < 8 or len(password) > 30:
            flash('Password must be 8-30 characters long.')
            return redirect(url_for('auth.signup'))

        if get_user_by_username_or_email(username):
            flash('Username already exists.')
            return redirect(url_for('auth.signup'))

        if get_user_by_username_or_email(email):
            flash('Email already registered.')
            return redirect(url_for('auth.signup'))

        password_hash = generate_password_hash(password)
        supabase = current_app.supabase
        response = supabase.table('users').insert({
            "username": username,
            "email": email,
            "password_hash": password_hash,
            "confirmed": False,
            "confirmed_on": None
        }).execute()

        data = response.data
        if not data:
            flash('Error creating user. Please try again.')
            return redirect(url_for('auth.signup'))
        
        if not current_app.config.get('TESTING'):
            send_confirmation_email(email)

        flash('Signup successful! A confirmation email has been sent. Please check your inbox.')
        return redirect(url_for('auth.signup'))

    return render_template('signup.html')

@auth_bp.route('/confirm/<token>')
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
        supabase = current_app.supabase
        supabase.table('users').update({
            "confirmed": True,
            "confirmed_on": datetime.utcnow().isoformat()
        }).eq('email', email).execute()
        message = "You have confirmed your account and may now login."

    return render_template('confirm_result.html', message=message)

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        recaptcha_token = request.form.get('g-recaptcha-response', '')
        if not recaptcha_token or not verify_recaptcha(recaptcha_token):
            flash('reCAPTCHA verification failed. Please try again.', 'error')
            return redirect(url_for('auth.login'))
        username_or_email = request.form.get('username_or_email')
        password = request.form.get('password')

        user = get_user_by_username_or_email(username_or_email)

        if user and user.check_password(password):
            if not user.confirmed:
                flash('Please confirm your email before logging in.', 'warning')
                return redirect(url_for('auth.login'))

            login_user(user)
            return redirect(url_for('business.dashboard'))

        flash('Invalid credentials, please try again.')
        return redirect(url_for('auth.login'))

    return render_template('login.html')

@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.')
    return redirect(url_for('auth.login'))

@auth_bp.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        user = get_user_by_username_or_email(email)
        if user:
            token = generate_reset_token(email)
            reset_url = url_for('auth.reset_password', token=token, _external=True)
            subject = "Reset Your Password"
            msg = Message(
                subject=subject,
                sender=current_app.config['MAIL_DEFAULT_SENDER'],
                recipients=[email]
            )
            msg.html = f"""
            <div style="background-color:#1f1f1f; color:#b37bff; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; padding: 2em; border-radius: 10px; max-width: 600px; margin: auto;">
                <h2 style="color:#d4b3ff; margin-bottom: 0.5em;">Password Reset Request 🔐</h2>
                <p>Hi,</p>
                <p>We received a request to reset your password. Click the button below to set a new password:</p>
                <p style="text-align: center; margin: 2em 0;">
                    <a href="{reset_url}" style="background-color:#a78bfa; color:#1f1f1f; padding: 0.75em 1.5em; border-radius: 8px; text-decoration: none; font-weight: 600;">Reset Password</a>
                </p>
                <p>If you did not request a password reset, you can safely ignore this email.</p>
                <p style="margin-top: 1.5em;">Thanks,<br>Your Friendly Team</p>
            </div>
            """
            mail.send(msg)
            flash('Password reset instructions have been sent to your email.', 'info')
        else:
            flash('Email address not found.', 'error')
        return redirect(url_for('auth.forgot_password'))

    return render_template('forgot_password.html')

@auth_bp.route('/reset_password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    email = confirm_reset_token(token)
    if not email:
        flash('The reset link is invalid or has expired.', 'error')
        return redirect(url_for('auth.forgot_password'))

    if request.method == 'POST':
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')

        if not password or not confirm_password:
            flash('Please fill out all fields.', 'error')
            return redirect(url_for('auth.reset_password', token=token))

        if password != confirm_password:
            flash('Passwords do not match.', 'error')
            return redirect(url_for('auth.reset_password', token=token))

        if len(password) < 8 or len(password) > 30:
            flash('Password must be between 8 and 30 characters.', 'error')
            return redirect(url_for('auth.reset_password', token=token))

        password_hash = generate_password_hash(password)
        supabase = current_app.supabase
        response = supabase.table('users')\
            .update({'password_hash': password_hash})\
            .eq('email', email)\
            .execute()

        if not response.data:
            flash('An error occurred updating your password. Please try again.', 'error')
            return redirect(url_for('auth.reset_password', token=token))

        flash('Your password has been updated. Please log in.', 'success')
        return redirect(url_for('auth.login'))

    return render_template('reset_password.html', token=token)