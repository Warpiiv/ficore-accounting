from flask import Blueprint, request, render_template, redirect, url_for, flash, Response, current_app
from flask_wtf import FlaskForm
from wtforms import StringField, FloatField, SelectField, validators, BooleanField
from flask_login import login_required, current_user
from datetime import datetime, timedelta
from utils import trans_function, is_valid_email
import logging
import csv
from io import StringIO
from bson import ObjectId

logger = logging.getLogger(__name__)

transactions_bp = Blueprint('transactions', __name__, template_folder='templates')

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
    tags = StringField('Tags', [
        validators.Length(max=200, message='Tags cannot exceed 200 characters')
    ])
    is_recurring = BooleanField('Recurring Transaction')
    recurring_period = SelectField('Recurring Period', choices=[
        ('none', 'None'), ('weekly', 'Weekly'), ('monthly', 'Monthly'), ('yearly', 'Yearly')
    ])

@transactions_bp.route('/transaction_history', methods=['GET'])
def transaction_history():
    # Fix for UnboundLocalError - Initialize filter variables
    date_filter = ''
    category_filter = ''
    description_filter = ''
    tags_filter = ''
    try:
        user_id = current_user.id if current_user.is_authenticated else 'guest'
        mongo = current_app.extensions['pymongo']
        date_filter = request.args.get('date', '')
        category_filter = request.args.get('category', '')
        description_filter = request.args.get('description', '')
        tags_filter = request.args.get('tags', '')

        query = {'user_id': user_id}
        if date_filter:
            try:
                date = datetime.strptime(date_filter, '%Y-%m-%d')
                query['created_at'] = {
                    '$gte': date,
                    '$lt': date + timedelta(days=1)
                }
            except ValueError:
                flash(trans_function('invalid_date_format'), 'danger')
        if category_filter:
            query['category'] = category_filter
        if description_filter:
            query['description'] = {'$regex': description_filter, '$options': 'i'}
        if tags_filter:
            query['tags'] = {'$regex': tags_filter, '$options': 'i'}

        transactions = list(mongo.db.transactions.find(query).sort('created_at', -1))
        for transaction in transactions:
            transaction['_id'] = str(transaction['_id'])

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
                                 'description': description_filter,
                                 'tags': tags_filter
                             })
    except Exception as e:
        logger.error(f"Error fetching transactions: {str(e)}")
        flash(trans_function('core_something_went_wrong'), 'danger')
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
                                 'description': description_filter,
                                 'tags': tags_filter
                             }), 500

@transactions_bp.route('/add', methods=['GET', 'POST'])
def add_transaction():
    form = TransactionForm()
    if form.validate_on_submit():
        try:
            user_id = current_user.id if current_user.is_authenticated else 'guest'
            mongo = current_app.extensions['pymongo']
            transaction = {
                'user_id': user_id,
                'type': form.type.data,
                'category': form.category.data,
                'amount': float(form.amount.data),
                'description': form.description.data.strip(),
                'tags': [tag.strip() for tag in form.tags.data.split(',') if tag.strip()] if form.tags.data else [],
                'is_recurring': form.is_recurring.data,
                'recurring_period': form.recurring_period.data if form.is_recurring.data else 'none',
                'created_at': datetime.utcnow(),
                'updated_at': datetime.utcnow()
            }
            result = mongo.db.transactions.insert_one(transaction)
            flash(trans_function('transaction_added'), 'success')
            logger.info(f"Transaction added by user {user_id}: {result.inserted_id}")
            return redirect(url_for('transactions.transaction_history'))
        except Exception as e:
            logger.error(f"Error adding transaction: {str(e)}")
            flash(trans_function('core_something_went_wrong'), 'danger')
            return render_template('transactions/add.html', form=form), 500
    return render_template('transactions/add.html', form=form)

