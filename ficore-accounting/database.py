from pymongo import MongoClient
import os
import logging

logger = logging.getLogger(__name__)

def get_db(mongo_uri=None):
    """
    Connects to the MongoDB database specified by mongo_uri.
    Returns the database object.
    """
    try:
        mongo_uri = mongo_uri or os.getenv('MONGO_URI', 'mongodb://localhost:27017/minirecords')
        client = MongoClient(mongo_uri)
        db_name = mongo_uri.split('/')[-1] or 'minirecords'
        return client[db_name]
    except Exception as e:
        logger.error(f"Error connecting to database: {str(e)}")
        raise
