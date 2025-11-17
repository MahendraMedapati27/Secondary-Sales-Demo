"""
Input validation and sanitization utilities for production-ready security.

This module provides:
- Input validation decorators
- Sanitization functions
- Length limits
- SQL injection protection
- XSS protection
"""
import re
import html
from functools import wraps
from flask import jsonify, request
import logging

logger = logging.getLogger(__name__)

# Maximum length limits for different input types
MAX_LENGTHS = {
    'message': 5000,
    'order_id': 100,
    'product_code': 50,
    'product_name': 200,
    'customer_name': 200,
    'user_name': 100,
    'email': 255,
    'phone': 50,
    'unique_id': 100,
    'reason': 500,
    'lot_number': 100,
    'quantity': 10,  # For string representation
    'language': 10,
    'template_name': 100,
    'rejection_reason': 1000,
    'search_query': 500,
    'area': 100,
    'pharmacy_name': 200,
}

# Patterns for validation
EMAIL_PATTERN = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')
PHONE_PATTERN = re.compile(r'^[\d\s\-\+\(\)]+$')
ORDER_ID_PATTERN = re.compile(r'^[A-Z0-9\-_]+$')
PRODUCT_CODE_PATTERN = re.compile(r'^[A-Z0-9\-_]+$')
UNIQUE_ID_PATTERN = re.compile(r'^[A-Z0-9\-_]+$')

# Dangerous SQL keywords (basic protection - SQLAlchemy ORM provides primary protection)
SQL_KEYWORDS = ['DROP', 'DELETE', 'TRUNCATE', 'ALTER', 'CREATE', 'INSERT', 'UPDATE', 
                'EXEC', 'EXECUTE', 'UNION', 'SELECT', 'SCRIPT', '--', '/*', '*/']


def sanitize_string(value, max_length=None, allow_html=False):
    """
    Sanitize a string input to prevent XSS and SQL injection.
    
    Args:
        value: Input string to sanitize
        max_length: Maximum allowed length
        allow_html: If True, allow HTML (still escapes dangerous content)
    
    Returns:
        Sanitized string or None if invalid
    """
    if value is None:
        return None
    
    # Convert to string
    if not isinstance(value, str):
        value = str(value)
    
    # Strip whitespace
    value = value.strip()
    
    # Check length
    if max_length and len(value) > max_length:
        logger.warning(f"Input exceeded max length: {len(value)} > {max_length}")
        return None
    
    # Check for SQL injection patterns (basic check - ORM provides primary protection)
    value_upper = value.upper()
    for keyword in SQL_KEYWORDS:
        if keyword in value_upper:
            # Check if it's part of a word or standalone
            pattern = r'\b' + re.escape(keyword) + r'\b'
            if re.search(pattern, value_upper):
                logger.warning(f"Potential SQL injection attempt detected: {keyword}")
                return None
    
    # Escape HTML to prevent XSS (unless HTML is explicitly allowed)
    if not allow_html:
        value = html.escape(value)
    
    return value


def validate_email(email):
    """Validate email format"""
    if not email:
        return False
    email = email.strip()
    if len(email) > MAX_LENGTHS['email']:
        return False
    return bool(EMAIL_PATTERN.match(email))


def validate_phone(phone):
    """Validate phone number format"""
    if not phone:
        return False
    phone = phone.strip()
    if len(phone) > MAX_LENGTHS['phone']:
        return False
    return bool(PHONE_PATTERN.match(phone))


def validate_order_id(order_id):
    """Validate order ID format"""
    if not order_id:
        return False
    order_id = str(order_id).strip()
    if len(order_id) > MAX_LENGTHS['order_id']:
        return False
    return bool(ORDER_ID_PATTERN.match(order_id))


def validate_product_code(product_code):
    """Validate product code format"""
    if not product_code:
        return False
    product_code = str(product_code).strip()
    if len(product_code) > MAX_LENGTHS['product_code']:
        return False
    return bool(PRODUCT_CODE_PATTERN.match(product_code))


def validate_unique_id(unique_id):
    """Validate unique ID format"""
    if not unique_id:
        return False
    unique_id = str(unique_id).strip()
    if len(unique_id) > MAX_LENGTHS['unique_id']:
        return False
    return bool(UNIQUE_ID_PATTERN.match(unique_id))


