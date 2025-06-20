from flask import Blueprint, request, render_template, redirect, url_for, flash, send_file, current_app
from flask_wtf import FlaskForm
from wtforms import StringField, FloatField, SelectField, validators, BooleanField
from flask_login import login_required, current_user
from datetime import datetime, date, timedelta
from utils import trans_function
import logging
import csv
from io import StringIO
from bson import ObjectId

logger = logging.getLogger(__name__)

transactions_bp = Blueprint('transactions', __name__, template_folder='templates/transactions')

class TransactionForm(FlaskForm):
    type = SelectField('Type', choices=[
        ('income', 'Money In'), ('expense', 'Money Out')
    ], validators=[validators.DataRequired(message='Type is required')])
    category = SelectField('Category', choices=[
        ('sales', 'Sales'), ('utilities', 'Utilities'), ('transport', 'Transport'), ('other', 'Other')
    ], validators=[validators.DataRequired(message='Category is required')])
    amount = FloatField('Amount', [
        validators.DataRequired(message='Amount is required'),
        validators.NumberRange(min=0.01, message='Amount must be greater than zero')
    ])
    description = StringField('Description', [
        validators.DataRequired(message='Description is required'),
        validators.Length(max=500, message='Description cannot exceed 500 characters')
    ])
    is_recurring = BooleanField('Recurring Transaction')
    recurring_period = SelectField('Recurring Period', choices=[
        ('none', 'None'), ('weekly', 'Weekly'), ('monthly', 'Monthly'), ('yearly', 'Yearly')
    ])

@transactions_bp.route('/history', methods=['GET'])
@login_required
def history():
    date_filter = ''
    category_filter = ''
    description_filter = ''
    try:
        mongo = current_app.extensions['pymongo']
        user = mongo.db.users.find_one({'_id': current_user.id})
        query = {'user_id': str(current_user.id)}
        if user.get('is_admin', False):
            query = {}  # Admins can see all transactions
        date_filter = request.args.get('date', '')
        category_filter = request.args.get('category', '')
        description_filter = request.args.get('description', '')

        if date_filter:
            try:
                date = datetime.strptime(date_filter, '%Y-%m-%d')
                query['created_at'] = {
                    '$gte': date,
                    '$lt': date + timedelta(days=1)
                }
            except ValueError:
                flash(trans_function('invalid_date_format', default='Invalid date format'), 'danger')
                logger.warning(f"Invalid date filter: {date_filter}")
        if category_filter:
            query['category'] = category_filter
        if description_filter:
            query['description'] = {'$regex': description_filter, '$options': 'i'}

        logger.debug(f"Transaction query: {query}")
        transactions = list(mongo.db.transactions.find(query).sort('created_at', -1).limit(50))
        for transaction in transactions:
            transaction['_id'] = str(transaction['_id'])
            created_at = transaction.get('created_at')
            updated_at = transaction.get('updated_at')
            if isinstance(created_at, str):
                try:
                    transaction['created_at'] = datetime.strptime(created_at, '%Y-%m-%d')
                except ValueError:
                    transaction['created_at'] = None
                    logger.warning(f"Invalid created_at string: {created_at}")
            if isinstance(updated_at, str):
                try:
                    transaction['updated_at'] = datetime.strptime(updated_at, '%Y-%m-%d')
                except ValueError:
                    transaction['updated_at'] = None
                    logger.warning(f"Invalid updated_at string: {updated_at}")

        total_income = sum(t['amount'] for t in transactions if t['type'] == 'income')
        total_expense = sum(t['amount'] for t in transactions if t['type'] == 'expense')
        net_balance = total_income - total_expense

        category_totals = {}
        for t in transactions:
            category = t['category']
            amount = t['amount'] if t['type'] == 'income' else -t['amount']
            category_totals[category] = category_totals.get(category, 0) + amount

        return render_template('transactions/history.html',
                             transactions=transactions,
                             total_income=total_income,
                             total_expense=total_expense,
                             net_balance=net_balance,
                             category_totals=category_totals,
                             categories=[c[0] for c in TransactionForm().category.choices],
                             filter_values={
                                 'date': date_filter,
                                 'category': category_filter,
                                 'description': description_filter
                             })
    except Exception as e:
        logger.error(f"Error fetching transactions: {str(e)}")
        flash(trans_function('core_something_went_wrong', default='An error occurred, please try again'), 'danger')
        return render_template('transactions/history.html',
                             transactions=[],
                             total_income=0,
                             total_expense=0,
                             net_balance=0,
                             category_totals={},
                             categories=[c[0] for c in TransactionForm().category.choices],
                             filter_values={
                                 'date': date_filter,
                                 'category': category_filter,
                                 'description': description_filter
                             }), 500

