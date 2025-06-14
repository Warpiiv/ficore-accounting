from flask import Blueprint

invoices_bp = Blueprint('invoices', __name__, template_folder='templates')

from .routes import *
