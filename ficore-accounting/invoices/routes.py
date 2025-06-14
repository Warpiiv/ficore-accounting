from flask import Blueprint, request, render_template, redirect, url_for, flash
from flask_wtf import FlaskForm
from wtforms import StringField, FloatField, validators
from flask_login import login_required, current_user
from flask_pymongo import PyMongo
from datetime import datetime
from app import app, trans_function
import logging

logger = logging.getLogger(__name__)

invoices_bp = Blueprint('invoices', __name__, template_folder='templates/invoices')
mongo = PyMongo(app)

class InvoiceForm(FlaskForm):
    customer_name = StringField('Customer Name', [
        validators.DataRequired(message='Customer name is required'),
        validators.Length(min=2, max=100, message='Name must be between 2 and 100 characters')
    ])
    description = StringField('Description', [
        validators.DataRequired(message='Description is required'),
        validators.Length(max=500, message='Description cannot exceed 500 characters')
    ])
    amount = FloatField('Amount', [
        validators.DataRequired(message='Amount is required'),
        validators.NumberRange(min=0, message='Amount must be non-negative')
    ])

@invoices_bp.route('/invoice_dashboard', methods=['GET'])
@login_required
def invoice_dashboard():
    try:
        invoices = list(mongo.db.invoices.find({'user_id': current_user.id}))
        for invoice in invoices:
            invoice['_id'] = str(invoice['_id'])
        return render_template('invoices/view.html', invoices=invoices)
    except Exception as e:
        logger.error(f"Error fetching invoices: {str(e)}")
        flash(trans_function('core_something_went_wrong'), 'danger')
        return render_template('invoices/view.html', invoices=[]), 500

@invoices_bp.route('/create', methods=['GET', 'POST'])
@login_required
def create_invoice():
    form = InvoiceForm()
    if form.validate_on_submit():
        try:
            invoice = {
                'user_id': current_user.id,
                'customer_name': form.customer_name.data.strip(),
                'description': form.description.data.strip(),
                'amount': float(form.amount.data),
                'status': 'pending',
                'created_at': datetime.utcnow()
            }
            result = mongo.db.invoices.insert_one(invoice)
            flash(trans_function('invoice_created'), 'success')
            logger.info(f"Invoice created by user {current_user.id}: {result.inserted_id}")
            return redirect(url_for('invoices.invoice_dashboard'))
        except Exception as e:
            logger.error(f"Error creating invoice: {str(e)}")
            flash(trans_function('core_something_went_wrong'), 'danger')
            return render_template('invoices/create.html', form=form), 500
    return render_template('invoices/create.html', form=form)

@invoices_bp.route('/update/<invoice_id>', methods=['GET', 'POST'])
@login_required
def update_invoice(invoice_id):
    invoice = mongo.db.invoices.find_one({'_id': invoice_id, 'user_id': current_user.id})
    if not invoice:
        flash(trans_function('invoice_not_found'), 'danger')
        return redirect(url_for('invoices.invoice_dashboard'))
    
    form = InvoiceForm(data={
        'customer_name': invoice['customer_name'],
        'description': invoice['description'],
        'amount': invoice['amount']
    })
    
    if form.validate_on_submit():
        try:
            mongo.db.invoices.update_one(
                {'_id': invoice_id, 'user_id': current_user.id},
                {
                    '$set': {
                        'customer_name': form.customer_name.data.strip(),
                        'description': form.description.data.strip(),
                        'amount': float(form.amount.data),
                        'updated_at': datetime.utcnow()
                    }
                }
            )
            flash(trans_function('invoice_updated'), 'success')
            logger.info(f"Invoice updated by user {current_user.id}: {invoice_id}")
            return redirect(url_for('invoices.invoice_dashboard'))
        except Exception as e:
            logger.error(f"Error updating invoice: {str(e)}")
            flash(trans_function('core_something_went_wrong'), 'danger')
            return render_template('invoices/create.html', form=form, invoice_id=invoice_id), 500
    return render_template('invoices/create.html', form=form, invoice_id=invoice_id)

@invoices_bp.route('/delete/<invoice_id>', methods=['POST'])
@login_required
def delete_invoice(invoice_id):
    try:
        result = mongo.db.invoices.delete_one({'_id': invoice_id, 'user_id': current_user.id})
        if result.deleted_count == 0:
            flash(trans_function('invoice_not_found'), 'danger')
        else:
            flash(trans_function('invoice_deleted'), 'success')
            logger.info(f"Invoice deleted by user {current_user.id}: {invoice_id}")
        return redirect(url_for('invoices.invoice_dashboard'))
    except Exception as e:
        logger.error(f"Error deleting invoice: {str(e)}")
        flash(trans_function('core_something_went_wrong'), 'danger')
        return redirect(url_for('invoices.invoice_dashboard')), 500
