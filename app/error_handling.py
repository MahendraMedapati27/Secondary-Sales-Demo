"""
Structured error handling and logging utilities for production-ready applications.

This module provides:
- Specific exception classes
- Structured logging with request IDs
- Consistent error response formatting
- Performance tracking
"""
import logging
import time
import uuid
import traceback
from functools import wraps
from flask import request, jsonify, g, has_request_context
from datetime import datetime

# Configure structured logging
# Note: Format includes request_id which will be added by RequestContextFilter
# The filter must be added before any logging occurs
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] [%(name)s] [request_id=%(request_id)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    force=True  # Force reconfiguration if already configured
)

logger = logging.getLogger(__name__)


class AppError(Exception):
    """Base application error"""
    def __init__(self, message, status_code=500, error_code=None, details=None):
        self.message = message
        self.status_code = status_code
        self.error_code = error_code
        self.details = details
        super().__init__(self.message)


class ValidationError(AppError):
    """Input validation error"""
    def __init__(self, message, details=None):
        super().__init__(message, status_code=400, error_code='VALIDATION_ERROR', details=details)


class AuthenticationError(AppError):
    """Authentication error"""
    def __init__(self, message="Authentication required"):
        super().__init__(message, status_code=401, error_code='AUTH_ERROR')


class AuthorizationError(AppError):
    """Authorization error"""
    def __init__(self, message="Insufficient permissions"):
        super().__init__(message, status_code=403, error_code='AUTHORIZATION_ERROR')


class NotFoundError(AppError):
    """Resource not found error"""
    def __init__(self, message="Resource not found"):
        super().__init__(message, status_code=404, error_code='NOT_FOUND')


class DatabaseError(AppError):
    """Database operation error"""
    def __init__(self, message="Database operation failed", details=None):
        super().__init__(message, status_code=500, error_code='DATABASE_ERROR', details=details)


class ExternalServiceError(AppError):
    """External service error"""
    def __init__(self, service_name, message="External service error", details=None):
        super().__init__(
            f"{service_name}: {message}",
            status_code=503,
            error_code=f'{service_name.upper()}_ERROR',
            details=details
        )


class TimeoutError(AppError):
    """Operation timeout error"""
    def __init__(self, operation, timeout):
        super().__init__(
            f"{operation} timed out after {timeout}s",
            status_code=504,
            error_code='TIMEOUT_ERROR'
        )


def generate_request_id():
    """Generate unique request ID"""
    return str(uuid.uuid4())


def get_request_id():
    """Get current request ID from Flask g"""
    try:
        if has_request_context() and hasattr(g, 'request_id'):
            return g.request_id
        else:
            return 'no-request-id'
    except RuntimeError:
        return 'no-request-id'


class RequestContextFilter(logging.Filter):
    """Logging filter to add request ID to log records"""
    def filter(self, record):
        try:
            from flask import has_request_context, g
            if has_request_context() and hasattr(g, 'request_id'):
                record.request_id = g.request_id
            else:
                record.request_id = 'no-request-id'
        except RuntimeError:
            # Outside application context
            record.request_id = 'no-request-id'
        except Exception:
            record.request_id = 'no-request-id'
        return True


# Add filter to root logger and all existing handlers
root_logger = logging.getLogger()
filter_instance = RequestContextFilter()
root_logger.addFilter(filter_instance)

# Also add filter to all existing handlers
for handler in root_logger.handlers:
    handler.addFilter(filter_instance)


def handle_error(error, include_traceback=False):
    """
    Handle application errors and return consistent error response.
    
    Args:
        error: Exception instance
        include_traceback: Whether to include traceback in response (only in debug mode)
    
    Returns:
        Tuple of (response, status_code)
    """
    request_id = get_request_id()
    
    # Log error with context
    if isinstance(error, AppError):
        logger.warning(
            f"Application error: {error.error_code} - {error.message}",
            extra={
                'error_code': error.error_code,
                'status_code': error.status_code,
                'details': error.details
            }
        )
        status_code = error.status_code
        error_code = error.error_code
        message = error.message
        details = error.details
    else:
        # Generic exception
        logger.error(
            f"Unexpected error: {type(error).__name__} - {str(error)}",
            exc_info=True,
            extra={
                'error_type': type(error).__name__,
                'error_message': str(error)
            }
        )
        status_code = 500
        error_code = 'INTERNAL_ERROR'
        message = 'An unexpected error occurred'
        details = None
    
    response = {
        'error': message,
        'error_code': error_code,
        'request_id': request_id,
        'timestamp': datetime.utcnow().isoformat()
    }
    
    if details:
        response['details'] = details
    
    # Include traceback only in debug mode
    if include_traceback and hasattr(error, '__traceback__'):
        response['traceback'] = traceback.format_exception(
            type(error), error, error.__traceback__
        )
    
    return jsonify(response), status_code


def error_handler(func):
    """
    Decorator for consistent error handling in route handlers.
    
    Usage:
        @error_handler
        @chatbot_bp.route('/endpoint')
        def my_endpoint():
            ...
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except AppError as e:
            return handle_error(e)
        except Exception as e:
            return handle_error(e, include_traceback=False)
    
    return wrapper


def track_performance(func):
    """
    Decorator to track function execution time and log performance metrics.
    
    Usage:
        @track_performance
        def my_function():
            ...
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        request_id = get_request_id()
        
        try:
            result = func(*args, **kwargs)
            execution_time = time.time() - start_time
            
            logger.info(
                f"Function {func.__name__} completed in {execution_time:.3f}s",
                extra={
                    'function': func.__name__,
                    'execution_time': execution_time,
                    'request_id': request_id
                }
            )
            
            return result
        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(
                f"Function {func.__name__} failed after {execution_time:.3f}s: {str(e)}",
                extra={
                    'function': func.__name__,
                    'execution_time': execution_time,
                    'error': str(e),
                    'request_id': request_id
                },
                exc_info=True
            )
            raise
    
    return wrapper

