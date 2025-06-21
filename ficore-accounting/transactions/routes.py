from flask import Blueprint, request, render_template, redirect, url_for, flash, current_app, send_file
from flask_wtf import FlaskForm
from wtforms import StringField, FloatField, SelectField, validators, BooleanField, SubmitField
from flask_login import login_required, current_user
from datetime import datetime, date, timedelta
from utils import trans_function
import logging
import csv
from io import StringIO
from bson import ObjectId
from app import limiter

logger = logging.getLogger(__name__)

transactions_bp = Blueprint('transactions', __name__, template_folder='templates/transactions')

class TransactionForm(FlaskForm):
    party_name = StringField(trans_function('party_name', default='Party Name'), [
        validators.DataRequired(message=trans_function('party_name_required', default='Party name is required')),
        validators.Length(max=100)
    ])
    amount = FloatField(trans_function('amount', default='Amount'), [
        validators.DataRequired(message=trans_function('amount_required', default='Amount is required')),
        validators.NumberRange(min=0.01, message=trans_function('amount_positive', default='Amount must be greater than zero'))
    ])
    description = StringField(trans_function('description', default='Description'), [
        validators.DataRequired(message=trans_function('description_required', default='Description is required')),
        validators.Length(max=500)
    ])
    category = SelectField(trans_function('category', default='Category'), choices=[
        ('sales', trans_function('sales', default='Sales')),
        ('utilities', trans_function('utilities', default='Utilities')),
        ('transport', trans_function('transport', default='Transport')),
        ('other', trans_function('other', default='Other'))
    ], validators=[validators.DataRequired(message=trans_function('category_required', default='Category is required'))])
    is_recurring = BooleanField(trans_function('is_recurring', default='Recurring Transaction'))
    recurring_period = SelectField(trans_function('recurring_period', default='Recurring Period'), choices=[
        ('none', trans_function('none', default='None')),
        ('weekly', trans_function('weekly', default='Weekly')),
        ('monthly', trans_function('monthly', default='Monthly')),
        ('yearly', trans_function('yearly', default='Yearly'))
    ])
    submit = SubmitField(trans_function('submit', default='Submit'))

class FilterForm(FlaskForm):
    category = SelectField(trans_function('category', default='Category'), choices=[
        ('', trans_function('all', default='All')),
        ('sales', trans_function('sales', default='Sales')),
        ('utilities', trans_function('utilities', default='Utilities')),
        ('transport', trans_function('transport', default='Transport')),
        ('other', trans_function('other', default='Other'))
    ], validators=[validators.Optional()])
    party_name = StringField(trans_function('party_name', default='Party Name'), validators=[validators.Optional(), validators.Length(max=100)])
    date = DateField(trans_function('date', default='Date'), format='%Y-%m-%d', validators=[validators.Optional()])
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

@transactions_bp.route('/receipts', methods=['GET'])
@login_required
def receipts_history():
    form = FilterForm(request.args)
    date_filter = request.args.get('date', '')
    category_filter = request.args.get('category', '')
    party_name_filter = request.args.get('party_name', '')
    try:
        mongo = current_app.extensions['pymongo']
        user = mongo.db.users.find_one({'_id': current_user.id})
        query = {'user_id': str(current_user.id), 'type': 'receipt'}
        if user.get('role') == 'admin':
            query.pop('user_id')
        if date_filter:
            try:
                date_val = datetime.strptime(date_filter, '%Y-%m-%d')
                query['created_at'] = {'$gte': date_val, '$lt': date_val + timedelta(days=1)}
            except ValueError:
                flash(trans_function('invalid_date_format', default='Invalid date format'), 'danger')
        if category_filter:
            query['category'] = category_filter
        if party_name_filter:
            query['party_name'] = {'$regex': party_name_filter, '$options': 'i'}
        transactions = list(mongo.db.transactions.find(query).sort('created_at', -1).limit(50))
        total = sum(t['amount'] for t in transactions)
        category_totals = {}
        for t in transactions:
            t['_id'] = str(t['_id'])
            category = t['category']
            category_totals[category] = category_totals.get(category, 0) + t['amount']
        return render_template('transactions/receipts.html',
                             transactions=transactions,
                             total=total,
                             category_totals=category_totals,
                             form=form,
                             type='receipt',
                             filter_values={'date': date_filter, 'category': category_filter, 'party_name': party_name_filter})
    except pymongo.errors.PyMongoError as e:
        logger.error(f"MongoDB error fetching receipts: {str(e)}")
        flash(trans_function('core_something_went_wrong', default='An error occurred'), 'danger')
        return render_template('transactions/receipts.html', transactions=[], total=0, category_totals={}, form=form, type='receipt'), 500

