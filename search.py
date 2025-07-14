from flask import Blueprint, render_template, request, current_app, redirect, url_for, flash
from flask_login import login_required, current_user
from datetime import datetime

search_bp = Blueprint('search', __name__, url_prefix='/search')

@search_bp.route('/', methods=['GET'])
@login_required
def search():
    supabase = current_app.supabase
    query = request.args.get('q', '').strip()
    category = request.args.get('category', '').strip()
    city = request.args.get('city', '').strip()
    state = request.args.get('state', '').strip()

    if not query and not category and not city and not state:
        # No filters or search terms — no results to show yet
        businesses = None
    else:
        business_query = supabase.table('businesses').select('*')
        if query:
            business_query = business_query.ilike('name', f'%{query}%')
        if category:
            business_query = business_query.eq('category', category)
        if city:
            business_query = business_query.eq('city', city)
        if state:
            business_query = business_query.eq('state', state)

        response = business_query.execute()
        businesses = response.data or []

    return render_template('search.html', businesses=businesses)

@search_bp.route('/customer_view/<int:business_id>')
@login_required
def customer_view(business_id):
    supabase = current_app.supabase
    response = supabase.table('businesses').select('*').eq('id', business_id).single().execute()
    business = response.data

    if business:

        raw_opening = business['opening_time']
        raw_closing = business['closing_time']


        business['opening_time'] = datetime.strptime(raw_opening, "%H:%M:%S").strftime("%I:%M %p").lstrip('0')
        business['closing_time'] = datetime.strptime(raw_closing, "%H:%M:%S").strftime("%I:%M %p").lstrip('0')
    
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

    current_app.logger.info(f"Form submitted: business_id={business_id}, date={selected_date}, time={selected_time}")
    current_app.logger.info(f"Current user: id={current_user.id}, email={current_user.email}")

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

        flash("Appointment booked successfully, awaiting confirmation from owner!", "success")

    except Exception as e:
        current_app.logger.error(f"Error booking appointment: {e}")
        flash("Please make sure an account and profile is created before trying to book.", "error")

    return redirect(request.referrer or url_for('search.customer_view', business_id=business_id))