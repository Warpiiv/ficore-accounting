from pymongo import ASCENDING, DESCENDING, errors
from werkzeug.security import generate_password_hash
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

def setup_database():
    """
    Sets up the MongoDB database for the minirecords application.
    Creates necessary collections, indexes, and initializes a default admin user.
    Returns True on success, False on failure.
    """
    try:
        db = mongo.db
        collections = db.list_collection_names()

        # Users collection
        if 'users' not in collections:
            db.create_collection('users')
            logger.info("Created users collection")

        users_indexes = db.users.index_information()
        if 'email_1' not in users_indexes:
            try:
                db.users.create_index([('email', ASCENDING)], unique=True)
                logger.info("Created email index on users")
            except errors.DuplicateKeyError as e:
                logger.warning(f"Duplicate key error for email index, skipping: {str(e)}")
            except Exception as e:
                logger.warning(f"Could not create email index: {str(e)}")

        if 'reset_token_1' not in users_indexes:
            try:
                db.users.create_index([('reset_token', ASCENDING)], sparse=True)
                logger.info("Created reset_token index on users")
            except errors.DuplicateKeyError as e:
                logger.warning(f"Duplicate key error for reset_token index, skipping: {str(e)}")
            except Exception as e:
                logger.warning(f"Could not create reset_token index: {str(e)}")

        # Create default admin user if not exists
        if not db.users.find_one({'_id': 'admin'}):
            try:
                db.users.insert_one({
                    '_id': 'admin',
                    'email': 'ficoreafrica@gmail.com',
                    'password': generate_password_hash(os.getenv('ADMIN_PASSWORD', 'Admin123!')),
                    'dark_mode': False,
                    'is_admin': True,
                    'created_at': datetime.utcnow()
                })
                logger.info("Default admin user created")
            except errors.DuplicateKeyError:
                logger.info("Admin user already exists, skipping creation")
            except Exception as e:
                logger.error(f"Error creating admin user: {str(e)}")

        # Invoices collection
        if 'invoices' not in collections:
            db.create_collection('invoices')
            logger.info("Created invoices collection")

        invoices_indexes = db.invoices.index_information()
        if 'invoice_number_1' not in invoices_indexes:
            try:
                # Clean up duplicate null invoice_number values
                null_count = db.invoices.count_documents({'invoice_number': None})
                if null_count > 0:
                    logger.info(f"Found {null_count} invoices with null invoice_number. Assigning unique values...")
                    # Use bulk write for efficiency
                    bulk = db.invoices.initialize_ordered_bulk_op()
                    for i, doc in enumerate(db.invoices.find({'invoice_number': None}), start=1):
                        # Align with create_invoice format: 000001, 000002, etc.
                        bulk.find({'_id': doc['_id']}).update({'$set': {'invoice_number': str(i).zfill(6)}})
                    bulk.execute()
                    logger.info("Updated null invoice_numbers with unique values")

                # Create invoice indexes
                db.invoices.create_index([('user_id', ASCENDING)])
                db.invoices.create_index([('created_at', DESCENDING)])
                db.invoices.create_index([('status', ASCENDING)])
                db.invoices.create_index([('due_date', ASCENDING)])
                db.invoices.create_index([('invoice_number', ASCENDING)], unique=True)
                logger.info("Created indexes on invoices")
            except errors.DuplicateKeyError as e:
                logger.warning(f"Duplicate key error for invoice indexes, skipping: {str(e)}")
            except Exception as e:
                logger.warning(f"Could not create invoice indexes: {str(e)}")

        # Transactions collection
        if 'transactions' not in collections:
            db.create_collection('transactions')
            logger.info("Created transactions collection")

        transactions_indexes = db.transactions.index_information()
        if 'user_id_1' not in transactions_indexes:
            try:
                db.transactions.create_index([('user_id', ASCENDING)])
                db.transactions.create_index([('created_at', DESCENDING)])
                db.transactions.create_index([('category', ASCENDING)])
                db.transactions.create_index([('description', ASCENDING)])
                db.transactions.create_index([('tags', ASCENDING)])
                logger.info("Created indexes on transactions")
            except errors.DuplicateKeyError as e:
                logger.warning(f"Duplicate key error for transaction indexes, skipping: {str(e)}")
            except Exception as e:
                logger.warning(f"Could not create transaction indexes: {str(e)}")

        # Feedback collection
        if 'feedback' not in collections:
            db.create_collection('feedback')
            logger.info("Created feedback collection")

        feedback_indexes = db.feedback.index_information()
        if 'user_id_1' not in feedback_indexes:
            try:
                db.feedback.create_index([('user_id', ASCENDING)], sparse=True)
                db.feedback.create_index([('timestamp', DESCENDING)])
                logger.info("Created indexes on feedback")
            except errors.DuplicateKeyError as e:
                logger.warning(f"Duplicate key error for feedback indexes, skipping: {str(e)}")
            except Exception as e:
                logger.warning(f"Could not create feedback indexes: {str(e)}")

        # Sessions collection
        if 'sessions' not in collections:
            db.create_collection('sessions')
            logger.info("Created sessions collection")

        sessions_indexes = db.sessions.index_information()
        if 'expires_1' not in sessions_indexes:
            try:
                db.sessions.create_index([('expires', ASCENDING)], expireAfterSeconds=0)
                logger.info("Created index on sessions")
            except errors.DuplicateKeyError as e:
                logger.warning(f"Duplicate key error for sessions index, skipping: {str(e)}")
            except Exception as e:
                logger.warning(f"Could not create sessions index: {str(e)}")

        # Schema validation for feedback
        try:
            db.command({
                'collMod': 'feedback',
                'validator': {
                    '$jsonSchema': {
                        'bsonType': 'object',
                        'required': ['timestamp'],
                        'properties': {
                            'user_id': {'bsonType': ['string', 'null']},
                            'timestamp': {'bsonType': 'date'},
                            'comment': {'bsonType': 'string'},
                            'rating': {'bsonType': ['int', 'double', 'null']}
                        }
                    }
                }
            })
            logger.info("Set schema validation for feedback collection")
        except Exception as e:
            logger.warning(f"Could not set schema validation for feedback collection: {str(e)}")

        logger.info("Database initialization completed successfully")
        return True
    except Exception as e:
        logger.error(f"Error initializing database: {str(e)}")
        return False
