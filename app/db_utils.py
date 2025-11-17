"""
Database utility functions for transaction management, retry logic, and error handling.
Production-ready SQL checkpoint implementation.
"""
import logging
import time
from functools import wraps
from sqlalchemy.exc import OperationalError, DisconnectionError, IntegrityError, DatabaseError
from sqlalchemy.orm.exc import StaleDataError
from app import db

logger = logging.getLogger(__name__)

# Maximum retry attempts for transient failures
MAX_DB_RETRIES = 3
RETRY_DELAY_BASE = 0.5  # Base delay in seconds (exponential backoff)


def retry_on_transient_failure(max_retries=MAX_DB_RETRIES, delay_base=RETRY_DELAY_BASE):
    """
    Decorator to retry database operations on transient failures.
    
    Can be used in two ways:
    1. As a decorator: @retry_on_transient_failure()
    2. With parameters: @retry_on_transient_failure(max_retries=5)
    
    Handles:
    - Connection errors (OperationalError, DisconnectionError)
    - Stale data errors
    - Database errors that might be transient
    
    Args:
        max_retries: Maximum number of retry attempts
        delay_base: Base delay for exponential backoff
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                    
                except (OperationalError, DisconnectionError, StaleDataError) as e:
                    last_exception = e
                    if attempt < max_retries - 1:
                        # Rollback current transaction
                        try:
                            db.session.rollback()
                        except Exception:
                            pass
                        
                        # Exponential backoff
                        delay = delay_base * (2 ** attempt)
                        logger.warning(
                            f"Transient DB error in {func.__name__} (attempt {attempt + 1}/{max_retries}): {str(e)}. "
                            f"Retrying in {delay}s..."
                        )
                        time.sleep(delay)
                    else:
                        logger.error(f"DB operation {func.__name__} failed after {max_retries} attempts: {str(e)}")
                        
                except (IntegrityError, DatabaseError) as e:
                    # Non-transient errors - don't retry
                    logger.error(f"Non-transient DB error in {func.__name__}: {str(e)}")
                    try:
                        db.session.rollback()
                    except Exception:
                        pass
                    raise
            
            # If we exhausted retries, raise the last exception
            if last_exception:
                raise last_exception
                
        return wrapper
    
    # If called without parentheses, treat as decorator with default args
    if callable(max_retries):
        # Called as @retry_on_transient_failure (without parentheses)
        func = max_retries
        max_retries = MAX_DB_RETRIES
        delay_base = RETRY_DELAY_BASE
        return decorator(func)
    else:
        # Called as @retry_on_transient_failure() or @retry_on_transient_failure(max_retries=5)
        return decorator


def with_transaction(func):
    """
    Decorator to wrap function in a database transaction.
    
    Automatically:
    - Starts a transaction
    - Commits on success
    - Rolls back on exception
    - Handles cleanup
    
    Usage:
        @with_transaction
        def my_function():
            db.session.add(object)
            # Auto-commits on success, auto-rollbacks on exception
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            # Use begin() to start explicit transaction
            # This ensures atomicity
            with db.session.begin():
                result = func(*args, **kwargs)
                # Transaction commits automatically on success
                return result
                
        except Exception as e:
            # Transaction rolls back automatically on exception
            logger.error(f"Transaction failed in {func.__name__}: {str(e)}")
            # Ensure session is clean
            try:
                db.session.rollback()
            except Exception:
                pass
            raise
            
    return wrapper


def with_savepoint(func):
    """
    Decorator to wrap function in a savepoint (nested transaction).
    
    Useful for operations that might fail but shouldn't rollback the entire transaction.
    
    Usage:
        @with_savepoint
        def nested_operation():
            db.session.add(object)
            # Can rollback without affecting outer transaction
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        savepoint = None
        try:
            # Create savepoint
            savepoint = db.session.begin_nested()
            result = func(*args, **kwargs)
            # Commit savepoint
            savepoint.commit()
            return result
            
        except Exception as e:
            # Rollback savepoint only
            if savepoint:
                try:
                    savepoint.rollback()
                except Exception:
                    pass
            logger.error(f"Savepoint operation failed in {func.__name__}: {str(e)}")
            raise
            
    return wrapper


def safe_db_operation(operation_func, *args, **kwargs):
    """
    Safely execute a database operation with proper error handling.
    
    Args:
        operation_func: Function to execute
        *args, **kwargs: Arguments to pass to operation_func
        
    Returns:
        Tuple of (success: bool, result: any, error: str or None)
    """
    try:
        result = operation_func(*args, **kwargs)
        return True, result, None
    except Exception as e:
        logger.error(f"Database operation failed: {str(e)}")
        try:
            db.session.rollback()
        except Exception:
            pass
        return False, None, str(e)


def commit_or_rollback(success=True):
    """
    Explicitly commit or rollback the current transaction.
    
    Args:
        success: If True, commit; if False, rollback
    """
    try:
        if success:
            db.session.commit()
        else:
            db.session.rollback()
    except Exception as e:
        logger.error(f"Error in commit_or_rollback: {str(e)}")
        try:
            db.session.rollback()
        except Exception:
            pass
        raise


def ensure_transaction(func):
    """
    Decorator that ensures function runs within a transaction.
    If already in a transaction, uses it; otherwise creates a new one.
    
    This is useful for nested operations.
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        # Check if we're already in a transaction
        if db.session.in_transaction():
            # Already in transaction, just execute
            return func(*args, **kwargs)
        else:
            # Not in transaction, create one
            return with_transaction(func)(*args, **kwargs)
            
    return wrapper

