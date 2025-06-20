from flask import Blueprint, request, render_template, redirect, url_for, flash, send_file, current_app
from flask_wtf import FlaskForm
from wtforms import StringField, FloatField, SelectField, DateField, validators, SubmitField
from flask_login import login_required, current_user
from datetime import datetime, date
from utils import trans_function
import logging
import csv
from io import StringIO
import pymongo
from bson import ObjectId

logger = logging.getLogger(__name__)

invoices_bp = Blueprint('invoices', __name__, template_folder='templates/invoices')

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
    submit = SubmitField('Submit')

class FilterForm(FlaskForm):
    status = SelectField('Status', choices=[('', 'All'), ('pending', 'Pending'), ('settled', 'Settled')],
                         validators=[validators.Optional()])
    customer_name = StringField('Customer Name', validators=[validators.Optional(), validators.Length(max=100)])
    start_date = DateField('Start Date', format='%Y-%m-%d', validators=[validators.Optional()])
    end_date = DateField('End Date', format='%Y-%m-%d', validators=[validators.Optional()])
    submit = SubmitField('Filter')

@invoices_bp.route('/dashboard', methods=['GET'])
@login_required
def dashboard():
    form = FilterForm(request.args)
    status_filter = request.args.get('status', '')
    customer_filter = request.args.get('customer_name', '')
    start_date_filter = request.args.get('start_date', '')
    end_date_filter = request.args.get('end_date', '')
    try:
        mongo = current_app.extensions['pymongo']
        user = mongo.db.users.find_one({'_id': current_user.id})
        if not user:
            logger.error(f"User {current_user.id} not found in database")
            flash(trans_function('core_user_not_found', default='User not found'), 'danger')
            return redirect(url_for('users.login'))

        query = {'user_id': str(current_user.id)}
        if user.get('is_admin', False):
            query = {}  # Admins can see all invoices
        if status_filter:
            query['status'] = status_filter
        if customer_filter:
            query['customer_name'] = {'$regex': customer_filter, '$options': 'i'}
        if start_date_filter and end_date_filter:
            try:
                start_date = datetime.strptime(start_date_filter, '%Y-%m-%d')
                end_date = datetime.strptime(end_date_filter, '%Y-%m-%d').replace(hour=23, minute=59, second=59)
                query['created_at'] = {'$gte': start_date, '$lte': end_date}
            except ValueError:
                flash(trans_function('invalid_date_format', default='Invalid date format'), 'danger')
                logger.warning(f"Invalid date range for user {current_user.id}: {start_date_filter} to {end_date_filter}")

        logger.debug(f"Invoice query for user {current_user.id}: {query}")
        invoices = list(mongo.db.invoices.find(query).sort('created_at', -1).limit(50))
        for invoice in invoices:
            invoice['_id'] = str(invoice['_id'])
            due_date = invoice.get('due_date')
            if isinstance(due_date, str):
                try:
                    due_date = datetime.strptime(due_date, '%Y-%m-%d').date()
                except ValueError:
                    due_date = None
            settled_date = invoice.get('settled_date')
            if isinstance(settled_date, str):
                try:
                    settled_date = datetime.strptime(settled_date, '%Y-%m-%d').date()
                except ValueError:
                    settled_date = None
            invoice['due_date'] = due_date
            invoice['settled_date'] = settled_date
            invoice['is_overdue'] = invoice['status'] == 'pending' and due_date and due_date < date.today()

        return render_template(
            'invoices/view.html',
            invoices=invoices,
            form=form,
            status_filter=status_filter,
            customer_filter=customer_filter,
            start_date_filter=start_date_filter,
            end_date_filter=end_date_filter
        )
    except pymongo.errors.PyMongoError as e:
        logger.error(f"MongoDB error fetching invoices for user {current_user.id}: {str(e)}")
        flash(trans_function('core_something_went_wrong', default='An error occurred, please try again'), 'danger')
        return "An error occurred while loading the invoices dashboard.", 500
    except Exception as e:
        logger.error(f"Unexpected error fetching invoices for user {current_user.id}: {str(e)}")
        flash(trans_function('core_something_went_wrong', default='An error occurred, please try again'), 'danger')
        return "An error occurred while loading the invoices dashboard.", 500

