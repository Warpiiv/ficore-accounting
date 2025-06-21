from flask import Blueprint, render_template, redirect, url_for, flash, current_app, request
from flask_login import login_required, current_user
from datetime import datetime
from utils import trans_function
import logging
from bson import ObjectId
from app import limiter, requires_role

logger = logging.getLogger(__name__)

admin_bp = Blueprint('admin', __name__, template_folder='templates/admin')

@admin_bp.route('/dashboard', methods=['GET'])
@login_required
@requires_role('admin')
def dashboard():
    try:
        mongo = current_app.extensions['pymongo']
        user_count = mongo.db.users.count_documents({'role': {'$ne': 'admin'}})
        invoice_count = mongo.db.invoices.count_documents({})
        transaction_count = mongo.db.transactions.count_documents({})
        inventory_count = mongo.db.inventory.count_documents({})
        coin_tx_count = mongo.db.coin_transactions.count_documents({})
        recent_users = list(mongo.db.users.find({'role': {'$ne': 'admin'}}).sort('created_at', -1).limit(10))
        for user in recent_users:
            user['_id'] = str(user['_id'])
        return render_template(
            'admin/dashboard.html',
            stats={
                'users': user_count,
                'invoices': invoice_count,
                'transactions': transaction_count,
                'inventory': inventory_count,
                'coin_transactions': coin_tx_count
            },
            recent_users=recent_users
        )
    except Exception as e:
        logger.error(f"Error loading admin dashboard: {str(e)}")
        flash(trans_function('core_something_went_wrong', default='An error occurred'), 'danger')
        return render_template('admin/dashboard.html', stats={}, recent_users=[]), 500

@admin_bp.route('/users', methods=['GET'])
@login_required
@requires_role('admin')
def manage_users():
    try:
        mongo = current_app.extensions['pymongo']
        users = list(mongo.db.users.find({'role': {'$ne': 'admin'}}).sort('created_at', -1))
        for user in users:
            user['_id'] = str(user['_id'])
        return render_template('admin/users.html', users=users)
    except Exception as e:
        logger.error(f"Error fetching users for admin: {str(e)}")
        flash(trans_function('core_something_went_wrong', default='An error occurred'), 'danger')
        return render_template('admin/users.html', users=[]), 500

@admin_bp.route('/users/suspend/<user_id>', methods=['POST'])
@login_required
@requires_role('admin')
@limiter.limit("10 per hour")
def suspend_user(user_id):
    try:
        mongo = current_app.extensions['pymongo']
        result = mongo.db.users.update_one(
            {'_id': user_id, 'role': {'$ne': 'admin'}},
            {'$set': {'suspended': True, 'updated_at': datetime.utcnow()}}
        )
        if result.modified_count == 0:
            flash(trans_function('user_not_found', default='User not found'), 'danger')
        else:
            flash(trans_function('user_suspended', default='User suspended successfully'), 'success')
            logger.info(f"Admin {current_user.id} suspended user {user_id}")
        return redirect(url_for('admin.manage_users'))
    except Exception as e:
        logger.error(f"Error suspending user {user_id}: {str(e)}")
        flash(trans_function('core_something_went_wrong', default='An error occurred'), 'danger')
        return redirect(url_for('admin.manage_users')), 500

@admin_bp.route('/users/delete/<user_id>', methods=['POST'])
@login_required
@requires_role('admin')
@limiter.limit("5 per hour")
def delete_user(user_id):
    try:
        mongo = current_app.extensions['pymongo']
        mongo.db.invoices.delete_many({'user_id': user_id})
        mongo.db.transactions.delete_many({'user_id': user_id})
        mongo.db.inventory.delete_many({'user_id': user_id})
        mongo.db.coin_transactions.delete_many({'user_id': user_id})
        result = mongo.db.users.delete_one({'_id': user_id, 'role': {'$ne': 'admin'}})
        if result.deleted_count == 0:
            flash(trans_function('user_not_found', default='User not found'), 'danger')
        else:
            flash(trans_function('user_deleted', default='User deleted successfully'), 'success')
            logger.info(f"Admin {current_user.id} deleted user {user_id}")
        return redirect(url_for('admin.manage_users'))
    except Exception as e:
        logger.error(f"Error deleting user {user_id}: {str(e)}")
        flash(trans_function('core_something_went_wrong', default='An error occurred'), 'danger')
        return redirect(url_for('admin.manage_users')), 500

@admin_bp.route('/data/delete/<collection>/<item_id>', methods=['POST'])
@login_required
@requires_role('admin')
@limiter.limit("10 per hour")
def delete_item(collection, item_id):
    valid_collections = ['invoices', 'transactions', 'inventory']
    if collection not in valid_collections:
        flash(trans_function('invalid_collection', default='Invalid collection'), 'danger')
        return redirect(url_for('admin.dashboard'))
    try:
        mongo = current_app.extensions['pymongo']
        result = mongo.db[collection].delete_one({'_id': ObjectId(item_id)})
        if result.deleted_count == 0:
            flash(trans_function('item_not_found', default='Item not found'), 'danger')
        else:
            flash(trans_function('item_deleted', default='Item deleted successfully'), 'success')
            logger.info(f"Admin {current_user.id} deleted {collection} item {item_id}")
        return redirect(url_for('admin.dashboard'))
    except Exception as e:
        logger.error(f"Error deleting {collection} item {item_id}: {str(e)}")
        flash(trans_function('core_something_went_wrong', default='An error occurred'), 'danger')
        return redirect(url_for('admin.dashboard')), 500