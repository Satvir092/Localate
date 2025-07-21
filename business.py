from flask import Blueprint, render_template, redirect, url_for, request, flash, current_app, jsonify
from flask_login import login_required, current_user
from datetime import datetime
import json
from werkzeug.utils import secure_filename
from urllib.parse import urlparse
import uuid
from extensions import mail
from flask_mail import Message
from datetime import datetime
from datetime import datetime, date
import pytz

business_bp = Blueprint('business', __name__)

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp', 'svg'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

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
        social_url = request.form.get('social_url')
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

        if not timezone:
            flash("Please select a timezone", "error")
            return redirect(url_for('business.create_business'))

        if interval == 'none':
            interval = None
        elif interval:
            try:
                interval = int(interval)
            except (ValueError, TypeError):
                flash("Invalid appointment interval selected.", "error")
                return redirect(url_for('business.create_business'))
        else:
            flash("Please select an appointment interval", "error")
            return redirect(url_for('business.create_business'))

        if opening_time and closing_time and opening_time >= closing_time:
            flash("Opening time must be earlier than closing time.", "error")
            return redirect(url_for('business.create_business'))
        
        if len(name) > 50:
            flash("Business name must be under 50 characters.", "error")
            return redirect(url_for('business.create_business'))

        if description and len(description) > 500:
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
            "social_url": social_url,
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

@business_bp.route('/upload_business_profile_pic/<int:business_id>', methods=['POST'])
@login_required
def upload_business_profile_pic(business_id):
    supabase = current_app.supabase

    business_resp = supabase.table('businesses').select('user_id, profile_image_url').eq('id', business_id).single().execute()
    if not business_resp.data or str(business_resp.data['user_id']) != str(current_user.id):
        flash("Unauthorized to edit this business.", "error")
        return redirect(url_for('business.dashboard'))

    file = request.files.get('profile_pic')
    if not file or not file.filename:
        flash("No file selected.", "error")
        return redirect(url_for('business.edit_business', business_id=business_id))

    bucket_name = 'business-profile-pics'
    old_url = business_resp.data.get('profile_image_url')

    if old_url:
        try:
            parsed_url = urlparse(old_url)
            old_filename = parsed_url.path.split('/')[-1]
            delete_resp = supabase.storage.from_(bucket_name).remove([old_filename])
            current_app.logger.info(f"Deleted old image: {old_filename}")
        except Exception as e:
            current_app.logger.error(f"Error deleting old image: {e}")

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
    current_app.logger.info(f"Upload response: {upload_resp}")
    public_url = supabase.storage.from_(bucket_name).get_public_url(unique_filename)

    supabase.table('businesses').update({'profile_image_url': public_url}).eq('id', business_id).execute()

    return redirect(url_for('business.view_business', business_id=business_id))

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
        social_url = request.form.get('social_url')
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
            "social_url": social_url,
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

    appt_resp = supabase.table('appointments').select('*').eq('id', appt_id).single().execute()
    if not appt_resp.data:
        return "Appointment not found", 404

    appointment = appt_resp.data
    business_id = appointment['business_id']

    business_resp = supabase.table('businesses').select('user_id, name').eq('id', business_id).single().execute()
    if not business_resp.data or str(business_resp.data['user_id']) != str(current_user.id):
        return "Unauthorized", 403

    business_name = business_resp.data['name']

    supabase.table('appointments').update({'confirmed': True}).eq('id', appt_id).execute()

    date_str = appointment['date']
    time_str = appointment['time']
    date_obj = datetime.strptime(date_str, "%Y-%m-%d")
    time_obj = datetime.strptime(time_str, "%H:%M:%S")

    formatted_date = date_obj.strftime("%B %d, %Y")  
    formatted_time = time_obj.strftime("%I:%M %p").lstrip("0")  

    msg = Message(
        subject=f"Your Appointment with {business_name} is Confirmed",
        sender=current_app.config['MAIL_DEFAULT_SENDER'],
        recipients=[appointment['email']]
    )
    msg.html = f"""
    <div style="background-color:#1f1f1f; color:#e0d4ff; font-family:sans-serif; padding:1.5em; border-radius:8px;">
        <h2 style="color:#b37bff;">Appointment Confirmed 🎉</h2>
        <p>Hi <strong>{appointment['name']}</strong>,</p>
        <p>Your appointment with <strong>{business_name}</strong> has been confirmed!</p>
        <p>
            <strong>Date:</strong> {formatted_date}<br>
            <strong>Time:</strong> {formatted_time}
        </p>
        <p style="margin-top:1em;">We look forward to seeing you!</p>
    </div>
    """
    mail.send(msg)

    return "Appointment confirmed and email sent", 200

@business_bp.route('/submit_review/<int:business_id>', methods=['POST'])
@login_required
def submit_review(business_id):
    rating = request.form.get('rating')
    comment = request.form.get('comment', '').strip()

    try:
        rating = int(rating)
        if rating < 1 or rating > 5:
            flash("Invalid rating. Please choose a number between 1 and 5.", "error")
            return redirect(url_for('search.customer_view', business_id=business_id))
    except ValueError:
        flash("Rating must be a number.", "error")
        return redirect(url_for('search.customer_view', business_id=business_id))

    supabase = current_app.supabase


    existing_review = supabase.table('reviews')\
        .select('*')\
        .eq('user_id', str(current_user.id))\
        .eq('business_id', business_id)\
        .execute()

    if existing_review.data:

        review_id = existing_review.data[0]['id']  
        response = supabase.table('reviews')\
            .update({
                "rating": rating,
                "comment": comment
            })\
            .eq('id', review_id)\
            .execute()

        if response.data:
            flash("Your review has been updated!", "success")
        else:
            flash("Failed to update your review. Please try again.", "error")
    else:
        response = supabase.table('reviews').insert({
            "user_id": str(current_user.id),
            "business_id": business_id,
            "rating": rating,
            "comment": comment
        }).execute()

        if response.data:
            flash("Review submitted successfully!", "success")
        else:
            flash("Something went wrong. Please try again.", "error")

    return redirect(url_for('search.customer_view', business_id=business_id))

@business_bp.route('/business/<int:business_id>/reviews')
def view_reviews(business_id):
    supabase = current_app.supabase

    business_response = supabase.table('businesses')\
        .select('id, name')\
        .eq('id', business_id)\
        .single()\
        .execute()
    reviews_response = supabase.table('reviews')\
        .select('rating, comment, created_at, users(username)')\
        .eq('business_id', business_id)\
        .order('created_at', desc=True)\
        .execute()

    reviews = reviews_response.data

    review_count = len(reviews)
    if review_count > 0:
        avg_rating = sum([r['rating'] for r in reviews]) / review_count
    else:
        avg_rating = 0

    print("DEBUG: q =", request.args.get('q'))
    print("DEBUG: category =", request.args.get('category'))
    print("DEBUG: city =", request.args.get('city'))
    print("DEBUG: state =", request.args.get('state'))

    return render_template(
    'view_reviews.html',
    business=business_response.data,
    reviews=reviews,
    avg_rating=round(avg_rating, 1),
    review_count=review_count,
    q=request.args.get('q', ''),
    category=request.args.get('category', ''),
    city=request.args.get('city', ''),
    state=request.args.get('state', '')
)
