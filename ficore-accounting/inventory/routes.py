from flask import Blueprint, request, render_template, redirect, url_for, flash, current_app, send_file
from flask_wtf import FlaskForm
from wtforms import StringField, FloatField, SelectField, validators, SubmitField
from flask_login import login_required, current_user
from datetime import datetime
from utils import trans_function
import logging
import csv
from io import StringIO
from bson import ObjectId
from app import limiter

logger = logging.getLogger(__name__)

inventory_bp = Blueprint('inventory', __name__, template_folder='templates/inventory')

class InventoryForm(FlaskForm):
    item_name = StringField(trans_function('item_name', default='Item Name'), [
        validators.DataRequired(message=trans_function('item_name_required', default='Item name is required')),
        validators.Length(min=2, max=100)
    ])
    quantity = FloatField(trans_function('quantity', default='Quantity'), [
        validators.DataRequired(message=trans_function('quantity_required', default='Quantity is required')),
        validators.NumberRange(min=0)
    ])
    unit = SelectField(trans_function('unit', default='Unit'), choices=[
        ('unit', trans_function('unit', default='Unit')),
        ('kg', trans_function('kg', default='Kilogram')),
        ('liter', trans_function('liter', default='Liter')),
        ('piece', trans_function('piece', default='Piece'))
    ], validators=[validators.DataRequired()])
    buying_price = FloatField(trans_function('buying_price', default='Buying Price'), [
        validators.DataRequired(message=trans_function('buying_price_required', default='Buying price is required')),
        validators.NumberRange(min=0)
    ])
    selling_price = FloatField(trans_function('selling_price', default='Selling Price'), [
        validators.DataRequired(message=trans_function('selling_price_required', default='Selling price is required')),
        validators.NumberRange(min=0)
    ])
    threshold = FloatField(trans_function('threshold', default='Low Stock Threshold'), [
        validators.DataRequired(message=trans_function('threshold_required', default='Threshold is required')),
        validators.NumberRange(min=0)
    ])
    submit = SubmitField(trans_function('submit', default='Submit'))

class FilterForm(FlaskForm):
    item_name = StringField(trans_function('item_name', default='Item Name'), validators=[validators.Optional(), validators.Length(max=100)])
    low_stock = SelectField(trans_function('low_stock', default='Low Stock'), choices=[
        ('', trans_function('all', default='All')),
        ('yes', trans_function('yes', default='Yes')),
        ('no', trans_function('no', default='No'))
    ], validators=[validators.Optional()])
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

@inventory_bp.route('/', methods=['GET'])
@login_required
def inventory_dashboard():
    form = FilterForm(request.args)
    item_name_filter = request.args.get('item_name', '')
    low_stock_filter = request.args.get('low_stock', '')
    try:
        mongo = current_app.extensions['pymongo']
        user = mongo.db.users.find_one({'_id': current_user.id})
        query = {'user_id': str(current_user.id)}
        if user.get('role') == 'admin':
            query.pop('user_id')
        if item_name_filter:
            query['item_name'] = {'$regex': item_name_filter, '$options': 'i'}
        if low_stock_filter:
            query['low_stock'] = low_stock_filter == 'yes'
        items = list(mongo.db.inventory.find(query).sort('created_at', -1).limit(50))
        for item in items:
            item['_id'] = str(item['_id'])
            item['low_stock'] = item['quantity'] <= item['threshold']
        return render_template(
            'inventory/view.html',
            items=items,
            form=form,
            item_name_filter=item_name_filter,
            low_stock_filter=low_stock_filter
        )
    except pymongo.errors.PyMongoError as e:
        logger.error(f"MongoDB error fetching inventory for user {current_user.id}: {str(e)}")
        flash(trans_function('core_something_went_wrong', default='An error occurred'), 'danger')
        return render_template('inventory/view.html', items=[], form=form), 500

@inventory_bp.route('/add', methods=['GET', 'POST'])
@login_required
@limiter.limit("50 per hour")
def add_item():
    if not check_coins_required('add_inventory'):
        return redirect(url_for('coins.purchase'))
    form = InventoryForm()
    if form.validate_on_submit():
        try:
            mongo = current_app.extensions['pymongo']
            item = {
                'user_id': str(current_user.id),
                'item_name': form.item_name.data.strip(),
                'quantity': float(form.quantity.data),
                'unit': form.unit.data,
                'buying_price': float(form.buying_price.data),
                'selling_price': float(form.selling_price.data),
                'threshold': float(form.threshold.data),
                'created_at': datetime.utcnow(),
                'updated_at': datetime.utcnow()
            }
            item['low_stock'] = item['quantity'] <= item['threshold']
            result = mongo.db.inventory.insert_one(item)
            deduct_coins('add_inventory')
            flash(trans_function('item_added', default='Item added successfully'), 'success')
            logger.info(f"Inventory item added by user {current_user.id}: {result.inserted_id}")
            return redirect(url_for('inventory.inventory_dashboard'))
        except pymongo.errors.PyMongoError as e:
            logger.error(f"MongoDB error adding inventory item: {str(e)}")
            flash(trans_function('core_something_went_wrong', default='An error occurred'), 'danger')
            return render_template('inventory/add.html', form=form), 500
    return render_template('inventory/add.html', form=form)

