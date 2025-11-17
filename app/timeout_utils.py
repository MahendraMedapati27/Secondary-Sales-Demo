"""
Timeout utilities for external API calls and database operations.

This module provides:
- Timeout decorators
- Context managers for timeouts
- Timeout configuration
"""
import signal
import time
import logging
from functools import wraps
from contextlib import contextmanager
from app.error_handling import TimeoutError

logger = logging.getLogger(__name__)

# Timeout configurations (in seconds)
TIMEOUTS = {
    'llm': 30,           # LLM API calls (Groq)
    'database': 10,      # Database queries
    'translation': 5,    # Azure Translator
    'email': 10,         # Microsoft Graph email
    'search': 5,         # Azure AI Search
    'external': 10,      # Other external APIs
}


class TimeoutException(Exception):
    """Raised when an operation times out"""
    pass


def timeout_handler(signum, frame):
    """Signal handler for timeout"""
    raise TimeoutException("Operation timed out")


@contextmanager
def timeout_context(seconds):
    """
    Context manager for timeout operations.
    
    Usage:
        with timeout_context(10):
            # Your code here
            result = some_operation()
    """
    # Set up signal handler (Unix only)
    if hasattr(signal, 'SIGALRM'):
        old_handler = signal.signal(signal.SIGALRM, timeout_handler)
        signal.alarm(seconds)
        try:
            yield
        finally:
            signal.alarm(0)
            signal.signal(signal.SIGALRM, old_handler)
    else:
        # Windows doesn't support SIGALRM, use threading timeout instead
        import threading
        
        class TimeoutThread(threading.Thread):
            def __init__(self):
                super().__init__()
                self.timed_out = False
            
            def run(self):
                time.sleep(seconds)
                self.timed_out = True
        
        timeout_thread = TimeoutThread()
        timeout_thread.daemon = True
        timeout_thread.start()
        
        start_time = time.time()
        try:
            yield
            if timeout_thread.timed_out:
                elapsed = time.time() - start_time
                raise TimeoutException(f"Operation timed out after {elapsed:.2f}s")
        finally:
            timeout_thread.timed_out = False


def with_timeout(timeout_seconds, operation_name=None):
    """
    Decorator to add timeout to a function.
    
    Args:
        timeout_seconds: Timeout in seconds
        operation_name: Name of operation for error messages
    
    Usage:
        @with_timeout(30, 'LLM call')
        def call_llm():
            ...
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            op_name = operation_name or func.__name__
            start_time = time.time()
            
            try:
                if hasattr(signal, 'SIGALRM'):
                    # Unix: Use signal-based timeout
                    old_handler = signal.signal(signal.SIGALRM, timeout_handler)
                    signal.alarm(timeout_seconds)
                    try:
                        result = func(*args, **kwargs)
                        signal.alarm(0)
                        signal.signal(signal.SIGALRM, old_handler)
                        return result
                    except TimeoutException:
                        signal.alarm(0)
                        signal.signal(signal.SIGALRM, old_handler)
                        elapsed = time.time() - start_time
                        logger.error(f"{op_name} timed out after {elapsed:.2f}s")
                        raise TimeoutError(op_name, timeout_seconds)
                else:
                    # Windows: Use threading-based timeout
                    import threading
                    result_container = {'value': None, 'exception': None}
                    
                    def target():
                        try:
                            result_container['value'] = func(*args, **kwargs)
                        except Exception as e:
                            result_container['exception'] = e
                    
                    thread = threading.Thread(target=target)
                    thread.daemon = True
                    thread.start()
                    thread.join(timeout=timeout_seconds)
                    
                    if thread.is_alive():
                        elapsed = time.time() - start_time
                        logger.error(f"{op_name} timed out after {elapsed:.2f}s")
                        raise TimeoutError(op_name, timeout_seconds)
                    
                    if result_container['exception']:
                        raise result_container['exception']
                    
                    return result_container['value']
                    
            except TimeoutError:
                raise
            except Exception as e:
                elapsed = time.time() - start_time
                logger.error(f"{op_name} failed after {elapsed:.2f}s: {str(e)}")
                raise
        
        return wrapper
    return decorator


def get_timeout(operation_type):
    """Get timeout value for operation type"""
    return TIMEOUTS.get(operation_type, TIMEOUTS['external'])

