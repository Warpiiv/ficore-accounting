from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, TextAreaField, SelectField, SubmitField, validators
from flask_login import login_required, current_user, login_user, logout_user
from pymongo import errors
from werkzeug.security import generate_password_hash, check_password_hash
from flask_mail import Message
import logging
import uuid
from datetime import datetime, timedelta
from utils import trans_function, is_valid_email
import re
from itsdangerous import URLSafeTimedSerializer
from app import limiter  

logger = logging.getLogger(__name__)

users_bp = Blueprint('users', __name__, template_folder='templates/users')

# Username validation regex: alphanumeric, underscores, 3-50 characters
USERNAME_REGEX = re.compile(r'^[a-zA-Z0-9_]{3,50}$')

class LoginForm(FlaskForm):
    username = StringField(trans_function('Username', default='Username'), [
        validators.DataRequired(message=trans_function('Username is required', default='Username is required')),
        validators.Length(min=3, max=50, message=trans_function('Username must be between 3 and 50 characters', default='Username must be between 3 and 50 characters')),
        validators.Regexp(USERNAME_REGEX, message=trans_function('Username must be alphanumeric with underscores', default='Username must be alphanumeric with underscores'))
    ])
    password = PasswordField(trans_function('Password', default='Password'), [
        validators.DataRequired(message=trans_function('Password is required', default='Password is required')),
        validators.Length(min=8, message=trans_function('Password must be at least 8 characters', default='Password must be at least 8 characters'))
    ])

class SignupForm(FlaskForm):
    username = StringField(trans_function('Username', default='Username'), [
        validators.DataRequired(message=trans_function('Username is required', default='Username is required')),
        validators.Length(min=3, max=50, message=trans_function('Username must be between 3 and 50 characters', default='Username must be between 3 and 50 characters')),
        validators.Regexp(USERNAME_REGEX, message=trans_function('Username must be alphanumeric with underscores', default='Username must be alphanumeric with underscores'))
    ])
    email = StringField(trans_function('Email', default='Email'), [
        validators.DataRequired(message=trans_function('Email is required', default='Email is required')),
        validators.Email(message=trans_function('Invalid email address', default='Invalid email address')),
        validators.Length(max=254),
        validators.InputRequired(),
        lambda form, field: is_valid_email(field.data) or validators.ValidationError(trans_function('Invalid email domain', default='Invalid email domain'))
    ])
    password = PasswordField(trans_function('Password', default='Password'), [
        validators.DataRequired(message=trans_function('Password is required', default='Password is required')),
        validators.Length(min=8, message=trans_function('Password must be at least 8 characters', default='Password must be at least 8 characters'))
    ])

class ForgotPasswordForm(FlaskForm):
    email = StringField(trans_function('Email', default='Email'), [
        validators.DataRequired(message=trans_function('Email is required', default='Email is required')),
        validators.Email(message=trans_function('Invalid email address', default='Invalid email address'))
    ])

class ResetPasswordForm(FlaskForm):
    password = PasswordField(trans_function('Password', default='Password'), [
        validators.DataRequired(message=trans_function('Password is required', default='Password is required')),
        validators.Length(min=8, message=trans_function('Password must be at least 8 characters', default='Password must be at least 8 characters'))
    ])
    confirm_password = PasswordField(trans_function('Confirm Password', default='Confirm Password'), [
        validators.DataRequired(message=trans_function('Confirm password is required', default='Confirm password is required')),
        validators.EqualTo('password', message=trans_function('Passwords must match', default='Passwords must match'))
    ])

class ProfileForm(FlaskForm):
    email = StringField(trans_function('Email', default='Email'), [
        validators.DataRequired(message=trans_function('Email is required', default='Email is required')),
        validators.Email(message=trans_function('Invalid email address', default='Invalid email address'))
    ])
    display_name = StringField(trans_function('Display Name', default='Display Name'), [
        validators.DataRequired(message=trans_function('Display Name is required', default='Display Name is required')),
        validators.Length(min=3, max=50, message=trans_function('Display Name must be between 3 and 50 characters', default='Display Name must be between 3 and 50 characters'))
    ])

