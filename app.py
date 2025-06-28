from flask import Flask, render_template, redirect, url_for, request, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from flask_mail import Mail, Message
from itsdangerous import URLSafeTimedSerializer
from datetime import datetime

app = Flask(__name__)

# Configuration
app.config['SECRET_KEY'] = '394802394'  
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Mail configuration - replace with your credentials
app.config['MAIL_SERVER'] = 'smtp.gmail.com' 
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'schedulink.verify@gmail.com'     
app.config['MAIL_PASSWORD'] = 'rxezfiemubgxyoki'
app.config['MAIL_DEFAULT_SENDER'] = 'schedulink.verify@gmail.com' 

# Initialize extensions
db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
mail = Mail(app)

# User model
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    confirmed = db.Column(db.Boolean, default=False)
    confirmed_on = db.Column(db.DateTime, nullable=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

# Token helpers
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

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

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

        if User.query.filter_by(username=username).first():
            flash('Username already exists.')
            return redirect(url_for('signup'))

        if User.query.filter_by(email=email).first():
            flash('Email already registered.')
            return redirect(url_for('signup'))

        new_user = User(username=username, email=email, confirmed=False)
        new_user.set_password(password)
        db.session.add(new_user)
        db.session.commit()

        send_confirmation_email(new_user.email)
        flash('Signup successful! A confirmation email has been sent. Please check your inbox.')
        return redirect(url_for('signup'))

    return render_template('signup.html')

@app.route('/confirm/<token>')
def confirm_email(token):
    email = confirm_token(token)
    if not email:
        return render_template('confirm_result.html', message="The confirmation link is invalid or has expired.")

    user = User.query.filter_by(email=email).first_or_404()
    if user.confirmed:
        message = "Account already confirmed. Please login."
    else:
        user.confirmed = True
        user.confirmed_on = datetime.utcnow()
        db.session.commit()
        message = "You have confirmed your account and may now login."

    return render_template('confirm_result.html', message=message)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username_or_email = request.form.get('username_or_email')
        password = request.form.get('password')

        user = User.query.filter(
            (User.username == username_or_email) | (User.email == username_or_email)
        ).first()

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

@app.route('/dashboard')
@login_required
def dashboard():
    return render_template('dashboard.html', user=current_user)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.')
    return redirect(url_for('index'))

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)