@transactions_bp.route('/add', methods=['GET', 'POST'])
@login_required
def add():
    form = TransactionForm()
    if form.validate_on_submit():
        try:
            mongo = current_app.extensions['pymongo']
            transaction = {
                'user_id': str(current_user.id),
                'type': form.type.data,
                'category': form.category.data,
                'amount': float(form.amount.data),
                'description': form.description.data.strip(),
                'is_recurring': form.is_recurring.data,
                'recurring_period': form.recurring_period.data if form.is_recurring.data else 'none',
                'created_at': datetime.utcnow(),
                'updated_at': datetime.utcnow()
            }
            result = mongo.db.transactions.insert_one(transaction)
            flash(trans_function('transaction_added', default='Transaction added successfully'), 'success')
            logger.info(f"Transaction added by user {current_user.id}: {result.inserted_id}")
            return redirect(url_for('transactions.history'))
        except Exception as e:
            logger.error(f"Error adding transaction: {str(e)}")
            flash(trans_function('core_something_went_wrong', default='An error occurred, please try again'), 'danger')
            return render_template('transactions/add.html', form=form), 500
    return render_template('transactions/add.html', form=form)

@transactions_bp.route('/update/<transaction_id>', methods=['GET', 'POST'])
@login_required
def update(transaction_id):
    mongo = current_app.extensions['pymongo']
    transaction = mongo.db.transactions.find_one({'_id': ObjectId(transaction_id), 'user_id': str(current_user.id)})
    if not transaction:
        flash(trans_function('transaction_not_found', default='Transaction not found'), 'danger')
        return redirect(url_for('transactions.history'))
    
    form = TransactionForm(data={
        'type': transaction['type'],
        'category': transaction['category'],
        'amount': transaction['amount'],
        'description': transaction['description'],
        'is_recurring': transaction.get('is_recurring', False),
        'recurring_period': transaction.get('recurring_period', 'none')
    })
    
    if form.validate_on_submit():
        try:
            mongo.db.transactions.update_one(
                {'_id': ObjectId(transaction_id), 'user_id': str(current_user.id)},
                {
                    '$set': {
                        'type': form.type.data,
                        'category': form.category.data,
                        'amount': float(form.amount.data),
                        'description': form.description.data.strip(),
                        'is_recurring': form.is_recurring.data,
                        'recurring_period': form.recurring_period.data if form.is_recurring.data else 'none',
                        'updated_at': datetime.utcnow()
                    }
                }
            )
            flash(trans_function('transaction_updated', default='Transaction updated successfully'), 'success')
            logger.info(f"Transaction updated by user {current_user.id}: {transaction_id}")
            return redirect(url_for('transactions.history'))
        except Exception as e:
            logger.error(f"Error updating transaction: {str(e)}")
            flash(trans_function('core_something_went_wrong', default='An error occurred, please try again'), 'danger')
            return render_template('transactions/add.html', form=form, transaction_id=transaction_id), 500
    return render_template('transactions/add.html', form=form, transaction_id=transaction_id)

@transactions_bp.route('/delete/<transaction_id>', methods=['POST'])
@login_required
def delete(transaction_id):
    try:
        mongo = current_app.extensions['pymongo']
        result = mongo.db.transactions.delete_one({'_id': ObjectId(transaction_id), 'user_id': str(current_user.id)})
        if result.deleted_count == 0:
            flash(trans_function('transaction_not_found', default='Transaction not found'), 'danger')
        else:
            flash(trans_function('transaction_deleted', default='Transaction deleted successfully'), 'success')
            logger.info(f"Transaction deleted by user {current_user.id}: {transaction_id}")
        return redirect(url_for('transactions.history'))
    except Exception as e:
        logger.error(f"Error deleting transaction: {str(e)}")
        flash(trans_function('core_something_went_wrong', default='An error occurred, please try again'), 'danger')
        return redirect(url_for('transactions.history')), 500

@transactions_bp.route('/export', methods=['GET'])
@login_required
def export():
    try:
        mongo = current_app.extensions['pymongo']
        user = mongo.db.users.find_one({'_id': current_user.id})
        query = {'user_id': str(current_user.id)}
        if user.get('is_admin', False):
            query = {}  # Admins can export all transactions
        transactions = list(mongo.db.transactions.find(query))
        output = StringIO()
        writer = csv.writer(output)
        writer.writerow(['Type', 'Category', 'Amount', 'Description', 'Is Recurring', 'Recurring Period', 'Created At'])
        for t in transactions:
            created_at = t.get('created_at')
            if isinstance(created_at, str):
                try:
                    created_at = datetime.strptime(created_at, '%Y-%m-%d')
                except ValueError:
                    created_at = None
                    logger.warning(f"Invalid created_at string in export: {t.get('created_at')}")
            writer.writerow([
                t['type'].capitalize(),
                t['category'].capitalize(),
                t['amount'],
                t['description'],
                t.get('is_recurring', False),
                t.get('recurring_period', 'none').capitalize(),
                created_at.strftime('%Y-%m-%d %H:%M:%S') if created_at else ''
            ])
        output.seek(0)
        return send_file(
            output,
            mimetype='text/csv',
            as_attachment=True,
            download_name=f'transactions_{datetime.utcnow().strftime("%Y%m%d")}.csv'
        )
    except Exception as e:
        logger.error(f"Error exporting transactions: {str(e)}")
        flash(trans_function('core_something_went_wrong', default='An error occurred, please try again'), 'danger')
        return redirect(url_for('transactions.history')), 500
