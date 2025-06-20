from flask import Flask, session, redirect, url_for, flash, render_template, request, Response
from flask_pymongo import PyMongo
from flask_cors import CORS
from flask_login import LoginManager, UserMixin, login_user, current_user, login_required
from flask_mail import Mail, Message
from werkzeug.security import generate_password_hash
from datetime import datetime, date, timedelta
import os
import jinja2
from flask_wtf import CSRFProtect
import logging
from bson import ObjectId
from translations import TRANSLATIONS
from utils import trans_function, is_valid_email
from flask_session import Session
from pymongo import ASCENDING, DESCENDING, errors
from pymongo.operations import UpdateOne
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from itsdangerous import URLSafeTimedSerializer

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__, template_folder='templates', static_folder='static')
CORS(app)
CSRFProtect(app)

# Ensure SECRET_KEY is set securely
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')
if not app.config['SECRET_KEY']:
    raise ValueError("SECRET_KEY must be set in environment variables")
app.config['MONGO_URI'] = os.getenv('MONGO_URI', 'mongodb://localhost:27017/minirecords')
app.config['SESSION_TYPE'] = 'mongodb'
app.config['SESSION_MONGODB_DB'] = 'minirecords'
app.config['SESSION_MONGODB_COLLECTION'] = 'sessions'
app.config['SESSION_PERMANENT'] = False
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(minutes=30)
app.config['SESSION_COOKIE_SECURE'] = os.getenv('FLASK_ENV', 'development') == 'production'
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.jinja_env.undefined = jinja2.Undefined

# Dynamically fetch social links from environment variables
app.config['FACEBOOK_URL'] = os.getenv('FACEBOOK_URL', 'https://www.facebook.com')
app.config['TWITTER_URL'] = os.getenv('TWITTER_URL', 'https://www.twitter.com')
app.config['LINKEDIN_URL'] = os.getenv('LINKEDIN_URL', 'https://www.linkedin.com')

