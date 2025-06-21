from flask import Blueprint, request, render_template, redirect, url_for, flash, current_app
from flask_wtf import FlaskForm
from wtforms import FloatField, StringField, SelectField, validators, SubmitField
from flask_login import login_required, current_user
from datetime import datetime
from utils import trans_function
import logging
from bson import ObjectId
from app import limiter

logger = logging.getLogger(__name__)

coins_bp = Blueprint('coins', __name__, template_folder='templates/coins')

class PurchaseForm(FlaskForm):
    amount = SelectField(trans_function('coin_amount', default='Coin Amount'), choices=[
        ('10', '10 Coins'),
        ('50', '50 Coins'),
        ('100', '100 Coins')
    ], validators=[validators.DataRequired()])
    payment_method = SelectField(trans_function('payment_method', default='Payment Method'), choices=[
        ('card', trans_function('card', default='Credit/Debit Card')),
        ('bank', trans_function('bank', default='Bank Transfer'))
    ], validators=[validators.DataRequired()])
    submit = SubmitField(trans_function('purchase', default='Purchase'))

class CreditForm(FlaskForm):
    username = StringField(trans_function('username', default='Username'), [
        validators.DataRequired(),
        validators.Length(min=3, max=50)
    ])
    amount = FloatField(trans_function('coin_amount', default='Coin Amount'), [
        validators.DataRequired(),
        validators.NumberRange(min=1)
    ])
    submit = SubmitField(trans_function('credit_coins', default='Credit Coins'))

def credit_coins(user_id, amount, ref, type='purchase'):
    """Credit coins to a user and log transaction."""
    mongo = current_app.extensions['pymongo']
    mongo.db.users.update_one(
        {'_id': user_id},
        {'$inc': {'coin_balance': amount}}
    )
    mongo.db.coin_transactions.insert_one({
        'user_id': user_id,
        'amount': amount,
        'type': type,
        'ref': ref,
        'date': datetime.utcnow()
    })

@coins_bp.route('/purchase', methods=['GET', 'POST'])
@login_required
@limiter.limit("50 per hour")
def purchase():
    form = PurchaseForm()
    if form.validate_on_submit():
        try:
            mongo = current_app.extensions['pymongo']
            amount = int(form.amount.data)
            payment_method = form.payment_method.data
            # Mock payment gateway integration
            payment_ref = f"PAY_{datetime.utcnow().isoformat()}"
            credit_coins(str(current_user.id), amount, payment_ref, 'purchase')
            flash(trans_function('purchase_success', default='Coins purchased successfully'), 'success')
            logger.info(f"User {current_user.id} purchased {amount} coins via {payment_method}")
            return redirect(url_for('coins.history'))
        except Exception as e:
            logger.error(f"Error purchasing coins for user {current_user.id}: {str(e)}")
            flash(trans_function('core_something_went_wrong', default='An error occurred'), 'danger')
            return render_template('coins/purchase.html', form=form), 500
    return render_template('coins/purchase.html', form=form)

@coins_bp.route('/history', methods=['GET'])
@login_required
def history():
    try:
        mongo = current_app.extensions['pymongo']
        user = mongo.db.users.find_one({'_id': current_user.id})
        query = {'user_id': str(current_user.id)}
        if user.get('role') == 'admin':
            query.pop('user_id')
        transactions = list(mongo.db.coin_transactions.find(query).sort('date', -1).limit(50))
        for tx in transactions:
            tx['_id'] = str(tx['_id'])
        return render_template('coins/history.html', transactions=transactions, coin_balance=user.get('coin_balance', 0))
    except Exception as e:
        logger.error(f"Error fetching coin history for user {current_user.id}: {str(e)}")
        flash(trans_function('core_something_went_wrong', default='An error occurred'), 'danger')
        return render_template('coins/history.html', transactions=[], coin_balance=0), 500

@coins_bp.route('/credit', methods=['GET', 'POST'])
@login_required
@limiter.limit("10 per hour")
def credit():
    if current_user.role != 'admin':
        flash(trans_function('forbidden_access', default='Access denied'), 'danger')
        return redirect(url_for('index'))
    form = CreditForm()
    if form.validate_on_submit():
        try:
            mongo = current_app.extensions['pymongo']
            username = form.username.data.strip().lower()
            amount = int(form.amount.data)
            user = mongo.db.users.find_one({'_id': username})
            if not user:
                flash(trans_function('user_not_found', default='User not found'), 'danger')
                return render_template('coins/credit.html', form=form)
            credit_coins(username, amount, f"ADMIN_CREDIT_{datetime.utcnow().isoformat()}", 'admin')
            flash(trans_function('credit_success', default='Coins credited successfully'), 'success')
            logger.info(f"Admin {current_user.id} credited {amount} coins to user {username}")
            return redirect(url_for('coins.history'))
        except Exception as e:
            logger.error(f"Error crediting coins by admin {current_user.id}: {str(e)}")
            flash(trans_function('core_something_went_wrong', default='An error occurred'), 'danger')
            return render_template('coins/credit.html', form=form), 500
    return render_template('coins/credit.html', form=form)