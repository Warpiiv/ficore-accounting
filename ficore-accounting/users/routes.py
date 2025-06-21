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
# Password validation regex: at least 8 chars, 1 uppercase, 1 lowercase, 1 number, 1 special char
PASSWORD_REGEX = re.compile(r'^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*?&])[A-Za-z\d@$!%*?&]{8,}$')

class LoginForm(FlaskForm):
    username = StringField(trans_function('username', default='Username'), [
        validators.DataRequired(message=trans_function('username_required', default='Username is required')),
        validators.Length(min=3, max=50, message=trans_function('username_length', default='Username must be between 3 and 50 characters')),
        validators.Regexp(USERNAME_REGEX, message=trans_function('username_format', default='Username must be alphanumeric with underscores'))
    ])
    password = PasswordField(trans_function('password', default='Password'), [
        validators.DataRequired(message=trans_function('password_required', default='Password is required')),
        validators.Length(min=8, message=trans_function('password_length', default='Password must be at least 8 characters'))
    ])
    submit = SubmitField(trans_function('login', default='Login'))

class SignupForm(FlaskForm):
    username = StringField(trans_function('username', default='Username'), [
        validators.DataRequired(message=trans_function('username_required', default='Username is required')),
        validators.Length(min=3, max=50, message=trans_function('username_length', default='Username must be between 3 and 50 characters')),
        validators.Regexp(USERNAME_REGEX, message=trans_function('username_format', default='Username must be alphanumeric with underscores'))
    ])
    email = StringField(trans_function('email', default='Email'), [
        validators.DataRequired(message=trans_function('email_required', default='Email is required')),
        validators.Email(message=trans_function('email_invalid', default='Invalid email address')),
        validators.Length(max=254),
        lambda form, field: is_valid_email(field.data) or validators.ValidationError(trans_function('email_domain_invalid', default='Invalid email domain'))
    ])
    password = PasswordField(trans_function('password', default='Password'), [
        validators.DataRequired(message=trans_function('password_required', default='Password is required')),
        validators.Length(min=8, message=trans_function('password_length', default='Password must be at least 8 characters')),
        validators.Regexp(PASSWORD_REGEX, message=trans_function('password_format', default='Password must include uppercase, lowercase, number, and special character'))
    ])
    role = SelectField(trans_function('role', default='Role'), choices=[
        ('personal', trans_function('personal', default='Personal')),
        ('trader', trans_function('trader', default='Trader')),
        ('agent', trans_function('agent', default='Agent'))
    ], validators=[validators.DataRequired(message=trans_function('role_required', default='Role is required'))])
    language = SelectField(trans_function('language', default='Language'), choices=[
        ('en', trans_function('english', default='English')),
        ('ha', trans_function('hausa', default='Hausa'))
    ], validators=[validators.DataRequired(message=trans_function('language_required', default='Language is required'))])
    submit = SubmitField(trans_function('signup', default='Sign Up'))

class ForgotPasswordForm(FlaskForm):
    email = StringField(trans_function('email', default='Email'), [
        validators.DataRequired(message=trans_function('email_required', default='Email is required')),
        validators.Email(message=trans_function('email_invalid', default='Invalid email address'))
    ])
    submit = SubmitField(trans_function('send_reset_link', default='Send Reset Link'))

class ResetPasswordForm(FlaskForm):
    password = PasswordField(trans_function('password', default='Password'), [
        validators.DataRequired(message=trans_function('password_required', default='Password is required')),
        validators.Length(min=8, message=trans_function('password_length', default='Password must be at least 8 characters')),
        validators.Regexp(PASSWORD_REGEX, message=trans_function('password_format', default='Password must include uppercase, lowercase, number, and special character'))
    ])
    confirm_password = PasswordField(trans_function('confirm_password', default='Confirm Password'), [
        validators.DataRequired(message=trans_function('confirm_password_required', default='Confirm password is required')),
        validators.EqualTo('password', message=trans_function('passwords_must_match', default='Passwords must match'))
    ])
    submit = SubmitField(trans_function('reset_password', default='Reset Password'))

class ProfileForm(FlaskForm):
    email = StringField(trans_function('email', default='Email'), [
        validators.DataRequired(message=trans_function('email_required', default='Email is required')),
        validators.Email(message=trans_function('email_invalid', default='Invalid email address'))
    ])
    display_name = StringField(trans_function('display_name', default='Display Name'), [
        validators.DataRequired(message=trans_function('display_name_required', default='Display Name is required')),
        validators.Length(min=3, max=50, message=trans_function('display_name_length', default='Display Name must be between 3 and 50 characters'))
    ])
    language = SelectField(trans_function('language', default='Language'), choices=[
        ('en', trans_function('english', default='English')),
        ('ha', trans_function('hausa', default='Hausa'))
    ], validators=[validators.DataRequired(message=trans_function('language_required', default='Language is required'))])
    submit = SubmitField(trans_function('update_profile', default='Update Profile'))

