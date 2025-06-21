from flask import Blueprint, request, render_template, redirect, url_for, flash, current_app
from flask_wtf import FlaskForm
from wtforms import StringField, FloatField, SelectField, DateField, validators, SubmitField, FieldList, FormField
from flask_login import login_required, current_user
from datetime import datetime, date
from utils import trans_function
import logging
import csv
from io import StringIO
import pymongo
from bson import ObjectId
from app import limiter

logger = logging.getLogger(__name__)

invoices_bp = Blueprint('invoices', __name__, template_folder='templates/invoices')

class InvoiceItemForm(FlaskForm):
    description = StringField(trans_function('item_description', default='Description'), [
        validators.DataRequired(message=trans_function('item_description_required', default='Item description is required')),
        validators.Length(max=200)
    ])
    quantity = FloatField(trans_function('quantity', default='Quantity'), [
        validators.DataRequired(message=trans_function('quantity_required', default='Quantity is required')),
        validators.NumberRange(min=0.01)
    ])
    price = FloatField(trans_function('price', default='Price'), [
        validators.DataRequired(message=trans_function('price_required', default='Price is required')),
        validators.NumberRange(min=0)
    ])

class InvoiceForm(FlaskForm):
    party_name = StringField(trans_function('party_name', default='Party Name'), [
        validators.DataRequired(message=trans_function('party_name_required', default='Party name is required')),
        validators.Length(min=2, max=100)
    ])
    phone = StringField(trans_function('phone', default='Phone'), [
        validators.Optional(),
        validators.Length(max=20)
    ])
    items = FieldList(FormField(InvoiceItemForm), min_entries=1, max_entries=50)
    due_date = DateField(trans_function('due_date', default='Due Date'), format='%Y-%m-%d', validators=[validators.Optional()])
    submit = SubmitField(trans_function('submit', default='Submit'))

class FilterForm(FlaskForm):
    status = SelectField(trans_function('status', default='Status'), choices=[
        ('', trans_function('all', default='All')),
        ('unpaid', trans_function('unpaid', default='Unpaid')),
        ('part-paid', trans_function('part_paid', default='Part Paid')),
        ('paid', trans_function('paid', default='Paid'))
    ], validators=[validators.Optional()])
    party_name = StringField(trans_function('party_name', default='Party Name'), validators=[validators.Optional(), validators.Length(max=100)])
    start_date = DateField(trans_function('start_date', default='Start Date'), format='%Y-%m-%d', validators=[validators.Optional()])
    end_date = DateField(trans_function('end_date', default='End Date'), format='%Y-%m-%d', validators=[validators.Optional()])
    submit = SubmitField(trans_function('filter', default='Filter'))

def check_coins_required(action, required_coins=1):
    """Check if user has enough coins for an action."""
    mongo = current_app.extensions['pymongo']
    user = mongo.db.users.find_one({'_id': current_user.id})
    if user['coin_balance'] < required_coins:
        flash(trans_function('insufficient_coins', default='Insufficient coins. Please purchase more.'), 'danger')
        return False
    return True

def deduct_coins(action, coins=1):
    """Deduct coins and log transaction."""
    mongo = current_app.extensions['pymongo']
    mongo.db.users.update_one(
        {'_id': current_user.id},
        {'$inc': {'coin_balance': -coins}}
    )
    mongo.db.coin_transactions.insert_one({
        'user_id': str(current_user.id),
        'amount': -coins,
        'type': 'spend',
        'ref': f"{action}_{datetime.utcnow().isoformat()}",
        'date': datetime.utcnow()
    })

