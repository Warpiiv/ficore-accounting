from flask import Flask, request, jsonify
from flask_pymongo import PyMongo
from flask_wtf import FlaskForm
from wtforms import StringField, FloatField, SelectField, validators
from translations import TRANSLATIONS
from datetime import datetime
import os
from flask_cors import CORS

app = Flask(__name__)
CORS(app)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'your-secret-key')
app.config['MONGO_URI'] = os.getenv('MONGO_URI')
mongo = PyMongo(app)

class InvoiceForm(FlaskForm):
    customer_name = StringField('Customer Name', [validators.DataRequired()])
    description = StringField('Description', [validators.DataRequired()])
    amount = FloatField('Amount', [validators.DataRequired(), validators.NumberRange(min=0)])

class TransactionForm(FlaskForm):
    type = SelectField('Type', choices=[('income', 'Money In'), ('expense', 'Money Out')], validators=[validators.DataRequired()])
    category = SelectField('Category', choices=[('Sales', 'Sales'), ('Utilities', 'Utilities'), ('Transport', 'Transport'), ('Other', 'Other')], validators=[validators.DataRequired()])
    amount = FloatField('Amount', [validators.DataRequired(), validators.NumberRange(min=0)])
    description = StringField('Description', [validators.DataRequired()])

@app.route('/api/invoices', methods=['GET', 'POST'])
def handle_invoices():
    if request.method == 'POST':
        form = InvoiceForm(data=request.json)
        if form.validate():
            invoice = {
                'customer_name': form.customer_name.data,
                'description': form.description.data,
                'amount': form.amount.data,
                'status': 'pending',
                'created_at': datetime.now().strftime('%Y-%m-%d')
            }
            result = mongo.db.invoices.insert_one(invoice)
            invoice['_id'] = str(result.inserted_id)
            return jsonify({'message': 'Invoice created', 'invoice': invoice}), 201
        return jsonify({'errors': form.errors}), 400
    invoices = list(mongo.db.invoices.find())
    for invoice in invoices:
        invoice['_id'] = str(invoice['_id'])
    return jsonify(invoices)

@app.route('/api/transactions', methods=['GET', 'POST'])
def handle_transactions():
    if request.method == 'POST':
        form = TransactionForm(data=request.json)
        if form.validate():
            transaction = {
                'type': form.type.data,
                'category': form.category.data,
                'amount': form.amount.data,
                'description': form.description.data,
                'created_at': datetime.now().strftime('%Y-%m-%d')
            }
            result = mongo.db.transactions.insert_one(transaction)
            transaction['_id'] = str(result.inserted_id)
            return jsonify({'message': 'Transaction created', 'transaction': transaction}), 201
        return jsonify({'errors': form.errors}), 400
    transactions = list(mongo.db.transactions.find())
    for transaction in transactions:
        transaction['_id'] = str(transaction['_id'])
    return jsonify(transactions)

@app.route('/api/translations/<lang>')
def get_translations(lang):
    return jsonify(TRANSLATIONS.get(lang, TRANSLATIONS['en']))

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
