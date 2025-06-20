import logging
from flask import has_request_context, session
from translations import TRANSLATIONS

logger = logging.getLogger(__name__)

def trans_function(key, default=None):
    """
    Translate a key with optional arguments, handling context safely.
    """
    # Use session lang if in request context, otherwise fallback to 'en'
    lang = 'en'  # Default language
    if has_request_context():
        lang = session.get('lang', 'en')
    
    translation = TRANSLATIONS.get(lang, {}).get(key, default or key)
    if translation == (default or key):
        logger.info(f"Missing translation for key '{key}' in language '{lang}'")
    return translation

import re
def is_valid_email(email):
    email_regex = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(email_regex, email) is not None
