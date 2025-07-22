from flask import Blueprint, render_template, request, current_app, redirect, url_for, flash
from flask_login import login_required, current_user
from datetime import datetime
from flask_mail import Message
from itsdangerous import URLSafeTimedSerializer
from extensions import mail
from datetime import datetime, date
import pytz
from flask import jsonify


search_bp = Blueprint('search', __name__, url_prefix='/search')

@search_bp.route('/', methods=['GET'])
def search():
    supabase = current_app.supabase
    query = request.args.get('q', '').strip()
    category = request.args.get('category', '').strip()
    state = request.args.get('state', '').strip()
    popularity = request.args.get('popularity', '').strip()

    if not query and not category and not state:
        businesses = None
    else:
        business_query = supabase.table('businesses').select('*')
        if query:
            business_query = business_query.or_(
                f"name.ilike.%{query}%,city.ilike.%{query}%"
            )
        if category:
            business_query = business_query.eq('category', category)
        if state:
            business_query = business_query.eq('state', state)

        response = business_query.execute()
        businesses = response.data or []

        business_ids = [b['id'] for b in businesses]
        if business_ids:
            reviews_response = supabase.table('reviews')\
                .select('rating, business_id')\
                .in_('business_id', business_ids)\
                .execute()
            reviews = reviews_response.data or []
        else:
            reviews = []

        from collections import defaultdict
        review_map = defaultdict(list)
        for review in reviews:
            review_map[review['business_id']].append(review['rating'])

        for business in businesses:
            ratings = review_map[business['id']]
            if ratings:
                business['avg_rating'] = round(sum(ratings) / len(ratings), 1)
                business['review_count'] = len(ratings)
            else:
                business['avg_rating'] = 0
                business['review_count'] = 0

        if popularity == 'most':
            businesses.sort(key=lambda b: b['review_count'], reverse=True)
        elif popularity == 'least':
            businesses.sort(key=lambda b: b['review_count'])

    return render_template('search.html', businesses=businesses, popularity=popularity)

@search_bp.route('/customer_view/<int:business_id>')
@login_required
def customer_view(business_id):
    supabase = current_app.supabase
    response = supabase.table('businesses').select('*').eq('id', business_id).single().execute()
    business = response.data

    if business:

        tz_str = business.get('timezone', 'UTC')
        try:
            tz = pytz.timezone(tz_str)
        except:
            tz = pytz.utc  

        today = date.today().isoformat()
        raw_opening = business['opening_time']
        raw_closing = business['closing_time']

        opening_str = f"{today} {raw_opening}"
        closing_str = f"{today} {raw_closing}"

        opening_dt = tz.localize(datetime.strptime(opening_str, "%Y-%m-%d %H:%M:%S"))
        closing_dt = tz.localize(datetime.strptime(closing_str, "%Y-%m-%d %H:%M:%S"))

        business['opening_time'] = opening_dt.strftime("%I:%M %p").lstrip('0')
        business['closing_time'] = closing_dt.strftime("%I:%M %p").lstrip('0')
    else:
        raw_opening = None
        raw_closing = None

    return render_template(
        'customer_view.html',
        business=business,
        raw_opening=raw_opening,
        raw_closing=raw_closing,
        q=request.args.get('q', ''),
        category=request.args.get('category', ''),
        city=request.args.get('city', ''),
        state=request.args.get('state', '')
    )

@search_bp.route('/book_appointment', methods=['POST'])
@login_required
def book_appointment():
    supabase = current_app.supabase

    business_id = request.form.get('business_id')
    selected_date = request.form.get('selected_date')
    selected_time = request.form.get('selected_time')

    if not all([business_id, selected_date, selected_time]):
        flash("Please select a date and time.", "error")
        return redirect(request.referrer or url_for('search.search'))

    try:
        date_obj = datetime.strptime(selected_date, "%Y-%m-%d").date()
        time_obj = datetime.strptime(selected_time, "%H:%M").time()

        existing = supabase.table('appointments') \
            .select('id') \
            .eq('business_id', int(business_id)) \
            .eq('date', date_obj.isoformat()) \
            .eq('time', time_obj.strftime("%H:%M:%S")) \
            .execute()

        if existing.data:
            flash("This time slot is already booked. Please choose another.", "error")
            return redirect(request.referrer or url_for('search.customer_view', business_id=business_id))
        
        supabase.table('appointments').insert({
            'user_id': current_user.id,
            'business_id': int(business_id),
            'date': date_obj.isoformat(),
            'time': time_obj.strftime("%H:%M:%S"),
            'email': current_user.email,
            'name': current_user.full_name,
            'phone': current_user.phone_number,
            'age': current_user.age,
            'profile_image_url': current_user.profile_image_url
        }).execute()

        business_info = supabase.table('businesses') \
            .select('user_id, name') \
            .eq('id', int(business_id)) \
            .single() \
            .execute()
        
        owner_id = business_info.data['user_id']
        business_name = business_info.data['name']

        owner_info = supabase.table('users') \
            .select('email') \
            .eq('id', owner_id) \
            .single() \
            .execute()

        owner_email = owner_info.data['email']

        msg = Message(
            subject=f"New Appointment for {business_name}",
            sender=current_app.config['MAIL_DEFAULT_SENDER'],
            recipients=[owner_email]
        )
        formatted_time = time_obj.strftime("%I:%M %p").lstrip("0")
        msg.html = f"""
            <!DOCTYPE html>
            <html>
            <body style="background-color: #1e1e1e; color: #e0e0e0; font-family: Arial, sans-serif; padding: 20px;">
                <table width="100%" cellpadding="0" cellspacing="0" style="max-width: 600px; margin: auto; background-color: #2b2b2b; border-radius: 8px;">
                <tr>
                    <td style="padding: 30px;">
                    <h2 style="color: #bb86fc; margin-top: 0;">New Appointment for {business_name}</h2>

                    <p style="font-size: 16px; line-height: 1.6;">
                        You have a new appointment booking:
                    </p>

                    <hr style="border: 1px solid #444;" />

                    <p style="font-size: 16px;">
                        <strong>Name:</strong> {current_user.full_name}<br>
                        <strong>Email:</strong> {current_user.email}<br>
                        <strong>Phone:</strong> {current_user.phone_number}<br>
                        <strong>Date:</strong> {selected_date}<br>
                        <strong>Time:</strong> {formatted_time}
                    </p>

                    <hr style="border: 1px solid #444;" />

                    <p style="font-size: 16px;">
                        Please confirm this appointment or contact the user if the time is no longer available.
                    </p>

                    <p style="margin-top: 30px; font-size: 14px; color: #999;">
                        — Localate Team
                    </p>
                    </td>
                </tr>
                </table>
            </body>
            </html>
            """

        mail.send(msg)

        flash("Appointment booked successfully. Confirmation pending from owner!", "success")

    except Exception as e:
        current_app.logger.error(f"Error booking appointment: {e}")
        flash("Error booking appointment. Please try again or update your profile.", "error")

    return redirect(request.referrer or url_for('search.customer_view', business_id=business_id))

@search_bp.route('/autocomplete')
def autocomplete():
    supabase = current_app.supabase
    query = request.args.get('q', '').strip()

    if not query:
        return jsonify([])

    response = supabase.table('businesses') \
        .select('name') \
        .ilike('name', f'%{query}%') \
        .limit(10) \
        .execute()

    results = [b['name'] for b in response.data]
    return jsonify(results)
