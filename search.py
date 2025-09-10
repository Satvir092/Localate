from flask import Blueprint, render_template, request, current_app, redirect, url_for, flash
from flask_login import login_required, current_user
from datetime import datetime
from math import ceil
from datetime import datetime, date, timedelta
import pytz
from flask import jsonify
from sib_api_v3_sdk import Configuration, ApiClient
from sib_api_v3_sdk.api.transactional_emails_api import TransactionalEmailsApi
from sib_api_v3_sdk.models.send_smtp_email import SendSmtpEmail
from sib_api_v3_sdk.rest import ApiException

search_bp = Blueprint('search', __name__, url_prefix='/search')

def record_analytics(business_id, field):
    supabase = current_app.supabase

    # Check if today's row exists
    existing = supabase.table("business_analytics")\
        .select("id, " + field)\
        .eq("business_id", business_id)\
        .eq("date", str(date.today()))\
        .execute()

    if not existing.data:
        # Insert a new row for today
        supabase.table("business_analytics").insert({
            "business_id": business_id,
            "date": str(date.today()),
            "profile_views": 1 if field == "profile_views" else 0,
            "search_appearances": 1 if field == "search_appearances" else 0
        }).execute()
    else:
        row = existing.data[0]
        supabase.table("business_analytics").update({
            field: row[field] + 1
        }).eq("id", row["id"]).execute()

def record_search_analytics(businesses):
    for b in businesses:
        try:
            record_analytics(b["id"], "search_appearances")
        except Exception as e:
            current_app.logger.warning(f"Analytics error for business {b['id']}: {e}")


def create_gcal_event(business_name, business_id, date, time, user_name, user_email, user_phone):
    """
    Create a simple Google Calendar "Add Event" link
    """
    try:
        # Calculate end time (1 hour after start time by default)
        start_datetime = datetime.strptime(f'{date} {time}', '%Y-%m-%d %H:%M:%S')
        end_datetime = start_datetime.replace(hour=(start_datetime.hour + 1) % 24)
        
        # Format dates for Google Calendar URL
        start_date_str = start_datetime.strftime('%Y%m%dT%H%M%S')
        end_date_str = end_datetime.strftime('%Y%m%dT%H%M%S')
        
        # Create event description
        description = f"Appointment with {business_name}\n\nCustomer Information:\nName: {user_name}\nEmail: {user_email}\nPhone: {user_phone}\n\nBusiness: {business_name}"
        
        # Build Google Calendar "Add Event" URL
        details_encoded = description.replace(' ', '%20').replace('\n', '%0A')
        calendar_url = (
            f"https://calendar.google.com/calendar/r/eventedit?"
            f"action=TEMPLATE"
            f"&text=Appointment with {business_name}"
            f"&dates={start_date_str}/{end_date_str}"
            f"&details={details_encoded}"
            f"&location={business_name.replace(' ', '%20')}"
            f"&sf=true"
            f"&output=xml"
        )
        
        return {
            'calendar_url': calendar_url,
            'start_time': start_datetime.strftime('%I:%M %p').lstrip('0'),
            'end_time': end_datetime.strftime('%I:%M %p').lstrip('0')
        }
        
    except Exception as e:
        current_app.logger.error(f'Error creating Google Calendar link: {e}')
        return None
    
