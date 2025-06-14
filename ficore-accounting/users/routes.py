from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash, session
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, validators
from flask_pymongo import PyMongo
from werkzeug.security import generate_password_hash, check_password_hash
from app import app

users_bp = Blueprint('users', __name__, template_folder='templates/users/users')
mongo = PyMongo(app)

class LoginForm(FlaskForm):
    username = StringField('Username', [validators.DataRequired()])
    password = PasswordField('Password', [validators.DataRequired()])

@users_bp.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        user = mongo.db.users.find_one({'username': form.username.data})
        if user and check_password_hash(user['password'], form.password.data):
            session['user_id'] = str(user['_id'])  # Simple session management
            flash('Login successful!', 'success')
            return redirect(url_for('users.profile'))
        flash('Invalid credentials', 'error')
    return render_template('login.html', form=form)

@users_bp.route('/profile', methods=['GET'])
def profile():
    if 'user_id' not in session:
        flash('Please log in first', 'error')
        return redirect(url_for('users.login'))
    user = mongo.db.users.find_one({'_id': session['user_id']})
    if user:
        user['_id'] = str(user['_id'])
    return render_template('profile.html', user=user)
