from flask import Flask, session, redirect, url_for, flash, render_template, request, Response
from flask_pymongo import PyMongo
from flask_cors import CORS
from flask_login import LoginManager, UserMixin, login_user, current_user, logout_user
from datetime import datetime
import os
import jinja2
from flask_wtf import CSRFProtect
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__, template_folder='templates')
CORS(app)
CSRFProtect(app)

# Configuration
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'your-secret-key')
app.config['MONGO_URI'] = os.getenv('MONGO_URI')
app.config['SESSION_TYPE'] = 'filesystem'
app.config['PERMANENT_SESSION_LIFETIME'] = 3600
app.jinja_env.undefined = jinja2.Undefined  # Ensure undefined variables don’t crash

mongo = PyMongo(app)

# Initialize Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'signin'

# Simple User model for Flask-Login
class User(UserMixin):
    def __init__(self, id):
        self.id = id

# User loader for Flask-Login
@login_manager.user_loader
def load_user(user_id):
    # Replace with actual user lookup from MongoDB
    user_data = mongo.db.users.find_one({'_id': user_id})
    if user_data:
        return User(user_id)
    return None

# Register blueprints
from invoices.routes import invoices_bp
from transactions.routes import transactions_bp
from users.routes import users_bp
app.register_blueprint(invoices_bp, url_prefix='/invoices')
app.register_blueprint(transactions_bp, url_prefix='/transactions')
app.register_blueprint(users_bp, url_prefix='/users')

# Translations
from translations import TRANSLATIONS

# Define translation function for global use and filter
def trans_function(key):
    try:
        lang = session.get('lang', 'en')
        translation = TRANSLATIONS.get(lang, {}).get(key, key)
        if translation == key:
            logger.info(f"Missing translation for key '{key}' in language '{lang}'")
        return translation
    except Exception as e:
        logger.error(f"Error in trans function: {e}")
        return key  # Fallback to key on error

# Add trans as a global function
app.jinja_env.globals['trans'] = trans_function

# Add trans as a filter for fallback compatibility
@app.template_filter('trans')
def trans_filter(key):
    return trans_function(key)  # Reuse the same logic

# Add number formatting filters
@app.template_filter('format_number')
def format_number(value):
    try:
        if isinstance(value, (int, float)):
            return f"{float(value):,.2f}"
        return str(value)
    except (ValueError, TypeError) as e:
        logger.warning(f"Error formatting number {value}: {str(e)}")
        return str(value)

@app.template_filter('format_currency')
def format_currency(value):
    try:
        value = float(value)
        if value.is_integer():
            return f"₦{int(value):,}"
        return f"₦{value:,.2f}"
    except (TypeError, ValueError) as e:
        logger.warning(f"Error formatting currency {value}: {str(e)}")
        return str(value)

@app.template_filter('format_datetime')
def format_datetime(value):
    try:
        if isinstance(value, datetime):
            return value.strftime('%B %d, %Y, %I:%M %p')
        return str(value)
    except Exception as e:
        logger.warning(f"Error formatting datetime {value}: {str(e)}")
        return str(value)

@app.route('/api/translations/<lang>')
def get_translations(lang):
    return {'translations': TRANSLATIONS.get(lang, TRANSLATIONS['en'])}

# Language switching route
@app.route('/setlang/<lang>')
def set_language(lang):
    # Validate language to prevent invalid session values
    valid_langs = ['en', 'ha']  # Add supported languages as needed
    if lang in valid_langs:
        session['lang'] = lang
        flash(trans_function('language_updated'), 'success')
    else:
        session['lang'] = 'en'
        flash(trans_function('invalid_language'), 'danger')
    return redirect(request.referrer or url_for('index'))

# Dark mode toggle route
@app.route('/set_dark_mode', methods=['POST'])
def set_dark_mode():
    data = request.get_json()
    session['dark_mode'] = str(data.get('dark_mode', False)).lower()
    if current_user.is_authenticated:
        mongo.db.users.update_one(
            {'_id': current_user.id},
            {'$set': {'dark_mode': session['dark_mode'] == 'true'}}
        )
    return Response(status=204)

# Logout route
@app.route('/logout')
def logout():
    logout_user()
    flash(trans_function('logged_out'), 'success')
    return redirect(url_for('index'))

# General routes
@app.route('/')
def index():
    return redirect(url_for('invoices.invoice_dashboard'))

@app.route('/about')
def about():
    return render_template('general/about.html')

@app.route('/feedback', methods=['GET', 'POST'])
def feedback():
    lang = session.get('lang', 'en')
    tool_options = ['invoices', 'transactions', 'profile']
    if request.method == 'POST':
        try:
            tool_name = request.form.get('tool_name')
            rating = request.form.get('rating')
            comment = request.form.get('comment', '').strip()

            # Validate inputs
            if not tool_name or tool_name not in tool_options:
                flash(trans_function('invalid_tool'), 'danger')
                return render_template('general/feedback.html', tool_options=tool_options)
            if not rating or not rating.isdigit() or int(rating) < 1 or int(rating) > 5:
                flash(trans_function('invalid_rating'), 'danger')
                return render_template('general/feedback.html', tool_options=tool_options)

            # Store feedback in MongoDB
            feedback_entry = {
                'user_id': current_user.id if current_user.is_authenticated else None,
                'tool_name': tool_name,
                'rating': int(rating),
                'comment': comment or None,
                'timestamp': datetime.utcnow()
            }
            mongo.db.feedback.insert_one(feedback_entry)
            flash(trans_function('feedback_success'), 'success')
            return redirect(url_for('index'))
        except Exception as e:
            logger.error(f"Error processing feedback: {str(e)}")
            flash(trans_function('feedback_error'), 'danger')
            return render_template('general/feedback.html', tool_options=tool_options), 500

    return render_template('general/feedback.html', tool_options=tool_options)

@app.route('/dashboard/admin')
def admin_dashboard():
    return render_template('dashboard/admin_dashboard.html')

@app.route('/dashboard/general')
def general_dashboard():
    return render_template('dashboard/general_dashboard.html')

# Error handlers
@app.errorhandler(404)
def page_not_found(e):
    return render_template('errors/404.html'), 404

@app.errorhandler(500)
def internal_server_error(e):
    return render_template('errors/500.html'), 500

# Auth routes
@app.route('/auth/signin', methods=['GET', 'POST'])
def signin():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    if request.method == 'POST':
        # Placeholder: Replace with actual authentication logic
        user_id = request.form.get('user_id')  # Example form field
        user = mongo.db.users.find_one({'_id': user_id})
        if user:
            login_user(User(user_id))
            flash(trans_function('logged_in'), 'success')
            return redirect(url_for('index'))
        flash(trans_function('invalid_credentials'), 'danger')
    return render_template('auth/signin.html')

@app.route('/auth/signup')
def signup():
    return render_template('auth/signup.html')

@app.route('/auth/forgot-password')
def forgot_password():
    return render_template('auth/forgot_password.html')

@app.route('/auth/reset-password')
def reset_password():
    return render_template('auth/reset_password.html')

if __name__ == '__main__':
    port = int(os.getenv('PORT', 10000))
    app.run(host='0.0.0.0', port=port, debug=False)
