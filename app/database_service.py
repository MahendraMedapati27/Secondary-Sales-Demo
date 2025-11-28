import logging
from datetime import datetime
from sqlalchemy import text, and_, or_, func
from app import db
from app.models import (User, Product, Order, OrderItem, CartItem, ChatSession, 
                        Conversation, PendingOrderProducts, Customer, FOC, DealerWiseStockDetails)

# Single logger initialization - logging.basicConfig should only be called once in __init__.py
logger = logging.getLogger(__name__)

class DatabaseService:
    """Service for database operations"""
    
    def __init__(self):
        self.logger = logger
    
    # User Management
    def get_user_by_email(self, email):
        """Get user by email"""
        return User.query.filter_by(email=email).first()
    
    def create_user(self, name, email, phone, role='mr', pharmacy_name=None, area=None, discount=0.0):
        """Create new user with updated schema fields"""
        try:
            user = User(
                name=name,
                email=email,
                phone=phone,
                role=role,  # 'mr' or 'distributor'
                pharmacy_name=pharmacy_name,
                area=area,
                discount=discount
            )
            user.generate_unique_id()
            db.session.add(user)
            db.session.commit()
            return user
        except Exception as e:
            self.logger.error(f"Error creating user: {str(e)}")
            db.session.rollback()
            raise
    
    def get_user_by_unique_id(self, unique_id):
        """Get user by unique ID"""
        return User.query.filter_by(unique_id=unique_id).first()
    
    def get_user_by_phone(self, phone):
        """Get user by phone number"""
        return User.query.filter_by(phone=phone).first()
    
    def get_users_by_role(self, role):
        """Get users by role (mr, distributor)"""
        return User.query.filter_by(role=role, is_active=True).all()
    
    def get_distributors(self):
        """Get all distributors"""
        return self.get_users_by_role('distributor')
    
    def get_medical_representatives(self):
        """Get all medical representatives"""
        return self.get_users_by_role('mr')
    
    def update_user_area(self, user_id, area):
        """Update user's area"""
        try:
            user = User.query.get(user_id)
            if user:
                user.area = area
                user.updated_at = datetime.utcnow()
                db.session.commit()
                return user
            return None
        except Exception as e:
            self.logger.error(f"Error updating user area: {str(e)}")
            db.session.rollback()
            raise
    
    # Product Management
    def get_all_products(self):
        """Get all products"""
        return Product.query.all()
    
    def get_product_by_id(self, product_id):
        """Get product by ID"""
        return Product.query.get(product_id)
    
    def get_product_by_name(self, product_name):
        """Get product by name"""
        return Product.query.filter_by(product_name=product_name).first()
    
    def get_products_from_dealer_stock(self, user_area):
        """
        Get products from dealer_wise_stock_details for MRs based on area
        Returns list of dicts with product info and available quantities
        """
        try:
            # Find dealers in the user's area
            dealers_in_area = User.query.filter_by(
                role='distributor',
                area=user_area
            ).all()
            
            if not dealers_in_area:
                self.logger.warning(f"No dealers found in area {user_area}")
                return []
            
            dealer_unique_ids = [d.unique_id for d in dealers_in_area]
            
            # Get confirmed stock from dealers in this area
            # Group by product to get aggregate availability
            stock_details = db.session.query(
                DealerWiseStockDetails.product_id,
                DealerWiseStockDetails.product_code,
                DealerWiseStockDetails.product_name,
                func.sum(DealerWiseStockDetails.available_for_sale).label('total_available'),
                func.avg(DealerWiseStockDetails.sales_price).label('avg_sales_price'),
                func.min(DealerWiseStockDetails.expiry_date).label('earliest_expiry')
            ).filter(
                DealerWiseStockDetails.dealer_unique_id.in_(dealer_unique_ids),
                DealerWiseStockDetails.status == 'confirmed',
                DealerWiseStockDetails.available_for_sale > 0
            ).group_by(
                DealerWiseStockDetails.product_id,
                DealerWiseStockDetails.product_code,
                DealerWiseStockDetails.product_name
            ).all()
            
            products = []
            for stock in stock_details:
                product_data = {
                    'product_id': stock.product_id,
                    'product_code': stock.product_code,
                    'product_name': stock.product_name,
                    'available_quantity': int(stock.total_available) if stock.total_available else 0,
                    'sales_price': float(stock.avg_sales_price) if stock.avg_sales_price else 0.0,
                    'earliest_expiry': stock.earliest_expiry
                }
                
                # Get FOC schemes if product_id exists
                if stock.product_id:
                    product = Product.query.get(stock.product_id)
                    if product:
                        product_data['price'] = product.price
                        product_data['team'] = product.team
                        
                        # Get FOC schemes
                        foc = FOC.query.filter_by(product_id=stock.product_id, is_active=True).first()
                        if foc:
                            product_data['foc'] = foc.to_dict()
                
                products.append(product_data)
            
            self.logger.info(f"Found {len(products)} products from dealer stock in area {user_area}")
            return products
            
        except Exception as e:
            self.logger.error(f"Error getting products from dealer stock: {str(e)}")
            return []
    
    def search_products(self, query):
        """Search products by name"""
        return Product.query.filter(
            Product.product_name.ilike(f'%{query}%')
        ).all()
    
    # Order Management
    def create_order(self, mr_id, mr_unique_id, customer_id=None, customer_unique_id=None):
        """Create new order"""
        try:
            order = Order(
                mr_id=mr_id,
                mr_unique_id=mr_unique_id,
                customer_id=customer_id,
                customer_unique_id=customer_unique_id
            )
            order.generate_order_id()
            db.session.add(order)
            db.session.commit()
            return order
        except Exception as e:
            self.logger.error(f"Error creating order: {str(e)}")
            try:
                db.session.rollback()
            except Exception:
                pass
            raise
    
    def add_order_item(self, order_id, product_id, product_code, product_name, quantity, unit_price):
        """Add item to order"""
        try:
            total_price = quantity * unit_price
            order_item = OrderItem(
                order_id=order_id,
                product_id=product_id,
                product_code=product_code,
                product_name=product_name,
                quantity=quantity,
                unit_price=unit_price,
                total_price=total_price
            )
            db.session.add(order_item)
            db.session.commit()
            return order_item
        except Exception as e:
            self.logger.error(f"Error adding order item: {str(e)}")
            try:
                db.session.rollback()
            except Exception:
                pass
            raise
    
    def update_order_total(self, order_id):
        """Update order total amount including tax"""
        try:
            order = Order.query.get(order_id)
            if order:
                # Calculate subtotal from order items
                subtotal = sum(item.total_price for item in order.order_items)
                
                # Calculate tax (use order's tax_rate or config default)
                from flask import current_app
                tax_rate = order.tax_rate if hasattr(order, 'tax_rate') and order.tax_rate else current_app.config.get('TAX_RATE', 0.05)
                tax_amount = subtotal * tax_rate
                
                # Calculate grand total
                grand_total = subtotal + tax_amount
                
                # Update order fields
                order.subtotal = subtotal
                order.tax_amount = tax_amount
                order.total_amount = grand_total
                order.updated_at = datetime.utcnow()
                
                db.session.commit()
                return order
            return None
        except Exception as e:
            self.logger.error(f"Error updating order total: {str(e)}")
            try:
                db.session.rollback()
            except Exception:
                pass
            raise
    
    def get_orders_by_mr(self, mr_id):
        """Get orders by MR"""
        return Order.query.filter_by(mr_id=mr_id).order_by(Order.created_at.desc()).all()
    
    def get_orders_by_email(self, email):
        """Get orders by user email"""
        # Find user by email first
        user = self.get_user_by_email(email)
        if user:
            if user.role == 'mr':
                return self.get_orders_by_mr(user.id)
            else:
                return []
        return []
    
    def get_orders_by_user(self, user_id):
        """Get orders by user (MR)"""
        user = User.query.get(user_id)
        if user and user.role == 'mr':
            return self.get_orders_by_mr(user_id)
        return []
    
    def get_order_by_id(self, order_id):
        """Get order by order ID"""
        return Order.query.filter_by(order_id=order_id).first()
    
    def update_order_status(self, order_id, status):
        """Update order status with validation"""
        # Import valid statuses from enhanced_order_service
        try:
            from app.enhanced_order_service import VALID_ORDER_STATUSES, ORDER_STATUS_TRANSITIONS
            
            order = Order.query.filter_by(order_id=order_id).first()
            if order:
                # Validate status
                if status not in VALID_ORDER_STATUSES:
                    self.logger.warning(f"Invalid order status '{status}' for order {order_id}")
                    return None
                
                # Validate status transition
                current_status = order.status
                if current_status in ORDER_STATUS_TRANSITIONS:
                    if status not in ORDER_STATUS_TRANSITIONS[current_status]:
                        self.logger.warning(f"Invalid status transition from '{current_status}' to '{status}' for order {order_id}")
                        # Allow transition but log warning
                
                order.status = status
                order.updated_at = datetime.utcnow()
                db.session.commit()
                return order
            return None
        except ImportError:
            # Fallback if import fails
            order = Order.query.filter_by(order_id=order_id).first()
            if order:
                order.status = status
                order.updated_at = datetime.utcnow()
                db.session.commit()
                return order
            return None
    
    def get_orders_for_distributor(self, distributor_user, status_filter=None):
        """Get orders for a distributor's area"""
        area = distributor_user.area
        
        # Build query - filter by MR.area matching distributor.area
        query = Order.query.join(User, Order.mr_id == User.id).filter(User.area == area)
        
        # Apply status filter
        if status_filter:
            if isinstance(status_filter, str):
                status_filter = [status_filter]
            query = query.filter(
                or_(
                    Order.status.in_(status_filter),
                    Order.order_stage.in_(status_filter)
                )
            )
        else:
            # Default: exclude completed orders
            query = query.filter(Order.order_stage != 'completed')
        
        return query.order_by(Order.created_at.desc()).all()
    
    # Chat Session Management
    def create_chat_session(self, user_id):
        """Create new chat session"""
        session = ChatSession(user_id=user_id)
        session.generate_session_id()
        db.session.add(session)
        db.session.commit()
        return session
    
    def get_active_session(self, user_id):
        """Get active chat session for user"""
        return ChatSession.query.filter_by(
            user_id=user_id,
            is_active=True,
            is_deleted=False
        ).first()
    
    def deactivate_session(self, session_id):
        """Deactivate chat session"""
        try:
            session = ChatSession.query.filter_by(session_id=session_id).first()
            if session:
                session.is_active = False
                session.is_deleted = True
                session.deleted_at = datetime.utcnow()
                db.session.commit()
                self.logger.info(f"Successfully deactivated session {session_id}")
                return True
            else:
                self.logger.warning(f"No session found to deactivate: {session_id}")
                return False
        except Exception as e:
            self.logger.error(f"Error deactivating session {session_id}: {str(e)}")
            try:
                db.session.rollback()
            except:
                pass
            return False
    
    # Conversation Management
    def save_conversation(self, user_id, session_id, user_message, bot_response, data_sources=None, response_time=None):
        """Save conversation"""
        try:
            conversation = Conversation(
                user_id=user_id,
                session_id=session_id,
                user_message=user_message,
                bot_response=bot_response,
                data_sources=str(data_sources) if data_sources else None,
                response_time=response_time
            )
            db.session.add(conversation)
            db.session.commit()
            self.logger.info(f"Saved conversation for user {user_id}")
            return conversation
        except Exception as e:
            self.logger.error(f"Error saving conversation: {str(e)}")
            try:
                db.session.rollback()
            except Exception:
                pass
            return None
    
    def get_conversation_history(self, user_id, limit=50):
        """Get conversation history for user"""
        return Conversation.query.filter_by(user_id=user_id).order_by(
            Conversation.created_at.desc()
        ).limit(limit).all()
    
    # Cart Management
    def add_to_cart(self, user_id, product_id, product_code, product_name, quantity, unit_price):
        """Add item to user's cart with row-level locking"""
        try:
            from app.db_locking import with_row_lock
            
            # Check if item already exists in cart (with lock to prevent race conditions)
            existing_item_query = CartItem.query.filter_by(
                user_id=user_id, 
                product_id=product_id
            )
            existing_item = with_row_lock(existing_item_query, nowait=False).first()
            
            if existing_item:
                # Update quantity
                existing_item.quantity += quantity
                existing_item.total_price = existing_item.unit_price * existing_item.quantity
                existing_item.updated_at = datetime.utcnow()
                db.session.commit()
                return existing_item, "Item added to cart"
            else:
                # Create new cart item
                total_price = unit_price * quantity
                cart_item = CartItem(
                    user_id=user_id,
                    product_id=product_id,
                    product_code=product_code,
                    product_name=product_name,
                    quantity=quantity,
                    unit_price=unit_price,
                    total_price=total_price
                )
                db.session.add(cart_item)
                db.session.commit()
                return cart_item, "Item added to cart"
        except Exception as e:
            self.logger.error(f"Error adding to cart: {str(e)}")
            try:
                db.session.rollback()
            except Exception:
                pass
            raise
    
    def get_cart_items(self, user_id):
        """Get user's cart items"""
        try:
            return CartItem.query.filter_by(user_id=user_id).all()
        except Exception as e:
            self.logger.error(f"Error getting cart items: {str(e)}")
            return []
    
    def update_cart_item_quantity(self, cart_item_id, quantity):
        """Update cart item quantity"""
        try:
            cart_item = CartItem.query.get(cart_item_id)
            if cart_item:
                cart_item.quantity = quantity
                cart_item.total_price = (cart_item.unit_price or 0) * quantity
                cart_item.updated_at = datetime.utcnow()
                db.session.commit()
                return cart_item, "Cart item updated"
            return None, "Cart item not found"
        except Exception as e:
            self.logger.error(f"Error updating cart item: {str(e)}")
            try:
                db.session.rollback()
            except Exception:
                pass
            return None, f"Error updating cart item: {str(e)}"
    
    def remove_from_cart(self, cart_item_id):
        """Remove item from cart"""
        try:
            cart_item = CartItem.query.get(cart_item_id)
            if cart_item:
                db.session.delete(cart_item)
                db.session.commit()
                return True, "Item removed from cart"
            return False, "Cart item not found"
        except Exception as e:
            self.logger.error(f"Error removing from cart: {str(e)}")
            try:
                db.session.rollback()
            except Exception:
                pass
            return False, f"Error removing from cart: {str(e)}"
    
    def remove_from_cart_by_product(self, user_id, product_id, quantity):
        """Remove specific quantity of a product from cart by product_id"""
        try:
            from app.db_locking import with_row_lock
            
            # Find cart item with row lock to prevent race conditions
            cart_item_query = CartItem.query.filter_by(
                user_id=user_id,
                product_id=product_id
            )
            cart_item = with_row_lock(cart_item_query, nowait=False).first()
            
            if not cart_item:
                return False, "Product not found in cart"
            
            if cart_item.quantity <= quantity:
                # Remove entire item if quantity to remove >= current quantity
                db.session.delete(cart_item)
                db.session.commit()
                return True, "Item removed from cart"
            else:
                # Reduce quantity
                cart_item.quantity -= quantity
                cart_item.total_price = (cart_item.unit_price or 0) * cart_item.quantity
                cart_item.updated_at = datetime.utcnow()
                db.session.commit()
                return True, f"Reduced quantity by {quantity}"
        except Exception as e:
            self.logger.error(f"Error removing from cart by product: {str(e)}")
            try:
                db.session.rollback()
            except Exception:
                pass
            return False, f"Error removing from cart: {str(e)}"
    
    def clear_cart(self, user_id):
        """Clear user's cart"""
        try:
            CartItem.query.filter_by(user_id=user_id).delete()
            db.session.commit()
            return True, "Cart cleared"
        except Exception as e:
            self.logger.error(f"Error clearing cart: {str(e)}")
            try:
                db.session.rollback()
            except Exception:
                pass
            return False, f"Error clearing cart: {str(e)}"
    
    # Dealer Stock Management
    def get_dealer_stock_by_dealer(self, dealer_unique_id, status=None):
        """Get stock details for a specific dealer"""
        query = DealerWiseStockDetails.query.filter_by(dealer_unique_id=dealer_unique_id)
        if status:
            query = query.filter_by(status=status)
        return query.order_by(DealerWiseStockDetails.dispatch_date.desc()).all()
    
    def confirm_dealer_stock(self, stock_id, received_quantity, confirmed_by_user_id):
        """Confirm stock arrival by dealer"""
        try:
            stock = DealerWiseStockDetails.query.get(stock_id)
            if stock:
                stock.received_quantity = received_quantity
                stock.status = 'confirmed'
                stock.confirmed_at = datetime.utcnow()
                stock.confirmed_by = confirmed_by_user_id
                
                # Check if quantity was adjusted
                if received_quantity != stock.quantity:
                    stock.quantity_adjusted = True
                    stock.adjustment_reason = f"Received {received_quantity} instead of {stock.quantity}"
                
                # Update available_for_sale (must account for blocked, out_for_delivery, and sold quantities)
                stock.update_available_quantity()  # Uses the method that correctly calculates
                
                db.session.commit()
                self.logger.info(f"Stock {stock_id} confirmed by dealer")
                return stock
            return None
        except Exception as e:
            self.logger.error(f"Error confirming dealer stock: {str(e)}")
            try:
                db.session.rollback()
            except Exception:
                pass
            return None
    
    # Customer Management
    def create_customer(self, name, email, phone, address, mr_id, mr_unique_id):
        """Create new customer"""
        try:
            customer = Customer(
                name=name,
                email=email,
                phone=phone,
                address=address,
                mr_id=mr_id,
                mr_unique_id=mr_unique_id
            )
            customer.generate_unique_id()
            db.session.add(customer)
            db.session.commit()
            return customer
        except Exception as e:
            self.logger.error(f"Error creating customer: {str(e)}")
            try:
                db.session.rollback()
            except Exception:
                pass
            raise
    
    def get_customers_by_mr(self, mr_id):
        """Get customers for a specific MR"""
        return Customer.query.filter_by(mr_id=mr_id, is_active=True).all()
    
    def get_customer_by_unique_id(self, unique_id):
        """Get customer by unique ID"""
        return Customer.query.filter_by(unique_id=unique_id).first()
    
    # Pending Orders Management
    def create_pending_order_product(self, original_order_id, product_code, product_name, 
                                    requested_quantity, user_id, user_email, original_order_item_id=None):
        """Create a pending order product entry for out-of-stock items"""
        try:
            # Validate all required fields before creating
            if not product_code or not str(product_code).strip():
                self.logger.error("product_code is required for pending order")
                return None
            
            if not product_name or not str(product_name).strip():
                self.logger.error("product_name is required for pending order")
                return None
            
            if requested_quantity is None or requested_quantity < 0:
                self.logger.error(f"Invalid requested_quantity: {requested_quantity}")
                return None
            
            if not user_id:
                self.logger.error("user_id is required for pending order")
                return None
            
            # Ensure user_email is not None or empty
            if not user_email or not str(user_email).strip():
                # Try to get email from user
                user = User.query.get(user_id)
                if user and user.email:
                    user_email = user.email
                else:
                    self.logger.warning(f"No email found for user {user_id}, using placeholder")
                    user_email = 'no-email@placeholder.com'  # Ensure non-null value
            
            # Check for existing pending order for same product and user
            # Only merge if from same original order item to avoid incorrect aggregation
            existing_pending = None
            if original_order_item_id:
                # If we have original_order_item_id, check for pending from same item
                existing_pending = PendingOrderProducts.query.filter_by(
                    user_id=int(user_id),
                    product_code=str(product_code).strip(),
                    original_order_item_id=original_order_item_id,
                    status='pending'
                ).first()
            else:
                # Fallback: check without original_order_item_id (for backward compatibility)
                existing_pending = PendingOrderProducts.query.filter_by(
                    user_id=int(user_id),
                    product_code=str(product_code).strip(),
                    status='pending'
                ).first()
            
            if existing_pending:
                # Update existing pending order quantity instead of creating duplicate
                existing_pending.requested_quantity += int(requested_quantity)
                existing_pending.updated_at = datetime.utcnow()
                db.session.commit()
                self.logger.info(f"Updated existing pending order {existing_pending.id} for product {product_code}, new quantity: {existing_pending.requested_quantity}")
                return existing_pending
            
            # Create new pending order
            pending_order = PendingOrderProducts(
                original_order_id=original_order_id if original_order_id else None,
                original_order_item_id=original_order_item_id,  # Link to original OrderItem
                product_code=str(product_code).strip(),
                product_name=str(product_name).strip(),
                requested_quantity=int(requested_quantity),
                user_id=int(user_id),
                user_email=str(user_email).strip(),
                status='pending'
            )
            db.session.add(pending_order)
            db.session.commit()
            self.logger.info(f"Created pending order for product {product_code}, quantity {requested_quantity}, user {user_id}, original_item_id={original_order_item_id}")
            return pending_order
        except Exception as e:
            self.logger.error(f"Error creating pending order product: {str(e)}")
            import traceback
            traceback.print_exc()
            try:
                db.session.rollback()
            except Exception:
                pass
            return None
    
    def get_pending_orders(self, user_id=None, status='pending'):
        """Get pending orders"""
        query = PendingOrderProducts.query.filter_by(status=status)
        if user_id:
            query = query.filter_by(user_id=user_id)
        return query.all()
    
    def update_pending_order_status(self, pending_id, status, fulfilled_order_id=None):
        """Update the status of a pending order"""
        try:
            pending_order = PendingOrderProducts.query.get(pending_id)
            if pending_order:
                pending_order.status = status
                if fulfilled_order_id:
                    pending_order.fulfilled_order_id = fulfilled_order_id
                db.session.commit()
                self.logger.info(f"Updated pending order {pending_id} status to {status}")
                return True
            return False
        except Exception as e:
            self.logger.error(f"Error updating pending order status: {str(e)}")
            db.session.rollback()
            return False
    
    def mark_pending_order_notified(self, pending_id, notification_type='user'):
        """Mark a pending order as notified"""
        try:
            pending_order = PendingOrderProducts.query.get(pending_id)
            if pending_order:
                pending_order.user_notified = True
                db.session.commit()
                self.logger.info(f"Marked pending order {pending_id} as notified ({notification_type})")
                return True
            return False
        except Exception as e:
            self.logger.error(f"Error marking pending order as notified: {str(e)}")
            db.session.rollback()
            return False
    
    # Legacy/Compatibility Methods
    def get_warehouse_by_area(self, area):
        """Legacy method - returns None (warehouses removed)"""
        # This method is kept for backward compatibility
        # Returns None since we no longer use warehouses
        return None
    
    def get_all_pending_products(self):
        """Get all pending order products"""
        return self.get_pending_orders(status='pending')
    
    def initialize_warehouses(self):
        """Legacy method - does nothing (warehouses removed)"""
        # This method is kept for backward compatibility
        self.logger.info("Warehouses table no longer used - skipping initialization")
        pass
    
    def create_sample_users(self):
        """Legacy method - sample users already imported from Excel/CSV"""
        self.logger.info("Sample users already imported from data files - skipping")
        pass
    
    def get_products_by_warehouse(self, warehouse_id):
        """Legacy method - returns all products (warehouses removed)"""
        return self.get_all_products()
    
    def get_product_by_code(self, product_code):
        """
        Get product by product code or name
        Searches in both DealerWiseStockDetails (for product_code) and Product (for product_name)
        """
        if not product_code:
            return None
        
        # Method 1: Try to find product via DealerWiseStockDetails by product_code
        # DealerWiseStockDetails has product_code field, then get the Product via product_id
        stock_detail = DealerWiseStockDetails.query.filter_by(
            product_code=product_code,
            status='confirmed'
        ).first()
        
        if stock_detail and stock_detail.product_id:
            product = Product.query.get(stock_detail.product_id)
            if product:
                self.logger.debug(f"Found product via DealerWiseStockDetails: {product_code} -> Product ID {product.id}")
                return product
        
        # Method 2: Try to find Product by product_name (case-insensitive partial match)
        # Some product codes might actually be product names
        product = Product.query.filter(
            Product.product_name.ilike(f'%{product_code}%')
        ).first()
        
        if product:
            self.logger.debug(f"Found product by name match: {product_code} -> Product ID {product.id}")
            return product
        
        # Method 3: Try exact match on product_name (case-insensitive)
        product = Product.query.filter(
            func.lower(Product.product_name) == func.lower(product_code)
        ).first()
        
        if product:
            self.logger.debug(f"Found product by exact name match: {product_code} -> Product ID {product.id}")
            return product
        
        self.logger.warning(f"Product not found by code/name: {product_code}")
        return None
    
    # FOC Management
    def get_foc_for_product(self, product_id):
        """Get FOC schemes for a product"""
        return FOC.query.filter_by(product_id=product_id, is_active=True).first()
    
    def get_product_pricing(self, product_id, quantity, user_area):
        """Get pricing for a product including FOC"""
        try:
            # Get product
            product = Product.query.get(product_id)
            if not product:
                return {
                    'final_price': 0,
                    'total_amount': 0,
                    'total_quantity': quantity,
                    'base_price': 0
                }
            
            # Get sales price from dealer stock in user's area
            dealers_in_area = User.query.filter_by(role='distributor', area=user_area).all()
            dealer_ids = [d.unique_id for d in dealers_in_area]
            
            stock = DealerWiseStockDetails.query.filter(
                DealerWiseStockDetails.dealer_unique_id.in_(dealer_ids),
                DealerWiseStockDetails.product_id == product_id,
                DealerWiseStockDetails.status == 'confirmed',
                DealerWiseStockDetails.available_for_sale > 0
            ).first()
            
            if stock:
                base_price = float(stock.sales_price)
            else:
                base_price = float(product.price)
            
            # Get FOC scheme
            foc = self.get_foc_for_product(product_id)
            if foc:
                foc_result = foc.get_foc_for_quantity(quantity)
                total_quantity = foc_result['total_quantity']
                free_quantity = foc_result['free_quantity']
            else:
                total_quantity = quantity
                free_quantity = 0
            
            # Calculate final price (customer pays for ordered quantity, gets extra free)
            final_price = base_price
            total_amount = final_price * quantity
            
            result = {
                'final_price': round(final_price, 2),
                'total_amount': round(total_amount, 2),
                'total_quantity': total_quantity,
                'free_quantity': free_quantity,
                'base_price': round(base_price, 2)
            }
            
            self.logger.info(f"Pricing calculation for product {product_id} (qty {quantity}): {result}")
            return result
            
        except Exception as e:
            self.logger.error(f"Error calculating pricing for product {product_id}: {str(e)}")
            return {
                'final_price': 0,
                'total_amount': 0,
                'total_quantity': quantity,
                'base_price': 0
            }

