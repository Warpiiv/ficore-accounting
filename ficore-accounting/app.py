from flask import Flask, session, redirect, url_for, flash, render_template, request, Response
from flask_pymongo import PyMongo
from flask_cors import CORS
from flask_login import LoginManager, UserMixin, login_user, current_user
from flask_mail import Mail, Message
from werkzeug.security import generate_password_hash
from datetime import datetime, timedelta
import os
import jinja2
from flask_wtf import CSRFProtect
import logging
from bson import ObjectId
from translations import TRANSLATIONS
from utils import trans_function
from flask_session import Session

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__, template_folder='templates')
CORS(app)
CSRFProtect(app)

# Configuration
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'your-secret-key')
app.config['MONGO_URI'] = os.getenv('MONGO_URI', 'mongodb://localhost:27017/minirecords')
app.config['SESSION_TYPE'] = 'mongodb'
app.config['SESSION_MONGODB_DB'] = 'minirecords'
app.config['SESSION_MONGODB_COLLECT'] = 'sessions'
app.config['SESSION_PERMANENT'] = True
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(seconds=3600)
app.config['SESSION_COOKIE_SECURE'] = os.getenv('FLASK_ENV', 'development') == 'production'
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.jinja_env.undefined = jinja2.Undefined

# Flask-Mail configuration
app.config['MAIL_SERVER'] = os.getenv('MAIL_SERVER', 'smtp.gmail.com')
app.config['MAIL_PORT'] = int(os.getenv('MAIL_PORT', 587))
app.config['MAIL_USE_TLS'] = os.getenv('MAIL_USE_TLS', 'true').lower() == 'true'
app.config['MAIL_USERNAME'] = os.getenv('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.getenv('MAIL_PASSWORD')
app.config['MAIL_DEFAULT_SENDER'] = os.getenv('MAIL_DEFAULT_SENDER', 'support@ficoreminirecords.com')

# Initialize extensions after app creation
mongo = PyMongo(app)
app.config['SESSION_MONGODB'] = mongo.cx  # Set MongoDB connection for Flask-Session
mail = Mail(app)
sess = Session(app)

# Initialize Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'users.login'

# User model for Flask-Login
class User(UserMixin):
    def __init__(self, id, email):
        self.id = id
        self.email = email

# User loader for Flask-Login
@login_manager.user_loader
def load_user(user_id):
    user_data = mongo.db.users.find_one({'_id': user_id})
    if user_data:
        return User(user_id, user_data.get('email'))
    return None

# Register blueprints
from invoices.routes import invoices_bp, init_mongo
from transactions.routes import transactions_bp
from users.routes import users_bp

# Initialize mongo for invoices blueprint
init_mongo(app)

app.register_blueprint(invoices_bp, url_prefix='/invoices')
app.register_blueprint(transactions_bp, url_prefix='/transactions')
app.register_blueprint(users_bp, url_prefix='/users')

app.jinja_env.globals['trans'] = trans_function

@app.template_filter('trans')
def trans_filter(key):
    return trans_function(key)

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

@app.template_filter('format_date')
def format_date(value):
    try:
        if isinstance(value, datetime):
            return value.strftime('%Y-%m-%d')
        return str(value)
    except Exception as e:
        logger.warning(f"Error formatting date {value}: {str(e)}")
        return str(value)

@app.route('/api/translations/<lang>')
def get_translations(lang):
    return {'translations': TRANSLATIONS.get(lang, TRANSLATIONS['en'])}

@app.route('/setlang/<lang>')
def set_language(lang):
    valid_langs = ['en', 'ha']
    if lang in valid_langs:
        session['lang'] = lang
        flash(trans_function('language_updated'), 'success')
    else:
        session['lang'] = 'en'
        flash(trans_function('invalid_language'), 'danger')
    return redirect(request.referrer or url_for('index'))

@app.route('/set_dark_mode', methods=['POST'])
def set_dark_mode():
    data = request.get_json()
    session['dark_mode'] = str(data.get('dark_mode', False)).lower()
    return Response(status=204)

# Database setup
def setup_database():
    try:
        # Create users collection and indexes
        mongo.db.users.create_index([('_id', 1)], unique=True)
        mongo.db.users.create_index([('email', 1)], unique=True)
        mongo.db.users.create_index([('reset_token', 1)], sparse=True)

        # Create default admin user if not exists
        if not mongo.db.users.find_one({'_id': 'admin'}):
            mongo.db.users.insert_one({
                '_id': 'admin',
                'email': 'ficoreafrica@gmail.com',
                'password': generate_password_hash('Admin123!'),
                'dark_mode': False,
                'is_admin': True,
                'created_at': datetime.utcnow()
            })
            logger.info("Default admin user created")

        # Create invoices collection and indexes
        mongo.db.invoices.create_index([('user_id', 1)])
        mongo.db.invoices.create_index([('created_at', -1)])
        mongo.db.invoices.create_index([('status', 1)])
        mongo.db.invoices.create_index([('due_date', 1)])
        mongo.db.invoices.create_index([('invoice_number', 1)], unique=True)

        # Create transactions collection and indexes
        mongo.db.transactions.create_index([('user_id', 1)])
        mongo.db.transactions.create_index([('created_at', -1)])

        # Create feedback collection and indexes
        mongo.db.feedback.create_index([('user_id', 1)], sparse=True)
        mongo.db.feedback.create_index([('timestamp', -1)])

        # Create sessions collection index
        mongo.db.sessions.create_index([('expires', 1)], expireAfterSeconds=0)

        logger.info("Database initialization completed successfully")
        return True
    except Exception as e:
        logger.error(f"Error initializing database: {str(e)}")
        return False

# Manual database setup route
@app.route('/setup', methods=['GET'])
def setup_database_route():
    setup_key = request.args.get('key')
    if setup_key != os.getenv('SETUP_KEY', 'setup-secret'):
        return render_template('errors/403.html'), 403
    
    if os.getenv('FLASK_ENV', 'development') == 'production' and not os.getenv('ALLOW_DB_SETUP', 'false').lower() == 'true':
        flash(trans_function('database_setup_production_disabled'), 'danger')
        return render_template('errors/403.html'), 403

    if setup_database():
        flash(trans_function('database_setup_success'), 'success')
        return redirect(url_for('index'))
    else:
        flash(trans_function('database_setup_error'), 'danger')
        return render_template('errors/500.html'), 500

# General routes
@app.route('/')
def index():
    return render_template('general/home.html')

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

            if not tool_name or tool_name not in tool_options:
                flash(trans_function('invalid_tool'), 'danger')
                return render_template('general/feedback.html', tool_options=tool_options)
            if not rating or not rating.isdigit() or int(rating) < 1 or int(rating) > 5:
                flash(trans_function('invalid_rating'), 'danger')
                return render_template('general/feedback.html', tool_options=tool_options)

            feedback_entry = {
                'user_id': None,
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
@app.errorhandler(403)
def forbidden(e):
    return render_template('errors/403.html', message=trans_function('forbidden')), 403

@app.errorhandler(404)
def page_not_found(e):
    return render_template('errors/404.html', message=trans_function('page_not_found')), 404

@app.errorhandler(500)
def internal_server_error(e):
    return render_template('errors/500.html', message=trans_function('internal_server_error')), 500

# Initialize database on startup
with app.app_context():
    if os.getenv('FLASK_ENV', 'development') != 'production' or os.getenv('ALLOW_DB_SETUP', 'false').lower() == 'true':
        if not setup_database():
            logger.error("Application startup aborted due to database initialization failure")
            raise RuntimeError("Database initialization failed")
    else:
        logger.info("Database initialization skipped in production environment")

if __name__ == '__main__':
    port = int(os.getenv('PORT', 10000))
    logger.info(f"Starting Flask app on port {port}")
    app.run(host='0.0.0.0', port=port, debug=False)