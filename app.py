from flask import Flask
from flask_pymongo import PyMongo
from flask_cors import CORS
import os

# Initialize Flask app
app = Flask(__name__)
CORS(app)

# Configuration
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'your-secret-key')
app.config['MONGO_URI'] = os.getenv('MONGO_URI')
mongo = PyMongo(app)

# Register blueprints
from invoices import invoices_bp
from transactions import transactions_bp
from users import users_bp
app.register_blueprint(invoices_bp, url_prefix='/invoices')
app.register_blueprint(transactions_bp, url_prefix='/transactions')
app.register_blueprint(users_bp, url_prefix='/users')

# Translations route (kept outside blueprints for simplicity)
from translations import TRANSLATIONS
@app.route('/api/translations/<lang>')
def get_translations(lang):
    return {'translations': TRANSLATIONS.get(lang, TRANSLATIONS['en'])}

if __name__ == '__main__':
    port = int(os.getenv('PORT', 10000))  # Match Render's expected port
    app.run(host='0.0.0.0', port=port, debug=False)