class BusinessSetupForm(FlaskForm):
    business_name = StringField(trans_function('Business Name', default='Business Name'), 
                               validators=[validators.DataRequired(), validators.Length(min=2, max=100)])
    address = TextAreaField(trans_function('Business Address', default='Business Address'), 
                            validators=[validators.DataRequired(), validators.Length(max=500)])
    industry = SelectField(trans_function('Industry', default='Industry'), 
                          choices=[
                              ('retail', trans_function('Retail', default='Retail')),
                              ('services', trans_function('Services', default='Services')),
                              ('manufacturing', trans_function('Manufacturing', default='Manufacturing')),
                              ('other', trans_function('Other', default='Other'))
                          ], 
                          validators=[validators.DataRequired()])
    submit = SubmitField(trans_function('Save and Continue', default='Save and Continue'))

@users_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    form = LoginForm()
    if form.validate_on_submit():
        try:
            mongo = current_app.extensions['pymongo']
            username = form.username.data.strip().lower()
            if not USERNAME_REGEX.match(username):
                flash(trans_function('invalid_username_format'), 'danger')
                logger.warning(f"Invalid username format: {username}")
                return render_template('users/login.html', form=form)
            user = mongo.db.users.find_one({'_id': username})
            if user and check_password_hash(user['password'], form.password.data):
                from app import User
                login_user(User(user['_id'], user['email'], user.get('display_name')), remember=True)
                logger.info(f"User {username} logged in successfully, session authenticated: {current_user.is_authenticated}")
                if not user.get('setup_complete', False):
                    return redirect(url_for('users.setup_wizard'))
                return redirect(url_for('users.profile'))
            flash(trans_function('invalid_credentials'), 'danger')
            logger.warning(f"Failed login attempt for username: {username}")
        except errors.PyMongoError as e:
            logger.error(f"MongoDB error during login: {str(e)}")
            flash(trans_function('core_something_went_wrong'), 'danger')
            return render_template('users/login.html', form=form), 500
        except Exception as e:
            logger.error(f"Unexpected error during login: {str(e)}")
            flash(trans_function('core_something_went_wrong'), 'danger')
            return render_template('users/login.html', form=form), 500
    return render_template('users/login.html', form=form)

@users_bp.route('/signup', methods=['GET', 'POST'])
def signup():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    form = SignupForm()
    if form.validate_on_submit():
        try:
            mongo = current_app.extensions['pymongo']
            mongo.db.command('ping')
            username = form.username.data.strip().lower()
            email = form.email.data.strip().lower()
            logger.debug(f"Signup attempt: username={username}, email={email}")
            if mongo.db.users.find_one({'_id': username}) or mongo.db.users.find_one({'email': email}):
                flash(trans_function('user_exists'), 'danger')
                return render_template('users/signup.html', form=form)
            user_data = {
                '_id': username,
                'email': email,
                'password': generate_password_hash(form.password.data),
                'dark_mode': False,
                'is_admin': False,
                'created_at': datetime.utcnow(),
                'setup_complete': False,
                'display_name': username  # Initial display_name
            }
            result = mongo.db.users.insert_one(user_data)
            if not result.inserted_id:
                logger.error("Failed to insert user document")
                flash(trans_function('signup_error'), 'danger')
                return render_template('users/signup.html', form=form), 500
            from app import User
            login_user(User(username, email, username), remember=True)
            logger.info(f"New user created and logged in: {username}, session authenticated: {current_user.is_authenticated}")
            return redirect(url_for('users.setup_wizard'))
        except errors.PyMongoError as e:
            logger.error(f"MongoDB error during signup: {str(e)}")
            flash(trans_function('signup_error'), 'danger')
            return render_template('users/signup.html', form=form), 500
        except Exception as e:
            logger.error(f"Unexpected error during signup: {str(e)}")
            flash(trans_function('signup_error'), 'danger')
            return render_template('users/signup.html', form=form), 500
    return render_template('users/signup.html', form=form)