@search_bp.route('/', methods=['GET'])
def search():
    
    STATE_ABBREVIATIONS = {
        'alabama': 'AL', 'alaska': 'AK', 'arizona': 'AZ', 'arkansas': 'AR', 'california': 'CA',
        'colorado': 'CO', 'connecticut': 'CT', 'delaware': 'DE', 'florida': 'FL', 'georgia': 'GA',
        'hawaii': 'HI', 'idaho': 'ID', 'illinois': 'IL', 'indiana': 'IN', 'iowa': 'IA',
        'kansas': 'KS', 'kentucky': 'KY', 'louisiana': 'LA', 'maine': 'ME', 'maryland': 'MD',
        'massachusetts': 'MA', 'michigan': 'MI', 'minnesota': 'MN', 'mississippi': 'MS', 'missouri': 'MO',
        'montana': 'MT', 'nebraska': 'NE', 'nevada': 'NV', 'new hampshire': 'NH', 'new jersey': 'NJ',
        'new mexico': 'NM', 'new york': 'NY', 'north carolina': 'NC', 'north dakota': 'ND', 'ohio': 'OH',
        'oklahoma': 'OK', 'oregon': 'OR', 'pennsylvania': 'PA', 'rhode island': 'RI', 'south carolina': 'SC',
        'south dakota': 'SD', 'tennessee': 'TN', 'texas': 'TX', 'utah': 'UT', 'vermont': 'VT',
        'virginia': 'VA', 'washington': 'WA', 'west virginia': 'WV', 'wisconsin': 'WI', 'wyoming': 'WY'
    }

    supabase = current_app.supabase
    query = request.args.get('q', '').strip()
    category = request.args.get('category', '').strip()
    location = request.args.get('location', '').strip()
    popularity = request.args.get('popularity', '').strip()
    page = int(request.args.get('page', 1))
    per_page = 20
    offset = (page - 1) * per_page

    if not query and not category and not location:
        return render_template(
            'search.html',
            businesses=[],
            popularity=popularity,
            page=1,
            total_pages=0,
            query=query,
            category=category,
            location=location,
            is_empty_search=True
        )

    # Include the owner's is_premium status
    filters = supabase.table('businesses').select('*, user:user_id(is_premium)')

    if query:
        filters = filters.ilike('name', f'%{query}%')

    if category:
        filters = filters.eq('category', category)

    if location:
        if ',' in location:
            city, state = [part.strip() for part in location.split(',', 1)]
            state_lower = state.lower()
            if state_lower in STATE_ABBREVIATIONS:
                state = STATE_ABBREVIATIONS[state_lower]
            filters = filters.ilike('city', f'%{city}%').ilike('state', f'%{state}%')
        else:
            location_to_search = location
            if location.lower() in STATE_ABBREVIATIONS:
                location_to_search = STATE_ABBREVIATIONS[location.lower()]
            filters = filters.or_(f'city.ilike.%{location_to_search}%,state.ilike.%{location_to_search}%')

    if popularity == 'most':
        filters = filters.order('review_count', desc=True)
    elif popularity == 'least':
        filters = filters.order('review_count', desc=False)

    response = filters.range(offset, offset + per_page - 1).execute()
    businesses = response.data or []
    total_count = response.count or 0
    total_pages = ceil(total_count / per_page)

    if businesses:
        record_search_analytics(businesses)

    return render_template(
        'search.html',
        businesses=businesses,
        popularity=popularity,
        page=page,
        total_pages=total_pages,
        query=query,
        category=category,
        location=location,
        is_empty_search=False
    )

