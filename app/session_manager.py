"""
Session management utilities for production-ready applications.

This module provides:
- Session cleanup
- Session timeout enforcement
- Session size limits
- Session monitoring
"""
import time
import logging
from datetime import datetime, timedelta
from flask import session, g
from functools import wraps

logger = logging.getLogger(__name__)

# Session configuration
SESSION_TIMEOUT = 3600  # 1 hour in seconds
SESSION_MAX_SIZE = 4096  # 4KB max session size
SESSION_CLEANUP_INTERVAL = 300  # Cleanup every 5 minutes

# Track last cleanup time
_last_cleanup = time.time()


def get_session_size():
    """Calculate current session size in bytes"""
    import sys
    return sys.getsizeof(session)


def enforce_session_timeout():
    """Enforce session timeout based on last activity"""
    if 'last_activity' not in session:
        session['last_activity'] = time.time()
        return True
    
    last_activity = session.get('last_activity', 0)
    elapsed = time.time() - last_activity
    
    if elapsed > SESSION_TIMEOUT:
        logger.info(f"Session expired after {elapsed:.0f}s of inactivity")
        session.clear()
        return False
    
    # Update last activity
    session['last_activity'] = time.time()
    return True


def enforce_session_size():
    """Enforce maximum session size"""
    current_size = get_session_size()
    
    if current_size > SESSION_MAX_SIZE:
        logger.warning(f"Session size ({current_size} bytes) exceeds limit ({SESSION_MAX_SIZE} bytes)")
        
        # Remove non-essential session data
        essential_keys = ['user_id', 'unique_id', 'user_type', 'area', 'last_activity']
        keys_to_remove = [k for k in session.keys() if k not in essential_keys]
        
        for key in keys_to_remove:
            del session[key]
            if get_session_size() <= SESSION_MAX_SIZE:
                break
        
        logger.info(f"Cleaned session: removed {len(keys_to_remove)} non-essential keys")


def cleanup_session():
    """Clean up session data"""
    # Remove expired temporary data
    temp_keys = [k for k in session.keys() if k.startswith('temp_')]
    for key in temp_keys:
        if 'expires_at' in session.get(key, {}):
            if time.time() > session[key].get('expires_at', 0):
                del session[key]
    
    # Enforce size limits
    enforce_session_size()


def session_required(func):
    """
    Decorator to ensure session is valid and not expired.
    
    Usage:
        @session_required
        @chatbot_bp.route('/endpoint')
        def my_endpoint():
            ...
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        # Enforce timeout
        if not enforce_session_timeout():
            from app.error_handling import AuthenticationError
            raise AuthenticationError("Session expired. Please log in again.")
        
        # Cleanup session
        cleanup_session()
        
        return func(*args, **kwargs)
    
    return wrapper


def periodic_session_cleanup():
    """Periodic cleanup of all sessions (call from background thread)"""
    global _last_cleanup
    
    current_time = time.time()
    if current_time - _last_cleanup < SESSION_CLEANUP_INTERVAL:
        return
    
    _last_cleanup = current_time
    
    # Note: Flask sessions are stored server-side, so we can't directly iterate
    # This is a placeholder for future implementation with Redis/database-backed sessions
    logger.debug("Session cleanup cycle completed")


def get_session_info():
    """Get session information for monitoring"""
    return {
        'size': get_session_size(),
        'keys': list(session.keys()),
        'last_activity': session.get('last_activity'),
        'user_id': session.get('user_id'),
        'timeout': SESSION_TIMEOUT,
        'max_size': SESSION_MAX_SIZE
    }

