from flask import Blueprint, request, jsonify, render_template, redirect, url_for, flash
from flask_wtf import FlaskForm
from wtforms import StringField, FloatField, SelectField, validators
from flask_pymongo import PyMongo
from datetime import datetime
from ... import app

transactions_bp = Blueprint('transactions', __name__, template_folder='templates')
mongo = PyMongo(app)

class TransactionForm(FlaskForm):
    type = SelectField('Type', choices=[('income', 'Money In'), ('expense', 'Money Out')], validators=[validators.DataRequired()])
    category = SelectField('Category', choices=[('Sales', 'Sales'), ('Utilities', 'Utilities'), ('Transport', 'Transport'), ('Other', 'Other')], validators=[validators.DataRequired()])
    amount = FloatField('Amount', [validators.DataRequired(), validators.NumberRange(min=0)])
    description = StringField('Description', [validators.DataRequired()])

@transactions_bp.route('/', methods=['GET'])
def transaction_history():
    transactions = list(mongo.db.transactions.find())
    for transaction in transactions:
        transaction['_id'] = str(transaction['_id'])
    return render_template('transactions/history.html', transactions=transactions)

@transactions_bp.route('/add', methods=['GET', 'POST'])
def add_transaction():
    form = TransactionForm()
    if form.validate_on_submit():
        transaction = {
            'type': form.type.data,
            'category': form.category.data,
            'amount': form.amount.data,
            'description': form.description.data,
            'created_at': datetime.now().strftime('%Y-%m-%d')
        }
        result = mongo.db.transactions.insert_one(transaction)
        transaction['_id'] = str(result.inserted_id)
        flash('Transaction added successfully!', 'success')
        return redirect(url_for('transactions.transaction_history'))
    return render_template('transactions/add.html', form=form)
