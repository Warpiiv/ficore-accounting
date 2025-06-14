from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, validators
from flask_login import login_required, current_user, login_user, UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from flask_pymongo import PyMongo
from app import app, 
from flask_mail import Message
import logging
import uuid
from datetime import datetime, timedelta
from utils import trans_function, mail, is_valid_email

logger = logging.getLogger(__name__)

users_bp = Blueprint('users', __name__, template_folder='templates/users')
mongo = PyMongo(app)

class LoginForm(FlaskForm):
    username = StringField('Username', [
        validators.DataRequired(message='Username is required'),
        validators.Length(min=3, max=50, message='Username must be between 3 and 50 characters')
    ])
    password = PasswordField('Password', [
        validators.DataRequired(message='Password is required'),
        validators.Length(min=8, message='Password must be at least 8 characters')
    ])

class SignupForm(FlaskForm):
    username = StringField('Username', [
        validators.DataRequired(message='Username is required'),
        validators.Length(min=3, max=50, message='Username must be between 3 and 50 characters')
    ])
    email = StringField('Email', [
        validators.DataRequired(message='Email is required'),
        validators.Email(message='Invalid email address')
    ])
    password = PasswordField('Password', [
        validators.DataRequired(message='Password is required'),
        validators.Length(min=8, message='Password must be at least 8 characters')
    ])

class ForgotPasswordForm(FlaskForm):
    email = StringField('Email', [
        validators.DataRequired(message='Email is required'),
        validators.Email(message='Invalid email address')
    ])

class ResetPasswordForm(FlaskForm):
    password = PasswordField('Password', [
        validators.DataRequired(message='Password is required'),
        validators.Length(min=8, message='Password must be at least 8 characters')
    ])
    confirm_password = PasswordField('Confirm Password', [
        validators.DataRequired(message='Confirm password is required'),
        validators.EqualTo('password', message='Passwords must match')
    ])

class ProfileForm(FlaskForm):
    email = StringField('Email', [
        validators.DataRequired(message='Email is required'),
        validators.Email(message='Invalid email address')
    ])
    username = StringField('Username', [
        validators.DataRequired(message='Username is required'),
        validators.Length(min=3, max=50, message='Username must be between 3 and 50 characters')
    ])

@users_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    form = LoginForm()
    if form.validate_on_submit():
        try:
            user = mongo.db.users.find_one({'_id': form.username.data.strip()})
            if user and check_password_hash(user['password'], form.password.data):
                login_user(User(user['_id'], user['email']))
                flash(trans_function('logged_in'), 'success')
                logger.info(f"User {form.username.data} logged in successfully")
                return redirect(url_for('users.profile'))
            flash(trans_function('invalid_credentials'), 'danger')
            logger.warning(f"Failed login attempt for username: {form.username.data}")
        except Exception as e:
            logger.error(f"Error during login: {str(e)}")
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
            username = form.username.data.strip()
            email = form.email.data.strip()
            if mongo.db.users.find_one({'_id': username}) or mongo.db.users.find_one({'email': email}):
                flash(trans_function('user_exists'), 'danger')
                return render_template('auth/signup.html', form=form)
            user_data = {
                '_id': username,
                'email': email,
                'password': generate_password_hash(form.password.data),
                'dark_mode': False,
                'is_admin': False,
                'created_at': datetime.utcnow()
            }
            mongo.db.users.insert_one(user_data)
            login_user(User(username, email))
            flash(trans_function('signup_success'), 'success')
            logger.info(f"New user created: {username}")
            return redirect(url_for('index'))
        except Exception as e:
            logger.error(f"Error during signup: {str(e)}")
            flash(trans_function('signup_error'), 'danger')
            return render_template('auth/signup.html', form=form), 500
    return render_template('auth/signup.html', form=form)

