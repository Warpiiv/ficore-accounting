import logging
from flask import has_request_context, session
from translations import TRANSLATIONS
import os

logger = logging.getLogger(__name__)

def trans_function(key, default=None):
    """
    Translate a key with optional arguments, handling context safely.
    """
    lang = 'en'
    if has_request_context():
        lang = session.get('lang', 'en')
        if os.getenv('FLASK_ENV', 'development') == 'development':
            logger.debug(f"Requested translation: key='{key}', lang='{lang}'")
    translation = TRANSLATIONS.get(lang, TRANSLATIONS.get('en', {})).get(key, default or key)
    if translation == (default or key) and os.getenv('FLASK_ENV', 'development') == 'development':
        logger.debug(f"Missing translation for key '{key}' in language '{lang}'")
    return translation
    
import re
def is_valid_email(email):
    email_regex = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(email_regex, email) is not None