@invoices_bp.route('/debtors', methods=['GET'])
@login_required
def debtors_dashboard():
    form = FilterForm(request.args)
    status_filter = request.args.get('status', '')
    party_name_filter = request.args.get('party_name', '')
    start_date_filter = request.args.get('start_date', '')
    end_date_filter = request.args.get('end_date', '')
    try:
        mongo = current_app.extensions['pymongo']
        user = mongo.db.users.find_one({'_id': current_user.id})
        query = {'user_id': str(current_user.id), 'type': 'debtor'}
        if user.get('role') == 'admin':
            query.pop('user_id')
        if status_filter:
            query['status'] = status_filter
        if party_name_filter:
            query['party_name'] = {'$regex': party_name_filter, '$options': 'i'}
        if start_date_filter and end_date_filter:
            try:
                start_date = datetime.strptime(start_date_filter, '%Y-%m-%d')
                end_date = datetime.strptime(end_date_filter, '%Y-%m-%d').replace(hour=23, minute=59, second=59)
                query['created_at'] = {'$gte': start_date, '$lte': end_date}
            except ValueError:
                flash(trans_function('invalid_date_format', default='Invalid date format'), 'danger')
        invoices = list(mongo.db.invoices.find(query).sort('created_at', -1).limit(50))
        for invoice in invoices:
            invoice['_id'] = str(invoice['_id'])
            invoice['total'] = sum(item['qty'] * item['price'] for item in invoice.get('items', []))
            invoice['is_overdue'] = invoice['status'] == 'unpaid' and invoice.get('due_date') and invoice['due_date'] < date.today()
        return render_template(
            'invoices/debtors.html',
            invoices=invoices,
            form=form,
            type='debtor',
            status_filter=status_filter,
            party_name_filter=party_name_filter,
            start_date_filter=start_date_filter,
            end_date_filter=end_date_filter
        )
    except pymongo.errors.PyMongoError as e:
        logger.error(f"MongoDB error fetching debtors for user {current_user.id}: {str(e)}")
        flash(trans_function('core_something_went_wrong', default='An error occurred'), 'danger')
        return render_template('invoices/debtors.html', invoices=[], form=form, type='debtor'), 500

@invoices_bp.route('/creditors', methods=['GET'])
@login_required
def creditors_dashboard():
    form = FilterForm(request.args)
    status_filter = request.args.get('status', '')
    party_name_filter = request.args.get('party_name', '')
    start_date_filter = request.args.get('start_date', '')
    end_date_filter = request.args.get('end_date', '')
    try:
        mongo = current_app.extensions['pymongo']
        user = mongo.db.users.find_one({'_id': current_user.id})
        query = {'user_id': str(current_user.id), 'type': 'creditor'}
        if user.get('role') == 'admin':
            query.pop('user_id')
        if status_filter:
            query['status'] = status_filter
        if party_name_filter:
            query['party_name'] = {'$regex': party_name_filter, '$options': 'i'}
        if start_date_filter and end_date_filter:
            try:
                start_date = datetime.strptime(start_date_filter, '%Y-%m-%d')
                end_date = datetime.strptime(end_date_filter, '%Y-%m-%d').replace(hour=23, minute=59, second=59)
                query['created_at'] = {'$gte': start_date, '$lte': end_date}
            except ValueError:
                flash(trans_function('invalid_date_format', default='Invalid date format'), 'danger')
        invoices = list(mongo.db.invoices.find(query).sort('created_at', -1).limit(50))
        for invoice in invoices:
            invoice['_id'] = str(invoice['_id'])
            invoice['total'] = sum(item['qty'] * item['price'] for item in invoice.get('items', []))
            invoice['is_overdue'] = invoice['status'] == 'unpaid' and invoice.get('due_date') and invoice['due_date'] < date.today()
        return render_template(
            'invoices/creditors.html',
            invoices=invoices,
            form=form,
            type='creditor',
            status_filter=status_filter,
            party_name_filter=party_name_filter,
            start_date_filter=start_date_filter,
            end_date_filter=end_date_filter
        )
    except pymongo.errors.PyMongoError as e:
        logger.error(f"MongoDB error fetching creditors for user {current_user.id}: {str(e)}")
        flash(trans_function('core_something_went_wrong', default='An error occurred'), 'danger')
        return render_template('invoices/creditors.html', invoices=[], form=form, type='creditor'), 500