def validate_quantity(quantity):
    """Validate quantity (must be positive integer)"""
    try:
        qty = int(quantity)
        return qty > 0 and qty <= 1000000  # Reasonable upper limit
    except (ValueError, TypeError):
        return False


def validate_json_input(required_fields=None, optional_fields=None):
    """
    Decorator to validate JSON input from request.
    
    Args:
        required_fields: Dict of {field_name: validation_func} for required fields
        optional_fields: Dict of {field_name: validation_func} for optional fields
    
    Usage:
        @validate_json_input(
            required_fields={'message': lambda x: len(x) <= 5000},
            optional_fields={'language': lambda x: x in ['en', 'hi', 'my', 'te']}
        )
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                data = request.get_json()
                if data is None:
                    return jsonify({'error': 'Invalid JSON or missing Content-Type header'}), 400
                
                errors = []
                
                # Validate required fields
                if required_fields:
                    for field, validator in required_fields.items():
                        if field not in data:
                            errors.append(f"Missing required field: {field}")
                        else:
                            value = data[field]
                            # Apply sanitization
                            if isinstance(value, str):
                                max_length = MAX_LENGTHS.get(field)
                                sanitized = sanitize_string(value, max_length=max_length)
                                if sanitized is None:
                                    errors.append(f"Invalid or too long value for field: {field}")
                                    continue
                                data[field] = sanitized
                            
                            # Apply custom validator
                            if not validator(value):
                                errors.append(f"Invalid value for field: {field}")
                
                # Validate optional fields (if present)
                if optional_fields:
                    for field, validator in optional_fields.items():
                        if field in data:
                            value = data[field]
                            # Apply sanitization
                            if isinstance(value, str):
                                max_length = MAX_LENGTHS.get(field)
                                sanitized = sanitize_string(value, max_length=max_length)
                                if sanitized is None:
                                    errors.append(f"Invalid or too long value for field: {field}")
                                    continue
                                data[field] = sanitized
                            
                            # Apply custom validator
                            if not validator(value):
                                errors.append(f"Invalid value for field: {field}")
                
                if errors:
                    logger.warning(f"Validation errors in {func.__name__}: {errors}")
                    return jsonify({'error': 'Validation failed', 'details': errors}), 400
                
                # Replace request data with sanitized data
                request._cached_json = data
                
                return func(*args, **kwargs)
                
            except Exception as e:
                logger.error(f"Error in input validation for {func.__name__}: {str(e)}")
                return jsonify({'error': 'Input validation error'}), 400
        
        return wrapper
    return decorator


def sanitize_dict(data, field_configs=None):
    """
    Sanitize all string values in a dictionary.
    
    Args:
        data: Dictionary to sanitize
        field_configs: Dict of {field_name: {'max_length': int, 'allow_html': bool}}
    
    Returns:
        Sanitized dictionary
    """
    if not isinstance(data, dict):
        return data
    
    sanitized = {}
    for key, value in data.items():
        if isinstance(value, str):
            config = field_configs.get(key, {}) if field_configs else {}
            max_length = config.get('max_length', MAX_LENGTHS.get(key))
            allow_html = config.get('allow_html', False)
            sanitized[key] = sanitize_string(value, max_length=max_length, allow_html=allow_html)
        elif isinstance(value, dict):
            sanitized[key] = sanitize_dict(value, field_configs)
        elif isinstance(value, list):
            sanitized[key] = [
                sanitize_dict(item, field_configs) if isinstance(item, dict) 
                else sanitize_string(item, MAX_LENGTHS.get(key)) if isinstance(item, str) 
                else item
                for item in value
            ]
        else:
            sanitized[key] = value
    
    return sanitized


def validate_and_sanitize_message(message):
    """Validate and sanitize chat message"""
    if not message:
        return None
    
    sanitized = sanitize_string(message, max_length=MAX_LENGTHS['message'])
    if not sanitized:
        return None
    
    return sanitized


def validate_and_sanitize_order_id(order_id):
    """Validate and sanitize order ID"""
    if not order_id:
        return None
    
    order_id = str(order_id).strip()
    if not validate_order_id(order_id):
        return None
    
    return sanitize_string(order_id, max_length=MAX_LENGTHS['order_id'])


def validate_and_sanitize_product_code(product_code):
    """Validate and sanitize product code"""
    if not product_code:
        return None
    
    product_code = str(product_code).strip()
    if not validate_product_code(product_code):
        return None
    
    return sanitize_string(product_code, max_length=MAX_LENGTHS['product_code'])

