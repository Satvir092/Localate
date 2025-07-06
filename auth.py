from flask import Blueprint, render_template, redirect, url_for, request, flash, current_app
from werkzeug.security import generate_password_hash
from flask_login import login_user, logout_user, login_required, current_user
from models import User, get_user_by_username_or_email, get_user_by_id
from utils import generate_confirmation_token, confirm_token
from extensions import mail
from flask_mail import Message
from datetime import datetime

auth_bp = Blueprint('auth', __name__)

def send_confirmation_email(user_email):
    token = generate_confirmation_token(user_email)
    confirm_url = url_for('auth.confirm_email', token=token, _external=True)
    html = render_template('confirm.html', confirm_url=confirm_url)
    subject = "Please confirm your email"
    msg = Message(subject, recipients=[user_email], html=html)
    mail.send(msg)

@auth_bp.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')

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