@invoices_bp.route('/create/<type>', methods=['GET', 'POST'])
@login_required
@limiter.limit("50 per hour")
def create_invoice(type):
    if type not in ['debtor', 'creditor']:
        flash(trans_function('invalid_invoice_type', default='Invalid invoice type'), 'danger')
        return redirect(url_for('invoices.debtors_dashboard'))
    if not check_coins_required(f"create_{type}_invoice"):
        return redirect(url_for('coins.purchase'))
    form = InvoiceForm()
    if form.validate_on_submit():
        try:
            mongo = current_app.extensions['pymongo']
            last_invoice = mongo.db.invoices.find_one(sort=[('invoice_number', -1)])
            invoice_number = str(int(last_invoice['invoice_number']) + 1).zfill(6) if last_invoice else '000001'
            items = [{
                'desc': item.description.data.strip(),
                'qty': float(item.quantity.data),
                'price': float(item.price.data)
            } for item in form.items]
            total = sum(item['qty'] * item['price'] for item in items)
            invoice = {
                'user_id': str(current_user.id),
                'type': type,
                'party_name': form.party_name.data.strip(),
                'phone': form.phone.data.strip() if form.phone.data else None,
                'items': items,
                'total': total,
                'paid_amount': 0,
                'due_date': form.due_date.data,
                'status': 'unpaid',
                'payments': [],
                'created_at': datetime.utcnow(),
                'invoice_number': invoice_number
            }
            result = mongo.db.invoices.insert_one(invoice)
            deduct_coins(f"create_{type}_invoice")
            flash(trans_function('invoice_created', default='Invoice created successfully'), 'success')
            logger.info(f"{type.capitalize()} invoice {invoice_number} created by user {current_user.id}")
            return redirect(url_for(f'invoices.{type}s_dashboard'))
        except pymongo.errors.PyMongoError as e:
            logger.error(f"MongoDB error creating {type} invoice: {str(e)}")
            flash(trans_function('core_something_went_wrong', default='An error occurred'), 'danger')
            return render_template('invoices/create.html', form=form, type=type), 500
    return render_template('invoices/create.html', form=form, type=type)

@invoices_bp.route('/update/<type>/<invoice_id>', methods=['GET', 'POST'])
@login_required
@limiter.limit("50 per hour")
def update_invoice(type, invoice_id):
    if type not in ['debtor', 'creditor']:
        flash(trans_function('invalid_invoice_type', default='Invalid invoice type'), 'danger')
        return redirect(url_for('invoices.debtors_dashboard'))
    if not check_coins_required(f"update_{type}_invoice"):
        return redirect(url_for('coins.purchase'))
    try:
        mongo = current_app.extensions['pymongo']
        invoice = mongo.db.invoices.find_one({'_id': ObjectId(invoice_id), 'user_id': str(current_user.id), 'type': type})
        if not invoice:
            flash(trans_function('invoice_not_found', default='Invoice not found'), 'danger')
            return redirect(url_for(f'invoices.{type}s_dashboard'))
        form = InvoiceForm(data={
            'party_name': invoice['party_name'],
            'phone': invoice.get('phone'),
            'due_date': invoice.get('due_date'),
            'items': [{'description': item['desc'], 'quantity': item['qty'], 'price': item['price']} for item in invoice['items']]
        })
        if form.validate_on_submit():
            items = [{
                'desc': item.description.data.strip(),
                'qty': float(item.quantity.data),
                'price': float(item.price.data)
            } for item in form.items]
            total = sum(item['qty'] * item['price'] for item in items)
            mongo.db.invoices.update_one(
                {'_id': ObjectId(invoice_id), 'user_id': str(current_user.id)},
                {
                    '$set': {
                        'party_name': form.party_name.data.strip(),
                        'phone': form.phone.data.strip() if form.phone.data else None,
                        'items': items,
                        'total': total,
                        'due_date': form.due_date.data,
                        'updated_at': datetime.utcnow()
                    }
                }
            )
            deduct_coins(f"update_{type}_invoice")
            flash(trans_function('invoice_updated', default='Invoice updated successfully'), 'success')
            logger.info(f"{type.capitalize()} invoice {invoice_id} updated by user {current_user.id}")
            return redirect(url_for(f'invoices.{type}s_dashboard'))
        return render_template('invoices/create.html', form=form, type=type, invoice_id=invoice_id)
    except pymongo.errors.PyMongoError as e:
        logger.error(f"MongoDB error updating {type} invoice {invoice_id}: {str(e)}")
        flash(trans_function('core_something_went_wrong', default='An error occurred'), 'danger')
        return redirect(url_for(f'invoices.{type}s_dashboard')), 500