class BusinessSetupForm(FlaskForm):
    business_name = StringField(trans_function('business_name', default='Business Name'), 
                              validators=[validators.DataRequired(), validators.Length(min=2, max=100)])
    address = TextAreaField(trans_function('business_address', default='Business Address'), 
                           validators=[validators.DataRequired(), validators.Length(max=500)])
    industry = SelectField(trans_function('industry', default='Industry'), 
                         choices=[
                             ('retail', trans_function('retail', default='Retail')),
                             ('services', trans_function('services', default='Services')),
                             ('manufacturing', trans_function('manufacturing', default='Manufacturing')),
                             ('other', trans_function('other', default='Other'))
                         ], 
                         validators=[validators.DataRequired()])
    submit = SubmitField(trans_function('save_and_continue', default='Save and Continue'))

@users_bp.route('/login', methods=['GET', 'POST'])
@limiter.limit("50 per hour")
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    form = LoginForm()
    if form.validate_on_submit():
        try:
            mongo = current_app.extensions['pymongo']
            username = form.username.data.strip().lower()
            if not USERNAME_REGEX.match(username):
                flash(trans_function('username_format', default='Invalid username format'), 'danger')
                logger.warning(f"Invalid username format: {username}")
                return render_template('users/login.html', form=form)
            user = mongo.db.users.find_one({'_id': username})
            if user and check_password_hash(user['password'], form.password.data):
                from app import User
                login_user(User(user['_id'], user['email'], user.get('display_name'), user.get('role', 'personal')), 
                          remember=True)
                session['lang'] = user.get('language', 'en')
                logger.info(f"User {username} logged in successfully")
                if not user.get('setup_complete', False):
                    return redirect(url_for('users.setup_wizard'))
                return redirect(url_for('users.profile'))
            flash(trans_function('invalid_credentials', default='Invalid username or password'), 'danger')
            logger.warning(f"Failed login attempt for username: {username}")
        except errors.PyMongoError as e:
            logger.error(f"MongoDB error during login: {str(e)}")
            flash(trans_function('core_something_went_wrong', default='An error occurred, please try again'), 'danger')
            return render_template('users/login.html', form=form), 500
    return render_template('users/login.html', form=form)

@users_bp.route('/signup', methods=['GET', 'POST'])
@limiter.limit("50 per hour")
def signup():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    form = SignupForm()
    if form.validate_on_submit():
        try:
            mongo = current_app.extensions['pymongo']
            username = form.username.data.strip().lower()
            email = form.email.data.strip().lower()
            role = form.role.data
            language = form.language.data
            if mongo.db.users.find_one({'_id': username}) or mongo.db.users.find_one({'email': email}):
                flash(trans_function('user_exists', default='Username or email already exists'), 'danger')
                return render_template('users/signup.html', form=form)
            user_data = {
                '_id': username,
                'email': email,
                'password': generate_password_hash(form.password.data),
                'role': role,
                'coin_balance': 0,
                'language': language,
                'dark_mode': False,
                'is_admin': role == 'admin',
                'setup_complete': False,
                'display_name': username,
                'created_at': datetime.utcnow()
            }
            result = mongo.db.users.insert_one(user_data)
            login_user(User(username, email, username, role), remember=True)
            session['lang'] = language
            logger.info(f"New user created: {username} (role: {role})")
            return redirect(url_for('users.setup_wizard'))
        except errors.PyMongoError as e:
            logger.error(f"MongoDB error during signup: {str(e)}")
            flash(trans_function('signup_error', default='Error during signup'), 'danger')
            return render_template('users/signup.html', form=form), 500
    return render_template('users/signup.html', form=form)

@users_bp.route('/forgot_password', methods=['GET', 'POST'])
@limiter.limit("50 per hour")
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
                flash(trans_function('email_not_found', default='Email not found'), 'danger')
                return render_template('users/forgot_password.html', form=form)
            reset_token = serializer.dumps(email, salt='reset-salt')
            expiry = datetime.utcnow() + timedelta(minutes=15)
            mongo.db.users.update_one(
                {'_id': user['_id']},
                {'$set': {'reset_token': reset_token, 'reset_token_expiry': expiry}}
            )
            reset_url = url_for('users.reset_password', token=reset_token, _external=True)
            msg = Message(
                subject=trans_function('reset_password_subject', default='Reset Your Password'),
                recipients=[email],
                body=trans_function('reset_password_body', default=f'Click the link to reset your password: {reset_url}\nLink expires in 15 minutes.')
            )
            mail.send(msg)
            flash(trans_function('reset_email_sent', default='Password reset email sent'), 'success')
            return render_template('users/forgot_password.html', form=form)
        except Exception as e:
            logger.error(f"Error during forgot password: {str(e)}")
            flash(trans_function('forgot_password_error', default='Error processing request'), 'danger')
            return render_template('users/forgot_password.html', form=form), 500
    return render_template('users/forgot_password.html', form=form)

