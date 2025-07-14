from flask import Blueprint, render_template, redirect, url_for, request, flash, jsonify, current_app
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from datetime import datetime
import json

business_bp = Blueprint('business', __name__)

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

@business_bp.route('/')
def index():
    return render_template('index.html')

@business_bp.route('/about')
def about():
    return render_template('about.html')

@business_bp.route('/dashboard', methods=['GET', 'POST'])
@login_required
def dashboard():
    supabase = current_app.supabase
    
    response = supabase.table('businesses').select('*').eq('user_id', str(current_user.id)).execute()
    businesses = response.data if response.data else []

    appointments_resp = supabase.table('appointments').select('*').eq('user_id', current_user.id).execute()
    appointments = appointments_resp.data or []

    for appt in appointments:
        business_resp = supabase.table('businesses').select('*').eq('id', appt['business_id']).single().execute()
        appt['business'] = business_resp.data or {}

    return render_template('dashboard.html', user=current_user, businesses=businesses, appointments=appointments)

@business_bp.route('/create_business', methods=['GET', 'POST'])
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
        state = request.form.get('state')

        if not name:
            flash("Business name is required.", "error")
            return redirect(url_for('business.create_business'))

        if not days_list:
            flash("Please select at least one open day.", "error")
            return redirect(url_for('business.create_business'))

        if not city:
            flash("Please select a city.", "error")
            return redirect(url_for('business.create_business'))

        if not state:
            flash("Please select a state.", "error")
            return redirect(url_for('business.create_business'))

        if not interval:
            flash("Please select an appointment interval", "error")
            return redirect(url_for('business.create_business'))

        if opening_time and closing_time and opening_time >= closing_time:
            flash("Opening time must be earlier than closing time.", "error")
            return redirect(url_for('business.create_business'))

        supabase = current_app.supabase
        response = supabase.table('businesses').insert({
            "user_id": str(current_user.id),
            "name": name,
            "category": category,
            "city": city,
            "description": description,
            "open_days": days_list,
            "opening_time": opening_time,
            "interval": interval,
            "state": state,
            "closing_time": closing_time
        }).execute()

        if response.data:
            return redirect(url_for('business.dashboard'))
        else:
            flash("Failed to create business. Please try again.", "error")
            return redirect(url_for('business.create_business'))

    return render_template('create_business.html')

@business_bp.route('/view_business/<int:business_id>')
@login_required
def view_business(business_id):
    supabase = current_app.supabase 

    response = supabase.table('businesses').select('*').eq('id', business_id).single().execute()
    if response.data:
        business = response.data

        business['opening_time'] = datetime.strptime(business['opening_time'], "%H:%M:%S").strftime("%I:%M %p")
        business['closing_time'] = datetime.strptime(business['closing_time'], "%H:%M:%S").strftime("%I:%M %p")

        if isinstance(business['open_days'], str) and business['open_days'].startswith("["):
            business['open_days'] = json.loads(business['open_days'])

        print("Profile image URL:", business.get('profile_image_url'))

        return render_template('view_business.html', business=business)
    else:
        flash("Business not found.", "error")
        return redirect(url_for('business.dashboard'))  
    
@business_bp.route('/edit_business/<int:business_id>', methods=['GET', 'POST'])
@login_required
def edit_business(business_id):
    supabase = current_app.supabase

    response = supabase.table('businesses').select('*').eq('id', business_id).eq('user_id', str(current_user.id)).single().execute()
    
    if not response.data:
        flash("Business not found or you don't have permission to edit it.", "error")
        return redirect(url_for('business.dashboard'))

    business = response.data

    if request.method == 'POST':
        name = request.form.get('name')
        category = request.form.get('category')
        city = request.form.get('city')
        description = request.form.get('description')
        opening_time = request.form.get('start_time')
        closing_time = request.form.get('end_time')
        interval = request.form.get('interval')
        days_list = request.form.getlist('weekdays')
        state = request.form.get('state')

        if not name:
            flash("Business name is required.", "error")
            return redirect(request.url)

        if not city:
            flash("Please select a city.", "error")
            return redirect(request.url)

        if not state:
            flash("Please select a state.", "error")
            return redirect(request.url)

        if not days_list:
            flash("Please select at least one open day.", "error")
            return redirect(request.url)

        if not interval:
            flash("Please select an appointment interval.", "error")
            return redirect(request.url)

        if opening_time and closing_time and opening_time >= closing_time:
            flash("Opening time must be earlier than closing time.", "error")
            return redirect(request.url)

        update_data = {
            "name": name,
            "category": category,
            "city": city,
            "description": description,
            "opening_time": opening_time,
            "closing_time": closing_time,
            "interval": interval,
            "open_days": days_list,
            "state": state
        }

        update_response = supabase.table('businesses').update(update_data).eq('id', business_id).execute()

        if update_response.data:
            return redirect(url_for('business.dashboard'))
        else:
            flash("Failed to update business. Please try again.", "error")
            return redirect(request.url)

    return render_template('edit_business.html', business=business)

@business_bp.route('/<int:business_id>/view_appointments')
@login_required
def view_appointments(business_id):
    supabase = current_app.supabase
    business_response = supabase.table('businesses') \
        .select('*') \
        .eq('id', business_id) \
        .eq('user_id', str(current_user.id)) \
        .single() \
        .execute()

    if not business_response.data:
        flash("Business not found or you don't have permission to view its appointments.", "error")
        return redirect(url_for('business.dashboard'))

    business = business_response.data

    appointments_response = supabase.table('appointments') \
        .select('*, users(full_name, phone_number, email, age)') \
        .eq('business_id', business_id) \
        .order('date', desc=False) \
        .order('time', desc=False) \
        .execute()

    appointments = appointments_response.data or []

    return render_template('view_appointments.html', business=business, appointments=appointments)