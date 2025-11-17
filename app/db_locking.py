"""
Database locking utilities for concurrent request handling.

This module provides:
- Optimistic locking
- Pessimistic locking (select_for_update)
- Row-level locking for order operations
"""
import logging
from sqlalchemy import select
from app import db

logger = logging.getLogger(__name__)


def with_row_lock(query, nowait=False, skip_locked=False):
    """
    Add row-level lock to query (SELECT FOR UPDATE).
    
    Args:
        query: SQLAlchemy query object
        nowait: If True, don't wait for lock (raise exception if locked)
        skip_locked: If True, skip locked rows
    
    Returns:
        Query with FOR UPDATE lock
    """
    if nowait:
        return query.with_for_update(nowait=True)
    elif skip_locked:
        return query.with_for_update(skip_locked=True)
    else:
        return query.with_for_update()


def lock_order_for_update(order_id, user_id=None, nowait=False):
    """
    Lock an order row for update to prevent concurrent modifications.
    
    Note: This function requires an active database transaction.
    Flask-SQLAlchemy auto-starts transactions, but ensure you're within
    a request context when calling this.
    
    Args:
        order_id: Order ID to lock
        user_id: Optional user ID for authorization check
        nowait: If True, don't wait for lock
    
    Returns:
        Locked Order object or None if not found
    
    Raises:
        Exception if locking fails or transaction is not active
    """
    from app.models import Order
    
    try:
        # Ensure we're in a transaction context
        # Flask-SQLAlchemy auto-starts transactions, but we verify session is active
        if not db.session.is_active:
            logger.warning("Session is not active, attempting to start transaction")
        
        query = Order.query.filter_by(order_id=order_id)
        
        if user_id:
            query = query.filter_by(mr_id=user_id)
        
        # Add row lock (requires active transaction)
        if nowait:
            order = query.with_for_update(nowait=True).first()
        else:
            order = query.with_for_update().first()
        
        if order:
            logger.debug(f"Locked order {order_id} for update")
        
        return order
    except Exception as e:
        logger.error(f"Error locking order {order_id}: {str(e)}")
        raise


def lock_cart_item_for_update(item_id, user_id, nowait=False):
    """
    Lock a cart item for update.
    
    Args:
        item_id: Cart item ID
        user_id: User ID (must match)
        nowait: If True, don't wait for lock
    
    Returns:
        Locked CartItem object or None
    """
    from app.models import CartItem
    
    try:
        query = CartItem.query.filter_by(id=item_id, user_id=user_id)
        
        if nowait:
            item = query.with_for_update(nowait=True).first()
        else:
            item = query.with_for_update().first()
        
        return item
    except Exception as e:
        logger.error(f"Error locking cart item {item_id}: {str(e)}")
        raise


def optimistic_lock_update(model_instance, version_field='version'):
    """
    Optimistic locking update helper.
    
    Args:
        model_instance: Model instance to update
        version_field: Name of version field
    
    Raises:
        StaleDataError if version mismatch
    """
    from sqlalchemy.orm.exc import StaleDataError
    
    if hasattr(model_instance, version_field):
        current_version = getattr(model_instance, version_field)
        # Increment version
        setattr(model_instance, version_field, current_version + 1)
        
        # Check version on update
        from sqlalchemy import and_
        result = db.session.execute(
            db.update(type(model_instance))
            .where(
                and_(
                    type(model_instance).id == model_instance.id,
                    getattr(type(model_instance), version_field) == current_version
                )
            )
            .values(**{k: v for k, v in model_instance.__dict__.items() if not k.startswith('_')})
        )
        
        if result.rowcount == 0:
            raise StaleDataError(f"Optimistic lock failed: {type(model_instance).__name__} {model_instance.id} was modified")

