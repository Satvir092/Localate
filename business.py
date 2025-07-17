from flask import Blueprint, render_template, redirect, url_for, request, flash, current_app
from flask_login import login_required, current_user
from datetime import datetime
import json
from datetime import datetime, date
import pytz

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

    filtered_appointments = []

    for appt in appointments:
        business_resp = supabase.table('businesses').select('*').eq('id', appt['business_id']).single().execute()
        business = business_resp.data or {}

        appt['business'] = business

        appt_datetime_str = f"{appt['date']} {appt['time']}" 
        business_tz_str = business.get('timezone', 'UTC')
        business_tz = pytz.timezone(business_tz_str)

        appt_naive = datetime.strptime(appt_datetime_str, '%Y-%m-%d %H:%M:%S')
        appt_localized = business_tz.localize(appt_naive)

        now_local = datetime.now(business_tz)

        if appt_localized >= now_local:
            filtered_appointments.append(appt)

    return render_template('dashboard.html', user=current_user, businesses=businesses, appointments=filtered_appointments)

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
        timezone = request.form.get('timezone')

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
        
        if not timezone:
            flash("Please select a timezone")
            return redirect(url_for('business.create_business'))

        if opening_time and closing_time and opening_time >= closing_time:
            flash("Opening time must be earlier than closing time.", "error")
            return redirect(url_for('business.create_business'))
        
        if len(name) > 50:
            flash("Business name must be under 50 characters.", "error")
            return redirect(url_for('business.create_business'))

        if len(description) > 500:
            flash("Description must be under 500 characters.", "error")
            return redirect(url_for('business.create_business'))

        if len(city) > 50:
            flash("City name must be under 50 characters.", "error")
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
            "timezone": timezone,
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

        tz_str = business.get('timezone', 'UTC')
        try:
            tz = pytz.timezone(tz_str)
        except:
            tz = pytz.utc 

        today = date.today().isoformat()
        opening_str = f"{today} {business['opening_time']}"
        closing_str = f"{today} {business['closing_time']}"

        opening_dt = tz.localize(datetime.strptime(opening_str, "%Y-%m-%d %H:%M:%S"))
        closing_dt = tz.localize(datetime.strptime(closing_str, "%Y-%m-%d %H:%M:%S"))

        business['opening_time'] = opening_dt.strftime("%I:%M %p")
        business['closing_time'] = closing_dt.strftime("%I:%M %p")

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
        timezone = request.form.get('timezone')

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
        
        if not timezone:
            flash("Please select a timezone", "error")
            return redirect(request.url)

        if opening_time and closing_time and opening_time >= closing_time:
            flash("Opening time must be earlier than closing time.", "error")
            return redirect(request.url)
        
        if len(name) > 50:
            flash("Business name must be under 50 characters.", "error")
            return redirect(url_for('business.create_business'))

        if len(description) > 500:
            flash("Description must be under 500 characters.", "error")
            return redirect(url_for('business.create_business'))

        if len(city) > 50:
            flash("City name must be under 50 characters.", "error")
            return redirect(url_for('business.create_business'))


        update_data = {
            "name": name,
            "category": category,
            "city": city,
            "description": description,
            "opening_time": opening_time,
            "closing_time": closing_time,
            "interval": interval,
            "open_days": days_list,
            "timezone": timezone,
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
    business_tz_str = business.get('timezone', 'UTC')
    business_tz = pytz.timezone(business_tz_str)

    appointments_response = supabase.table('appointments') \
        .select('*, users(full_name, phone_number, email, age, profile_image_url)') \
        .eq('business_id', business_id) \
        .order('date', desc=False) \
        .order('time', desc=False) \
        .execute()

    appointments = appointments_response.data or []

    filtered_appointments = []
    for appt in appointments:
        appt_datetime_str = f"{appt['date']} {appt['time']}"
        try:
            appt_naive = datetime.strptime(appt_datetime_str, '%Y-%m-%d %H:%M:%S')
        except ValueError:

            appt_naive = datetime.strptime(appt_datetime_str, '%Y-%m-%d %H:%M')
        appt_localized = business_tz.localize(appt_naive)

        now_local = datetime.now(business_tz)

        print("DEBUG:", appt['date'], type(appt['date']))
        print("DEBUG:", appt['time'], type(appt['time']))

        if appt_localized >= now_local:
            appt['local_date'] = appt_localized.strftime('%B %d, %Y')
            appt['local_time'] = appt_localized.strftime('%I:%M %p')
            filtered_appointments.append(appt)

    return render_template('view_appointments.html', business=business, appointments=filtered_appointments)

@business_bp.route('/confirm_appointment', methods=['POST'])
@login_required
def confirm_appointment():
    supabase = current_app.supabase
    appt_id = request.form.get('id')

    if not appt_id:
        return "Missing appointment ID", 400

    appt_resp = supabase.table('appointments').select('business_id').eq('id', appt_id).single().execute()
    if not appt_resp.data:
        return "Appointment not found", 404

    business_id = appt_resp.data['business_id']

    business_resp = supabase.table('businesses').select('user_id').eq('id', business_id).single().execute()
    if not business_resp.data or str(business_resp.data['user_id']) != str(current_user.id):
        return "Unauthorized", 403

    supabase.table('appointments').update({'confirmed': True}).eq('id', appt_id).execute()

    return "Appointment confirmed", 200