@transactions_bp.route('/payments', methods=['GET'])
@login_required
def payments_history():
    form = FilterForm(request.args)
    date_filter = request.args.get('date', '')
    category_filter = request.args.get('category', '')
    party_name_filter = request.args.get('party_name', '')
    try:
        mongo = current_app.extensions['pymongo']
        user = mongo.db.users.find_one({'_id': current_user.id})
        query = {'user_id': str(current_user.id), 'type': 'payment'}
        if user.get('role') == 'admin':
            query.pop('user_id')
        if date_filter:
            try:
                date_val = datetime.strptime(date_filter, '%Y-%m-%d')
                query['created_at'] = {'$gte': date_val, '$lt': date_val + timedelta(days=1)}
            except ValueError:
                flash(trans_function('invalid_date_format', default='Invalid date format'), 'danger')
        if category_filter:
            query['category'] = category_filter
        if party_name_filter:
            query['party_name'] = {'$regex': party_name_filter, '$options': 'i'}
        transactions = list(mongo.db.transactions.find(query).sort('created_at', -1).limit(50))
        total = sum(t['amount'] for t in transactions)
        category_totals = {}
        for t in transactions:
            t['_id'] = str(t['_id'])
            category = t['category']
            category_totals[category] = category_totals.get(category, 0) + t['amount']
        return render_template('transactions/payments.html',
                             transactions=transactions,
                             total=total,
                             category_totals=category_totals,
                             form=form,
                             type='payment',
                             filter_values={'date': date_filter, 'category': category_filter, 'party_name': party_name_filter})
    except pymongo.errors.PyMongoError as e:
        logger.error(f"MongoDB error fetching payments: {str(e)}")
        flash(trans_function('core_something_went_wrong', default='An error occurred'), 'danger')
        return render_template('transactions/payments.html', transactions=[], total=0, category_totals={}, form=form, type='payment'), 500

@transactions_bp.route('/add/<type>', methods=['GET', 'POST'])
@login_required
@limiter.limit("50 per hour")
def add_transaction(type):
    if type not in ['receipt', 'payment']:
        flash(trans_function('invalid_transaction_type', default='Invalid transaction type'), 'danger')
        return redirect(url_for('transactions.receipts_history'))
    if not check_coins_required(f"add_{type}"):
        return redirect(url_for('coins.purchase'))
    form = TransactionForm()
    if form.validate_on_submit():
        try:
            mongo = current_app.extensions['pymongo']
            transaction = {
                'user_id': str(current_user.id),
                'type': type,
                'party_name': form.party_name.data.strip(),
                'amount': float(form.amount.data),
                'description': form.description.data.strip(),
                'category': form.category.data,
                'photo_url': None,  # Placeholder for future receipt upload
                'is_recurring': form.is_recurring.data,
                'recurring_period': form.recurring_period.data if form.is_recurring.data else 'none',
                'created_at': datetime.utcnow(),
                'updated_at': datetime.utcnow()
            }
            result = mongo.db.transactions.insert_one(transaction)
            deduct_coins(f"add_{type}")
            flash(trans_function('transaction_added', default='Transaction added successfully'), 'success')
            logger.info(f"{type.capitalize()} added by user {current_user.id}: {result.inserted_id}")
            return redirect(url_for(f'transactions.{type}s_history'))
        except pymongo.errors.PyMongoError as e:
            logger.error(f"MongoDB error adding {type}: {str(e)}")
            flash(trans_function('core_something_went_wrong', default='An error occurred'), 'danger')
            return render_template('transactions/add.html', form=form, type=type), 500
    return render_template('transactions/add.html', form=form, type=type)

