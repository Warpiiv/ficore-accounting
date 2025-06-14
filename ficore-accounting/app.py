from flask import Flask, session, redirect, url_for, flash, render_template
from flask_pymongo import PyMongo
from flask_cors import CORS
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

# Register blueprints
from invoices.routes import invoices_bp
from transactions.routes import transactions_bp
from users.routes import users_bp
app.register_blueprint(invoices_bp, url_prefix='/invoices')
app.register_blueprint(transactions_bp, url_prefix='/transactions')
app.register_blueprint(users_bp, url_prefix='/users')

# Translations
from translations import TRANSLATIONS
import jinja2  # Import jinja2 explicitly

# Add trans filter to Jinja2 with logging for missing translations
@app.template_filter('trans')
def trans_filter(key):
    try:
        lang = session.get('lang', 'en')
        translation = TRANSLATIONS.get(lang, {}).get(key, key)
        if translation == key:
            logger.info(f"Missing translation for key '{key}' in language '{lang}'")
        return translation
    except Exception as e:
        logger.error(f"Error in trans filter: {e}")
        return key  # Fallback to key on error

@app.route('/api/translations/<lang>')
def get_translations(lang):
    return {'translations': TRANSLATIONS.get(lang, TRANSLATIONS['en'])}

# General routes
@app.route('/')
def index():
    return redirect(url_for('invoices.invoice_dashboard'))

@app.route('/about')
def about():
    return render_template('general/about.html')

@app.route('/feedback')
def feedback():
    return render_template('general/feedback.html')

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

# Auth routes (placeholders)
@app.route('/auth/signin')
def signin():
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
