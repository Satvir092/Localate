import os
from dotenv import load_dotenv
from flask import Flask
from supabase import create_client
from extensions import login_manager, mail
from auth import auth_bp
from business import business_bp
from search import search_bp
from flask import render_template
from users import user_bp

load_dotenv()

def create_app():
    app = Flask(__name__)
    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')

    app.config['MAIL_SERVER'] = 'smtp.gmail.com'
    app.config['MAIL_PORT'] = 587
    app.config['MAIL_USE_TLS'] = True
    app.config['MAIL_USERNAME'] = os.getenv('MAIL_USERNAME')
    app.config['MAIL_PASSWORD'] = os.getenv('MAIL_PASSWORD')
    app.config['MAIL_DEFAULT_SENDER'] = os.getenv('MAIL_DEFAULT_SENDER')

    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    mail.init_app(app)

    SUPABASE_URL = os.getenv('SUPABASE_URL')
    SUPABASE_SERVICE_ROLE_KEY = os.getenv('SUPABASE_SERVICE_ROLE_KEY')
    app.supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)

    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(business_bp, url_prefix='/business')
    app.register_blueprint(search_bp, url_prefix='/search')
    app.register_blueprint(user_bp)

    @app.route('/')
    def index():
        return render_template('index.html')
    return app

if __name__ == "__main__":
    app = create_app()
    app.run(debug=True)