app.config['MAIL_SERVER'] = os.getenv('MAIL_SERVER', 'smtp.gmail.com')
app.config['MAIL_PORT'] = int(os.getenv('MAIL_PORT', 587))
app.config['MAIL_USE_TLS'] = os.getenv('MAIL_USE_TLS', 'true').lower() == 'true'
app.config['MAIL_USERNAME'] = os.getenv('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.getenv('MAIL_PASSWORD')
app.config['MAIL_DEFAULT_SENDER'] = os.getenv('MAIL_DEFAULT_SENDER', 'support@ficoreminirecords.com')

mongo = PyMongo(app)
app.extensions = getattr(app, 'extensions', {})
app.extensions['pymongo'] = mongo
app.config['SESSION_MONGODB'] = mongo.cx
mail = Mail(app)
sess = Session(app)

# Initialize Limiter for rate limiting
limiter = Limiter(get_remote_address, app=app, default_limits=["100 per day", "100 per hour"])
# Initialize Serializer for secure tokens
serializer = URLSafeTimedSerializer(app.config['SECRET_KEY'])

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'users.login'

class User(UserMixin):
    def __init__(self, id, email, display_name=None):
        self.id = id
        self.email = email
        self.display_name = display_name or id  # Default to id if no display_name

    def is_active(self):
        return True

    def is_anonymous(self):
        return False

    def is_authenticated(self):
        return True

    def get_id(self):
        return self.id

@login_manager.user_loader
def load_user(user_id):
    try:
        user_data = mongo.db.users.find_one({'_id': user_id})
        if user_data:
            return User(str(user_data['_id']), user_data.get('email'), user_data.get('display_name'))
        return None
    except Exception as e:
        logger.error(f"Error loading user {user_id}: {str(e)}")
        return None

from invoices.routes import invoices_bp
from transactions.routes import transactions_bp
from users.routes import users_bp

app.register_blueprint(invoices_bp, url_prefix='/invoices')
app.register_blueprint(transactions_bp, url_prefix='/transactions')
app.register_blueprint(users_bp, url_prefix='/users')

# Register Jinja2 filters and globals within app context
with app.app_context():
    # Register social links as Jinja2 globals
    app.jinja_env.globals['FACEBOOK_URL'] = app.config['FACEBOOK_URL']
    app.jinja_env.globals['TWITTER_URL'] = app.config['TWITTER_URL']
    app.jinja_env.globals['LINKEDIN_URL'] = app.config['LINKEDIN_URL']

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
            elif isinstance(value, date):
                return value.strftime('%B %d, %Y')
            elif isinstance(value, str):
                parsed = datetime.strptime(value, '%Y-%m-%d')
                return parsed.strftime('%B %d, %Y, %I:%M %p')
            return str(value)
        except Exception as e:
            logger.warning(f"Error formatting datetime {value}: {str(e)}")
            return str(value)

    @app.template_filter('format_date')
    def format_date(value):
        try:
            if isinstance(value, datetime):
                return value.strftime('%Y-%m-%d')
            elif isinstance(value, date):
                return value.strftime('%Y-%m-%d')
            elif isinstance(value, str):
                parsed = datetime.strptime(value, '%Y-%m-%d').date()
                return parsed.strftime('%Y-%m-%d')
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
        flash(trans_function('language_updated', default='Language updated'), 'success')
    else:
        session['lang'] = 'en'
        flash(trans_function('invalid_language', default='Invalid language'), 'danger')
    return redirect(request.referrer or url_for('index'))

@app.route('/set_dark_mode', methods=['POST'])
def set_dark_mode():
    data = request.get_json()
    session['dark_mode'] = str(data.get('dark_mode', False)).lower()
    return Response(status=204)

def setup_database():
    try:
        db = mongo.db
        collections = db.list_collection_names()

        # Test MongoDB connection
        db.command('ping')
        logger.info("MongoDB connection successful")

        # Clean up shared 'guest' data
        try:
            db.invoices.delete_many({'user_id': 'guest'})
            db.transactions.delete_many({'user_id': 'guest'})
            db.feedback.delete_many({'user_id': {'$in': ['guest', None]}})
            logger.info("Cleaned up shared 'guest' data")
        except Exception as e:
            logger.error(f"Error cleaning up guest data: {str(e)}")

        if 'users' not in collections:
            db.create_collection('users')
            logger.info("Created users collection")

        users_indexes = db.users.index_information()
        if 'email_1' not in users_indexes:
            try:
                db.users.create_index([('email', ASCENDING)], unique=True)
                logger.info("Created email index on users")
            except errors.DuplicateKeyError as e:
                logger.warning(f"Duplicate key error for email index, skipping: {str(e)}")
            except Exception as e:
                logger.error(f"Could not create email index: {str(e)}")

        if 'reset_token_1' not in users_indexes:
            try:
                db.users.create_index([('reset_token', ASCENDING)], sparse=True)
                logger.info("Created reset_token index on users")
            except errors.DuplicateKeyError as e:
                logger.warning(f"Duplicate key error for reset_token index, skipping: {str(e)}")
            except Exception as e:
                logger.error(f"Could not create reset_token index: {str(e)}")

        if 'setup_complete_1' not in users_indexes:
            try:
                db.users.create_index([('setup_complete', ASCENDING)])
                logger.info("Created setup_complete index on users")
            except Exception as e:
                logger.error(f"Could not create setup_complete index: {str(e)}")

        try:
            result = db.users.update_many(
                {'setup_complete': {'$exists': False}},
                {'$set': {'setup_complete': False, 'display_name': ''}}
            )
            logger.info(f"Updated {result.modified_count} user documents with setup_complete and display_name fields")
        except Exception as e:
            logger.error(f"Error updating users with setup_complete field: {str(e)}")

        # Create admin user from environment variables
        admin_username = os.getenv('ADMIN_USERNAME', 'admin')
        admin_email = os.getenv('ADMIN_EMAIL', 'admin@ficoreminirecords.com')
        admin_password = os.getenv('ADMIN_PASSWORD', 'Admin123!')
        if not db.users.find_one({'_id': admin_username}):
            try:
                db.users.insert_one({
                    '_id': admin_username.lower(),
                    'email': admin_email.lower(),
                    'password': generate_password_hash(admin_password),
                    'dark_mode': False,
                    'is_admin': True,
                    'setup_complete': False,
                    'display_name': admin_username,
                    'created_at': datetime.utcnow()
                })
                logger.info(f"Default admin user created: username={admin_username}, email={admin_email}")
            except errors.DuplicateKeyError:
                logger.info(f"Admin user {admin_username} already exists, skipping creation")
            except Exception as e:
                logger.error(f"Error creating admin user: {str(e)}")

        if 'invoices' not in collections:
            db.create_collection('invoices')
            logger.info("Created invoices collection")

        invoices_indexes = db.invoices.index_information()
        if 'invoice_number_1' not in invoices_indexes:
            try:
                null_count = db.invoices.count_documents({'invoice_number': None})
                if null_count > 0:
                    logger.info(f"Found {null_count} invoices with null invoice_number. Assigning unique values...")
                    operations = [
                        UpdateOne(
                            {'_id': doc['_id']},
                            {'$set': {'invoice_number': str(i).zfill(6)}}
                        )
                        for i, doc in enumerate(db.invoices.find({'invoice_number': None}), start=1)
                    ]
                    if operations:
                        db.invoices.bulk_write(operations, ordered=True)
                    logger.info("Updated null invoice_numbers with unique values")

                db.invoices.create_index([('user_id', ASCENDING)])
                db.invoices.create_index([('created_at', DESCENDING)])
                db.invoices.create_index([('status', ASCENDING)])
                db.invoices.create_index([('due_date', ASCENDING)])
                db.invoices.create_index([('invoice_number', ASCENDING)], unique=True)
                logger.info("Created indexes on invoices")
            except errors.DuplicateKeyError as e:
                logger.warning(f"Duplicate key error for invoice indexes, skipping: {str(e)}")
            except Exception as e:
                logger.error(f"Could not create invoice indexes: {str(e)}")

        if 'transactions' not in collections:
            db.create_collection('transactions')
            logger.info("Created transactions collection")

        transactions_indexes = db.transactions.index_information()
        if 'user_id_1' not in transactions_indexes:
            try:
                db.transactions.create_index([('user_id', ASCENDING)])
                db.transactions.create_index([('created_at', DESCENDING)])
                db.transactions.create_index([('category', ASCENDING)])
                db.transactions.create_index([('description', ASCENDING)])
                logger.info("Created indexes on transactions")
            except errors.DuplicateKeyError as e:
                logger.warning(f"Duplicate key error for transaction indexes, skipping: {str(e)}")
            except Exception as e:
                logger.error(f"Could not create transaction indexes: {str(e)}")

        if 'feedback' not in collections:
            db.create_collection('feedback')
            logger.info("Created feedback collection")

        feedback_indexes = db.feedback.index_information()
        if 'user_id_1' not in feedback_indexes:
            try:
                db.feedback.create_index([('user_id', ASCENDING)], sparse=True)
                db.feedback.create_index([('timestamp', DESCENDING)])
                logger.info("Created indexes on feedback")
            except errors.DuplicateKeyError as e:
                logger.warning(f"Duplicate key error for feedback indexes, skipping: {str(e)}")
            except Exception as e:
                logger.error(f"Could not create feedback indexes: {str(e)}")

        if 'sessions' not in collections:
            db.create_collection('sessions')
            logger.info("Created sessions collection")

        sessions_indexes = db.sessions.index_information()
        if 'expires_1' not in sessions_indexes:
            try:
                db.sessions.create_index([('expires', ASCENDING)], expireAfterSeconds=0)
                logger.info("Created index on sessions")
            except errors.DuplicateKeyError as e:
                logger.warning(f"Duplicate key error for sessions index, skipping: {str(e)}")
            except Exception as e:
                logger.error(f"Could not create session index: {str(e)}")

        try:
            db.command({
                'collMod': 'feedback',
                'validator': {
                    '$jsonSchema': {
                        'bsonType': 'object',
                        'required': ['timestamp'],
                        'properties': {
                            'user_id': {'bsonType': ['string', 'null']},
                            'timestamp': {'bsonType': 'date'},
                            'comment': {'bsonType': 'string'},
                            'rating': {'bsonType': ['int', 'double', 'null']}
                        }
                    }
                }
            })
            logger.info("Set schema validation for feedback collection")
        except Exception as e:
            logger.warning(f"Could not set schema validation for feedback collection: {str(e)}")

        logger.info("Database setup completed successfully")
        return True
    except Exception as e:
        logger.error(f"Error initializing database: {str(e)}")
        return False

# Server-side setup enforcement
def verify_setup_completion():
    if current_user.is_authenticated:
        try:
            mongo = app.extensions['pymongo']
            user = mongo.db.users.find_one({'_id': current_user.id})
            if user and not user.get('setup_complete', False):
                return redirect(url_for('users.setup_wizard'))
        except Exception as e:
            logger.error(f"Error verifying setup completion: {str(e)}")
            flash(trans_function('core_something_went_wrong'), 'danger')
            return redirect(url_for('index'))
    return None

@app.route('/setup', methods=['GET'])
def setup_database_route():
    setup_key = request.args.get('key')
    if setup_key != os.getenv('SETUP_KEY', 'setup-secret'):
        return render_template('errors/403.html', content=trans_function('forbidden_access', default='Access denied')), 403

    if os.getenv('FLASK_ENV', 'development') == 'production' and not os.getenv('ALLOW_DB_SETUP', 'false').lower() == 'true':
        flash(trans_function('database_setup_disabled', default='Database setup disabled in production'), 'danger')
        return render_template('errors/403.html', content=trans_function('forbidden_access', default='Access denied')), 403

    if setup_database():
        flash(trans_function('database_setup_success', default='Database setup successful'), 'success')
        return redirect(url_for('index'))
    else:
        flash(trans_function('database_setup_error', default='Database setup failed'), 'danger')
        return render_template('errors/500.html', content=trans_function('internal_error', default='Internal server error')), 500

@app.route('/')
def index():
    redirect_response = verify_setup_completion()
    if redirect_response:
        return redirect_response
    return render_template('general/home.html')

@app.route('/about')
def about():
    redirect_response = verify_setup_completion()
    if redirect_response:
        return redirect_response
    return render_template('general/about.html')

@app.route('/feedback', methods=['GET', 'POST'])
@login_required
def feedback():
    redirect_response = verify_setup_completion()
    if redirect_response:
        return redirect_response
    lang = session.get('lang', 'en')
    tool_options = [['invoices', trans_function('tool_invoices', default='Invoices')],
                    ['transactions', trans_function('tool_transactions', default='Transactions')],
                    ['profile', trans_function('tool_profile', default='Profile')]]
    
    if request.method == 'POST':
        try:
            tool_name = request.form.get('tool_name')
            rating = request.form.get('rating')
            comment = request.form.get('comment', '').strip()

            valid_tools = [option[0] for option in tool_options]
            if not tool_name or tool_name not in valid_tools:
                flash(trans_function('invalid_tool', default='Invalid tool selected'), 'danger')
                return render_template('general/feedback.html', tool_options=tool_options)
            
            if not rating or not rating.isdigit() or int(rating) < 1 or int(rating) > 5:
                flash(trans_function('invalid_rating', default='Invalid rating'), 'danger')
                return render_template('general/feedback.html', tool_options=tool_options)

            feedback_entry = {
                'user_id': str(current_user.id),
                'tool_name': tool_name,
                'rating': int(rating),
                'comment': comment or None,
                'timestamp': datetime.utcnow()
            }
            mongo.db.feedback.insert_one(feedback_entry)
            flash(trans_function('feedback_success', default='Feedback submitted successfully'), 'success')
            return redirect(url_for('index'))

        except Exception as e:
            logger.error(f"Error processing feedback: {str(e)}")
            flash(trans_function('feedback_error', default='Error submitting feedback'), 'danger')
            return render_template('general/feedback.html', tool_options=tool_options), 500

    return render_template('general/feedback.html', tool_options=tool_options)

@app.route('/dashboard/admin')
@login_required
def admin_dashboard():
    redirect_response = verify_setup_completion()
    if redirect_response:
        return redirect_response
    try:
        mongo = app.extensions['pymongo']
        user = mongo.db.users.find_one({'_id': current_user.id})
        if not user.get('is_admin', False):
            flash(trans_function('forbidden_access', default='Access denied'), 'danger')
            return redirect(url_for('index')), 403
        invoices = list(mongo.db.invoices.find().sort('created_at', DESCENDING).limit(100))
        transactions = list(mongo.db.transactions.find().sort('created_at', DESCENDING).limit(100))
        for invoice in invoices:
            invoice['_id'] = str(invoice['_id'])
            if isinstance(invoice.get('created_at'), str):
                try:
                    invoice['created_at'] = datetime.strptime(invoice['created_at'], '%Y-%m-%d')
                except ValueError:
                    pass
            if isinstance(invoice.get('due_date'), str):
                try:
                    invoice['due_date'] = datetime.strptime(invoice['due_date'], '%Y-%m-%d')
                except ValueError:
                    pass
            if isinstance(invoice.get('settled_date'), str):
                try:
                    invoice['settled_date'] = datetime.strptime(invoice['settled_date'], '%Y-%m-%d')
                except ValueError:
                    pass
        for transaction in transactions:
            transaction['_id'] = str(transaction['_id'])
            if isinstance(transaction.get('created_at'), str):
                try:
                    transaction['created_at'] = datetime.strptime(transaction['created_at'], '%Y-%m-%d')
                except ValueError:
                    pass
        return render_template('dashboard/admin_dashboard.html', invoices=invoices, transactions=transactions)
    except Exception as e:
        logger.error(f"Error loading admin dashboard: {str(e)}")
        flash(trans_function('core_something_went_wrong', default='An error occurred, please try again'), 'danger')
        return redirect(url_for('index')), 500

@app.route('/dashboard/general')
@login_required
def general_dashboard():
    redirect_response = verify_setup_completion()
    if redirect_response:
        return redirect_response
    try:
        mongo = app.extensions['pymongo']
        user = mongo.db.users.find_one({'_id': current_user.id})
        query = {'user_id': str(current_user.id)}
        if user.get('is_admin', False):
            query = {}  # Admins can see all data
        recent_invoices = list(mongo.db.invoices.find(query).sort('created_at', DESCENDING).limit(100))
        recent_transactions = list(mongo.db.transactions.find(query).sort('created_at', DESCENDING).limit(100))

        for invoice in recent_invoices:
            invoice['_id'] = str(invoice['_id'])
            if isinstance(invoice.get('created_at'), str):
                try:
                    invoice['created_at'] = datetime.strptime(invoice['created_at'], '%Y-%m-%d')
                except ValueError:
                    pass
            if isinstance(invoice.get('due_date'), str):
                try:
                    invoice['due_date'] = datetime.strptime(invoice['due_date'], '%Y-%m-%d')
                except ValueError:
                    pass
            if isinstance(invoice.get('settled_date'), str):
                try:
                    invoice['settled_date'] = datetime.strptime(invoice['settled_date'], '%Y-%m-%d')
                except ValueError:
                    pass
        
        for transaction in recent_transactions:
            transaction['_id'] = str(transaction['_id'])
            if isinstance(transaction.get('created_at'), str):
                try:
                    transaction['created_at'] = datetime.strptime(transaction['created_at'], '%Y-%m-%d')
                except ValueError:
                    pass

        return render_template('dashboard/general_dashboard.html',
                             recent_invoices=recent_invoices,
                             recent_transactions=recent_transactions)
    except Exception as e:
        logger.error(f"Error fetching dashboard data: {str(e)}")
        flash(trans_function('core_something_went_wrong', default='An error occurred, please try again'), 'danger')
        return render_template('dashboard/general_dashboard.html',
                               recent_invoices=[],
                               recent_transactions=[]), 500

@app.errorhandler(403)
def forbidden(e):
    return render_template('errors/403.html', message=trans_function('forbidden', default='Forbidden')), 403

@app.errorhandler(404)
def page_not_found(e):
    return render_template('errors/404.html', message=trans_function('page_not_found', default='Page not found')), 404

@app.errorhandler(500)
def internal_server_error(e):
    return render_template('errors/500.html', message=trans_function('internal_server_error', default='Internal server error')), 500

with app.app_context():
    if os.getenv('FLASK_ENV', 'development') != 'production' or os.getenv('ALLOW_DB_SETUP', 'false').lower() == 'true':
        if not setup_database():
            logger.error("Application startup aborted due to database initialization failure")
            raise RuntimeError("Database initialization failed")
    else:
        logger.info("Database initialization skipped in production environment")

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    logger.info(f"Starting Flask app on port {port} at {datetime.now().strftime('%I:%M %p WAT on %B %d, %Y')}")
    app.run(host='0.0.0.0', port=port, debug=False)
