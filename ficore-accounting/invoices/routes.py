from flask import Blueprint, request, render_template, redirect, url_for, flash, send_file, current_app
from flask_wtf import FlaskForm
from wtforms import StringField, FloatField, SelectField, DateField, validators
from flask_login import login_required, current_user
from datetime import datetime, date
from utils import trans_function
import logging
import csv
from io import StringIO
import pymongo
from bson import ObjectId

logger = logging.getLogger(__name__)

invoices_bp = Blueprint('invoices', __name__, template_folder='templates')

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
    status = SelectField('Status', choices=[('pending', 'Pending'), ('settled', 'Settled')],
                        validators=[validators.DataRequired()])
    due_date = DateField('Due Date', format='%Y-%m-%d', validators=[validators.Optional()])
    settled_date = DateField('Settled Date', format='%Y-%m-%d', validators=[validators.Optional()])

@invoices_bp.route('/invoice_dashboard', methods=['GET'])
def invoice_dashboard():
    # Initialize filter variables for robustness
    status_filter = ''
    customer_filter = ''
    start_date = ''
    end_date = ''
    try:
        user_id = current_user.id if current_user.is_authenticated else 'guest'
        mongo = current_app.extensions['pymongo']
        status_filter = request.args.get('status', '')
        customer_filter = request.args.get('customer', '')
        start_date = request.args.get('start_date', '')
        end_date = request.args.get('end_date', '')
        
        query = {'user_id': user_id}
        if status_filter:
            query['status'] = status_filter
        if customer_filter:
            query['customer_name'] = {'$regex': customer_filter, '$options': 'i'}
        if start_date and end_date:
            query['created_at'] = {
                '$gte': datetime.strptime(start_date, '%Y-%m-%d'),
                '$lte': datetime.strptime(end_date, '%Y-%m-%d')
            }
        
        invoices = list(mongo.db.invoices.find(query).sort('created_at', -1))
        for invoice in invoices:
            invoice['_id'] = str(invoice['_id'])
            due_date = invoice.get('due_date')
            # Convert string date to datetime for comparison if stored as string
            if isinstance(due_date, str):
                due_date = datetime.strptime(due_date, '%Y-%m-%d')
            invoice['is_overdue'] = invoice['status'] == 'pending' and due_date and due_date < datetime.utcnow()
        return render_template('invoices/view.html', invoices=invoices, 
                            status_filter=status_filter, customer_filter=customer_filter,
                            start_date=start_date, end_date=end_date)
    except Exception as e:
        logger.error(f"Error fetching invoices: {str(e)}")
        flash(trans_function('core_something_went_wrong', default='An error occurred, please try again'), 'danger')
        return render_template('invoices/view.html', invoices=[]), 500

@invoices_bp.route('/create', methods=['GET', 'POST'])
def create_invoice():
    form = InvoiceForm()
    if form.validate_on_submit():
        try:
            user_id = current_user.id if current_user.is_authenticated else 'guest'
            mongo = current_app.extensions['pymongo']
            # Generate invoice number atomically
            last_invoice = mongo.db.invoices.find_one(sort=[('invoice_number', -1)])
            if last_invoice and last_invoice.get('invoice_number'):
                try:
                    last_num = int(last_invoice['invoice_number'])
                    invoice_number = str(last_num + 1).zfill(6)
                except ValueError:
                    # Handle cases where invoice_number isn't a number
                    count = mongo.db.invoices.count_documents({})
                    invoice_number = str(count + 1).zfill(6)
            else:
                invoice_number = '000001'

            # Convert date objects to strings for MongoDB compatibility
            due_date = form.due_date.data.strftime('%Y-%m-%d') if form.due_date.data else None
            settled_date = form.settled_date.data.strftime('%Y-%m-%d') if form.status.data == 'settled' and form.settled_date.data else None

            invoice = {
                'user_id': user_id,
                'customer_name': form.customer_name.data.strip(),
                'description': form.description.data.strip(),
                'amount': float(form.amount.data),
                'status': form.status.data,
                'due_date': due_date,
                'settled_date': settled_date,
                'created_at': datetime.utcnow(),
                'invoice_number': invoice_number
            }
            try:
                result = mongo.db.invoices.insert_one(invoice)
                flash(trans_function('invoice_created', default='Invoice created successfully'), 'success')
                logger.info(f"Invoice created by user {user_id}: {result.inserted_id}")
                return redirect(url_for('invoices.invoice_dashboard'))
            except pymongo.errors.DuplicateKeyError:
                # Single retry in case of race condition
                last_invoice = mongo.db.invoices.find_one(sort=[('invoice_number', -1)])
                last_num = int(last_invoice['invoice_number']) if last_invoice and last_invoice.get('invoice_number') else 0
                invoice['invoice_number'] = str(last_num + 1).zfill(6)
                result = mongo.db.invoices.insert_one(invoice)
                flash(trans_function('invoice_created', default='Invoice created successfully'), 'success')
                logger.info(f"Invoice created by user {user_id}: {result.inserted_id}")
                return redirect(url_for('invoices.invoice_dashboard'))
        except Exception as e:
            logger.error(f"Error creating invoice: {str(e)}")
            flash(trans_function('core_something_went_wrong', default='An error occurred, please try again'), 'danger')
            return render_template('invoices/create.html', form=form), 500
    return render_template('invoices/create.html', form=form)
    
