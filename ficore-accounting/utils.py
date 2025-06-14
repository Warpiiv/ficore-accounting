import logging
from flask import session
from translations import TRANSLATIONS

logger = logging.getLogger(__name__)

def trans_function(key):
    try:
        lang = session.get('lang', 'en')
        translation = TRANSLATIONS.get(lang, {}).get(key, key)
        if translation == key:
            logger.info(f"Missing translation for key '{key}' in language '{lang}'")
        return translation
    except Exception as e:
        logger.error(f"Error in trans function: {e}")
        return key

import re
def is_valid_email(email):
    email_regex = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(email_regex, email) is not None
