import logging
import time
from functools import wraps
from datetime import datetime
import uuid
import socket
from os import getenv
import csv

logger = logging.getLogger(__name__)

def log_to_request_file(request_id: str, status: str, message: str) -> None:
    """Log message to request-specific CSV file without console output.
    
    Args:
        request_id: The request ID.
        status: The current status.
        message: The message to log.
    """
    if not request_id:
        return
        
    log_file = f"system_log/request_{request_id}.csv"
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    try:
        with open(log_file, 'a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow([timestamp, status, message])
    except Exception as e:
        # Only log errors to console, not the actual messages
        logger.error(f"Error writing to request log file: {str(e)}")

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
                        msg = f"Attempt {attempt + 1} failed: {str(e)}. Retrying in {delay} seconds..."
                        logger.warning(msg)
                        # Try to get request_id from args or kwargs
                        request_id = getattr(args[0], 'current_request_id', None) if args else None
                        if request_id:
                            log_to_request_file(request_id, "retry", msg)
                        time.sleep(delay)
                        delay = min(delay * 2, max_delay)
                    else:
                        msg = f"All {max_retries} attempts failed. Last error: {str(e)}"
                        logger.error(msg)
                        request_id = getattr(args[0], 'current_request_id', None) if args else None
                        if request_id:
                            log_to_request_file(request_id, "error", msg)
                        raise last_exception
            
            return None
        return wrapper
    return decorator

def initialize_request():
    """Initialize a new request with a unique ID"""
    global current_request_id, token_metrics
    current_request_id = f"{datetime.now().strftime('%Y%m%d')}_{str(uuid.uuid4())[:8]}"
    token_metrics = []
    
    # Create request log file
    log_file = f"request_{current_request_id}.csv"
    try:
        with open(log_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(["Timestamp", "Status", "Message"])
    except Exception as e:
        logger.error(f"Error creating request log file: {str(e)}")
    return current_request_id