@transactions_bp.route('/update/<transaction_id>', methods=['GET', 'POST'])
def update_transaction(transaction_id):
    user_id = current_user.id if current_user.is_authenticated else 'guest'
    mongo = current_app.extensions['pymongo']
    transaction = mongo.db.transactions.find_one({'_id': ObjectId(transaction_id), 'user_id': user_id})
    if not transaction:
        flash(trans_function('transaction_not_found'), 'danger')
        return redirect(url_for('transactions.transaction_history'))
    
    form = TransactionForm(data={
        'type': transaction['type'],
        'category': transaction['category'],
        'amount': transaction['amount'],
        'description': transaction['description'],
        'tags': ','.join(transaction.get('tags', [])),
        'is_recurring': transaction.get('is_recurring', False),
        'recurring_period': transaction.get('recurring_period', 'none')
    })
    
    if form.validate_on_submit():
        try:
            mongo.db.transactions.update_one(
                {'_id': ObjectId(transaction_id), 'user_id': user_id},
                {
                    '$set': {
                        'type': form.type.data,
                        'category': form.category.data,
                        'amount': float(form.amount.data),
                        'description': form.description.data.strip(),
                        'tags': [tag.strip() for tag in form.tags.data.split(',') if tag.strip()] if form.tags.data else [],
                        'is_recurring': form.is_recurring.data,
                        'recurring_period': form.recurring_period.data if form.is_recurring.data else 'none',
                        'updated_at': datetime.utcnow()
                    }
                }
            )
            flash(trans_function('transaction_updated'), 'success')
            logger.info(f"Transaction updated by user {user_id}: {transaction_id}")
            return redirect(url_for('transactions.transaction_history'))
        except Exception as e:
            logger.error(f"Error updating transaction: {str(e)}")
            flash(trans_function('core_something_went_wrong'), 'danger')
            return render_template('transactions/add.html', form=form, transaction_id=transaction_id), 500
    return render_template('transactions/add.html', form=form, transaction_id=transaction_id)

@transactions_bp.route('/delete/<transaction_id>', methods=['POST'])
def delete_transaction(transaction_id):
    try:
        user_id = current_user.id if current_user.is_authenticated else 'guest'
        mongo = current_app.extensions['pymongo']
        result = mongo.db.transactions.delete_one({'_id': ObjectId(transaction_id), 'user_id': user_id})
        if result.deleted_count == 0:
            flash(trans_function('transaction_not_found'), 'danger')
        else:
            flash(trans_function('transaction_deleted'), 'success')
            logger.info(f"Transaction deleted by user {user_id}: {transaction_id}")
        return redirect(url_for('transactions.transaction_history'))
    except Exception as e:
        logger.error(f"Error deleting transaction: {str(e)}")
        flash(trans_function('core_something_went_wrong'), 'danger')
        return redirect(url_for('transactions.transaction_history')), 500

@transactions_bp.route('/export', methods=['GET'])
def export_transactions():
    try:
        user_id = current_user.id if current_user.is_authenticated else 'guest'
        mongo = current_app.extensions['pymongo']
        transactions = list(mongo.db.transactions.find({'user_id': user_id}))
        output = StringIO()
        writer = csv.writer(output)
        writer.writerow(['Type', 'Category', 'Amount', 'Description', 'Tags', 'Is Recurring', 'Recurring Period', 'Created At'])
        for t in transactions:
            writer.writerow([
                t['type'].capitalize(),
                t['category'].capitalize(),
                t['amount'],
                t['description'],
                ','.join(t.get('tags', [])),
                t.get('is_recurring', False),
                t.get('recurring_period', 'none').capitalize(),
                t['created_at'].strftime('%Y-%m-%d %H:%M:%S')
            ])
        output.seek(0)
        return Response(
            output.getvalue(),
            mimetype='text/csv',
            headers={'Content-Disposition': 'attachment;filename=transactions.csv'}
        )
    except Exception as e:
        logger.error(f"Error exporting transactions: {str(e)}")
        flash(trans_function('core_something_went_wrong'), 'danger')
        return redirect(url_for('transactions.transaction_history')), 500
