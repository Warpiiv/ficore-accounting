from flask import Blueprint

users_bp = Blueprint('users', __name__)

from .routes import *