@users_bp.route('/forgot_password', methods=['GET', 'POST'])
@limiter.limit("5 per minute")  # Now works with imported limiter
def forgot_password():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    form = ForgotPasswordForm()
    if form.validate_on_submit():
        try:
            mongo = current_app.extensions['pymongo']
            email = form.email.data.strip().lower()
            user = mongo.db.users.find_one({'email': email})
            if not user:
                flash(trans_function('email_not_found'), 'danger')
                return render_template('users/forgot_password.html', form=form)
            reset_token = serializer.dumps(email, salt='reset-salt')
            expiry = datetime.utcnow() + timedelta(minutes=15)
            mongo.db.users.update_one(
                {'_id': user['_id']},
                {'$set': {'reset_token': reset_token, 'reset_token_expiry': expiry}}
            )
            reset_url = url_for('users.reset_password', token=reset_token, _external=True)
            msg = Message(
                subject=trans_function('reset_password_subject'),
                recipients=[email],
                body=f"{trans_function('reset_password_body')}\n\n{reset_url}\n\n{trans_function('reset_password_expiry')}"
            )
            mail.send(msg)
            flash(trans_function('reset_email_sent'), 'success')
            return render_template('users/forgot_password.html', form=form)
        except Exception as e:
            logger.error(f"Error during forgot password: {str(e)}")
            flash(trans_function('forgot_password_error'), 'danger')
            return render_template('users/forgot_password.html', form=form), 500
    return render_template('users/forgot_password.html', form=form)

@users_bp.route('/reset_password', methods=['GET', 'POST'])
@limiter.limit("5 per minute")  # Now works with imported limiter
def reset_password():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    token = request.args.get('token')
    try:
        email = serializer.loads(token, salt='reset-salt', max_age=900)  # 15 minutes
    except Exception:
        flash(trans_function('invalid_or_expired_token'), 'danger')
        return redirect(url_for('users.forgot_password'))
    form = ResetPasswordForm()
    if form.validate_on_submit():
        try:
            mongo = current_app.extensions['pymongo']
            user = mongo.db.users.find_one({'email': email})
            if not user:
                flash(trans_function('invalid_or_expired_token'), 'danger')
                return render_template('users/reset_password.html', form=form, token=token)
            mongo.db.users.update_one(
                {'_id': user['_id']},
                {'$set': {'password': generate_password_hash(form.password.data)}, '$unset': {'reset_token': '', 'reset_token_expiry': ''}}
            )
            flash(trans_function('reset_password_success'), 'success')
            return redirect(url_for('users.login'))
        except Exception as e:
            logger.error(f"Error during password reset: {str(e)}")
            flash(trans_function('reset_password_error'), 'danger')
            return render_template('users/reset_password.html', form=form, token=token), 500
    return render_template('users/reset_password.html', form=form, token=token)

@users_bp.route('/profile', methods=['GET'])
@login_required
def profile():
    try:
        mongo = current_app.extensions['pymongo']
        user = mongo.db.users.find_one({'_id': current_user.id})
        if user:
            user['_id'] = str(user['_id'])
            return render_template('users/profile.html', user=user, form=ProfileForm())
        flash(trans_function('user_not_found'), 'danger')
        return redirect(url_for('index'))
    except errors.PyMongoError as e:
        logger.error(f"MongoDB error fetching profile: {str(e)}")
        flash(trans_function('core_something_went_wrong'), 'danger')
        return redirect(url_for('index')), 500
    except Exception as e:
        logger.error(f"Unexpected error fetching profile: {str(e)}")
        flash(trans_function('core_something_went_wrong'), 'danger')
        return redirect(url_for('index')), 500

