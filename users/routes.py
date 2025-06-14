from flask import Blueprint, render_template, request, jsonify
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, validators
from flask_pymongo import PyMongo
from werkzeug.security import generate_password_hash, check_password_hash
from .. import app

users_bp = Blueprint('users', __name__)
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
            return jsonify({'message': 'Login successful'}), 200
        return jsonify({'message': 'Invalid credentials'}), 401
    return render_template('users/login.html', form=form)

@users_bp.route('/profile', methods=['GET'])
def profile():
    # Placeholder: Requires authentication logic
    return render_template('users/profile.html')