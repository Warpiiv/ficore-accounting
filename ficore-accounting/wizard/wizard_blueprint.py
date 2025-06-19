from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, SelectField, SubmitField
from wtforms.validators import DataRequired, Length
from flask_login import current_user
from bson.objectid import ObjectId
from pymongo import MongoClient
from flask_babel import _, lazy_gettext

# Initialize Blueprint
wizard_bp = Blueprint('wizard', __name__, template_folder='templates')

# MongoDB connection (assuming config is in your app)
client = MongoClient('mongodb://localhost:27017/')
db = client['your_database']
users_collection = db['users']

# Flask-WTF Form for Business Setup
class BusinessSetupForm(FlaskForm):
    business_name = StringField(lazy_gettext('Business Name'), 
                               validators=[DataRequired(), Length(min=2, max=100)])
    address = TextAreaField(lazy_gettext('Business Address'), 
                           validators=[DataRequired(), Length(max=500)])
    industry = SelectField(lazy_gettext('Industry'), 
                          choices=[
                              ('retail', lazy_gettext('Retail')),
                              ('services', lazy_gettext('Services')),
                              ('manufacturing', lazy_gettext('Manufacturing')),
                              ('other', lazy_gettext('Other'))
                          ], 
                          validators=[DataRequired()])
    submit = SubmitField(lazy_gettext('Save and Continue'))

# Wizard Route
@wizard_bp.route('/wizard', methods=['GET', 'POST'])
def setup_wizard():
    if not current_user.is_authenticated:
        return redirect(url_for('auth.login'))
    
    # Check if user has completed setup
    user = users_collection.find_one({'_id': ObjectId(current_user.id)})
    if user.get('setup_complete', False):
        return redirect(url_for('dashboard.general_dashboard'))
    
    form = BusinessSetupForm()
    
    if form.validate_on_submit():
        # Update user document with business details
        users_collection.update_one(
            {'_id': ObjectId(current_user.id)},
            {
                '$set': {
                    'business_details': {
                        'name': form.business_name.data,
                        'address': form.address.data,
                        'industry': form.industry.data
                    },
                    'setup_complete': True
                }
            }
        )
        flash(_('Business setup completed successfully!'), 'success')
        return redirect(url_for('dashboard.general_dashboard'))
    
    return render_template('wizard/setup.html', form=form)

# Redirect new users after signup
@wizard_bp.before_app_request
def check_wizard_completion():
    if current_user.is_authenticated and request.endpoint not in ['wizard.setup_wizard', 'auth.logout']:
        user = users_collection.find_one({'_id': ObjectId(current_user.id)})
        if not user.get('setup_complete', False):
            return redirect(url_for('wizard.setup_wizard'))