@transactions_bp.route('/update/<type>/<transaction_id>', methods=['GET', 'POST'])
@login_required
@limiter.limit("50 per hour")
def update_transaction(type, transaction_id):
    if type not in ['receipt', 'payment']:
        flash(trans_function('invalid_transaction_type', default='Invalid transaction type'), 'danger')
        return redirect(url_for('transactions.receipts_history'))
    if not check_coins_required(f"update_{type}"):
        return redirect(url_for('coins.purchase'))
    try:
        mongo = current_app.extensions['pymongo']
        transaction = mongo.db.transactions.find_one({'_id': ObjectId(transaction_id), 'user_id': str(current_user.id), 'type': type})
        if not transaction:
            flash(trans_function('transaction_not_found', default='Transaction not found'), 'danger')
            return redirect(url_for(f'transactions.{type}s_history'))
        form = TransactionForm(data={
            'party_name': transaction['party_name'],
            'amount': transaction['amount'],
            'description': transaction['description'],
            'category': transaction['category'],
            'is_recurring': transaction.get('is_recurring', False),
            'recurring_period': transaction.get('recurring_period', 'none')
        })
        if form.validate_on_submit():
            mongo.db.transactions.update_one(
                {'_id': ObjectId(transaction_id), 'user_id': str(current_user.id)},
                {
                    '$set': {
                        'party_name': form.party_name.data.strip(),
                        'amount': float(form.amount.data),
                        'description': form.description.data.strip(),
                        'category': form.category.data,
                        'is_recurring': form.is_recurring.data,
                        'recurring_period': form.recurring_period.data if form.is_recurring.data else 'none',
                        'updated_at': datetime.utcnow()
                    }
                }
            )
            deduct_coins(f"update_{type}")
            flash(trans_function('transaction_updated', default='Transaction updated successfully'), 'success')
            logger.info(f"{type.capitalize()} updated by user {current_user.id}: {transaction_id}")
            return redirect(url_for(f'transactions.{type}s_history'))
        return render_template('transactions/add.html', form=form, type=type, transaction_id=transaction_id)
    except pymongo.errors.PyMongoError as e:
        logger.error(f"MongoDB error updating {type} {transaction_id}: {str(e)}")
        flash(trans_function('core_something_went_wrong', default='An error occurred'), 'danger')
        return render_template('transactions/add.html', form=form, type=type, transaction_id=transaction_id), 500

@transactions_bp.route('/delete/<type>/<transaction_id>', methods=['POST'])
@login_required
@limiter.limit("50 per hour")
def delete_transaction(type, transaction_id):
    if type not in ['receipt', 'payment']:
        flash(trans_function('invalid_transaction_type', default='Invalid transaction type'), 'danger')
        return redirect(url_for('transactions.receipts_history'))
    try:
        mongo = current_app.extensions['pymongo']
        result = mongo.db.transactions.delete_one({'_id': ObjectId(transaction_id), 'user_id': str(current_user.id), 'type': type})
        if result.deleted_count == 0:
            flash(trans_function('transaction_not_found', default='Transaction not found'), 'danger')
        else:
            flash(trans_function('transaction_deleted', default='Transaction deleted successfully'), 'success')
            logger.info(f"{type.capitalize()} deleted by user {current_user.id}: {transaction_id}")
        return redirect(url_for(f'transactions.{type}s_history'))
    except pymongo.errors.PyMongoError as e:
        logger.error(f"MongoDB error deleting {type} {transaction_id}: {str(e)}")
        flash(trans_function('core_something_went_wrong', default='An error occurred'), 'danger')
        return redirect(url_for(f'transactions.{type}s_history')), 500

@transactions_bp.route('/export/<type>/csv', methods=['GET'])
@login_required
@limiter.limit("10 per hour")
def export_transactions_csv(type):
    if type not in ['receipt', 'payment']:
        flash(trans_function('invalid_transaction_type', default='Invalid transaction type'), 'danger')
        return redirect(url_for('transactions.receipts_history'))
    try:
        mongo = current_app.extensions['pymongo']
        user = mongo.db.users.find_one({'_id': current_user.id})
        query = {'user_id': str(current_user.id), 'type': type}
        if user.get('role') == 'admin':
            query.pop('user_id')
        transactions = list(mongo.db.transactions.find(query))
        output = StringIO()
        writer = csv.writer(output)
        writer.writerow(['Party Name', 'Amount', 'Description', 'Category', 'Is Recurring', 'Recurring Period', 'Created At'])
        for t in transactions:
            writer.writerow([
                t.get('party_name', ''),
                t.get('amount', 0),
                t.get('description', ''),
                t.get('category', '').capitalize(),
                t.get('is_recurring', False),
                t.get('recurring_period', 'none').capitalize(),
                t.get('created_at', '').strftime('%Y-%m-%d') if t.get('created_at') else ''
            ])
        output.seek(0)
        return send_file(
            output,
            mimetype='text/csv',
            as_attachment=True,
            download_name=f'{type}s_{datetime.utcnow().strftime("%Y%m%d")}.csv'
        )
    except pymongo.errors.PyMongoError as e:
        logger.error(f"MongoDB error exporting {type}s: {str(e)}")
        flash(trans_function('core_something_went_wrong', default='An error occurred'), 'danger')
        return redirect(url_for(f'transactions.{type}s_history')), 500