@invoices_bp.route('/delete/<type>/<invoice_id>', methods=['POST'])
@login_required
@limiter.limit("50 per hour")
def delete_invoice(type, invoice_id):
    if type not in ['debtor', 'creditor']:
        flash(trans_function('invalid_invoice_type', default='Invalid invoice type'), 'danger')
        return redirect(url_for('invoices.debtors_dashboard'))
    try:
        mongo = current_app.extensions['pymongo']
        result = mongo.db.invoices.delete_one({'_id': ObjectId(invoice_id), 'user_id': str(current_user.id), 'type': type})
        if result.deleted_count == 0:
            flash(trans_function('invoice_not_found', default='Invoice not found'), 'danger')
        else:
            flash(trans_function('invoice_deleted', default='Invoice deleted successfully'), 'success')
            logger.info(f"{type.capitalize()} invoice {invoice_id} deleted by user {current_user.id}")
        return redirect(url_for(f'invoices.{type}s_dashboard'))
    except pymongo.errors.PyMongoError as e:
        logger.error(f"MongoDB error deleting {type} invoice {invoice_id}: {str(e)}")
        flash(trans_function('core_something_went_wrong', default='An error occurred'), 'danger')
        return redirect(url_for(f'invoices.{type}s_dashboard')), 500

@invoices_bp.route('/export/<type>/csv', methods=['GET'])
@login_required
@limiter.limit("10 per hour")
def export_invoices_csv(type):
    if type not in ['debtor', 'creditor']:
        flash(trans_function('invalid_invoice_type', default='Invalid invoice type'), 'danger')
        return redirect(url_for('invoices.debtors_dashboard'))
    try:
        mongo = current_app.extensions['pymongo']
        user = mongo.db.users.find_one({'_id': current_user.id})
        query = {'user_id': str(current_user.id), 'type': type}
        if user.get('role') == 'admin':
            query.pop('user_id')
        invoices = list(mongo.db.invoices.find(query))
        output = StringIO()
        writer = csv.writer(output)
        writer.writerow(['Invoice Number', 'Party Name', 'Phone', 'Total', 'Paid Amount', 'Status', 'Created At', 'Due Date'])
        for invoice in invoices:
            writer.writerow([
                invoice.get('invoice_number', ''),
                invoice.get('party_name', ''),
                invoice.get('phone', ''),
                sum(item['qty'] * item['price'] for item in invoice.get('items', [])),
                invoice.get('paid_amount', 0),
                invoice.get('status', ''),
                invoice.get('created_at', '').strftime('%Y-%m-%d') if invoice.get('created_at') else '',
                invoice.get('due_date', '').strftime('%Y-%m-%d') if invoice.get('due_date') else ''
            ])
        output.seek(0)
        return send_file(
            output,
            mimetype='text/csv',
            as_attachment=True,
            download_name=f'{type}s_{datetime.utcnow().strftime("%Y%m%d")}.csv'
        )
    except pymongo.errors.PyMongoError as e:
        logger.error(f"MongoDB error exporting {type} invoices: {str(e)}")
        flash(trans_function('core_something_went_wrong', default='An error occurred'), 'danger')
        return redirect(url_for(f'invoices.{type}s_dashboard')), 500
