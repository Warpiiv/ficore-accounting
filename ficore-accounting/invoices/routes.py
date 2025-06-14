from flask import Blueprint, request, jsonify, render_template, redirect, url_for, flash
from flask_wtf import FlaskForm
from wtforms import StringField, FloatField, validators
from flask_pymongo import PyMongo
from datetime import datetime
from app import app

invoices_bp = Blueprint('invoices', __name__, template_folder='templates')
mongo = PyMongo(app)

class InvoiceForm(FlaskForm):
    customer_name = StringField('Customer Name', [validators.DataRequired()])
    description = StringField('Description', [validators.DataRequired()])
    amount = FloatField('Amount', [validators.DataRequired(), validators.NumberRange(min=0)])

@invoices_bp.route('/', methods=['GET'])
def invoice_dashboard():
    invoices = list(mongo.db.invoices.find())
    for invoice in invoices:
        invoice['_id'] = str(invoice['_id'])
    return render_template('invoices/view.html', invoices=invoices)

@invoices_bp.route('/create', methods=['GET', 'POST'])
def create_invoice():
    form = InvoiceForm()
    if form.validate_on_submit():
        invoice = {
            'customer_name': form.customer_name.data,
            'description': form.description.data,
            'amount': form.amount.data,
            'status': 'pending',
            'created_at': datetime.now().strftime('%Y-%m-%d')
        }
        result = mongo.db.invoices.insert_one(invoice)
        invoice['_id'] = str(result.inserted_id)
        flash('Invoice created successfully!', 'success')
        return redirect(url_for('invoices.invoice_dashboard'))
    return render_template('invoices/create.html', form=form)
