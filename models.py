from flask_login import UserMixin
from extensions import login_manager
from flask import current_app
from postgrest.exceptions import APIError

class User(UserMixin):
    def __init__(self, id, username, email, password_hash, confirmed, confirmed_on, profile_image_url, full_name, phone_number, age):
        self.id = id
        self.username = username
        self.email = email
        self.password_hash = password_hash
        self.confirmed = confirmed
        self.confirmed_on = confirmed_on
        self.profile_image_url = profile_image_url
        self.full_name = full_name
        self.phone_number = phone_number
        self.age = age

    def check_password(self, password):
        from werkzeug.security import check_password_hash
        return check_password_hash(self.password_hash, password)


def get_user_by_id(user_id):
    supabase = current_app.supabase
    try:
        response = supabase.table('users').select('*').eq('id', user_id).execute()
    except APIError:
        return None
    data = response.data
    if isinstance(data, list) and len(data) == 1:
        return User(**data[0])
    return None

def get_user_by_username_or_email(username_or_email):
    supabase = current_app.supabase
    response = supabase.table('users').select('*').or_(
        f"username.eq.{username_or_email},email.eq.{username_or_email}"
    ).limit(1).execute()
    data = response.data
    if data:
        return User(**data[0])
    return None

@login_manager.user_loader
def load_user(user_id):
    return get_user_by_id(int(user_id))