@users_bp.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    form = ForgotPasswordForm()
    if form.validate_on_submit():
        try:
            email = form.email.data.strip()
            user = mongo.db.users.find_one({'email': email})
            if not user:
                flash(trans_function('email_not_found'), 'danger')
                return render_template('auth/forgot_password.html', form=form)
            reset_token = str(uuid.uuid4())
            expiry = datetime.utcnow() + timedelta(hours=1)
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
            try:
                mail.send(msg)
                logger.info(f"Password reset email sent to {email}")
            except Exception as e:
                logger.error(f"Failed to send reset email to {email}: {str(e)}")
                logger.info(f"Reset URL for {email}: {reset_url}")
                flash(trans_function('reset_email_failed'), 'warning')
                return render_template('auth/forgot_password.html', form=form)
            flash(trans_function('reset_email_sent'), 'success')
            return render_template('auth/forgot_password.html', form=form)
        except Exception as e:
            logger.error(f"Error during forgot password: {str(e)}")
            flash(trans_function('forgot_password_error'), 'danger')
            return render_template('auth/forgot_password.html', form=form), 500
    return render_template('auth/forgot_password.html', form=form)

@users_bp.route('/reset_password', methods=['GET', 'POST'])
def reset_password():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    token = request.args.get('token')
    form = ResetPasswordForm()
    if form.validate_on_submit():
        try:
            token = request.form.get('token') or token
            user = mongo.db.users.find_one({
                'reset_token': token,
                'reset_token_expiry': {'$gt': datetime.utcnow()}
            })
            if not user:
                flash(trans_function('invalid_or_expired_token'), 'danger')
                return render_template('auth/reset_password.html', form=form, token=token)
            mongo.db.users.update_one(
                {'_id': user['_id']},
                {
                    '$set': {'password': generate_password_hash(form.password.data)},
                    '$unset': {'reset_token': '', 'reset_token_expiry': ''}
                }
            )
            flash(trans_function('reset_password_success'), 'success')
            logger.info(f"Password reset for user: {user['_id']}")
            return redirect(url_for('users.login'))
        except Exception as e:
            logger.error(f"Error during password reset: {str(e)}")
            flash(trans_function('reset_password_error'), 'danger')
            return render_template('auth/reset_password.html', form=form, token=token), 500
    if not token:
        flash(trans_function('invalid_or_expired_token'), 'danger')
        return redirect(url_for('users.forgot_password'))
    return render_template('auth/reset_password.html', form=form, token=token)

@users_bp.route('/profile', methods=['GET'])
@login_required
def profile():
    try:
        user = mongo.db.users.find_one({'_id': current_user.id})
        if user:
            user['_id'] = str(user['_id'])
            return render_template('users/profile.html', user=user, form=ProfileForm())
        flash(trans_function('user_not_found'), 'danger')
        return redirect(url_for('index'))
    except Exception as e:
        logger.error(f"Error fetching profile: {str(e)}")
        flash(trans_function('core_something_went_wrong'), 'danger')
        return redirect(url_for('index')), 500

@users_bp.route('/update_profile', methods=['GET', 'POST'])
@login_required
def update_profile():
    form = ProfileForm(data={
        'username': current_user.id,
        'email': current_user.email
    })
    if form.validate_on_submit():
        try:
            new_username = form.username.data.strip()
            new_email = form.email.data.strip()
            if new_username != current_user.id and mongo.db.users.find_one({'_id': new_username}):
                flash(trans_function('username_exists'), 'danger')
                return render_template('users/profile.html', form=form, user={'_id': current_user.id, 'email': current_user.email})
            if new_email != current_user.email and mongo.db.users.find_one({'email': new_email}):
                flash(trans_function('email_exists'), 'danger')
                return render_template('users/profile.html', form=form, user={'_id': current_user.id, 'email': current_user.email})
            mongo.db.users.update_one(
                {'_id': current_user.id},
                {
                    '$set': {
                        '_id': new_username,
                        'email': new_email,
                        'updated_at': datetime.utcnow()
                    }
                }
            )
            current_user.id = new_username
            current_user.email = new_email
            flash(trans_function('profile_updated'), 'success')
            logger.info(f"Profile updated for user: {new_username}")
            return redirect(url_for('users.profile'))
        except Exception as e:
            logger.error(f"Error updating profile: {str(e)}")
            flash(trans_function('core_something_went_wrong'), 'danger')
            return render_template('users/profile.html', form=form, user={'_id': current_user.id, 'email': current_user.email}), 500
    return render_template('users/profile.html', form=form, user={'_id': current_user.id, 'email': current_user.email})