@inventory_bp.route('/update/<item_id>', methods=['GET', 'POST'])
@login_required
@limiter.limit("50 per hour")
def update_item(item_id):
    if not check_coins_required('update_inventory'):
        return redirect(url_for('coins.purchase'))
    try:
        mongo = current_app.extensions['pymongo']
        item = mongo.db.inventory.find_one({'_id': ObjectId(item_id), 'user_id': str(current_user.id)})
        if not item:
            flash(trans_function('item_not_found', default='Item not found'), 'danger')
            return redirect(url_for('inventory.inventory_dashboard'))
        form = InventoryForm(data={
            'item_name': item['item_name'],
            'quantity': item['quantity'],
            'unit': item['unit'],
            'buying_price': item['buying_price'],
            'selling_price': item['selling_price'],
            'threshold': item['threshold']
        })
        if form.validate_on_submit():
            try:
                item_update = {
                    'item_name': form.item_name.data.strip(),
                    'quantity': float(form.quantity.data),
                    'unit': form.unit.data,
                    'buying_price': float(form.buying_price.data),
                    'selling_price': float(form.selling_price.data),
                    'threshold': float(form.threshold.data),
                    'updated_at': datetime.utcnow()
                }
                item_update['low_stock'] = item_update['quantity'] <= item_update['threshold']
                mongo.db.inventory.update_one(
                    {'_id': ObjectId(item_id), 'user_id': str(current_user.id)},
                    {'$set': item_update}
                )
                deduct_coins('update_inventory')
                flash(trans_function('item_updated', default='Item updated successfully'), 'success')
                logger.info(f"Inventory item updated by user {current_user.id}: {item_id}")
                return redirect(url_for('inventory.inventory_dashboard'))
            except pymongo.errors.PyMongoError as e:
                logger.error(f"MongoDB error updating inventory item {item_id}: {str(e)}")
                flash(trans_function('core_something_went_wrong', default='An error occurred'), 'danger')
                return render_template('inventory/add.html', form=form, item_id=item_id), 500
        return render_template('inventory/add.html', form=form, item_id=item_id)
    except pymongo.errors.PyMongoError as e:
        logger.error(f"MongoDB error fetching inventory item {item_id}: {str(e)}")
        flash(trans_function('core_something_went_wrong', default='An error occurred'), 'danger')
        return redirect(url_for('inventory.inventory_dashboard')), 500

@inventory_bp.route('/delete/<item_id>', methods=['POST'])
@login_required
@limiter.limit("50 per hour")
def delete_item(item_id):
    try:
        mongo = current_app.extensions['pymongo']
        result = mongo.db.inventory.delete_one({'_id': ObjectId(item_id), 'user_id': str(current_user.id)})
        if result.deleted_count == 0:
            flash(trans_function('item_not_found', default='Item not found'), 'danger')
        else:
            flash(trans_function('item_deleted', default='Item deleted successfully'), 'success')
            logger.info(f"Inventory item deleted by user {current_user.id}: {item_id}")
        return redirect(url_for('inventory.inventory_dashboard'))
    except pymongo.errors.PyMongoError as e:
        logger.error(f"MongoDB error deleting inventory item {item_id}: {str(e)}")
        flash(trans_function('core_something_went_wrong', default='An error occurred'), 'danger')
        return redirect(url_for('inventory.inventory_dashboard')), 500

@inventory_bp.route('/export/csv', methods=['GET'])
@login_required
@limiter.limit("10 per hour")
def export_inventory_csv():
    try:
        mongo = current_app.extensions['pymongo']
        user = mongo.db.users.find_one({'_id': current_user.id})
        query = {'user_id': str(current_user.id)}
        if user.get('role') == 'admin':
            query.pop('user_id')
        items = list(mongo.db.inventory.find(query))
        output = StringIO()
        writer = csv.writer(output)
        writer.writerow(['Item Name', 'Quantity', 'Unit', 'Buying Price', 'Selling Price', 'Threshold', 'Low Stock', 'Created At'])
        for item in items:
            writer.writerow([
                item.get('item_name', ''),
                item.get('quantity', 0),
                item.get('unit', ''),
                item.get('buying_price', 0),
                item.get('selling_price', 0),
                item.get('threshold', 0),
                item.get('low_stock', False),
                item.get('created_at', '').strftime('%Y-%m-%d') if item.get('created_at') else ''
            ])
        output.seek(0)
        return send_file(
            output,
            mimetype='text/csv',
            as_attachment=True,
            download_name=f'inventory_{datetime.utcnow().strftime("%Y%m%d")}.csv'
        )
    except pymongo.errors.PyMongoError as e:
        logger.error(f"MongoDB error exporting inventory: {str(e)}")
        flash(trans_function('core_something_went_wrong', default='An error occurred'), 'danger')
        return redirect(url_for('inventory.inventory_dashboard')), 500