from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from urllib.parse import urlparse
import uuid
import os

user_bp = Blueprint('user', __name__, url_prefix='/user')

@user_bp.route('/edit_profile', methods=['GET', 'POST'])
@login_required
def edit_profile():
    supabase = current_app.supabase

    if request.method == 'POST':
        name = request.form.get('full_name', '').strip()
        age = request.form.get('age', '').strip()
        phone = request.form.get('phone_number', '').strip()
        profile_image_url = current_user.profile_image_url  

        file = request.files.get('profile_pic')
        if file and file.filename:
            filename = secure_filename(file.filename)
            file.save(os.path.join('static/uploads', filename))  
            profile_image_url = url_for('static', filename=f'uploads/{filename}', _external=True)

        if not (name and age and phone):
            flash("Please fill out all required fields: Full Name, Age, and Phone Number.", "error")
            return redirect(url_for('user.edit_profile'))

        if len(name) > 50:
            flash("Full Name must be 50 characters or fewer.", "error")
            return redirect(url_for('user.edit_profile'))

        if not age.isdigit() or not(0 < int(age) <= 120):
            flash("Please enter a valid age between 1 and 120.", "error")
            return redirect(url_for('user.edit_profile'))

        if not(10 <= len(phone) <= 14):
            flash("Phone number must be between 10 and 14 characters", "error")
            return redirect(url_for('user.edit_profile'))

        update_data = {
            'full_name': name,
            'age': int(age),
            'phone_number': phone,
            'profile_image_url': profile_image_url
        }

        supabase.table('users').update(update_data).eq('id', current_user.id).execute()
        return redirect(url_for('business.dashboard'))

    return render_template('edit_profile.html', user=current_user)

@user_bp.route('/upload_profile_pic', methods=['POST'])
@login_required
def upload_profile_pic():
    supabase = current_app.supabase
    file = request.files.get('profile_pic')
    if not file or not file.filename:
        flash("No file selected.", "error")
        return redirect(url_for('business.dashboard'))

    bucket_name = "user-profile-pics"

    user_resp = supabase.table('users').select('profile_image_url').eq('id', current_user.id).single().execute()
    old_url = None
    if user_resp.data:
        old_url = user_resp.data.get('profile_image_url')
        print("Old profile image URL:", old_url)
    if old_url:
        try:
            parsed_url = urlparse(old_url)
            old_filename = parsed_url.path.split('/')[-1]
            delete_resp = supabase.storage.from_(bucket_name).remove([old_filename])
            print("Delete response:", delete_resp)
        except Exception as e:
            print("Error deleting old image:", e)

    filename = secure_filename(file.filename)
    unique_filename = f"{uuid.uuid4().hex}_{filename}"
    file_bytes = file.read()

    upload_resp = supabase.storage.from_(bucket_name).upload(
        unique_filename,
        file_bytes,
        file_options={
            "content-type": file.content_type,
            "x-upsert": "true"
        }
    )
    print("Upload response:", upload_resp)

    public_url = supabase.storage.from_(bucket_name).get_public_url(unique_filename)

    supabase.table('users').update({'profile_image_url': public_url}).eq('id', current_user.id).execute()

    return redirect(url_for('business.dashboard'))