from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
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

        update_data = {
            'full_name': name,
            'age': age,
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

    filename = secure_filename(file.filename)
    upload_folder = os.path.join(current_app.root_path, 'static', 'uploads')
    os.makedirs(upload_folder, exist_ok=True)
    filepath = os.path.join(upload_folder, filename)
    file.save(filepath)

    profile_image_url = url_for('static', filename=f'uploads/{filename}', _external=True)

    supabase.table('users').update({'profile_image_url': profile_image_url}).eq('id', current_user.id).execute()

    return redirect(url_for('business.dashboard'))