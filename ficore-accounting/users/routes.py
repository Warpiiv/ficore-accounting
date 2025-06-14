from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, validators
from flask_login import login_required, current_user, login_user, UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from flask_pymongo import PyMongo
from app import app, trans_function
import logging

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
            user = mongo.db.users.find_one({'_id': form.username.data})
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

@users_bp.route('/profile', methods=['GET'])
@login_required
def profile():
    try:
        user = mongo.db.users.find_one({'_id': current_user.id})
        if user:
            user['_id'] = str(user['_id'])
            return render_template('users/profile.html', user=user)
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
            
            # Check for existing username/email (excluding current user)
            if new_username != current_user.id and mongo.db.users.find_one({'_id': new_username}):
                flash(trans_function('username_exists'), 'danger')
                return render_template('users/profile.html', form=form, user={'_id': current_user.id, 'email': current_user.email})
            if new_email != current_user.email and mongo.db.users.find_one({'email': new_email}):
                flash(trans_function('email_exists'), 'danger')
                return render_template('users/profile.html', form=form, user={'_id': current_user.id, 'email': current_user.email})

            # Update user
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
            # Update current_user
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
