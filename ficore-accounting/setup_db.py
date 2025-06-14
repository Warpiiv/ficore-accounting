from pymongo import MongoClient
from werkzeug.security import generate_password_hash
from datetime import datetime
import os
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

MONGO_URI = os.getenv('MONGO_URI', 'mongodb://localhost:27017/minirecords')

def setup_database():
    """
    Sets up the MongoDB database for the minirecords application.
    Creates necessary collections and indexes, and initializes a default admin user.
    Returns True on success, False on failure.
    """
    client = None
    try:
        client = MongoClient(MONGO_URI)
        db = client.get_database('minirecords')

        # Users collection
        db.users.create_index([('_id', 1)], unique=True)
        db.users.create_index([('email', 1)], unique=True)
        db.users.create_index([('reset_token', 1)], sparse=True)
        
        if not db.users.find_one({'_id': 'admin'}):
            db.users.insert_one({
                '_id': 'admin',
                'email': 'ficoreafrica@gmail.com',
                'password': generate_password_hash('Admin123!'),
                'dark_mode': False,
                'is_admin': True,
                'created_at': datetime.utcnow()
            })
            logger.info("Default admin user created")

        # Invoices collection
        db.invoices.create_index([('user_id', 1)])
        db.invoices.create_index([('created_at', -1)])

        # Transactions collection
        db.transactions.create_index([('user_id', 1)])
        db.transactions.create_index([('created_at', -1)])

        # Feedback collection
        db.feedback.create_index([('user_id', 1)], sparse=True)
        db.feedback.create_index([('timestamp', -1)])

        # Sessions collection (for Flask-Session)
        db.sessions.create_index([('expires', 1)], expireAfterSeconds=0)
        logger.info("Sessions collection index created")

        logger.info("Database setup completed successfully")
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