@invoices_bp.route('/update/<invoice_id>', methods=['GET', 'POST'])
def update_invoice(invoice_id):
    user_id = current_user.id if current_user.is_authenticated else 'guest'
    mongo = current_app.extensions['pymongo']
    invoice = mongo.db.invoices.find_one({'_id': ObjectId(invoice_id), 'user_id': user_id})
    if not invoice:
        flash(trans_function('invoice_not_found', default='Invoice not found'), 'danger')
        return redirect(url_for('invoices.invoice_dashboard'))
    
    # Convert string dates back to date objects for form population
    due_date = datetime.strptime(invoice['due_date'], '%Y-%m-%d').date() if invoice.get('due_date') else None
    settled_date = datetime.strptime(invoice['settled_date'], '%Y-%m-%d').date() if invoice.get('settled_date') else None

    form = InvoiceForm(data={
        'customer_name': invoice['customer_name'],
        'description': invoice['description'],
        'amount': invoice['amount'],
        'status': invoice['status'],
        'due_date': due_date,
        'settled_date': settled_date
    })
    
    if form.validate_on_submit():
        try:
            # Convert date objects to strings for MongoDB
            due_date = form.due_date.data.strftime('%Y-%m-%d') if form.due_date.data else None
            settled_date = form.settled_date.data.strftime('%Y-%m-%d') if form.status.data == 'settled' and form.settled_date.data else None

            mongo.db.invoices.update_one(
                {'_id': ObjectId(invoice_id), 'user_id': user_id},
                {
                    '$set': {
                        'customer_name': form.customer_name.data.strip(),
                        'description': form.description.data.strip(),
                        'amount': float(form.amount.data),
                        'status': form.status.data,
                        'due_date': due_date,
                        'settled_date': settled_date,
                        'updated_at': datetime.utcnow()
                    }
                }
            )
            flash(trans_function('invoice_updated', default='Invoice updated successfully'), 'success')
            logger.info(f"Invoice updated by user {user_id}: {invoice_id}")
            return redirect(url_for('invoices.invoice_dashboard'))
        except Exception as e:
            logger.error(f"Error updating invoice: {str(e)}")
            flash(trans_function('core_something_went_wrong', default='An error occurred, please try again'), 'danger')
            return render_template('invoices/create.html', form=form, invoice_id=invoice_id), 500
    return render_template('invoices/create.html', form=form, invoice_id=invoice_id)

@invoices_bp.route('/delete/<invoice_id>', methods=['POST'])
def delete_invoice(invoice_id):
    try:
        user_id = current_user.id if current_user.is_authenticated else 'guest'
        mongo = current_app.extensions['pymongo']
        result = mongo.db.invoices.delete_one({'_id': ObjectId(invoice_id), 'user_id': user_id})
        if result.deleted_count == 0:
            flash(trans_function('invoice_not_found', default='Invoice not found'), 'danger')
        else:
            flash(trans_function('invoice_deleted', default='Invoice deleted successfully'), 'success')
            logger.info(f"Invoice deleted by user {user_id}: {invoice_id}")
        return redirect(url_for('invoices.invoice_dashboard'))
    except Exception as e:
        logger.error(f"Error deleting invoice: {str(e)}")
        flash(trans_function('core_something_went_wrong', default='An error occurred, please try again'), 'danger')
        return redirect(url_for('invoices.invoice_dashboard')), 500

@invoices_bp.route('/export/csv', methods=['GET'])
def export_invoices_csv():
    try:
        user_id = current_user.id if current_user.is_authenticated else 'guest'
        mongo = current_app.extensions['pymongo']
        invoices = list(mongo.db.invoices.find({'user_id': user_id}))
        output = StringIO()
        writer = csv.writer(output)
        writer.writerow(['Invoice Number', 'Customer Name', 'Description', 'Amount', 'Status', 'Created At', 'Due Date', 'Settled Date'])
        for invoice in invoices:
            writer.writerow([
                invoice.get('invoice_number', ''),
                invoice.get('customer_name', ''),
                invoice.get('description', ''),
                invoice.get('amount', 0),
                invoice.get('status', ''),
                invoice.get('created_at', '').strftime('%Y-%m-%d') if invoice.get('created_at') else '',
                invoice.get('due_date', ''),
                invoice.get('settled_date', '')
            ])
        output.seek(0)
        return send_file(
            output,
            mimetype='text/csv',
            as_attachment=True,
            download_name=f'invoices_{datetime.utcnow().strftime("%Y%m%d")}.csv'
        )
    except Exception as e:
        logger.error(f"Error exporting invoices: {str(e)}")
        flash(trans_function('core_something_went_wrong', default='An error occurred, please try again'), 'danger')
        return redirect(url_for('invoices.invoice_dashboard')), 500