@users_bp.route('/reset_password', methods=['GET', 'POST'])
@limiter.limit("50 per hour")
def reset_password():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    token = request.args.get('token')
    try:
        email = serializer.loads(token, salt='reset-salt', max_age=900)
    except Exception:
        flash(trans_function('invalid_or_expired_token', default='Invalid or expired token'), 'danger')
        return redirect(url_for('users.forgot_password'))
    form = ResetPasswordForm()
    if form.validate_on_submit():
        try:
            mongo = current_app.extensions['pymongo']
            user = mongo.db.users.find_one({'email': email})
            if not user:
                flash(trans_function('invalid_or_expired_token', default='Invalid or expired token'), 'danger')
                return render_template('users/reset_password.html', form=form, token=token)
            mongo.db.users.update_one(
                {'_id': user['_id']},
                {'$set': {'password': generate_password_hash(form.password.data)}, 
                 '$unset': {'reset_token': '', 'reset_token_expiry': ''}}
            )
            flash(trans_function('reset_password_success', default='Password reset successfully'), 'success')
            return redirect(url_for('users.login'))
        except Exception as e:
            logger.error(f"Error during password reset: {str(e)}")
            flash(trans_function('reset_password_error', default='Error resetting password'), 'danger')
            return render_template('users/reset_password.html', form=form, token=token), 500
    return render_template('users/reset_password.html', form=form, token=token)

@users_bp.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    try:
        mongo = current_app.extensions['pymongo']
        user = mongo.db.users.find_one({'_id': current_user.id})
        if not user:
            flash(trans_function('user_not_found', default='User not found'), 'danger')
            return redirect(url_for('index'))
        form = ProfileForm(data={
            'email': user['email'],
            'display_name': user['display_name'],
            'language': user.get('language', 'en')
        })
        if form.validate_on_submit():
            try:
                new_email = form.email.data.strip().lower()
                new_display_name = form.display_name.data.strip()
                new_language = form.language.data
                if new_email != user['email'] and mongo.db.users.find_one({'email': new_email}):
                    flash(trans_function('email_exists', default='Email already exists'), 'danger')
                    return render_template('users/profile.html', form=form, user=user)
                mongo.db.users.update_one(
                    {'_id': current_user.id},
                    {
                        '$set': {
                            'email': new_email,
                            'display_name': new_display_name,
                            'language': new_language,
                            'updated_at': datetime.utcnow()
                        }
                    }
                )
                current_user.email = new_email
                current_user.display_name = new_display_name
                session['lang'] = new_language
                flash(trans_function('profile_updated', default='Profile updated successfully'), 'success')
                logger.info(f"Profile updated for user: {current_user.id}")
                return redirect(url_for('users.profile'))
            except errors.PyMongoError as e:
                logger.error(f"MongoDB error updating profile: {str(e)}")
                flash(trans_function('core_something_went_wrong', default='An error occurred'), 'danger')
                return render_template('users/profile.html', form=form, user=user), 500
        user['_id'] = str(user['_id'])
        user['coin_balance'] = user.get('coin_balance', 0)
        return render_template('users/profile.html', form=form, user=user)
    except errors.PyMongoError as e:
        logger.error(f"MongoDB error fetching profile: {str(e)}")
        flash(trans_function('core_something_went_wrong', default='An error occurred'), 'danger')
        return redirect(url_for('index')), 500

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
                            'name': form.business_name.data.strip(),
                            'address': form.address.data.strip(),
                            'industry': form.industry.data
                        },
                        'setup_complete': True
                    }
                }
            )
            flash(trans_function('business_setup_completed', default='Business setup completed'), 'success')
            logger.info(f"Business setup completed for user: {current_user.id}")
            return redirect(url_for('users.profile'))
        except errors.PyMongoError as e:
            logger.error(f"MongoDB error during business setup: {str(e)}")
            flash(trans_function('core_something_went_wrong', default='An error occurred'), 'danger')
            return render_template('users/setup.html', form=form), 500
    return render_template('users/setup.html', form=form)

@users_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash(trans_function('logged_out', default='Logged out successfully'), 'success')
    session.clear()
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
            flash(trans_function('core_something_went_wrong', default='An error occurred'), 'danger')
            return redirect(url_for('index')), 500
