from pymongo import MongoClient, ASCENDING, DESCENDING
from werkzeug.security import generate_password_hash
from datetime import datetime
import os
import logging
from urllib.parse import urlparse

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

MONGO_URI = os.getenv('MONGO_URI', 'mongodb://localhost:27017/minirecords')
ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD', 'Admin123!')  # Configurable admin password

def get_db_name_from_uri(uri):
    """Extract database name from MONGO_URI."""
    parsed = urlparse(uri)
    path = parsed.path.lstrip('/')
    return path if path else 'minirecords'

def setup_database(mongo_uri=MONGO_URI):
    """
    Sets up the MongoDB database for the minirecords application.
    Creates necessary collections, indexes, and initializes a default admin user.
    Returns True on success, False on failure.
    """
    client = None
    try:
        client = MongoClient(mongo_uri)
        db_name = get_db_name_from_uri(mongo_uri)
        db = client[db_name]

        # Users collection
        db.users.create_index([('_id', ASCENDING)], unique=True)
        db.users.create_index([('email', ASCENDING)], unique=True)
        db.users.create_index([('reset_token', ASCENDING)], sparse=True)
        
        if not db.users.find_one({'_id': 'admin'}):
            db.users.insert_one({
                '_id': 'admin',
                'email': 'ficoreafrica@gmail.com',
                'password': generate_password_hash(ADMIN_PASSWORD),
                'dark_mode': False,
                'is_admin': True,
                'created_at': datetime.utcnow()
            })
            logger.info("Default admin user created")

        # Invoices collection
        db.invoices.create_index([('user_id', ASCENDING)])
        db.invoices.create_index([('created_at', DESCENDING)])
        db.invoices.create_index([('status', ASCENDING)])
        db.invoices.create_index([('due_date', ASCENDING)])
        db.invoices.create_index([('invoice_number', ASCENDING)], unique=True)

        # Transactions collection
        db.transactions.create_index([('user_id', ASCENDING)])
        db.transactions.create_index([('created_at', DESCENDING)])
        db.transactions.create_index([('category', ASCENDING)])  # For filtering
        db.transactions.create_index([('description', ASCENDING)])  # For regex searches
        db.transactions.create_index([('tags', ASCENDING)])  # For regex searches

        # Feedback collection
        db.feedback.create_index([('user_id', ASCENDING)], sparse=True)
        db.feedback.create_index([('timestamp', DESCENDING)])

        # Sessions collection
        db.sessions.create_index([('expires', ASCENDING)], expireAfterSeconds=0)
        logger.info("Sessions collection index created")

        # Optional: Schema validation for feedback
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

        logger.info(f"Database '{db_name}' setup completed successfully")
        return True
    except Exception as e:
        logger.error(f"Error setting up database: {str(e)}")
        return False
    finally:
        if client:
            client.close()
            logger.debug("MongoDB client connection closed")

if __name__ == '__main__':
    success = setup_database()
    exit(0 if success else 1)
