from flask import Blueprint, render_template, request, current_app, redirect, url_for, flash
from flask_login import login_required, current_user
from datetime import datetime
from extensions import mail
from math import ceil
from datetime import datetime, date
import pytz
from flask import jsonify
from sib_api_v3_sdk import Configuration, ApiClient
from sib_api_v3_sdk.api.transactional_emails_api import TransactionalEmailsApi
from sib_api_v3_sdk.models.send_smtp_email import SendSmtpEmail
from sib_api_v3_sdk.rest import ApiException
#gcal imports
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import os.path


search_bp = Blueprint('search', __name__, url_prefix='/search')

def create_gcal_event(business_name, business_id, date, time, user_name, user_email, user_phone):
    creds = Credentials.from_authorized_user_file('credentials.json', ['https://www.googleapis.com/auth/calendar'])
    service = build('calendar', 'v3', credentials=creds)

    event = {
        'summary': f'Appointment with {business_name}',
        'description': f'{user_name} has booked an appointment with {business_name} on {date} at {time}.',
        'start': {
            'dateTime': f'{date}T{time}:00',
            'timeZone': 'America/New_York'
        },
        'end': {
    }
}
    
    
@search_bp.route('/', methods=['GET'])
def search():
    supabase = current_app.supabase
    query = request.args.get('q', '').strip()
    category = request.args.get('category', '').strip()
    state = request.args.get('state', '').strip()
    popularity = request.args.get('popularity', '').strip()
    page = int(request.args.get('page', 1))
    per_page = 5
    offset = (page - 1) * per_page

    filters = supabase.table('businesses').select('*', count='exact')

    if query:
        filters = filters.or_(
            f"name.ilike.%{query}%,city.ilike.%{query}%"
        )
    if category:
        filters = filters.eq('category', category)
    if state:
        filters = filters.eq('state', state)

    if popularity == 'most':
        filters = filters.order('review_count', desc=True)
    elif popularity == 'least':
        filters = filters.order('review_count', desc=False)

    response = filters.range(offset, offset + per_page - 1).execute()

    businesses = response.data or []
    total_count = response.count or 0

    total_pages = ceil(total_count / per_page)

    return render_template(
        'search.html',
        businesses=businesses,
        popularity=popularity,
        page=page,
        total_pages=total_pages,
        query=query,
        category=category,
        state=state
    )

@search_bp.route('/customer_view/<int:business_id>')
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

        formatted_time = time_obj.strftime("%I:%M %p").lstrip("0")

        html_content = f"""
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
            <!DOCTYPE html>
            <html>
            <body style="background-color: #1e1e1e; color: #e0e0e0; font-family: Arial, sans-serif; padding: 20px;">
                <table width="100%" cellpadding="0" cellspacing="0" style="max-width: 600px; margin: auto; background-color: #2b2b2b; border-radius: 8px;">
                <tr>
                    <td style="padding: 30px;">
                    <h2 style="color: #ff6b6b; margin-top: 0;">Appointment Canceled for {business_name}</h2>

                    <p style="font-size: 16px; line-height: 1.6;">
                        A user has canceled their appointment:
                    </p>

                    <hr style="border: 1px solid #444;" />

                    <p style="font-size: 16px;">
                        <strong>Name:</strong> {appointment['name']}<br>
                        <strong>Email:</strong> {appointment['email']}<br>
                        <strong>Phone:</strong> {appointment['phone']}<br>
                        <strong>Date:</strong> {appointment['date']}<br>
                        <strong>Time:</strong> {formatted_time}
                    </p>

                    <hr style="border: 1px solid #444;" />

                    <p style="font-size: 16px;">
                        This slot is now reopened automatically.
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
