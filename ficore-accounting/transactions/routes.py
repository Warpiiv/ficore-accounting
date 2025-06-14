from flask import Blueprint, request, render_template, redirect, url_for, flash
from flask_wtf import FlaskForm
from wtforms import StringField, FloatField, SelectField, validators
from flask_login import login_required, current_user
from flask_pymongo import PyMongo
from datetime import datetime
from utils import trans_function, mail, is_valid_email
from app import app
import logging

logger = logging.getLogger(__name__)

transactions_bp = Blueprint('transactions', __name__, template_folder='templates/transactions')
mongo = PyMongo(app)

class TransactionForm(FlaskForm):
    type = SelectField('Type', choices=[
        ('income', 'Money In'), ('expense', 'Money Out')
    ], validators=[validators.DataRequired(message='Type is required')])
    category = SelectField('Category', choices=[
        ('sales', 'Sales'), ('utilities', 'Utilities'), ('transport', 'Transport'), ('other', 'Other')
    ], validators=[validators.DataRequired(message='Category is required')])
    amount = FloatField('Amount', [
        validators.DataRequired(message='Amount is required'),
        validators.NumberRange(min=0, message='Amount must be non-negative')
    ])
    description = StringField('Description', [
        validators.DataRequired(message='Description is required'),
        validators.Length(max=500, message='Description cannot exceed 500 characters')
    ])

@transactions_bp.route('/transaction_history', methods=['GET'])
@login_required
def transaction_history():
    try:
        transactions = list(mongo.db.transactions.find({'user_id': current_user.id}))
        for transaction in transactions:
            transaction['_id'] = str(transaction['_id'])
        return render_template('transactions/history.html', transactions=transactions)
    except Exception as e:
        logger.error(f"Error fetching transactions: {str(e)}")
        flash(trans_function('core_something_went_wrong'), 'danger')
        return render_template('transactions/history.html', transactions=[]), 500

@transactions_bp.route('/add', methods=['GET', 'POST'])
@login_required
def add_transaction():
    form = TransactionForm()
    if form.validate_on_submit():
        try:
            transaction = {
                'user_id': current_user.id,
                'type': form.type.data,
                'category': form.category.data,
                'amount': float(form.amount.data),
                'description': form.description.data.strip(),
                'created_at': datetime.utcnow()
            }
            result = mongo.db.transactions.insert_one(transaction)
            flash(trans_function('transaction_added'), 'success')
            logger.info(f"Transaction added by user {current_user.id}: {result.inserted_id}")
            return redirect(url_for('transactions.transaction_history'))
        except Exception as e:
            logger.error(f"Error adding transaction: {str(e)}")
            flash(trans_function('core_something_went_wrong'), 'danger')
            return render_template('transactions/add.html', form=form), 500
    return render_template('transactions/add.html', form=form)

@transactions_bp.route('/update/<transaction_id>', methods=['GET', 'POST'])
@login_required
def update_transaction(transaction_id):
    transaction = mongo.db.transactions.find_one({'_id': transaction_id, 'user_id': current_user.id})
    if not transaction:
        flash(trans_function('transaction_not_found'), 'danger')
        return redirect(url_for('transactions.transaction_history'))
    
    form = TransactionForm(data={
        'type': transaction['type'],
        'category': transaction['category'],
        'amount': transaction['amount'],
        'description': transaction['description']
    })
    
    if form.validate_on_submit():
        try:
            mongo.db.transactions.update_one(
                {'_id': transaction_id, 'user_id': current_user.id},
                {
                    '$set': {
                        'type': form.type.data,
                        'category': form.category.data,
                        'amount': float(form.amount.data),
                        'description': form.description.data.strip(),
                        'updated_at': datetime.utcnow()
                    }
                }
            )
            flash(trans_function('transaction_updated'), 'success')
            logger.info(f"Transaction updated by user {current_user.id}: {transaction_id}")
            return redirect(url_for('transactions.transaction_history'))
        except Exception as e:
            logger.error(f"Error updating transaction: {str(e)}")
            flash(trans_function('core_something_went_wrong'), 'danger')
            return render_template('transactions/add.html', form=form, transaction_id=transaction_id), 500
    return render_template('transactions/add.html', form=form, transaction_id=transaction_id)

@transactions_bp.route('/delete/<transaction_id>', methods=['POST'])
@login_required
def delete_transaction(transaction_id):
    try:
        result = mongo.db.transactions.delete_one({'_id': transaction_id, 'user_id': current_user.id})
        if result.deleted_count == 0:
            flash(trans_function('transaction_not_found'), 'danger')
        else:
            flash(trans_function('transaction_deleted'), 'success')
            logger.info(f"Transaction deleted by user {current_user.id}: {transaction_id}")
        return redirect(url_for('transactions.transaction_history'))
    except Exception as e:
        logger.error(f"Error deleting transaction: {str(e)}")
        flash(trans_function('core_something_went_wrong'), 'danger')
        return redirect(url_for('transactions.transaction_history')), 500