@search_bp.route('/customer_view/<int:business_id>')
def customer_view(business_id):
    record_analytics(business_id, "profile_views")
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

    # Get parameters and ensure they're not empty strings
    q = request.args.get('q', '') 
    category = request.args.get('category', '')
    location = request.args.get('location', '')
    popularity = request.args.get('popularity', '') 
    page = request.args.get('page', '1')
    
    # Convert page to int, fallback to 1 if invalid
    try:
        page = int(page) if page else 1
    except (ValueError, TypeError):
        page = 1

    return render_template(
        'customer_view.html',
        business=business,
        raw_opening=raw_opening,
        raw_closing=raw_closing,
        q=q,
        category=category,
        location=location,
        popularity=popularity,
        page=page
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

        formatted_time = time_obj.strftime("%I:%M %p").lstrip("0")

        # Create Google Calendar event link
        calendar_event = create_gcal_event(
            business_name=business_name,
            business_id=int(business_id),
            date=selected_date,
            time=time_obj.strftime("%H:%M:%S"),
            user_name=current_user.full_name,
            user_email=current_user.email,
            user_phone=current_user.phone_number
        )

        # Prepare calendar section for email
        calendar_section = ""
        if calendar_event:
            calendar_section = f"""
                    <p style="font-size: 16px; margin-top: 20px;">
                        <a href="{calendar_event['calendar_url']}" style="color: #0000EE; text-decoration: underline;">
                            📅 Add to Google Calendar
                        </a>
                    </p>
            """

        html_content = f"""
            <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
                <h2 style="color: #333; margin-top: 0;">New Appointment for {business_name}</h2>
                
                <p style="font-size: 16px; line-height: 1.6;">
                    You have a new appointment booking:
                </p>
                
                <div style="background-color: #f5f5f5; padding: 15px; border-radius: 5px; margin: 20px 0;">
                    <p style="font-size: 16px; margin: 5px 0;">
                        <strong>Name:</strong> {current_user.full_name}
                    </p>
                    <p style="font-size: 16px; margin: 5px 0;">
                        <strong>Email:</strong> {current_user.email}
                    </p>
                    <p style="font-size: 16px; margin: 5px 0;">
                        <strong>Phone:</strong> {current_user.phone_number}
                    </p>
                    <p style="font-size: 16px; margin: 5px 0;">
                        <strong>Date:</strong> {selected_date}
                    </p>
                    <p style="font-size: 16px; margin: 5px 0;">
                        <strong>Time:</strong> {formatted_time}
                    </p>
                </div>
                
                <p style="font-size: 16px;">
                    Please confirm this appointment or contact the user if the time is no longer available.
                </p>
                
                {calendar_section}
                
                <p style="margin-top: 30px; font-size: 14px; color: #666;">
                    — Localate Team
                </p>
            </div>
        """
        configuration = Configuration()
        configuration.api_key['api-key'] = current_app.config['BREVO_API_KEY']

        api_client = ApiClient(configuration)
        api_instance = TransactionalEmailsApi(api_client)

        send_smtp_email = SendSmtpEmail(
            to=[{"email": owner_email}],
            subject=f"New Appointment for {business_name}",
            html_content=html_content,
            sender={"name": "Localate", "email": current_app.config['MAIL_DEFAULT_SENDER']}
        )

        api_instance.send_transac_email(send_smtp_email)

        flash("Appointment booked successfully. Confirmation pending from owner!", "success")

    except ApiException as api_err:
            current_app.logger.error(f"Failed to send email via Brevo: {api_err}")
            flash("Appointment booked but failed to send confirmation email.", "warning")

    except Exception as e:
        print(e)
        current_app.logger.error(f"Error booking appointment: {e}")
        flash("Please update your profile on the dashboard before booking appointments.", "error")

    return redirect(request.referrer or url_for('search.customer_view', business_id=business_id))

@search_bp.route('/cancel_appointment', methods=['POST'])
@login_required
def cancel_appointment():
    supabase = current_app.supabase
    appointment_id = request.form.get('appointment_id')

    if not appointment_id:
        flash("Missing appointment ID.", "error")
        return redirect(request.referrer or url_for('search.search'))

    try:
        appt_resp = supabase.table('appointments') \
            .select('*') \
            .eq('id', appointment_id) \
            .single() \
            .execute()

        appointment = appt_resp.data
        if not appointment:
            return redirect(request.referrer or url_for('search.search'))

        if appointment['user_id'] != current_user.id:
            return redirect(request.referrer or url_for('search.search'))

        business_resp = supabase.table('businesses') \
            .select('user_id, name') \
            .eq('id', appointment['business_id']) \
            .single() \
            .execute()

        business = business_resp.data
        owner_id = business['user_id']
        business_name = business['name']
        owner_resp = supabase.table('users') \
            .select('email') \
            .eq('id', owner_id) \
            .single() \
            .execute()

        owner_email = owner_resp.data['email']

        formatted_time = datetime.strptime(appointment['time'], "%H:%M:%S").strftime("%I:%M %p").lstrip("0")

        supabase.table('appointments').delete().eq('id', appointment_id).execute()

        configuration = Configuration()
        configuration.api_key['api-key'] = current_app.config['BREVO_API_KEY']
        api_client = ApiClient(configuration)
        api_instance = TransactionalEmailsApi(api_client)

        html_content = f"""
            <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
                <h2 style="color: #d32f2f; margin-top: 0;">Appointment Canceled for {business_name}</h2>
                
                <p style="font-size: 16px; line-height: 1.6;">
                    A user has canceled their appointment:
                </p>
                
                <div style="background-color: #f5f5f5; padding: 15px; border-radius: 5px; margin: 20px 0;">
                    <p style="font-size: 16px; margin: 5px 0;">
                        <strong>Name:</strong> {appointment['name']}
                    </p>
                    <p style="font-size: 16px; margin: 5px 0;">
                        <strong>Email:</strong> {appointment['email']}
                    </p>
                    <p style="font-size: 16px; margin: 5px 0;">
                        <strong>Phone:</strong> {appointment['phone']}
                    </p>
                    <p style="font-size: 16px; margin: 5px 0;">
                        <strong>Date:</strong> {appointment['date']}
                    </p>
                    <p style="font-size: 16px; margin: 5px 0;">
                        <strong>Time:</strong> {formatted_time}
                    </p>
                </div>
                
                <p style="font-size: 16px;">
                    This slot is now reopened automatically.
                </p>
                
                <p style="margin-top: 30px; font-size: 14px; color: #666;">
                    — Localate Team
                </p>
            </div>
        """

        send_smtp_email = SendSmtpEmail(
            to=[{"email": owner_email}],
            subject=f"Appointment Canceled for {business_name}",
            html_content=html_content,
            sender={"name": "Localate", "email": current_app.config['MAIL_DEFAULT_SENDER']}
        )

        api_instance.send_transac_email(send_smtp_email)


    except ApiException as api_err:
        current_app.logger.error(f"Brevo API error: {api_err}")

    except Exception as e:
        current_app.logger.error(f"Error canceling appointment: {e}")

    return redirect(url_for('business.dashboard'))


@search_bp.route('/autocomplete')
def autocomplete():
    supabase = current_app.supabase
    query = request.args.get('q', '').strip()

    if not query:
        return jsonify([])

    response = supabase.table('businesses') \
        .select('name, review_count') \
        .ilike('name', f'%{query}%') \
        .order('review_count', desc=True) \
        .limit(10) \
        .execute()

    results = [b['name'] for b in response.data]
    return jsonify(results)

@search_bp.route('/business/<int:business_id>/trophy', methods=['POST'])
@login_required
def toggle_trophy(business_id):
    try:
        supabase = current_app.supabase
        user_id = current_user.id  # INT, not str

        # Check if business exists
        business_check = supabase.table("businesses") \
            .select("id, trophies") \
            .eq("id", business_id) \
            .execute()
        if not business_check.data:
            return jsonify({"error": "Business not found"}), 404

        current_count = business_check.data[0].get("trophies", 0)

        # Check if user already gave a trophy
        existing = supabase.table("business_trophies") \
            .select("id") \
            .eq("business_id", business_id) \
            .eq("user_id", user_id) \
            .execute()

        if existing.data:
            # Remove trophy
            supabase.table("business_trophies") \
                .delete() \
                .eq("business_id", business_id) \
                .eq("user_id", user_id) \
                .execute()
            new_count = max(current_count - 1, 0)
            toggled = "removed"
        else:
            # Add trophy
            supabase.table("business_trophies") \
                .insert({"business_id": business_id, "user_id": user_id}) \
                .execute()
            new_count = current_count + 1
            toggled = "added"

        # Update trophies count in businesses table
        supabase.table("businesses") \
            .update({"trophies": new_count}) \
            .eq("id", business_id) \
            .execute()

        return jsonify({
            "success": True,
            "new_count": new_count,
            "toggled": toggled
        })

    except Exception as e:
        print(f"Trophy error: {e}")
        return jsonify({"error": "Server error"}), 500


@search_bp.route('/business/<int:business_id>/trophy_status', methods=['GET'])
@login_required
def trophy_status(business_id):
    try:
        supabase = current_app.supabase
        user_id = current_user.id  # INT, not str

        existing = supabase.table("business_trophies") \
            .select("id") \
            .eq("business_id", business_id) \
            .eq("user_id", user_id) \
            .execute()

        return jsonify({"has_trophy": bool(existing.data)})

    except Exception as e:
        print(f"Trophy status error: {e}")
        return jsonify({"error": "Server error"}), 500
    
@search_bp.route('/leaderboard', methods=['GET'])
def leaderboard():
    supabase = current_app.supabase

    # State abbreviation map (reuse from search)
    STATE_ABBREVIATIONS = {
        'alabama': 'AL', 'alaska': 'AK', 'arizona': 'AZ', 'arkansas': 'AR', 'california': 'CA',
        'colorado': 'CO', 'connecticut': 'CT', 'delaware': 'DE', 'florida': 'FL', 'georgia': 'GA',
        'hawaii': 'HI', 'idaho': 'ID', 'illinois': 'IL', 'indiana': 'IN', 'iowa': 'IA',
        'kansas': 'KS', 'kentucky': 'KY', 'louisiana': 'LA', 'maine': 'ME', 'maryland': 'MD',
        'massachusetts': 'MA', 'michigan': 'MI', 'minnesota': 'MN', 'mississippi': 'MS', 'missouri': 'MO',
        'montana': 'MT', 'nebraska': 'NE', 'nevada': 'NV', 'new hampshire': 'NH', 'new jersey': 'NJ',
        'new mexico': 'NM', 'new york': 'NY', 'north carolina': 'NC', 'north dakota': 'ND', 'ohio': 'OH',
        'oklahoma': 'OK', 'oregon': 'OR', 'pennsylvania': 'PA', 'rhode island': 'RI', 'south carolina': 'SC',
        'south dakota': 'SD', 'tennessee': 'TN', 'texas': 'TX', 'utah': 'UT', 'vermont': 'VT',
        'virginia': 'VA', 'washington': 'WA', 'west virginia': 'WV', 'wisconsin': 'WI', 'wyoming': 'WY'
    }

    location = request.args.get('location', '').strip()
    per_page = int(request.args.get('per_page', 10))
    page = int(request.args.get('page', 1))
    offset = (page - 1) * per_page

    query = supabase.table('businesses').select('id, name, trophies, city, state', count='exact')

    if location:
        if ',' in location:
            city, state = [x.strip() for x in location.split(',', 1)]
            # match city and state
            query = query.ilike('city', f'%{city}%').ilike('state', f'%{state}%')
        else:
            # check if input is a known state abbreviation or name
            state_input = STATE_ABBREVIATIONS.get(location.lower(), None)
            if state_input:
                # only filter by state
                query = query.eq('state', state_input)
            else:
                # only filter by city
                query = query.ilike('city', f'%{location}%')

    response = query.order('trophies', desc=True).range(offset, offset + per_page - 1).execute()
    businesses = response.data or []

    return jsonify({
        "success": True,
        "leaderboard": businesses,
        "page": page,
        "per_page": per_page,
        "total": response.count or 0
    })

@search_bp.route('/business/<int:business_id>/analytics', methods=['GET'])
@login_required
def business_analytics(business_id):
    supabase = current_app.supabase
    today = date.today()

    try:
        # --- Week (last 7 days) ---
        week_start = today - timedelta(days=7)
        week_resp = supabase.table("business_analytics") \
            .select("profile_views, search_appearances") \
            .eq("business_id", business_id) \
            .gte("date", str(week_start)) \
            .execute()
        week_views = sum(r["profile_views"] for r in week_resp.data)
        week_searches = sum(r["search_appearances"] for r in week_resp.data)

        # --- Month (last 30 days) ---
        month_start = today - timedelta(days=30)
        month_resp = supabase.table("business_analytics") \
            .select("profile_views, search_appearances") \
            .eq("business_id", business_id) \
            .gte("date", str(month_start)) \
            .execute()
        month_views = sum(r["profile_views"] for r in month_resp.data)
        month_searches = sum(r["search_appearances"] for r in month_resp.data)

        # --- All time ---
        all_resp = supabase.table("business_analytics") \
            .select("profile_views, search_appearances") \
            .eq("business_id", business_id) \
            .execute()
        all_views = sum(r["profile_views"] for r in all_resp.data)
        all_searches = sum(r["search_appearances"] for r in all_resp.data)

        return jsonify({
            "success": True,
            "week": {"profile_views": week_views, "search_appearances": week_searches},
            "month": {"profile_views": month_views, "search_appearances": month_searches},
            "all_time": {"profile_views": all_views, "search_appearances": all_searches}
        })

    except Exception as e:
        current_app.logger.error(f"Error fetching analytics for business {business_id}: {e}")
        return jsonify({"success": False, "error": "Could not fetch analytics"}), 500