@users_bp.route('/update_profile', methods=['GET', 'POST'])
@login_required
def update_profile():
    form = ProfileForm(data={
        'email': current_user.email,
        'display_name': current_user.display_name
    })
    if form.validate_on_submit():
        try:
            mongo = current_app.extensions['pymongo']
            new_email = form.email.data.strip().lower()
            new_display_name = form.display_name.data.strip()
            if new_email != current_user.email and mongo.db.users.find_one({'email': new_email}):
                flash(trans_function('email_exists'), 'danger')
                return render_template('users/profile.html', form=form, user={'_id': current_user.id, 'email': current_user.email, 'display_name': current_user.display_name})
            mongo.db.users.update_one(
                {'_id': current_user.id},
                {
                    '$set': {
                        'email': new_email,
                        'display_name': new_display_name,
                        'updated_at': datetime.utcnow()
                    }
                }
            )
            current_user.email = new_email
            current_user.display_name = new_display_name
            flash(trans_function('profile_updated'), 'success')
            logger.info(f"Profile updated for user: {current_user.id}")
            return redirect(url_for('users.profile'))
        except errors.PyMongoError as e:
            logger.error(f"MongoDB error updating profile: {str(e)}")
            flash(trans_function('core_something_went_wrong'), 'danger')
            return render_template('users/profile.html', form=form, user={'_id': current_user.id, 'email': current_user.email, 'display_name': current_user.display_name}), 500
        except Exception as e:
            logger.error(f"Unexpected error updating profile: {str(e)}")
            flash(trans_function('core_something_went_wrong'), 'danger')
            return render_template('users/profile.html', form=form, user={'_id': current_user.id, 'email': current_user.email, 'display_name': current_user.display_name}), 500
    return render_template('users/profile.html', form=form, user={'_id': current_user.id, 'email': current_user.email, 'display_name': current_user.display_name})

@users_bp.route('/setup_wizard', methods=['GET', 'POST'])
@login_required
def setup_wizard():
    mongo = current_app.extensions['pymongo']
    user = mongo.db.users.find_one({'_id': current_user.id})
    if user.get('setup_complete', False):
        return redirect(url_for('general_dashboard'))
    
    form = BusinessSetupForm()
    if form.validate_on_submit():
        try:
            mongo.db.users.update_one(
                {'_id': current_user.id},
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
            flash(trans_function('business_setup_completed'), 'success')
            logger.info(f"Business setup completed for user: {current_user.id}")
            return redirect(url_for('users.profile'))
        except errors.PyMongoError as e:
            logger.error(f"MongoDB error during business setup: {str(e)}")
            flash(trans_function('core_something_went_wrong'), 'danger')
            return render_template('users/setup.html', form=form), 500
        except Exception as e:
            logger.error(f"Unexpected error during business setup: {str(e)}")
            flash(trans_function('core_something_went_wrong'), 'danger')
            return render_template('users/setup.html', form=form), 500
    
    return render_template('users/setup.html', form=form)

@users_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash(trans_function('logged_out'), 'success')
    session.clear()  # Invalidate session
    return redirect(url_for('index'))

@users_bp.route('/auth/signin')
def signin():
    return redirect(url_for('users.login'))

@users_bp.route('/auth/signup')
def signup_redirect():
    return redirect(url_for('users.signup'))

@users_bp.route('/auth/forgot-password')
def forgot_password_redirect():
    return redirect(url_for('users.forgot_password'))

@users_bp.route('/auth/reset-password')
def reset_password_redirect():
    return redirect(url_for('users.reset_password'))

@users_bp.before_app_request
def check_wizard_completion():
    if (current_user.is_authenticated and 
        request.endpoint not in ['users.setup_wizard', 'users.logout', 'users.login', 
                               'users.signup', 'users.forgot_password', 'users.reset_password']):
        try:
            mongo = current_app.extensions['pymongo']
            user = mongo.db.users.find_one({'_id': current_user.id})
            if not user.get('setup_complete', False):
                return redirect(url_for('users.setup_wizard'))
        except errors.PyMongoError as e:
            logger.error(f"MongoDB error checking wizard completion: {str(e)}")
            flash(trans_function('core_something_went_wrong'), 'danger')
            return redirect(url_for('index')), 500
        except Exception as e:
            logger.error(f"Unexpected error checking wizard completion: {str(e)}")
            flash(trans_function('core_something_went_wrong'), 'danger')
            return redirect(url_for('index')), 500
