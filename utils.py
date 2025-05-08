import logging
import time
from functools import wraps
from datetime import datetime
import uuid

logger = logging.getLogger(__name__)

def retry_with_backoff(max_retries=3, initial_delay=1, max_delay=10):
    """Decorator for retrying functions with exponential backoff"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            delay = initial_delay
            last_exception = None
            
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    if attempt < max_retries - 1:
                        logger.warning(f"Attempt {attempt + 1} failed: {str(e)}. Retrying in {delay} seconds...")
                        time.sleep(delay)
                        delay = min(delay * 2, max_delay)
                    else:
                        logger.error(f"All {max_retries} attempts failed. Last error: {str(e)}")
                        raise last_exception
            
            return None
        return wrapper
    return decorator

def initialize_request():
    """Initialize a new request with a unique ID"""
    global current_request_id, token_metrics
    current_request_id = f"{datetime.now().strftime('%Y%m%d')}_{str(uuid.uuid4())[:8]}"
    token_metrics = []
    logger.info(f"🆕 Starting new request: {current_request_id}")
    return current_request_id