@invoices_bp.route('/create', methods=['GET', 'POST'], endpoint='create')
@login_required
def create_invoice():
    form = InvoiceForm()
    if form.validate_on_submit():
        try:
            mongo = current_app.extensions['pymongo']
            last_invoice = mongo.db.invoices.find_one(sort=[('invoice_number', -1)])
            if last_invoice and last_invoice.get('invoice_number'):
                try:
                    last_num = int(last_invoice['invoice_number'])
                    invoice_number = str(last_num + 1).zfill(6)
                except ValueError:
                    count = mongo.db.invoices.count_documents({'user_id': str(current_user.id)})
                    invoice_number = str(count + 1).zfill(6)
            else:
                invoice_number = '000001'

            due_date = form.due_date.data
            settled_date = form.settled_date.data if form.status.data == 'settled' else None

            invoice = {
                'user_id': str(current_user.id),
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
                logger.info(f"Invoice {invoice_number} created by user {current_user.id}: {result.inserted_id}")
                return redirect(url_for('invoices.dashboard'))
            except pymongo.errors.DuplicateKeyError:
                last_invoice = mongo.db.invoices.find_one(sort=[('invoice_number', -1)])
                last_num = int(last_invoice['invoice_number']) if last_invoice and last_invoice.get('invoice_number') else 0
                invoice['invoice_number'] = str(last_num + 1).zfill(6)
                result = mongo.db.invoices.insert_one(invoice)
                flash(trans_function('invoice_created', default='Invoice created successfully'), 'success')
                logger.info(f"Invoice {invoice['invoice_number']} created by user {current_user.id}: {result.inserted_id}")
                return redirect(url_for('invoices.dashboard'))
        except pymongo.errors.PyMongoError as e:
            logger.error(f"MongoDB error creating invoice for user {current_user.id}: {str(e)}")
            flash(trans_function('core_something_went_wrong', default='An error occurred, please try again'), 'danger')
            return render_template('invoices/create.html', form=form), 500
        except Exception as e:
            logger.error(f"Unexpected error creating invoice for user {current_user.id}: {str(e)}")
            flash(trans_function('core_something_went_wrong', default='An error occurred, please try again'), 'danger')
            return render_template('invoices/create.html', form=form), 500
    return render_template('invoices/create.html', form=form)
    
@invoices_bp.route('/update/<invoice_id>', methods=['GET', 'POST'])
@login_required
def update_invoice(invoice_id):
    try:
        mongo = current_app.extensions['pymongo']
        invoice = mongo.db.invoices.find_one({'_id': ObjectId(invoice_id), 'user_id': str(current_user.id)})
        if not invoice:
            flash(trans_function('invoice_not_found', default='Invoice not found'), 'danger')
            return redirect(url_for('invoices.dashboard'))
        
        due_date = invoice.get('due_date')
        settled_date = invoice.get('settled_date')
        if isinstance(due_date, str):
            try:
                due_date = datetime.strptime(due_date, '%Y-%m-%d').date()
            except ValueError:
                due_date = None
        if isinstance(settled_date, str):
            try:
                settled_date = datetime.strptime(settled_date, '%Y-%m-%d').date()
            except ValueError:
                settled_date = None

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
                due_date = form.due_date.data
                settled_date = form.settled_date.data if form.status.data == 'settled' else None

                mongo.db.invoices.update_one(
                    {'_id': ObjectId(invoice_id), 'user_id': str(current_user.id)},
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
                logger.info(f"Invoice {invoice_id} updated by user {current_user.id}")
                return redirect(url_for('invoices.dashboard'))
            except pymongo.errors.PyMongoError as e:
                logger.error(f"MongoDB error updating invoice {invoice_id} for user {current_user.id}: {str(e)}")
                flash(trans_function('core_something_went_wrong', default='An error occurred, please try again'), 'danger')
                return render_template('invoices/create.html', form=form, invoice_id=invoice_id), 500
        return render_template('invoices/create.html', form=form, invoice_id=invoice_id)
    except pymongo.errors.PyMongoError as e:
        logger.error(f"MongoDB error fetching invoice {invoice_id} for user {current_user.id}: {str(e)}")
        flash(trans_function('invoice_not_found', default='Invoice not found'), 'danger')
        return redirect(url_for('invoices.dashboard'))
    except Exception as e:
        logger.error(f"Unexpected error fetching invoice {invoice_id} for user {current_user.id}: {str(e)}")
        flash(trans_function('core_something_went_wrong', default='An error occurred, please try again'), 'danger')
        return redirect(url_for('invoices.dashboard')), 500

@invoices_bp.route('/delete/<invoice_id>', methods=['POST'])
@login_required
def delete_invoice(invoice_id):
    try:
        mongo = current_app.extensions['pymongo']
        result = mongo.db.invoices.delete_one({'_id': ObjectId(invoice_id), 'user_id': str(current_user.id)})
        if result.deleted_count == 0:
            flash(trans_function('invoice_not_found', default='Invoice not found'), 'danger')
        else:
            flash(trans_function('invoice_deleted', default='Invoice deleted successfully'), 'success')
            logger.info(f"Invoice {invoice_id} deleted by user {current_user.id}")
        return redirect(url_for('invoices.dashboard'))
    except pymongo.errors.PyMongoError as e:
        logger.error(f"MongoDB error deleting invoice {invoice_id} for user {current_user.id}: {str(e)}")
        flash(trans_function('core_something_went_wrong', default='An error occurred, please try again'), 'danger')
        return redirect(url_for('invoices.dashboard')), 500
    except Exception as e:
        logger.error(f"Unexpected error deleting invoice {invoice_id} for user {current_user.id}: {str(e)}")
        flash(trans_function('core_something_went_wrong', default='An error occurred, please try again'), 'danger')
        return redirect(url_for('invoices.dashboard')), 500

@invoices_bp.route('/export/csv', methods=['GET'])
@login_required
def export_invoices_csv():
    try:
        mongo = current_app.extensions['pymongo']
        user = mongo.db.users.find_one({'_id': current_user.id})
        query = {'user_id': str(current_user.id)}
        if user.get('is_admin', False):
            query = {}  # Admins can export all invoices
        invoices = list(mongo.db.invoices.find(query))
        output = StringIO()
        writer = csv.writer(output)
        writer.writerow(['Invoice Number', 'Customer Name', 'Description', 'Amount', 'Status', 'Created At', 'Due Date', 'Settled Date'])
        for invoice in invoices:
            created_at = invoice.get('created_at')
            due_date = invoice.get('due_date')
            settled_date = invoice.get('settled_date')
            if isinstance(created_at, str):
                try:
                    created_at = datetime.strptime(created_at, '%Y-%m-%d')
                except ValueError:
                    created_at = None
            if isinstance(due_date, str):
                try:
                    due_date = datetime.strptime(due_date, '%Y-%m-%d').date()
                except ValueError:
                    due_date = None
            if isinstance(settled_date, str):
                try:
                    settled_date = datetime.strptime(settled_date, '%Y-%m-%d').date()
                except ValueError:
                    settled_date = None
            writer.writerow([
                invoice.get('invoice_number', ''),
                invoice.get('customer_name', ''),
                invoice.get('description', ''),
                invoice.get('amount', 0),
                invoice.get('status', ''),
                created_at.strftime('%Y-%m-%d') if created_at else '',
                due_date.strftime('%Y-%m-%d') if due_date else '',
                settled_date.strftime('%Y-%m-%d') if settled_date else ''
            ])
        output.seek(0)
        return send_file(
            output,
            mimetype='text/csv',
            as_attachment=True,
            download_name=f'invoices_{datetime.utcnow().strftime("%Y%m%d")}.csv'
        )
    except pymongo.errors.PyMongoError as e:
        logger.error(f"MongoDB error exporting invoices for user {current_user.id}: {str(e)}")
        flash(trans_function('core_something_went_wrong', default='An error occurred, please try again'), 'danger')
        return redirect(url_for('invoices.dashboard')), 500
    except Exception as e:
        logger.error(f"Unexpected error exporting invoices for user {current_user.id}: {str(e)}")
        flash(trans_function('core_something_went_wrong', default='An error occurred, please try again'), 'danger')
        return redirect(url_for('invoices.dashboard')), 500
