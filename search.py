from flask import Blueprint, render_template, request, current_app
from flask_login import login_required

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

    #if not business:
        #flash("Business not found", "danger")
       # return redirect(url_for('search.search'))

    return render_template(
        'customer_view.html',
        business=business,
        q=request.args.get('q', ''),
        category=request.args.get('category', ''),
        city=request.args.get('city', ''),
        state=request.args.get('state', '')
    )