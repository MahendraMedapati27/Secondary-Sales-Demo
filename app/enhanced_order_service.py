import logging
from datetime import datetime
from flask import current_app
from app import db
from app.models import Order, OrderItem, Product, User, CartItem, DealerWiseStockDetails, Customer, FOC
from app.database_service import DatabaseService
from app.pricing_service import PricingService
from app.llm_order_service import LLMOrderService
from app.email_utils import send_email
from app.db_utils import retry_on_transient_failure

# Single logger initialization
logger = logging.getLogger(__name__)

# Valid order statuses and stages
VALID_ORDER_STATUSES = ['pending', 'confirmed', 'in_transit', 'delivered', 'cancelled', 'completed']
VALID_ORDER_STAGES = ['draft', 'placed', 'confirmed', 'distributor_notified', 'in_transit', 'delivered', 'completed', 'cancelled']

# Valid status transitions
# Note: 'confirmed' can go directly to 'delivered' when delivery partner marks it
ORDER_STATUS_TRANSITIONS = {
    'pending': ['confirmed', 'cancelled'],
    'confirmed': ['in_transit', 'delivered', 'cancelled'],  # Added 'delivered' for direct delivery
    'in_transit': ['delivered', 'cancelled'],
    'delivered': ['completed'],
    'cancelled': [],  # Terminal state
    'completed': []  # Terminal state
}

class EnhancedOrderService:
    """Enhanced order service for HV (Powered by Quantum Blue AI) workflow"""
    
    def __init__(self):
        self.db_service = DatabaseService()
        self.pricing_service = PricingService()
        self.llm_service = LLMOrderService()
        self.logger = logger
    
    def process_order_request(self, user_message, user_id, conversation_history=None):
        """
        Process user order request using LLM extraction and cart management
        """
        try:
            # Get user info first
            user = User.query.get(user_id)
            if not user:
                return {
                    'success': False,
                    'message': "User not found. Please log in again."
                }
            
            # Extract products from user message
            extraction_result = self.llm_service.extract_products_from_message(
                user_message, user_id, conversation_history
            )
            
            self.logger.info(f"Extraction result: {extraction_result}")
            
            if not extraction_result.get('order_ready', False):
                return {
                    'success': False,
                    'message': "I couldn't identify specific products in your message. " + 
                              "Please specify which products you'd like to order.",
                    'suggestions': extraction_result.get('suggestions', []),
                    'unclear_requests': extraction_result.get('unclear_requests', [])
                }
            
            # Process extracted products
            cart_updates = []
            errors = []
            stock_warnings = []  # Store stock availability issues for LLM to inform user
            
            # Aggregate same product codes within this message to avoid repeated adds
            # IMPORTANT: Handle both positive (add) and negative (remove) quantities
            aggregate = {}
            for p in extraction_result.get('extracted_products', []):
                code = p.get('product_code')
                qty = int(p.get('quantity', 0))
                if code and qty != 0:  # Changed from qty > 0 to qty != 0 to allow negative quantities
                    # Aggregate: if same product appears multiple times, sum their quantities
                    aggregate[code] = aggregate.get(code, 0) + qty
                    self.logger.info(f"Aggregating {code}: qty={qty}, running_total={aggregate[code]}")

            self.logger.info(f"Processing {len(aggregate)} unique products after aggregation: {list(aggregate.keys())}")

            for product_code, quantity in aggregate.items():
                
                self.logger.info(f"Processing product: {product_code}, quantity: {quantity}")
                
                # Find product by product_code from dealer stock in user's area
                product = None
                if user.area:
                    # Find product from dealer stock in this area
                    stock = DealerWiseStockDetails.query.join(
                        User, DealerWiseStockDetails.dealer_id == User.id
                    ).filter(
                        User.area == user.area,
                        User.role == 'distributor',
                        DealerWiseStockDetails.product_code == product_code,
                        DealerWiseStockDetails.status == 'confirmed'
                    ).first()
                    
                    if stock and stock.product_id:
                        product = Product.query.get(stock.product_id)
                
                if not product:
                    # Try to find product by name match
                    product = Product.query.filter(
                        Product.product_name.ilike(f'%{product_code}%')
                    ).first()
                if not product:
                    errors.append(f"Product {product_code} not found")
                    continue
                
                # Handle negative quantities (remove operations)
                if quantity < 0:
                    # This is a remove operation
                    remove_quantity = abs(quantity)
                    self.logger.info(f"🔄 REMOVE operation: Removing {remove_quantity} units of {product_code} from cart")
                    success, message = self.db_service.remove_from_cart_by_product(user_id, product.id, remove_quantity)
                    if success:
                        cart_updates.append({
                            'product_name': product.product_name,
                            'quantity': quantity,  # Keep negative for display
                            'total_price': 0,
                            'operation': 'removed'
                        })
                        self.logger.info(f"✓ Successfully removed {remove_quantity} units of {product_code}")
                    else:
                        error_msg = f"Failed to remove {remove_quantity} {product.product_name} from cart: {message}"
                        self.logger.error(error_msg)
                        errors.append(error_msg)
                    continue  # Skip add operation processing
                
                # Handle positive quantities (add operations)
                # ONLY process if quantity is positive (not negative/remove)
                self.logger.info(f"➕ ADD operation: Adding {quantity} units of {product_code} to cart")
                # Check availability from dealer stock in user's area
                total_available = 0
                if user.area:
                    # Get total available from all dealers in this area
                    stock_query = db.session.query(
                        db.func.sum(DealerWiseStockDetails.available_for_sale)
                    ).join(
                        User, DealerWiseStockDetails.dealer_id == User.id
                    ).filter(
                        User.area == user.area,
                        User.role == 'distributor',
                        DealerWiseStockDetails.product_id == product.id,
                        DealerWiseStockDetails.status == 'confirmed'
                    )
                    
                    result = stock_query.scalar()
                    total_available = int(result) if result else 0
                else:
                    total_available = 0
                
                # Store stock info for LLM to generate message later (don't skip, just inform)
                stock_info = {
                    'product_name': product.product_name,
                    'product_code': product_code,
                    'requested': quantity,
                    'available': total_available,
                    'sufficient': total_available >= quantity
                }
                
                # If insufficient stock, add to stock warnings but continue processing
                if total_available < quantity:
                    # Don't add to cart, but add to warnings list for LLM to inform user
                    self.logger.warning(f"Insufficient stock for {product_code}: requested={quantity}, available={total_available}")
                    stock_warnings.append(stock_info)
                    continue
                
                # Log successful stock check
                self.logger.info(f"Stock check passed for {product_code}: requested={quantity}, available={total_available}")
                
                # Calculate pricing for add operations
                pricing = self.pricing_service.calculate_product_pricing(product.id, quantity)
                if 'error' in pricing:
                    errors.append(f"Pricing error for {product.product_name}: {pricing['error']}")
                    continue
                
                # Add to cart
                self.logger.info(f"Attempting to add to cart: {product_code}, qty={quantity}, product_id={product.id}")
                unit_price = pricing.get('pricing', {}).get('final_price', 0)
                cart_item, message = self.db_service.add_to_cart(
                    user_id, 
                    product.id, 
                    product_code,
                    product.product_name,
                    quantity, 
                    unit_price
                )
                
                if cart_item:
                    self.logger.info(f"Successfully added to cart: {product_code}, qty={quantity}, cart_item_id={cart_item.id if hasattr(cart_item, 'id') else 'N/A'}")
                    cart_updates.append({
                        'product_name': product.product_name,
                        'quantity': quantity,
                        'total_price': cart_item.total_price,
                        'operation': 'added'
                    })
                else:
                    error_msg = f"Failed to add {product.product_name} to cart: {message}"
                    self.logger.error(error_msg)
                    errors.append(error_msg)
            
            # Generate response
            if cart_updates or stock_warnings:
                # Get updated cart
                cart_items = self.db_service.get_cart_items(user_id)
                
                # Separate added and removed items
                added_items = [item for item in cart_updates if item.get('operation') == 'added']
                removed_items = [item for item in cart_updates if item.get('operation') == 'removed']
                
                # Generate stock availability message using LLM if there are warnings
                stock_message = ""
                if stock_warnings:
                    stock_message = self.llm_service.generate_stock_availability_message(
                        stock_warnings, 
                        user_message,
                        added_items
                    )
                
                # Build initial response about added/removed items
                response_message = ""
                
                # Only show "added" message if there are actually added items AND no remove operation
                # If there are only removed items, don't show "added" message
                if added_items and not removed_items:
                    response_message += f"Great! I've added the following items to your cart:\n\n"
                    for item in added_items:
                        response_message += f"• {item['product_name']} - Qty: {item['quantity']} - {item['total_price']:,.2f} MMK\n"
                
                if removed_items:
                    if added_items:
                        response_message += "\n"
                    response_message += f"I've removed the following items from your cart:\n\n"
                    for item in removed_items:
                        response_message += f"• {item['product_name']} - Qty: {abs(item['quantity'])} removed\n"
                
                # If both added and removed, clarify
                if added_items and removed_items:
                    response_message = f"I've updated your cart:\n\n"
                    if added_items:
                        response_message += "Added:\n"
                        for item in added_items:
                            response_message += f"• {item['product_name']} - Qty: {item['quantity']} - {item['total_price']:,.2f} MMK\n"
                    if removed_items:
                        if added_items:
                            response_message += "\nRemoved:\n"
                        for item in removed_items:
                            response_message += f"• {item['product_name']} - Qty: {abs(item['quantity'])} removed\n"
                
                # Add stock availability message from LLM
                if stock_message:
                    if response_message:
                        response_message += "\n\n"
                    response_message += stock_message
                
                if errors:
                    if response_message:
                        response_message += "\n\n"
                    response_message += f"Note: {len(errors)} items couldn't be processed.\n"
                
                # Initialize order_summary to avoid reference before assignment error
                order_summary = {}
                
                # Generate order summary if cart has items
                if cart_items:
                    order_summary = self.llm_service.generate_order_summary(cart_items, user)
                    if response_message:
                        response_message += "\n\n"
                    response_message += order_summary['summary']
                elif not added_items and not removed_items:
                    # No items were added/removed and no stock warnings, something went wrong
                    response_message = stock_message if stock_message else "I couldn't process your request. Please try again."
                
                return {
                    'success': True,
                    'message': response_message,
                    'cart_items': cart_updates,
                    'order_summary': order_summary,
                    'errors': errors
                }
            else:
                return {
                    'success': False,
                    'message': "I couldn't add any items to your cart. Please check the product names and try again.",
                    'errors': errors
                }
            
        except Exception as e:
            self.logger.error(f"Error processing order request: {str(e)}")
            return {
                'success': False,
                'message': f"An error occurred while processing your order: {str(e)}"
            }
    
    @retry_on_transient_failure()
    def place_order(self, user_id, placed_by_user_id=None, customer_id=None):
        """
        Place order from cart with distributor notification workflow
        Includes customer details for MR orders
        Wrapped in single transaction for atomicity
        """
        try:
            from app.models import Customer
            
            # Get user and cart items (validation - no transaction needed)
            user = User.query.get(user_id)
            if not user:
                return {
                    'success': False,
                    'message': "User not found"
                }
            
            cart_items = self.db_service.get_cart_items(user_id)
            if not cart_items:
                return {
                    'success': False,
                    'message': "Your cart is empty"
                }
            
            # Determine who placed the order
            placed_by_user = User.query.get(placed_by_user_id) if placed_by_user_id else user
            
            # Get customer details if customer_id is provided (for both MR and Dealer)
            customer = None
            if customer_id:
                customer = Customer.query.get(customer_id)
                if not customer:
                    return {
                        'success': False,
                        'message': "Customer not found"
                    }
                
                # Verify customer belongs to this user
                if user.role == 'mr':
                    if customer.mr_unique_id != user.unique_id:
                        return {
                            'success': False,
                            'message': "Customer not found or not assigned to you"
                        }
                elif user.role == 'distributor':
                    if customer.dealer_id != user.id:
                        return {
                            'success': False,
                            'message': "Customer not found or not assigned to you"
                        }
            
            # Check if user has area assigned
            if not user.area:
                return {
                    'success': False,
                    'message': "No area assigned to your account. Please contact support."
                }
            
            # Separate cart items into expired and non-expired products FIRST
            # (Don't create order until we know there are valid items)
            valid_cart_items = []  # Products that can be ordered (non-expired or limited availability)
            expired_cart_items = []  # Products that are expired/out of stock
            expired_products_info = []  # Detailed info for notifications
            
            # Pre-process cart items to separate expired vs valid products
            for cart_item in cart_items:
                product = Product.query.get(cart_item.product_id)
                if not product:
                    continue
                
                # Check availability WITHOUT allocating (to avoid double allocation)
                from datetime import date
                from sqlalchemy import func
                today = date.today()
                
                # Check stock availability based on user role
                if user.role == 'mr' and user.area:
                    # For MRs, check stock from dealers in their area
                    dealers_in_area = User.query.filter_by(
                        role='distributor',
                        area=user.area
                    ).all()
                    
                    if dealers_in_area:
                        dealer_unique_ids = [d.unique_id for d in dealers_in_area]
                        
                        # Get stock from dealer_wise_stock_details
                        stock_details = DealerWiseStockDetails.query.filter(
                            DealerWiseStockDetails.product_code == cart_item.product_code,
                            DealerWiseStockDetails.status == 'confirmed',
                            DealerWiseStockDetails.dealer_unique_id.in_(dealer_unique_ids)
                        ).all()
                        
                        # Check if any non-expired batches exist
                        non_expired_batches = [s for s in stock_details if not s.expiry_date or s.expiry_date >= today]
                        expired_batches = [s for s in stock_details if s.expiry_date and s.expiry_date < today]
                        
                        # Calculate available quantities from dealer stock
                        non_expired_qty = sum(s.available_for_sale for s in non_expired_batches if s.available_for_sale > 0)
                        expired_qty = sum(s.available_for_sale for s in expired_batches if s.available_for_sale > 0)
                    else:
                        # No dealers found - treat as no stock
                        non_expired_qty = 0
                        expired_qty = 0
                        non_expired_batches = []
                        expired_batches = []
                elif user.role == 'distributor' and user.unique_id:
                    # For distributors, check their own stock from dealer_wise_stock_details
                    stock_details = DealerWiseStockDetails.query.filter(
                        DealerWiseStockDetails.product_code == cart_item.product_code,
                        DealerWiseStockDetails.status == 'confirmed',
                        DealerWiseStockDetails.dealer_unique_id == user.unique_id
                    ).all()
                    
                    # Check if any non-expired batches exist
                    non_expired_batches = [s for s in stock_details if not s.expiry_date or s.expiry_date >= today]
                    expired_batches = [s for s in stock_details if s.expiry_date and s.expiry_date < today]
                    
                    # Calculate available quantities from distributor's own stock
                    non_expired_qty = sum(s.available_for_sale for s in non_expired_batches if s.available_for_sale > 0)
                    expired_qty = sum(s.available_for_sale for s in expired_batches if s.available_for_sale > 0)
                    
                    self.logger.info(f"Distributor {user.unique_id} stock check for {cart_item.product_code}: non_expired={non_expired_qty}, expired={expired_qty}, requested={cart_item.quantity}")
                else:
                    # For other users or missing info, treat as no stock
                    non_expired_qty = 0
                    expired_qty = 0
                    non_expired_batches = []
                    expired_batches = []
                
                # Check three scenarios:
                # 1. Has both expired and non-expired but not enough total - treat as expired
                # 2. Has only non-expired but insufficient quantity - treat as expired (insufficient stock)
                # 3. Has enough non-expired stock - add to valid
                
                if non_expired_qty < cart_item.quantity:
                    # Not enough non-expired stock - treat as expired/insufficient
                    expired_cart_items.append(cart_item)
                    
                    # Track info for notification
                    product_name = product.product_name if product else cart_item.product_code
                    
                    expired_info = {
                        'product_code': cart_item.product_code,
                        'product_name': product_name,
                        'expired_batches': [],
                        'available_qty': non_expired_qty,
                        'requested_qty': cart_item.quantity,
                        'reason': 'expired' if expired_batches else 'insufficient_stock'
                    }
                    
                    # Track expired batches if any
                    for batch in expired_batches:
                        available_qty = batch.available_for_sale if hasattr(batch, 'available_for_sale') else 0
                        if available_qty > 0:
                            # Handle both Product and DealerWiseStockDetails
                            expiry_date = batch.expiry_date if hasattr(batch, 'expiry_date') else (batch.expiry_date if hasattr(batch, 'expiration_date') else None)
                            days_expired = (today - expiry_date).days if expiry_date else 0
                            
                            expired_info['expired_batches'].append({
                                'batch_number': (batch.batch_number if hasattr(batch, 'batch_number') else (batch.lot_number if hasattr(batch, 'lot_number') else 'N/A')) or 'N/A',
                                'quantity': available_qty,
                                'expiry_date': expiry_date.isoformat() if expiry_date else None,
                                'days_expired': days_expired
                            })
                    
                    # Always add to expired_products_info for notification
                    expired_products_info.append(expired_info)
                    
                    # Log the issue
                    if expired_batches:
                        self.logger.warning(f"⚠️ EXPIRED/INSUFFICIENT PRODUCT: {cart_item.product_code} - Requested: {cart_item.quantity}, Non-expired available: {non_expired_qty}, Expired available: {expired_qty}, creating pending order")
                    else:
                        self.logger.warning(f"⚠️ INSUFFICIENT STOCK: {cart_item.product_code} - Requested: {cart_item.quantity}, Available: {non_expired_qty}, creating pending order")
                else:
                    # Has enough non-expired stock - add to valid list
                    valid_cart_items.append(cart_item)
                    
                    # Still track any expired batches for notification
                    if expired_batches:
                        expired_batches_info = []
                        for batch in expired_batches:
                            available_qty = batch.available_for_sale if hasattr(batch, 'available_for_sale') else 0
                            if available_qty > 0:
                                # Handle both Product and DealerWiseStockDetails
                                expiry_date = batch.expiry_date if hasattr(batch, 'expiry_date') else (batch.expiry_date if hasattr(batch, 'expiration_date') else None)
                                
                                expired_batches_info.append({
                                    'batch_number': (batch.batch_number if hasattr(batch, 'batch_number') else (batch.lot_number if hasattr(batch, 'lot_number') else 'N/A')) or 'N/A',
                                    'quantity': available_qty,
                                    'expiry_date': expiry_date.isoformat() if expiry_date else None,
                                    'days_expired': (today - expiry_date).days if expiry_date else 0
                                })
                        
                        if expired_batches_info:
                            product_name = product.product_name if product else cart_item.product_code
                            
                            expired_info = {
                                'product_code': cart_item.product_code,
                                'product_name': product_name,
                                'expired_batches': expired_batches_info
                            }
                            
                            expired_products_info.append(expired_info)
                
            
            # If no valid cart items and no expired items, return error
            if not valid_cart_items and not expired_cart_items:
                return {
                    'success': False,
                    'message': "No products could be processed. Please check your cart items."
                }
            
            # If there are NO valid items (all are expired/insufficient), handle differently
            # (No order creation needed - just pending orders)
            if not valid_cart_items:
                # Only expired/insufficient items - don't create a regular order
                # Just create pending orders and inform user
                
                # Store expired items info BEFORE clearing cart
                expired_items_details = []
                for expired_item in expired_cart_items:
                    product = Product.query.get(expired_item.product_id)
                    if product:
                        expired_info = next((info for info in expired_products_info if info['product_code'] == expired_item.product_code), None)
                        expired_items_details.append({
                            'product_id': expired_item.product_id,
                            'product_code': expired_item.product_code,
                            'product_name': product.product_name,
                            'quantity': expired_item.quantity,
                            'available_qty': expired_info.get('available_qty', 0) if expired_info else 0,
                            'reason': expired_info.get('reason', 'expired') if expired_info else 'expired'
                        })
                
                # Create pending orders
                pending_products_created = []
                for expired_item in expired_cart_items:
                    product = Product.query.get(expired_item.product_id)
                    if product:
                        expired_info = next((info for info in expired_products_info if info['product_code'] == expired_item.product_code), None)
                        pending_order = self.db_service.create_pending_order_product(
                            original_order_id=None,  # No order created yet
                            product_code=expired_item.product_code,
                            product_name=product.product_name,
                            requested_quantity=expired_item.quantity,
                            user_id=user.id,
                            user_email=user.email,
                            original_order_item_id=None  # No order item yet
                        )
                        if pending_order:
                            pending_products_created.append(pending_order)
                
                # Clear cart
                self.db_service.clear_cart(user_id)
                
                # Build message for user
                message = "⚠️ **Order Status: All Products Currently Unavailable**\n\n"
                message += "Unfortunately, all the products in your cart are currently not available:\n\n"
                
                for item_detail in expired_items_details:
                    if item_detail['reason'] == 'insufficient_stock':
                        message += f"• **{item_detail['product_name']}** ({item_detail['product_code']}) - Requested: {item_detail['quantity']} units, Available: {item_detail['available_qty']} units (insufficient stock)\n"
                    else:
                        message += f"• **{item_detail['product_name']}** ({item_detail['product_code']}) - {item_detail['quantity']} units (expired/insufficient stock)\n"
                
                message += f"""
**📦 Auto-Order System:**
These products will be automatically ordered when new stock arrives, and you'll receive an email notification.

**💡 What You Can Do:**
• Wait for stock to arrive (you'll be notified automatically)
• Adjust quantities and try again
• Remove items and add different products

**📧 Email notifications:**
You'll receive an email when any of these products become available."""
                
                return {
                    'success': True,
                    'message': message,
                    'order_id': None,
                    'pending_orders': len(pending_products_created)
                }
            
            # Now create the order since we have valid items
            # Create order without explicit transaction (Flask-SQLAlchemy manages it)
            order = Order(
                mr_id=user_id,
                mr_unique_id=user.unique_id,
                status='pending',
                order_stage='placed',
                # Track who created this order
                created_by_role=user.role,
                created_by_id=user.id,
                created_by_unique_id=user.unique_id
            )
            
            # Add customer details if MR order
            if customer:
                order.customer_id = customer.id
                order.customer_unique_id = customer.unique_id
            
            order.generate_order_id()
            db.session.add(order)
            db.session.flush()  # Flush to get order.id without committing
            
            # Add order items and calculate totals only for valid cart items
            subtotal = 0
            
            for cart_item in valid_cart_items:
                # Calculate final pricing
                pricing = self.pricing_service.calculate_product_pricing(
                    cart_item.product_id, 
                    cart_item.quantity
                )
                
                if 'error' not in pricing:
                    # Get sales price (unit price)
                    sales_price = pricing['pricing']['final_price']
                    total_price = pricing['pricing']['total_amount']
                    
                    # Get FOC information from 'scheme' key
                    foc_info = pricing.get('scheme', {})
                    free_quantity = foc_info.get('free_quantity', 0)
                    
                    # Create order item with FOC information
                    # Ensure all required fields are populated before creating OrderItem
                    if not order.id:
                        self.logger.error("Order ID is missing")
                        raise ValueError("Order ID is required")
                    
                    if not cart_item.product_id:
                        self.logger.error(f"Product ID is missing for cart item {cart_item.id}")
                        raise ValueError(f"Product ID is required for {cart_item.product_code}")
                    
                    if not cart_item.product_code or not cart_item.product_name:
                        self.logger.error(f"Product code or name is missing for cart item {cart_item.id}")
                        raise ValueError(f"Product code and name are required for cart item {cart_item.id}")
                    
                    if cart_item.quantity is None or cart_item.quantity < 0:
                        self.logger.error(f"Invalid quantity for cart item {cart_item.id}: {cart_item.quantity}")
                        raise ValueError(f"Invalid quantity for {cart_item.product_code}")
                    
                    order_item = OrderItem(
                        order_id=int(order.id),
                        product_id=int(cart_item.product_id),
                        product_code=str(cart_item.product_code).strip(),
                        product_name=str(cart_item.product_name).strip(),
                        quantity=int(cart_item.quantity),  # Paid quantity
                        free_quantity=int(free_quantity) if free_quantity else 0,  # FOC quantity
                        unit_price=float(sales_price) if sales_price else 0.0,
                        total_price=float(total_price) if total_price else 0.0
                    )
                    db.session.add(order_item)
                    
                    subtotal += total_price
                    
                    # Calculate total quantity including FOC (paid + free)
                    total_quantity_to_block = cart_item.quantity + free_quantity
                    
                    # Block quantity in dealer stock using FEFO (First Expiry, First Out)
                    # IMPORTANT: Block total quantity (paid + FOC) since both need to be reserved from stock
                    if user.role == 'mr' and user.area:
                        # For MRs, block quantity from dealers in their area
                        success = self._block_quantity_for_mr_order(
                            user=user,
                            product_code=cart_item.product_code,
                            quantity=total_quantity_to_block  # Block paid + FOC quantity
                        )
                        
                        if not success:
                            self.logger.error(f"Failed to block quantity for {cart_item.product_code}")
                            raise Exception(f"Failed to block quantity for {cart_item.product_code}")
                        
                        self.logger.info(f"Successfully blocked {total_quantity_to_block} units ({cart_item.quantity} paid + {free_quantity} FOC) of {cart_item.product_code} in dealer stock")
                    elif user.role == 'distributor' and user.unique_id:
                        # For distributors, block quantity from their own stock
                        success = self._block_quantity_for_distributor_order(
                            user=user,
                            product_code=cart_item.product_code,
                            quantity=total_quantity_to_block  # Block paid + FOC quantity
                        )
                        
                        if not success:
                            self.logger.error(f"Failed to block quantity for {cart_item.product_code}")
                            raise Exception(f"Failed to block quantity for {cart_item.product_code}")
                        
                        self.logger.info(f"Successfully blocked {total_quantity_to_block} units ({cart_item.quantity} paid + {free_quantity} FOC) of {cart_item.product_code} from distributor's own stock")
            
            # Calculate tax and update order totals
            tax_rate = 0.05  # Default tax rate
            try:
                from flask import has_app_context
                if has_app_context():
                    tax_rate = current_app.config.get('TAX_RATE', 0.05)  # Get from config, default 5%
            except (RuntimeError, AttributeError):
                pass
            tax_amount = subtotal * tax_rate
            grand_total = subtotal + tax_amount
            
            # Store subtotal, tax, and grand total
            order.subtotal = subtotal
            order.tax_amount = tax_amount
            order.tax_rate = tax_rate
            order.total_amount = grand_total  # Grand total includes tax
            
            # Set order status based on user role with validation
            if user.role == 'mr':
                order.status = 'pending'  # MR orders start as pending until dealer confirms
                order.order_stage = 'placed'  # Order is placed, waiting for dealer confirmation
            elif user.role == 'distributor':
                # Distributors place orders for their own stock management
                # These orders are immediately confirmed (self-confirmed)
                order.status = 'confirmed'  # Distributor orders are self-confirmed
                order.order_stage = 'confirmed'
                order.distributor_confirmed_at = datetime.utcnow()
                order.distributor_confirmed_by = user.id
            else:
                order.status = 'in_transit'  # First stage: in transit
                order.order_stage = 'distributor_notified'
            
            # Validate order status and stage
            if order.status not in VALID_ORDER_STATUSES:
                self.logger.warning(f"Invalid order status '{order.status}', defaulting to 'pending'")
                order.status = 'pending'
            if order.order_stage not in VALID_ORDER_STAGES:
                self.logger.warning(f"Invalid order stage '{order.order_stage}', defaulting to 'placed'")
                order.order_stage = 'placed'
            
            # NOTE: Stock is now BLOCKED (not sold yet)
            # For MR orders: It will move from blocked to out_for_delivery when dealer confirms and assigns delivery partner
            # For distributor orders: It will move from blocked to out_for_delivery when order is placed (auto-confirmed)
            # Stock will then move from out_for_delivery to sold when delivery partner marks as delivered
            # IMPORTANT: Wait until order items are created to get FOC quantities
            # Stock movement will happen after order items are added (see below)
            
            # Store all needed information BEFORE clearing cart
            # Store expired items details
            expired_items_details = []
            for expired_item in expired_cart_items:
                product = Product.query.get(expired_item.product_id)
                if product:
                    expired_info = next((info for info in expired_products_info if info['product_code'] == expired_item.product_code), None)
                    expired_items_details.append({
                        'product_id': expired_item.product_id,
                        'product_code': expired_item.product_code,
                        'product_name': product.product_name,
                        'quantity': expired_item.quantity,
                        'available_qty': expired_info.get('available_qty', 0) if expired_info else 0,
                        'reason': expired_info.get('reason', 'expired') if expired_info else 'expired'
                    })
            
            # Store valid items details (for order summary)
            valid_items_details = []
            for cart_item in valid_cart_items:
                product = Product.query.get(cart_item.product_id)
                if product:
                    pricing = self.pricing_service.calculate_product_pricing(
                        cart_item.product_id, 
                        cart_item.quantity
                    )
                    if 'error' not in pricing:
                        # Get total quantity including FOC
                        foc_info = pricing.get('scheme', {})  # FOC info is in 'scheme' key
                        free_quantity = foc_info.get('free_quantity', 0)
                        total_quantity = cart_item.quantity + free_quantity
                        
                        valid_items_details.append({
                            'name': product.product_name,
                            'code': cart_item.product_code,
                            'quantity': cart_item.quantity,  # Paid quantity
                            'total_quantity': total_quantity,  # Total including FOC
                            'free_quantity': free_quantity,  # Free quantity
                            'unit_price': pricing['pricing']['final_price'],
                            'total': pricing['pricing']['total_amount']
                        })
            
            # Create pending orders for expired products
            pending_products_created = []
            for expired_item in expired_cart_items:
                product = Product.query.get(expired_item.product_id)
                if product:
                    pending_order = self.db_service.create_pending_order_product(
                        original_order_id=order.order_id,
                        product_code=expired_item.product_code,
                        product_name=product.product_name,
                        requested_quantity=expired_item.quantity,
                        user_id=user.id,
                        user_email=user.email,
                        original_order_item_id=None  # Expired items don't have order items yet
                    )
                    if pending_order:
                        pending_products_created.append(pending_order)
            
            # Generate order summary using valid cart items only (before clearing)
            order_summary = self.llm_service.generate_order_summary(valid_cart_items, user)

            # Clear cart
            self.db_service.clear_cart(user_id)
            
            # For distributor orders: Move stock from blocked to out_for_delivery after order items are created
            # IMPORTANT: Include FOC quantities in stock movement
            # Stock will move from out_for_delivery to sold when delivery partner marks as delivered
            if user.role == 'distributor':
                cart_items_for_movement = []
                # Get order items to include FOC quantities
                order_items_created = OrderItem.query.filter_by(order_id=order.id).all()
                for order_item in order_items_created:
                    # Include both paid and FOC quantities
                    total_quantity = order_item.quantity + (order_item.free_quantity or 0)
                    cart_items_for_movement.append(type('CartLikeItem', (), {
                        'product_code': order_item.product_code,
                        'quantity': total_quantity  # Move paid + FOC quantity
                    })())
                
                if cart_items_for_movement:
                    # Move stock from blocked to out_for_delivery for distributor's own stock
                    self._move_blocked_to_out_for_delivery_for_distributor_order(user, cart_items_for_movement)
                    self.logger.info(f"Moved stock from blocked to out_for_delivery for distributor order {order.order_id} (including FOC quantities)")
            
            # Commit all changes
            db.session.commit()
            
            # Notify distributor (include expired products info) - non-critical, outside transaction
            try:
                self._notify_distributor(order, placed_by_user, expired_products_info)
            except Exception as e:
                self.logger.error(f"Error notifying distributor: {str(e)}")
                # Don't fail the order if notification fails
            
            # Generate enhanced confirmation message (after transaction commits)
            # datetime is already imported at module level
            
            # Get order items details from stored valid_items_details (already calculated)
            # Note: These were calculated inside transaction but are used here
            order_items_details = valid_items_details
            # Total items (including FOC)
            total_items = sum(item['total_quantity'] for item in valid_items_details)
            
            # Format order date
            order_date_str = order.created_at.strftime('%B %d, %Y at %I:%M %p') if order.created_at else datetime.now().strftime('%B %d, %Y at %I:%M %p')
            
            # Build enhanced confirmation message
            status_display = order.status.replace('_', ' ').title()
            stage_display = order.order_stage.replace('_', ' ').title()
            
            # Determine status message based on user type
            if user.role == 'mr':
                status_message = f"Your order has been placed successfully and is currently **Pending** confirmation from the distributor. The distributor will review and confirm your order shortly."
            else:
                # For dealer orders, mention delivery partner notification instead of distributor
                if user.role == 'distributor':
                    status_message = f"Your order is currently in the **{stage_display}** stage with status **{status_display}**. The delivery partner has been notified and will deliver your order shortly."
                else:
                    status_message = f"Your order is currently in the **{stage_display}** stage with status **{status_display}**. The distributor has been notified and will process your order shortly."
            
            confirmation_message = f"""🎉 **Order Placed Successfully!**

**📋 Order Details:**
• **Order ID:** {order.order_id}
• **Order Date:** {order_date_str}
• **Status:** {status_display}
• **Area:** {order.mr.area if order.mr else 'N/A'}
• **Total Items:** {total_items} units

**🛍️ Order Items:**

| Product | Quantity | FOC | Total Qty | Unit Price | Total |
|---------|----------|-----|-----------|------------|-------|
"""
            for item in order_items_details:
                # Show FOC in separate column
                paid_qty = item['quantity']
                free_qty = item['free_quantity']
                total_qty = item['total_quantity']
                confirmation_message += f"| {item['name']} | {paid_qty} | +{free_qty} | **{total_qty}** | {item['unit_price']:,.2f} MMK | {item['total']:,.2f} MMK |\n"
            
            confirmation_message += f"""
**💰 Payment Summary:**
• **Subtotal:** {order.subtotal:,.2f} MMK
• **Tax (5%):** {order.tax_amount:,.2f} MMK
• **Grand Total:** {order.total_amount:,.2f} MMK

**📊 Status:**
• {status_message}

**📧 Email:**
• Confirmation sent to {user.email}
"""
            
            # Add expired/insufficient products notification if any
            if expired_items_details and pending_products_created:
                confirmation_message += """
**⚠️ Important Notice:**
Some products in your order are currently not available:
"""
                for item_detail in expired_items_details:
                    if item_detail['reason'] == 'insufficient_stock':
                        confirmation_message += f"• **{item_detail['product_name']}** ({item_detail['product_code']}) - Requested: {item_detail['quantity']} units, Available: {item_detail['available_qty']} units (insufficient stock)\n"
                    else:
                        confirmation_message += f"• **{item_detail['product_name']}** ({item_detail['product_code']}) - {item_detail['quantity']} units (expired stock)\n"
                
                confirmation_message += f"""
**📦 Auto-Order System:**
These products will be automatically ordered when new stock arrives. Track with Order ID: **{order.order_id}**.
"""
            
            # Order is now in transit and distributor has been notified
            return {
                'success': True,
                'message': confirmation_message,
                'order_id': order.order_id,
                'order_summary': order_summary,
                'next_steps': f"Your order has been sent to the distributor for confirmation. Current status: {order.status.replace('_', ' ').title()} | Stage: {order.order_stage.replace('_', ' ').title()}. You'll receive updates via email."
            }
            
        except Exception as e:
            self.logger.error(f"Error placing order: {str(e)}")
            # Transaction auto-rolls back, but ensure clean state
            try:
                db.session.rollback()
            except Exception:
                pass
            return {
                'success': False,
                'message': f"Error placing order: {str(e)}"
            }
    
    @retry_on_transient_failure()
    def confirm_order_by_distributor(self, order_id, distributor_user_id, item_edits=None, delivery_partner_id=None):
        """
        Confirm order by distributor with optional edits and stock discrepancy handling
        item_edits: dict of {item_id: {'quantity': int, 'expiry_date': date, 'reason': str}}
        delivery_partner_id: ID of delivery partner to assign for delivery
        Wrapped in single transaction for atomicity
        """
        try:
            from app.models import PendingOrderProducts
            from datetime import date
            
            # Lock order for update (requires active transaction)
            from app.db_locking import lock_order_for_update
            order = lock_order_for_update(order_id, nowait=False)
            if not order:
                return {
                    'success': False,
                    'message': "Order not found"
                }
            distributor = User.query.get(distributor_user_id)
            if not distributor or distributor.role != 'distributor':
                return {
                    'success': False,
                    'message': "Invalid distributor"
                }
            # Check if order has MR and area before comparing
            if not order.mr or not order.mr.area:
                return {
                    'success': False,
                    'message': "Order is missing MR information or area."
                }
            if order.mr.area != distributor.area:
                return {
                    'success': False,
                    'message': "This order doesn't belong to your area."
                }
            
            # Get order items
            order_items = OrderItem.query.filter_by(order_id=order.id).all()
            item_edits = item_edits or {}
            
            # Process edits and handle stock discrepancies
            notifications = []
            cart_like_items = []
            
            # Process order items (Flask-SQLAlchemy manages transactions)
            for item in order_items:
                item_id = item.id
                edit_data = item_edits.get(item_id, {})
                
                # Get actual available stock
                from app.models import DealerWiseStockDetails
                dealers_in_area = User.query.filter_by(role='distributor', area=order.mr.area).all()
                dealer_unique_ids = [d.unique_id for d in dealers_in_area] if dealers_in_area else []
                
                # First, try to get blocked stock (stock that was reserved for this order)
                stock_details = DealerWiseStockDetails.query.filter(
                    DealerWiseStockDetails.product_code == item.product_code,
                    DealerWiseStockDetails.status == 'confirmed',
                    DealerWiseStockDetails.dealer_unique_id.in_(dealer_unique_ids),
                    DealerWiseStockDetails.blocked_quantity > 0
                ).all()
                
                total_blocked = sum(s.blocked_quantity for s in stock_details)
                requested_qty = item.quantity
                # CRITICAL: total_blocked includes FOC, but requested_qty is only paid quantity
                # We need to account for FOC when comparing blocked vs requested
                original_foc_qty = item.free_quantity or 0
                total_requested_with_foc = requested_qty + original_foc_qty
                
                # Check if we need more stock (either no blocked stock, or not enough blocked stock)
                # Compare total_blocked with total_requested_with_foc to properly account for FOC
                if total_blocked < total_requested_with_foc:
                    # Need to check for additional available stock
                    shortfall = total_requested_with_foc - total_blocked
                    self.logger.info(f"Blocked stock ({total_blocked}) is less than total requested including FOC ({total_requested_with_foc} = {requested_qty} paid + {original_foc_qty} FOC), checking for {shortfall} more units")
                    
                    available_stock_details = DealerWiseStockDetails.query.filter(
                        DealerWiseStockDetails.product_code == item.product_code,
                        DealerWiseStockDetails.status == 'confirmed',
                        DealerWiseStockDetails.dealer_unique_id.in_(dealer_unique_ids),
                        DealerWiseStockDetails.available_for_sale > 0
                    ).order_by(DealerWiseStockDetails.expiry_date.asc()).all()  # FEFO: earliest expiry first
                    
                    total_available_stock = sum(s.available_for_sale for s in available_stock_details)
                    
                    if total_available_stock > 0:
                        # Block additional stock to meet the requested quantity
                        quantity_to_block = min(shortfall, total_available_stock)
                        remaining_to_block = quantity_to_block
                        
                        self.logger.info(f"Found {total_available_stock} units of available stock, blocking {quantity_to_block} more units for {item.product_code}")
                        
                        for stock_detail in available_stock_details:
                            if remaining_to_block <= 0:
                                break
                            
                            available_in_stock = stock_detail.available_for_sale
                            if available_in_stock <= 0:
                                continue
                            
                            block_amount = min(remaining_to_block, available_in_stock)
                            stock_detail.blocked_quantity += block_amount
                            stock_detail.update_available_quantity()
                            
                            self.logger.info(f"Blocked {block_amount} additional units of {item.product_code} from stock ID {stock_detail.id}")
                            remaining_to_block -= block_amount
                        
                        # Re-query to get all blocked stock (original + newly blocked)
                        stock_details = DealerWiseStockDetails.query.filter(
                            DealerWiseStockDetails.product_code == item.product_code,
                            DealerWiseStockDetails.status == 'confirmed',
                            DealerWiseStockDetails.dealer_unique_id.in_(dealer_unique_ids),
                            DealerWiseStockDetails.blocked_quantity > 0
                        ).all()
                        
                        total_blocked = sum(s.blocked_quantity for s in stock_details)
                        total_available = total_blocked
                        self.logger.info(f"Total blocked stock now: {total_blocked} units for {item.product_code} (requested: {total_requested_with_foc} = {requested_qty} paid + {original_foc_qty} FOC)")
                    else:
                        # No additional available stock, use what we have blocked
                        total_available = total_blocked
                        self.logger.warning(f"No additional available stock found for {item.product_code}, will dispatch only {total_blocked} units")
                else:
                    # We have enough or more blocked stock than total requested (including FOC)
                    total_available = total_blocked
                
                # CRITICAL: Ensure total_available is set correctly
                # Note: total_available may include FOC, but we only dispatch based on paid quantity requested
                if total_available <= 0:
                    self.logger.error(f"No stock available (blocked or available) for {item.product_code}, cannot dispatch")
                    # Still need to set dispatch_qty, but it will be 0
                    dispatch_qty = 0
                    pending_qty = requested_qty
                elif total_available < total_requested_with_foc:
                    # Partial dispatch - dispatch only the paid portion that's available
                    # Calculate how much paid quantity we can dispatch
                    # total_available might include FOC, but we only dispatch paid portion
                    # Remaining paid + FOC goes to pending
                    dispatch_qty = min(total_available, requested_qty)  # Only dispatch paid portion, not more
                    pending_qty = requested_qty - dispatch_qty
                    
                    # Update order item - ensure all fields are properly set
                    item.adjusted_quantity = int(dispatch_qty) if dispatch_qty is not None else None
                    item.pending_quantity = int(pending_qty) if pending_qty is not None else 0
                    adjustment_reason_text = f"Stock discrepancy: Only {dispatch_qty} units available. {pending_qty} units moved to pending orders."
                    item.adjustment_reason = adjustment_reason_text.strip() if adjustment_reason_text else None
                    
                    # Create pending order - ensure all required fields are populated
                    if not item.product_code or not item.product_name:
                        self.logger.error(f"Missing product_code or product_name for item {item.id}")
                        continue
                    
                    if not order.mr_id:
                        self.logger.error(f"Missing mr_id for order {order.order_id}")
                        continue
                    
                    mr_email = order.mr.email if order.mr and order.mr.email else ''
                    if not mr_email:
                        # Try to get email from user object
                        mr_user = User.query.get(order.mr_id)
                        mr_email = mr_user.email if mr_user and mr_user.email else ''
                    
                    if not mr_email:
                        self.logger.warning(f"No email found for MR {order.mr_id}, using placeholder")
                        mr_email = 'no-email@placeholder.com'  # Ensure non-null value
                    
                    # CRITICAL: Preserve original FOC information
                    # When quantity is split due to stock discrepancy, FOC goes with PENDING portion
                    # This ensures FOC is given when the full order (including pending) is complete
                    original_foc_qty = item.free_quantity or 0
                    original_total_qty = requested_qty + original_foc_qty
                    
                    # Remove FOC from dispatched quantity (FOC will go with pending)
                    item.free_quantity = 0  # No FOC for dispatched portion
                    
                    # IMPORTANT: Store original_order_item_id and FOC info to track which item this came from
                    pending_order = PendingOrderProducts(
                        original_order_id=order.order_id or None,
                        original_order_item_id=item.id,  # Link to original OrderItem
                        product_code=str(item.product_code).strip(),
                        product_name=str(item.product_name).strip(),
                        requested_quantity=int(pending_qty),  # Pending quantity (paid)
                        original_foc_quantity=int(original_foc_qty),  # FOC goes with pending order
                        original_total_quantity=original_total_qty,  # Store original total for reference
                        user_id=int(order.mr_id),
                        user_email=str(mr_email).strip(),
                        status='pending'
                    )
                    db.session.add(pending_order)
                    
                    # CRITICAL: Unblock the pending portion (pending_qty + FOC) so it becomes available again
                    # When pending order is fulfilled, it will block again (which is correct)
                    # This prevents double-blocking issue
                    pending_total_qty = pending_qty + original_foc_qty  # Total pending (paid + FOC)
                    if pending_total_qty > 0:
                        try:
                            self._unblock_quantity_for_mr_order(
                                user=order.mr,
                                product_code=item.product_code,
                                quantity=pending_total_qty
                            )
                            self.logger.info(f"Unblocked {pending_total_qty} units ({pending_qty} paid + {original_foc_qty} FOC) for pending order (stock discrepancy) - will be blocked again when pending order is fulfilled")
                        except Exception as unblock_e:
                            self.logger.error(f"Error unblocking pending quantity: {str(unblock_e)}")
                            # Don't fail the entire operation, but log the error
                    
                    # FOC goes with pending portion
                    # User gets: dispatch_qty paid + 0 FOC = total dispatched
                    # Pending: pending_qty paid + original_foc_qty FOC = total when fulfilled
                    notifications.append(f"{item.product_name}: Dispatched {dispatch_qty} units (no FOC). {pending_qty} units + {original_foc_qty} FOC moved to pending orders (will be dispatched when stock arrives).")
                    
                    # Use adjusted quantity for moving to sold
                    # IMPORTANT: Include FOC quantity when moving to sold (both paid and free items come from stock)
                    # CRITICAL: FOC went to pending, so dispatched has 0 FOC
                    # Only add if dispatch_qty > 0
                    if dispatch_qty > 0:
                        # FOC went to pending, so dispatched has 0 FOC
                        dispatched_foc_qty = 0  # FOC went to pending
                        total_quantity_to_move = dispatch_qty + dispatched_foc_qty
                        cart_like_items.append(type('CartLikeItem', (), {
                            'product_code': item.product_code,
                            'quantity': total_quantity_to_move  # Move paid only (FOC went to pending)
                        })())
                        self.logger.info(f"Preparing to move {total_quantity_to_move} units ({dispatch_qty} paid + {dispatched_foc_qty} FOC) of {item.product_code} from blocked to out_for_delivery. FOC ({original_foc_qty}) went to pending order.")
                    else:
                        self.logger.warning(f"Skipping stock movement for item {item.id} (stock discrepancy case) - dispatch_qty is {dispatch_qty}")
                else:
                    # Full dispatch possible - check if dealer adjusted quantity
                    # Get quantity from edits if provided, otherwise use requested
                    if 'quantity' in edit_data and edit_data['quantity'] is not None:
                        edit_qty = edit_data['quantity']
                        # Convert to int and validate
                        if isinstance(edit_qty, (int, float)):
                            edit_qty_int = int(edit_qty)
                            # If edit quantity is 0 or negative, use requested quantity (dealer can't dispatch 0)
                            # If edit quantity is positive, use it (dealer may have reduced quantity)
                            dispatch_qty = edit_qty_int if edit_qty_int > 0 else requested_qty
                        else:
                            # Invalid type, use requested quantity
                            dispatch_qty = requested_qty
                    else:
                        # No quantity in edits, use requested quantity from database
                        dispatch_qty = requested_qty
                    
                    # CRITICAL: Ensure dispatch_qty is never 0 or None when stock is available
                    if dispatch_qty <= 0:
                        self.logger.warning(f"dispatch_qty is {dispatch_qty} for item {item.id}, using requested_qty {requested_qty} instead")
                        dispatch_qty = requested_qty
                    
                    # Always save adjusted_quantity when dealer confirms (even if same as requested)
                    # This ensures we track what was actually dispatched
                    item.adjusted_quantity = int(dispatch_qty) if dispatch_qty is not None else None
                    
                    # CRITICAL: Preserve original FOC - when dealer adjusts due to stock shortage,
                    # FOC should go with the PENDING portion, not the dispatched portion
                    # This ensures FOC is given when the full order is complete
                    # Example: Order 10 → Get 1 FOC. If dealer adjusts to 8, FOC (1) goes with pending (2)
                    original_foc_qty = item.free_quantity or 0  # Original FOC from order
                    original_total_qty = requested_qty + original_foc_qty  # Original total (paid + FOC)
                    
                    # Handle quantity adjustment by dealer
                    if dispatch_qty != requested_qty:
                        if dispatch_qty < requested_qty:
                            # Dealer reduced quantity - move difference to pending
                            pending_qty = requested_qty - dispatch_qty
                            item.pending_quantity = int(pending_qty) if pending_qty is not None else 0
                            
                            # CRITICAL: When quantity is split due to stock shortage, FOC goes with PENDING portion
                            # Strategy: Dispatched gets NO FOC, pending gets the original FOC
                            # This ensures FOC is given when the full order (including pending) is complete
                            # Example: Order 10 + 1 FOC. Dispatched 8 (no FOC), Pending 2 + 1 FOC = 3 total
                            
                            # Remove FOC from dispatched quantity (FOC will go with pending)
                            item.free_quantity = 0  # No FOC for dispatched portion
                            
                            # Get reason from edits or use default
                            reason = edit_data.get('reason', f'Quantity adjusted: {dispatch_qty} units dispatched, {pending_qty} units moved to pending orders')
                            item.adjustment_reason = str(reason).strip() if reason else None
                            
                            # Create pending order - ensure all required fields are populated
                            if not item.product_code or not item.product_name:
                                self.logger.error(f"Missing product_code or product_name for item {item.id}")
                                continue
                            
                            if not order.mr_id:
                                self.logger.error(f"Missing mr_id for order {order.order_id}")
                                continue
                            
                            mr_email = order.mr.email if order.mr and order.mr.email else ''
                            if not mr_email:
                                # Try to get email from user object
                                mr_user = User.query.get(order.mr_id)
                                mr_email = mr_user.email if mr_user and mr_user.email else ''
                            
                            if not mr_email:
                                self.logger.warning(f"No email found for MR {order.mr_id}, using placeholder")
                                mr_email = 'no-email@placeholder.com'  # Ensure non-null value
                            
                            # IMPORTANT: Store original FOC with pending order
                            # Pending order gets the FOC (it will be dispatched when stock arrives)
                            # This ensures FOC is given when the full order is complete
                            pending_order = PendingOrderProducts(
                                original_order_id=order.order_id or None,
                                original_order_item_id=item.id,  # Link to original OrderItem
                                product_code=str(item.product_code).strip(),
                                product_name=str(item.product_name).strip(),
                                requested_quantity=int(pending_qty),  # Pending quantity (paid)
                                original_foc_quantity=int(original_foc_qty),  # FOC goes with pending order
                                original_total_quantity=original_total_qty,  # Store original total for reference
                                user_id=int(order.mr_id),
                                user_email=str(mr_email).strip(),
                                status='pending'
                            )
                            db.session.add(pending_order)
                            
                            # CRITICAL: Unblock the pending portion (pending_qty + FOC) so it becomes available again
                            # When pending order is fulfilled, it will block again (which is correct)
                            # This prevents double-blocking issue
                            pending_total_qty = pending_qty + original_foc_qty  # Total pending (paid + FOC)
                            if pending_total_qty > 0:
                                try:
                                    self._unblock_quantity_for_mr_order(
                                        user=order.mr,
                                        product_code=item.product_code,
                                        quantity=pending_total_qty
                                    )
                                    self.logger.info(f"Unblocked {pending_total_qty} units ({pending_qty} paid + {original_foc_qty} FOC) for pending order - will be blocked again when pending order is fulfilled")
                                except Exception as unblock_e:
                                    self.logger.error(f"Error unblocking pending quantity: {str(unblock_e)}")
                                    # Don't fail the entire operation, but log the error
                            
                            # FOC goes with pending portion
                            # User gets: 8 paid + 0 FOC = 8 total dispatched
                            # Pending: 2 paid + 1 FOC = 3 total when fulfilled
                            # Total: 8 + 3 = 11 (matching original 10 paid + 1 FOC)
                            self.logger.info(f"FOC allocation: Original order {requested_qty} paid + {original_foc_qty} FOC. Dispatched {dispatch_qty} gets 0 FOC. Pending {pending_qty} gets {original_foc_qty} FOC (will be dispatched when stock arrives).")
                            notifications.append(f"{item.product_name}: Dispatched {dispatch_qty} units (no FOC). {pending_qty} units + {original_foc_qty} FOC moved to pending orders (will be dispatched when stock arrives).")
                        else:
                            # Dealer increased quantity - not allowed, use original
                            dispatch_qty = requested_qty
                            item.adjusted_quantity = int(requested_qty) if requested_qty is not None else None  # Reset to original
                            notifications.append(f"{item.product_name}: Cannot increase quantity above ordered amount. Using original quantity {requested_qty}.")
                    else:
                        # Quantity unchanged, but still save it as adjusted_quantity
                        # Check if reason provided for notification
                        if 'reason' in edit_data and edit_data['reason']:
                            item.adjustment_reason = edit_data['reason']
                        # If no edits were made, adjusted_quantity is already set to dispatch_qty (which equals requested_qty)
                    
                    # Update expiry date if edited - ensure valid date
                    if 'expiry_date' in edit_data and edit_data['expiry_date']:
                        try:
                            # datetime is already imported at module level
                            if isinstance(edit_data['expiry_date'], str) and edit_data['expiry_date'].strip():
                                item.adjusted_expiry_date = datetime.strptime(edit_data['expiry_date'].strip(), '%Y-%m-%d').date()
                                self.logger.info(f"Updated expiry date for item {item.id}: {item.adjusted_expiry_date}")
                            elif hasattr(edit_data['expiry_date'], 'date'):  # Already a date object
                                item.adjusted_expiry_date = edit_data['expiry_date']
                                self.logger.info(f"Updated expiry date for item {item.id}: {item.adjusted_expiry_date}")
                            else:
                                self.logger.warning(f"Invalid expiry_date format for item {item.id}: {edit_data['expiry_date']}")
                        except (ValueError, TypeError) as e:
                            self.logger.error(f"Error parsing expiry date for item {item.id}: {str(e)}")
                            # Don't set invalid date, leave as None
                    
                    # Update lot number if edited (save to dedicated field) - ensure non-empty string
                    if 'lot_number' in edit_data and edit_data['lot_number']:
                        lot_number = str(edit_data['lot_number']).strip()
                        if lot_number:  # Only set if not empty after stripping
                            item.adjusted_lot_number = lot_number
                            self.logger.info(f"Updated lot number for item {item.id}: {item.adjusted_lot_number}")
                            # Also add to adjustment_reason if not already there
                            if item.adjustment_reason and 'lot number' not in item.adjustment_reason.lower():
                                item.adjustment_reason = f"{item.adjustment_reason}. Lot Number: {item.adjusted_lot_number}"
                            elif not item.adjustment_reason:
                                item.adjustment_reason = f"Lot Number: {item.adjusted_lot_number}"
                        else:
                            self.logger.warning(f"Empty lot_number provided for item {item.id}, skipping")
                    
                    # Ensure adjustment_reason is not empty string if set
                    if item.adjustment_reason and not str(item.adjustment_reason).strip():
                        item.adjustment_reason = None
                    
                    # Only add to cart_like_items if dispatch_qty > 0 (we have something to dispatch)
                    if dispatch_qty > 0:
                        # IMPORTANT: Include FOC quantity in stock movement
                        # CRITICAL: When quantity is unchanged, FOC stays with dispatched
                        # When quantity is adjusted, FOC goes to pending (handled above)
                        dispatched_foc_qty = item.free_quantity or 0  # FOC for dispatched
                        total_quantity_to_move = dispatch_qty + dispatched_foc_qty
                        cart_like_items.append(type('CartLikeItem', (), {
                            'product_code': item.product_code,
                            'quantity': total_quantity_to_move  # Move paid + FOC
                        })())
                        self.logger.info(f"Preparing to move {total_quantity_to_move} units ({dispatch_qty} paid + {dispatched_foc_qty} FOC) of {item.product_code} from blocked to out_for_delivery")
                    else:
                        self.logger.warning(f"Skipping stock movement for item {item.id} - dispatch_qty is {dispatch_qty}")
                
            # Validate delivery partner FIRST before making any changes (mandatory for new flow)
            if not delivery_partner_id:
                return {
                    'success': False,
                    'message': 'Delivery partner selection is required to confirm the order. Please select a delivery partner.'
                }
            
            delivery_partner = User.query.get(delivery_partner_id)
            if not delivery_partner or delivery_partner.role != 'delivery_partner':
                return {
                    'success': False,
                    'message': 'Invalid delivery partner selected. Please select a valid delivery partner.'
                }
            
            # Verify delivery partner is in the same area as distributor/MR
            if order.mr and order.mr.area and delivery_partner.area and delivery_partner.area != order.mr.area:
                self.logger.warning(f"Delivery partner {delivery_partner.unique_id} area {delivery_partner.area} doesn't match order area {order.mr.area}")
                # Still allow assignment but log warning
            
            # Now update order status with validation (after delivery partner validation passes)
            current_status = order.status
            if current_status not in ORDER_STATUS_TRANSITIONS:
                self.logger.warning(f"Order {order.order_id} has invalid status '{current_status}', allowing transition to 'confirmed'")
            elif 'confirmed' not in ORDER_STATUS_TRANSITIONS.get(current_status, []):
                self.logger.warning(f"Invalid status transition from '{current_status}' to 'confirmed' for order {order.order_id}")
                # Allow transition anyway but log warning
            
            # Update order fields
            order.distributor_confirmed_at = datetime.utcnow()
            order.distributor_confirmed_by = distributor_user_id
            order.status = 'confirmed'
            order.order_stage = 'confirmed'
            order.delivery_partner_id = delivery_partner_id
            order.delivery_partner_unique_id = delivery_partner.unique_id
            self.logger.info(f"Order {order_id} assigned to delivery partner {delivery_partner.unique_id}")
            
            # Move blocked quantities to out_for_delivery (not sold yet - will be sold when delivery partner marks as delivered)
            if order.mr and order.mr.area and cart_like_items:
                self._move_blocked_to_out_for_delivery_for_mr_order(order.mr, cart_like_items)
            
            # Commit all changes
            db.session.commit()
            
            # NOTE: Notification service removed - notifications tables have been dropped
            # Order approval notifications are now handled via email only
            
            # Include notifications in response if there are stock discrepancies
            result_message = f"Order {order_id} confirmed and invoice generated"
            if notifications:
                result_message += "\n\n⚠️ Stock Discrepancies:\n" + "\n".join(f"• {n}" for n in notifications)
            
            # Generate invoice (for records only - not stored in Order model)
            invoice_number = self._generate_invoice(order)
            
            # Send notification email to delivery partner if assigned
            if order.delivery_partner_id:
                try:
                    delivery_partner = User.query.get(order.delivery_partner_id)
                    if delivery_partner and delivery_partner.email:
                        self._send_delivery_assignment_email(order, delivery_partner)
                except Exception as email_e:
                    self.logger.error(f"Error sending delivery assignment email: {str(email_e)}")

            # Send enhanced confirmation email to MR or customer
            mr = User.query.get(order.mr_id)
            
            # Get admin email safely (check for Flask application context)
            admin_email = None
            try:
                from flask import has_app_context
                if has_app_context():
                    admin_email = current_app.config.get('ADMIN_EMAIL')
            except (RuntimeError, AttributeError):
                pass
            
            order_items_list = OrderItem.query.filter_by(order_id=order.id).all()
            
            # Build items table with FOC - show adjusted quantities if available
            table = """<table style='border-collapse:collapse; width:100%; margin:20px 0;'>
                <thead><tr style='background:#3b82f6; color:white;'>
                    <th style='padding:12px; text-align:left;'>Product</th>
                    <th style='padding:12px; text-align:center;'>Qty</th>
                    <th style='padding:12px; text-align:center;'>FOC</th>
                    <th style='padding:12px; text-align:right;'>Unit Price</th>
                    <th style='padding:12px; text-align:right;'>Total</th>
                </tr></thead><tbody>"""
            
            # Recalculate totals based on adjusted quantities
            recalculated_subtotal = 0.0
            for item in order_items_list:
                # Use adjusted quantity if available, otherwise use original
                # IMPORTANT: Only paid quantity is used for pricing (FOC is free, not charged)
                quantity = item.adjusted_quantity if item.adjusted_quantity is not None else (item.quantity or 0)
                foc_qty = item.free_quantity or 0
                foc_display = f"<strong>+{foc_qty}</strong>" if foc_qty > 0 else "-"
                
                # Calculate total based on adjusted quantity (only paid quantity, FOC is free)
                unit_price = item.unit_price or 0.0
                item_total = quantity * unit_price  # Only charge for paid quantity, FOC is free
                recalculated_subtotal += item_total
                
                # Show original quantity if different from adjusted
                qty_display = str(quantity)
                if item.adjusted_quantity is not None and item.adjusted_quantity != item.quantity:
                    qty_display = f"{quantity} <small style='color:#856404;'>(was {item.quantity})</small>"
                
                table += f"""<tr style='border-bottom:1px solid #e5e7eb;'>
                    <td style='padding:10px;'>{item.product.product_name} ({item.product_code})</td>
                    <td style='padding:10px; text-align:center;'>{qty_display}</td>
                    <td style='padding:10px; text-align:center; color:#10b981;'>{foc_display}</td>
                    <td style='padding:10px; text-align:right;'>{unit_price:,.2f} MMK</td>
                    <td style='padding:10px; text-align:right;'>{item_total:,.2f} MMK</td>
                </tr>"""
            table += "</tbody></table>"
            
            # Tax information - recalculate based on adjusted quantities
            tax_html = ""
            # Recalculate tax based on adjusted quantities
            tax_rate = 0.05  # Default tax rate
            try:
                from flask import has_app_context
                if has_app_context():
                    tax_rate = current_app.config.get('TAX_RATE', 0.05)  # Get from config, default 5%
            except (RuntimeError, AttributeError):
                pass
            recalculated_tax = recalculated_subtotal * tax_rate
            recalculated_grand_total = recalculated_subtotal + recalculated_tax
            
            # Check if totals need to be updated (if quantities were adjusted)
            has_quantity_adjustments = any(
                item.adjusted_quantity is not None and item.adjusted_quantity != item.quantity 
                for item in order_items_list
            )
            
            # IMPORTANT: Update order totals in database if quantities were adjusted
            if has_quantity_adjustments:
                # Update order record with recalculated totals
                order.subtotal = recalculated_subtotal
                order.tax_amount = recalculated_tax
                order.total_amount = recalculated_grand_total
                order.updated_at = datetime.utcnow()
                # Commit the order total updates
                db.session.flush()  # Flush to ensure totals are saved
                self.logger.info(f"Updated order {order.order_id} totals: subtotal={recalculated_subtotal:.2f}, tax={recalculated_tax:.2f}, total={recalculated_grand_total:.2f}")
            
            if hasattr(order, 'subtotal') and order.subtotal:
                # Show recalculated totals if quantities were adjusted
                if has_quantity_adjustments:
                    tax_html = f"""
                    <div class='success-box'>
                        <h3 style='margin-top: 0; color: #059669;'>💰 Payment Summary</h3>
                            <p style='margin: 5px 0;'><strong>Subtotal:</strong> {recalculated_subtotal:,.2f} MMK <small style='color:#856404;'>(adjusted from {order.subtotal:,.2f} MMK)</small></p>
                            <p style='margin: 5px 0;'><strong>Tax (5%):</strong> {recalculated_tax:,.2f} MMK</p>
                            <p style='margin: 5px 0; font-size: 1.2em;'><strong>Grand Total:</strong> {recalculated_grand_total:,.2f} MMK</p>
                    </div>
                """
                else:
                    tax_html = f"""
                        <div class='success-box'>
                            <h3 style='margin-top: 0; color: #059669;'>💰 Payment Summary</h3>
                            <p style='margin: 5px 0;'><strong>Subtotal:</strong> {order.subtotal:,.2f} MMK</p>
                            <p style='margin: 5px 0;'><strong>Tax (5%):</strong> {order.tax_amount:,.2f} MMK</p>
                            <p style='margin: 5px 0; font-size: 1.2em;'><strong>Grand Total:</strong> {order.total_amount:,.2f} MMK</p>
                        </div>
                    """
            else:
                if has_quantity_adjustments:
                    tax_html = f"<p style='font-size:1.2em;'><strong>Total Amount:</strong> {recalculated_grand_total:,.2f} MMK <small style='color:#856404;'>(adjusted)</small></p>"
                else:
                    tax_html = f"<p style='font-size:1.2em;'><strong>Total Amount:</strong> {order.total_amount:,.2f} MMK</p>"
            
            # Build adjustments section if any items were adjusted
            # Only show items with actual adjustments: quantity change, expiry change, or reason (excluding lot-only reasons)
            adjustments_html = ""
            adjusted_items = []
            
            for item in order_items_list:
                has_actual_adjustment = False
                adjustment_details = []
                
                # Check for quantity adjustment
                if item.adjusted_quantity is not None and item.adjusted_quantity != item.quantity:
                    has_actual_adjustment = True
                    adjustment_details.append({
                        'type': 'quantity',
                        'value': f"{item.quantity} → {item.adjusted_quantity} units",
                        'pending': item.pending_quantity if item.pending_quantity and item.pending_quantity > 0 else None
                    })
                
                # Check for lot number adjustment (separate field)
                # Only show lot number if there's a quantity change or other meaningful adjustment
                if item.adjusted_lot_number and (
                    (item.adjusted_quantity is not None and item.adjusted_quantity != item.quantity) or
                    (item.adjustment_reason and 'lot number' not in item.adjustment_reason.lower())
                ):
                    adjustment_details.append({
                        'type': 'lot_number',
                        'value': item.adjusted_lot_number
                    })
                    if not has_actual_adjustment:
                        has_actual_adjustment = True
                
                # Check for expiry date adjustment (only show if quantity was also changed)
                # Expiry date is always set from database, so only show as adjustment if quantity changed
                if item.adjusted_expiry_date and (item.adjusted_quantity is not None and item.adjusted_quantity != item.quantity):
                    adjustment_details.append({
                        'type': 'expiry',
                        'value': item.adjusted_expiry_date.strftime('%Y-%m-%d')
                    })
                
                # Check for reason (but exclude if it's only lot number)
                if item.adjustment_reason:
                    # Check if reason contains more than just lot number
                    reason_lower = item.adjustment_reason.lower().strip()
                    # Check if it's only a lot number (various formats)
                    is_only_lot = (
                        reason_lower.startswith('lot number:') or 
                        reason_lower.startswith('lot:') or
                        reason_lower == 'lot number' or
                        (reason_lower.startswith('lot number: lot:') and len(reason_lower.split(':')) <= 3)
                    )
                    
                    # Only include reason if:
                    # 1. It's not just a lot number, OR
                    # 2. There's a quantity change (in which case show the full reason including lot)
                    if not is_only_lot:
                        # It's a meaningful reason (not just lot number)
                        adjustment_details.append({
                            'type': 'reason',
                            'value': item.adjustment_reason
                        })
                        if not has_actual_adjustment:
                            has_actual_adjustment = True
                    elif item.adjusted_quantity is not None and item.adjusted_quantity != item.quantity:
                        # Quantity was changed, so include the reason even if it contains lot number
                        adjustment_details.append({
                            'type': 'reason',
                            'value': item.adjustment_reason
                        })
                
                if has_actual_adjustment:
                    adjusted_items.append({
                        'item': item,
                        'details': adjustment_details
                    })
            
            if adjusted_items:
                adjustments_html = """
                    <div class='warning-box' style='background-color:#fff3cd; border-left:4px solid #ffc107; padding:15px; margin:20px 0; border-radius:5px;'>
                        <h3 style='margin-top: 0; color: #856404;'>⚠️ Order Adjustments</h3>
                        <p style='margin: 5px 0; color: #856404;'>The following adjustments were made to your order:</p>
                        <ul style='margin: 10px 0; padding-left: 20px;'>
                """
                for adj_item in adjusted_items:
                    item = adj_item['item']
                    details = adj_item['details']
                    adj_info = f"<li style='margin: 8px 0;'><strong>{item.product_name}:</strong><br>"
                    
                    for detail in details:
                        if detail['type'] == 'quantity':
                            adj_info += f"• Quantity: {detail['value']}"
                            if detail['pending']:
                                # Get FOC information for pending order
                                pending_foc = 0
                                if item.pending_quantity:
                                    # Try to find pending order to get FOC
                                    from app.models import PendingOrderProducts
                                    pending_order = PendingOrderProducts.query.filter_by(
                                        original_order_item_id=item.id,
                                        status='pending'
                                    ).first()
                                    if pending_order:
                                        pending_foc = pending_order.original_foc_quantity or 0
                                
                                if pending_foc > 0:
                                    adj_info += f" ({detail['pending']} units + {pending_foc} FOC moved to pending orders)"
                                else:
                                    adj_info += f" ({detail['pending']} units moved to pending orders)"
                                adj_info += "<br>"
                        elif detail['type'] == 'expiry':
                            adj_info += f"• Expiry Date: {detail['value']}<br>"
                        elif detail['type'] == 'lot_number':
                            adj_info += f"• Lot Number: {detail['value']}<br>"
                        elif detail['type'] == 'reason':
                            # Filter out lot number from reason if it's already shown separately
                            reason_text = detail['value']
                            if item.adjusted_lot_number and f"Lot Number: {item.adjusted_lot_number}" in reason_text:
                                reason_text = reason_text.replace(f"Lot Number: {item.adjusted_lot_number}", "").strip()
                                reason_text = reason_text.rstrip('.').strip()
                            if reason_text:
                                adj_info += f"• Reason: {reason_text}<br>"
                    
                    adj_info += "</li>"
                    adjustments_html += adj_info
                
                adjustments_html += """
                        </ul>
                        <p style='margin: 10px 0 0 0; color: #856404; font-size: 0.9em;'>
                            <strong>Note:</strong> If any items were moved to pending orders, they will be automatically processed when new stock arrives.
                        </p>
                    </div>
                """
            
            content = f"""
                <h2 style='color:#059669; margin-top:0;'>✅ Order Confirmed!</h2>
                <p>Dear <strong>{mr.name}</strong>,</p>
                <p>Great news! Your order <strong>{order.order_id}</strong> has been confirmed by distributor <strong>{distributor.name}</strong>.</p>
                
                <div class='info-box'>
                    <h3 style='margin-top: 0;'>📋 Order Information</h3>
                    <p style='margin: 5px 0;'><strong>Order ID:</strong> {order.order_id}</p>
                    <p style='margin: 5px 0;'><strong>Date:</strong> {order.created_at.strftime('%B %d, %Y at %I:%M %p')}</p>
                    <p style='margin: 5px 0;'><strong>Area:</strong> {order.mr.area if order.mr else 'N/A'}</p>
                    <p style='margin: 5px 0;'><strong>Status:</strong> <span style='color:#059669; font-weight:bold;'>Confirmed</span></p>
                    <p style='margin: 5px 0;'><strong>Invoice:</strong> {invoice_number}</p>
                </div>
                
                {adjustments_html}
                
                <h3>🛍️ Order Items</h3>
                {table}
                
                {tax_html}
                
                <div class='info-box'>
                    <h3 style='margin-top: 0;'>Distributor Contact</h3>
                    <p style='margin: 5px 0;'><strong>Name:</strong> {distributor.name}</p>
                    <p style='margin: 5px 0;'><strong>Email:</strong> {distributor.email}</p>
                    <p style='margin: 5px 0;'><strong>Phone:</strong> {distributor.phone}</p>
                </div>
                
                <p style='margin-top: 20px;'>If you have any questions, please contact your distributor directly or reply to this email.</p>
            """
            
            from app.email_utils import create_email_template
            email_html = create_email_template(
                title="Order Confirmed",
                content=content,
                footer_text="Thank you for choosing Quantum Blue!"
            )
            
            if mr:
                send_email(
                    mr.email, 
                    f"✅ Your order {order.order_id} has been confirmed!", 
                    email_html, 
                    'order_confirmed_customer',
                    order_id=order.order_id,
                    receiver_name=mr.name
                )
            send_email(
                distributor.email, 
                f"Order {order.order_id} confirmed for fulfillment", 
                email_html, 
                'order_confirmed_distributor',
                order_id=order.order_id,
                receiver_name=distributor.name
            )
            if admin_email:
                send_email(
                    admin_email, 
                    f"[Admin] Order {order.order_id} confirmed", 
                    email_html, 
                    'order_confirmed_admin',
                    order_id=order.order_id,
                    receiver_name='Admin'
                )

            return {
                'success': True,
                'message': result_message,
                'invoice_number': invoice_number,
                'notifications': notifications
            }
        except Exception as e:
            self.logger.error(f"Error confirming order: {str(e)}")
            # Transaction auto-rolls back, but ensure clean state
            try:
                db.session.rollback()
            except Exception:
                pass
            return {
                'success': False,
                'message': f"Error confirming order: {str(e)}"
            }
    
    @retry_on_transient_failure()
    def cancel_order_by_mr(self, order_id, mr_user_id):
        """
        Cancel order by MR - unblock stock and update order status
        Wrapped in single transaction for atomicity
        """
        try:
            # Lock order for update (requires active transaction)
            from app.db_locking import lock_order_for_update
            order = lock_order_for_update(order_id, nowait=False)
            if not order:
                return {
                    'success': False,
                    'message': "Order not found"
                }
            
            mr = User.query.get(mr_user_id)
            if not mr or mr.role != 'mr':
                return {
                    'success': False,
                    'message': "Only MRs can cancel their own orders"
                }
            
            if order.mr_id != mr_user_id:
                return {
                    'success': False,
                    'message': "You can only cancel your own orders"
                }
            
            # Check if order can be cancelled (only pending orders)
            if order.status not in ['pending', 'draft']:
                return {
                    'success': False,
                    'message': f"Cannot cancel order. Order status is '{order.status}'. Only pending orders can be cancelled."
                }
            
            # Unblock quantities (Flask-SQLAlchemy manages transactions)
            order_items = OrderItem.query.filter_by(order_id=order.id).all()
            
            # Find dealers in MR's area
            dealers_in_area = User.query.filter_by(
                role='distributor',
                area=order.mr.area
            ).all()
            
            dealer_unique_ids = [d.unique_id for d in dealers_in_area] if dealers_in_area else []
            
            for item in order_items:
                # Get stock details with blocked quantity
                from sqlalchemy import case
                stock_details = DealerWiseStockDetails.query.filter(
                    DealerWiseStockDetails.product_code == item.product_code,
                    DealerWiseStockDetails.dealer_unique_id.in_(dealer_unique_ids),
                    DealerWiseStockDetails.blocked_quantity > 0
                ).order_by(
                    case(
                        (DealerWiseStockDetails.expiry_date.is_(None), 1),
                        else_=0
                    ),
                    DealerWiseStockDetails.expiry_date.asc()
                ).all()
                
                remaining_to_unblock = item.quantity
                
                # Unblock using FEFO
                for stock_detail in stock_details:
                    if remaining_to_unblock <= 0:
                        break
                    
                    blocked_in_this_stock = stock_detail.blocked_quantity
                    if blocked_in_this_stock <= 0:
                        continue
                    
                    quantity_to_unblock = min(remaining_to_unblock, blocked_in_this_stock)
                    
                    # Move from blocked back to available
                    stock_detail.blocked_quantity -= quantity_to_unblock
                    stock_detail.update_available_quantity()
                    
                    self.logger.info(
                        f"Unblocked {quantity_to_unblock} units of {item.product_code} "
                        f"(Stock ID: {stock_detail.id}, Available now: {stock_detail.available_for_sale})"
                    )
                    
                    remaining_to_unblock -= quantity_to_unblock
            
            # Update order status
            order.status = 'cancelled'
            order.order_stage = 'cancelled'
            
            # Commit all changes
            db.session.commit()
            
            # Send email notifications
            try:
                from app.email_utils import create_email_template, send_email
                
                # Prepare order items list for email
                items_html = ""
                total_amount = 0
                for item in order_items:
                    item_total = (item.quantity + (item.free_quantity or 0)) * item.unit_price
                    total_amount += item_total
                    foc_text = f" + {item.free_quantity} FREE" if item.free_quantity and item.free_quantity > 0 else ""
                    items_html += f"""
                        <tr>
                            <td style="padding: 10px; border-bottom: 1px solid #dee2e6;">
                                <strong>{item.product_name}</strong>
                            </td>
                            <td style="padding: 10px; border-bottom: 1px solid #dee2e6; text-align: center;">
                                {item.quantity}{foc_text}
                            </td>
                            <td style="padding: 10px; border-bottom: 1px solid #dee2e6; text-align: right;">
                                {item.unit_price:,.2f} MMK
                            </td>
                            <td style="padding: 10px; border-bottom: 1px solid #dee2e6; text-align: right;">
                                {item_total:,.2f} MMK
                            </td>
                        </tr>
                    """
                
                # Email to MR (Customer)
                mr_content = f"""
                    <h2 style='color:#ff9800; margin-top:0;'>⚠️ Order Cancelled</h2>
                    <p>Dear <strong>{mr.name}</strong>,</p>
                    <p>Your order <strong>{order.order_id}</strong> has been successfully cancelled.</p>
                    
                    <div class='info-box'>
                        <h3 style='margin-top: 0;'>Cancellation Details</h3>
                        <p style='margin: 5px 0;'><strong>Order ID:</strong> {order.order_id}</p>
                        <p style='margin: 5px 0;'><strong>Order Date:</strong> {order.created_at.strftime('%B %d, %Y at %I:%M %p') if order.created_at else 'N/A'}</p>
                        <p style='margin: 5px 0;'><strong>Cancellation Date:</strong> {datetime.utcnow().strftime('%B %d, %Y at %I:%M %p')}</p>
                    </div>
                    
                    <div class='info-box'>
                        <h3 style='margin-top: 0;'>Order Items</h3>
                        <table style='width: 100%; border-collapse: collapse; margin-top: 10px;'>
                            <thead>
                                <tr style='background-color: #f8f9fa;'>
                                    <th style='padding: 10px; text-align: left; border-bottom: 2px solid #dee2e6;'>Product Name</th>
                                    <th style='padding: 10px; text-align: center; border-bottom: 2px solid #dee2e6;'>Quantity</th>
                                    <th style='padding: 10px; text-align: center; border-bottom: 2px solid #dee2e6;'>FOC</th>
                                    <th style='padding: 10px; text-align: center; border-bottom: 2px solid #dee2e6;'>Total Qty</th>
                                    <th style='padding: 10px; text-align: right; border-bottom: 2px solid #dee2e6;'>Unit Price</th>
                                    <th style='padding: 10px; text-align: right; border-bottom: 2px solid #dee2e6;'>Total</th>
                                </tr>
                            </thead>
                            <tbody>
                                {items_html}
                            </tbody>
                            <tfoot>
                                <tr style='background-color: #f8f9fa; font-weight: bold;'>
                                    <td colspan='5' style='padding: 10px; text-align: right; border-top: 2px solid #dee2e6;'>Total Amount:</td>
                                    <td style='padding: 10px; text-align: right; border-top: 2px solid #dee2e6;'>{total_amount:,.2f} MMK</td>
                                </tr>
                            </tfoot>
                        </table>
                    </div>
                    
                    <p style='margin-top: 20px;'>The stock that was blocked for this order has been released and is now available for other orders.</p>
                    <p>You can place a new order anytime through the chatbot.</p>
                """
                
                mr_email_html = create_email_template(
                    title="Order Cancelled",
                    content=mr_content,
                    footer_text="If you have any questions, please contact your distributor or reply to this email."
                )
                
                send_email(
                    mr.email,
                    f"⚠️ Order {order.order_id} - Cancelled",
                    mr_email_html,
                    'order_cancelled_customer',
                    order_id=order.order_id,
                    receiver_name=mr.name
                )
                
                # Email to all distributors in the area
                for distributor in dealers_in_area:
                    distributor_content = f"""
                        <h2 style='color:#ff9800; margin-top:0;'>⚠️ Order Cancellation Notification</h2>
                        <p>Dear <strong>{distributor.name}</strong>,</p>
                        <p>This is to inform you that order <strong>{order.order_id}</strong> placed by MR <strong>{mr.name}</strong> has been cancelled.</p>
                        
                        <div class='info-box'>
                            <h3 style='margin-top: 0;'>Order Details</h3>
                            <p style='margin: 5px 0;'><strong>Order ID:</strong> {order.order_id}</p>
                            <p style='margin: 5px 0;'><strong>MR Name:</strong> {mr.name}</p>
                            <p style='margin: 5px 0;'><strong>MR Email:</strong> <a href='mailto:{mr.email}'>{mr.email}</a></p>
                            <p style='margin: 5px 0;'><strong>Area:</strong> {order.mr.area if order.mr else 'N/A'}</p>
                            <p style='margin: 5px 0;'><strong>Order Date:</strong> {order.created_at.strftime('%B %d, %Y at %I:%M %p') if order.created_at else 'N/A'}</p>
                            <p style='margin: 5px 0;'><strong>Cancellation Date:</strong> {datetime.utcnow().strftime('%B %d, %Y at %I:%M %p')}</p>
                        </div>
                        
                        <div class='info-box'>
                            <h3 style='margin-top: 0;'>Order Items</h3>
                            <table style='width: 100%; border-collapse: collapse; margin-top: 10px;'>
                                <thead>
                                    <tr style='background-color: #f8f9fa;'>
                                        <th style='padding: 10px; text-align: left; border-bottom: 2px solid #dee2e6;'>Product Name</th>
                                        <th style='padding: 10px; text-align: center; border-bottom: 2px solid #dee2e6;'>Quantity</th>
                                        <th style='padding: 10px; text-align: right; border-bottom: 2px solid #dee2e6;'>Unit Price</th>
                                        <th style='padding: 10px; text-align: right; border-bottom: 2px solid #dee2e6;'>Total</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {items_html}
                                </tbody>
                                <tfoot>
                                    <tr style='background-color: #f8f9fa; font-weight: bold;'>
                                        <td colspan='3' style='padding: 10px; text-align: right; border-top: 2px solid #dee2e6;'>Total Amount:</td>
                                        <td style='padding: 10px; text-align: right; border-top: 2px solid #dee2e6;'>{total_amount:,.2f} MMK</td>
                                    </tr>
                                </tfoot>
                            </table>
                        </div>
                        
                        <div class='warning-box'>
                            <h3 style='margin-top: 0;'>Stock Status</h3>
                            <p style='margin: 5px 0;'>The stock that was blocked for this order has been automatically released and is now available for other orders.</p>
                        </div>
                    """
                    
                    distributor_email_html = create_email_template(
                        title="Order Cancellation Notification",
                        content=distributor_content,
                        footer_text="This is an automated notification. Please check your inventory management system for updated stock levels."
                    )
                    
                    send_email(
                        distributor.email,
                        f"⚠️ Order {order.order_id} Cancelled by MR {mr.name}",
                        distributor_email_html,
                        'order_cancelled_distributor',
                        order_id=order.order_id,
                        receiver_name=distributor.name
                    )
                
                self.logger.info(f"Order cancellation emails sent for order {order.order_id}")
            except Exception as email_e:
                self.logger.error(f"Error sending cancellation emails: {str(email_e)}")
                # Don't fail the cancellation if email fails
            
            return {
                'success': True,
                'message': f"Order {order_id} has been cancelled successfully.",
                'action_buttons': [
                    {'text': 'View All Orders', 'action': 'track_order'},
                    {'text': 'Back to Home', 'action': 'home'}
                ]
            }
            
        except Exception as e:
            self.logger.error(f"Error cancelling order: {str(e)}")
            db.session.rollback()
            return {
                'success': False,
                'message': f"Error cancelling order: {str(e)}"
            }
    
    @retry_on_transient_failure()
    def reject_order_by_distributor(self, order_id, distributor_user_id, rejection_reason=None):
        """
        Reject order by distributor and unblock stock
        Wrapped in single transaction for atomicity
        """
        try:
            # Lock order for update (requires active transaction)
            from app.db_locking import lock_order_for_update
            order = lock_order_for_update(order_id, nowait=False)
            if not order:
                return {
                    'success': False,
                    'message': "Order not found"
                }
            
            distributor = User.query.get(distributor_user_id)
            if not distributor or distributor.role != 'distributor':
                return {
                    'success': False,
                    'message': "Invalid distributor"
                }
            
            if not order.mr or not order.mr.area:
                return {
                    'success': False,
                    'message': "Order is missing MR information or area."
                }
            if order.mr.area != distributor.area:
                return {
                    'success': False,
                    'message': "This order doesn't belong to your area."
                }
            
            # Check if order can be rejected (only pending orders)
            if order.status != 'pending':
                return {
                    'success': False,
                    'message': f"Cannot reject order. Order status is '{order.status}'. Only pending orders can be rejected."
                }
            
            # Update order status (Flask-SQLAlchemy manages transactions)
            order.status = 'rejected'
            order.order_stage = 'rejected'
            
            # Unblock quantities - move blocked back to available
            if order.mr and order.mr.area:
                # Get order items to unblock
                order_items = OrderItem.query.filter_by(order_id=order.id).all()
                
                # Find dealers in MR's area
                dealers_in_area = User.query.filter_by(
                    role='distributor',
                    area=order.mr.area
                ).all()
                
                dealer_unique_ids = [d.unique_id for d in dealers_in_area]
                
                for item in order_items:
                    # Get stock details with blocked quantity
                    from sqlalchemy import case
                    stock_details = DealerWiseStockDetails.query.filter(
                        DealerWiseStockDetails.product_code == item.product_code,
                        DealerWiseStockDetails.dealer_unique_id.in_(dealer_unique_ids),
                        DealerWiseStockDetails.blocked_quantity > 0
                    ).order_by(
                        case(
                            (DealerWiseStockDetails.expiry_date.is_(None), 1),
                            else_=0
                        ),
                        DealerWiseStockDetails.expiry_date.asc()
                    ).all()
                    
                    remaining_to_unblock = item.quantity
                    
                    for stock_detail in stock_details:
                        if remaining_to_unblock <= 0:
                            break
                        
                        blocked_in_this_stock = stock_detail.blocked_quantity
                        if blocked_in_this_stock <= 0:
                            continue
                        
                        # Unblock quantity
                        quantity_to_unblock = min(remaining_to_unblock, blocked_in_this_stock)
                        stock_detail.blocked_quantity -= quantity_to_unblock
                        stock_detail.update_available_quantity()
                        
                        self.logger.info(
                            f"Unblocked {quantity_to_unblock} units of {item.product_code} "
                            f"(Stock ID: {stock_detail.id}, Blocked now: {stock_detail.blocked_quantity}, "
                            f"Available now: {stock_detail.available_for_sale})"
                        )
                        
                        remaining_to_unblock -= quantity_to_unblock
            
            # Commit all changes
            db.session.commit()
            
            # Send rejection notification to MR with enhanced template
            mr = User.query.get(order.mr_id)
            if mr:
                reason_text = f"<strong>Reason:</strong> {rejection_reason}" if rejection_reason else "No specific reason was provided."
                
                # Get order items with FOC information
                order_items = OrderItem.query.filter_by(order_id=order.id).all()
                items_table = ""
                if order_items:
                    items_table = """
                    <table style='width:100%;border-collapse:collapse;margin:20px 0;'>
                        <tr style='background:#dc3545;color:white;'>
                            <th style='padding:12px;text-align:left;'>PRODUCT</th>
                            <th style='padding:12px;text-align:center;'>QUANTITY</th>
                            <th style='padding:12px;text-align:center;'>FOC</th>
                            <th style='padding:12px;text-align:center;'>TOTAL QTY</th>
                            <th style='padding:12px;text-align:right;'>UNIT PRICE</th>
                            <th style='padding:12px;text-align:right;'>TOTAL</th>
                        </tr>
                    """
                    for item in order_items:
                        quantity = item.quantity or 0
                        foc_qty = item.free_quantity or 0
                        total_qty = quantity + foc_qty
                        foc_display = f"+{foc_qty}" if foc_qty > 0 else "-"
                        items_table += f"""
                        <tr style='background:#f7f8fa;'>
                            <td style='padding:10px;'>{item.product_name}<br><small style='color:#666;'>({item.product_code})</small></td>
                            <td style='padding:10px;text-align:center;'>{quantity}</td>
                            <td style='padding:10px;text-align:center;color:#10b981;font-weight:bold;'>{foc_display}</td>
                            <td style='padding:10px;text-align:center;font-weight:bold;'>{total_qty}</td>
                            <td style='padding:10px;text-align:right;'>{item.unit_price:,.2f} MMK</td>
                            <td style='padding:10px;text-align:right;'>{item.total_price:,.2f} MMK</td>
                        </tr>"""
                    items_table += "</table>"
                
                # Payment summary
                payment_summary = ""
                if hasattr(order, 'subtotal') and order.subtotal:
                    payment_summary = f"""
                    <div class='info-box' style='margin-top:20px;'>
                        <h3 style='margin-top: 0;'>💰 Payment Summary</h3>
                        <p style='margin: 5px 0;'><strong>Subtotal:</strong> {order.subtotal:,.2f} MMK</p>
                        <p style='margin: 5px 0;'><strong>Tax (5%):</strong> {order.tax_amount:,.2f} MMK</p>
                        <p style='margin: 5px 0; font-size: 1.2em;'><strong>Grand Total:</strong> {order.total_amount:,.2f} MMK</p>
                    </div>
                    """
                else:
                    payment_summary = f"<p style='margin-top:20px; font-size:1.2em;'><strong>Total Amount:</strong> {order.total_amount:,.2f} MMK</p>"
                
                content = f"""
                    <h2 style='color:#dc3545; margin-top:0;'>❌ Order Rejected</h2>
                    <p>Dear <strong>{mr.name}</strong>,</p>
                    <p>We regret to inform you that your order <strong>{order.order_id}</strong> has been rejected by distributor <strong>{distributor.name}</strong>.</p>
                    
                    <div class='warning-box'>
                        <h3 style='margin-top: 0;'>Rejection Details</h3>
                        <p style='margin: 5px 0;'>{reason_text}</p>
                        <p style='margin: 5px 0;'><strong>Order ID:</strong> {order.order_id}</p>
                        <p style='margin: 5px 0;'><strong>Date:</strong> {order.created_at.strftime('%B %d, %Y at %I:%M %p')}</p>
                        <p style='margin: 5px 0;'><strong>Area:</strong> {order.mr.area if order.mr else 'N/A'}</p>
                    </div>
                    
                    {items_table}
                    
                    {payment_summary}
                    
                    <div class='info-box'>
                        <h3 style='margin-top: 0;'>Distributor Contact</h3>
                        <p style='margin: 5px 0;'>For more information about this rejection, please contact your distributor:</p>
                        <p style='margin: 5px 0;'><strong>Name:</strong> {distributor.name}</p>
                        <p style='margin: 5px 0;'><strong>Email:</strong> <a href='mailto:{distributor.email}'>{distributor.email}</a></p>
                        <p style='margin: 5px 0;'><strong>Phone:</strong> {distributor.phone}</p>
                    </div>
                    
                    <p style='margin-top: 20px;'>You can place a new order anytime through the chatbot.</p>
                """
                
                from app.email_utils import create_email_template
                email_html = create_email_template(
                    title="Order Rejected",
                    content=content,
                    footer_text="If you have any questions, please contact your distributor or reply to this email."
                )
                
                send_email(
                    mr.email, 
                    f"❌ Order {order.order_id} - Rejected", 
                    email_html, 
                    'order_rejected',
                    order_id=order.order_id,
                    receiver_name=mr.name
                )
            
            return {
                'success': True,
                'message': f"Order {order_id} has been rejected and stock unblocked"
            }
            
        except Exception as e:
            self.logger.error(f"Error rejecting order: {str(e)}")
            db.session.rollback()
            return {
                'success': False,
                'message': f"Error rejecting order: {str(e)}"
            }
    
    def get_order_status(self, order_id, user_id=None):
        """
        Get order status and details
        """
        try:
            # Lock order for update (requires active transaction)
            from app.db_locking import lock_order_for_update
            order = lock_order_for_update(order_id, nowait=False)
            if not order:
                return {
                    'success': False,
                    'message': "Order not found"
                }
            
            # Check if user has access to this order
            if user_id and order.mr_id != user_id:
                return {
                    'success': False,
                    'message': "Access denied"
                }
            
            # Get order items
            order_items = []
            for item in order.order_items:
                order_items.append({
                    'product_code': item.product_code,
                    'product_name': item.product.product_name,
                    'quantity': item.quantity,
                    'unit_price': item.unit_price,
                    'total_price': item.total_price
                })
            
            # Get distributor info
            distributor_info = None
            if order.distributor_confirmed_by:
                distributor = User.query.get(order.distributor_confirmed_by)
                if distributor:
                    distributor_info = {
                        'name': distributor.name,
                        'email': distributor.email,
                        'phone': distributor.phone,
                        'company': distributor.company_name
                    }
            
            # Get MR info
            mr = order.mr if order.mr else None
            
            return {
                'success': True,
                'order': {
                    'order_id': order.order_id,
                    'status': order.status,
                    'order_stage': order.order_stage,
                    'total_amount': order.total_amount,
                    'order_date': order.created_at.isoformat() if order.created_at else None,
                    'area': mr.area if mr else None,
                    'distributor_confirmed_at': order.distributor_confirmed_at.isoformat() if order.distributor_confirmed_at else None,
                    'items': order_items,
                    'distributor_info': distributor_info
                }
            }
            
        except Exception as e:
            self.logger.error(f"Error getting order status: {str(e)}")
            return {
                'success': False,
                'message': f"Error retrieving order: {str(e)}"
            }
    
    def get_order_status_for_distributor(self, order_id, distributor_id):
        """Get order status for a distributor based on warehouse/location"""
        distributor = User.query.get(distributor_id)
        if not distributor or distributor.role != "distributor":
            return {
                'success': False,
                'message': "Only distributors can track/confirm via warehouse."
            }
        order = Order.query.filter_by(order_id=order_id).first()
        if not order:
            return {
                'success': False,
                'message': "Order not found"
            }
        if not order.mr or not order.mr.area:
            return {
                'success': False,
                'message': "Order is missing MR information or area."
            }
        if order.mr.area != distributor.area:
            return {
                'success': False,
                'message': "This order doesn't belong to your area."
            }
        # Compose table with FOC information
        items = []
        for item in order.order_items:
            quantity = item.quantity or 0
            free_quantity = getattr(item, 'free_quantity', 0) or 0
            items.append({
                'product_code': item.product_code,
                'product_name': item.product.product_name,
                'quantity': quantity,
                'free_quantity': free_quantity,
                'total_quantity': quantity + free_quantity,
                'unit_price': item.unit_price,
                'total_price': item.total_price
            })
        table = "| Product | Quantity | Unit Price | Total |\n|--------|---------|-----------|-------|\n"
        for row in items:
            # Get FOC quantity if available
            free_qty = row.get('free_quantity', 0)
            quantity = row.get('quantity', 0)
            if free_qty and free_qty > 0:
                qty_display = f"{quantity} paid + {free_qty} FREE = {quantity + free_qty} total"
            else:
                qty_display = str(quantity)
            table += f"| {row['product_name']} | {qty_display} | {row['unit_price']:,.2f} MMK | {row['total_price']:,.2f} MMK |\n"
        status = order.status
        
        summary = f"**Order ID:** {order.order_id}\n**Status:** {status}\n**Placed By:** {order.mr.name} ({order.mr.role})\n\n" + table
        return {
            'success': True,
            'message': summary,
            'order_id': order.order_id,
            'order_status': order.status,
            'can_confirm': status in ["in_transit", "distributor_notified"],
        }

    def _notify_distributor(self, order, placed_by_user, expired_products_info=None):
        """Send notification to distributor about new order (professional HTML, LLM intro)
        
        Args:
            order: Order object
            placed_by_user: User who placed the order
            expired_products_info: List of dicts with expired product details
        """
        try:
            # Get distributor for the warehouse
            distributors = self.db_service.get_distributors()
            distributor = None
            for dist in distributors:
                if dist.area == order.mr.area:
                    distributor = dist
                    break
            if not distributor:
                self.logger.warning(f"No distributor found for area {order.mr.area if order.mr else 'N/A'}")
                return
            order_items = OrderItem.query.filter_by(order_id=order.id).all()
            # --- Table with FOC information ---
            table = """
            <table style='width:100%;border-collapse:collapse;margin-bottom:16px;'>
                <tr style='background:#175DDC;color:white;'>
                    <th style='padding:12px;text-align:left;'>PRODUCT</th>
                    <th style='padding:12px;text-align:center;'>QUANTITY</th>
                    <th style='padding:12px;text-align:center;'>FOC</th>
                    <th style='padding:12px;text-align:center;'>TOTAL QTY</th>
                    <th style='padding:12px;text-align:right;'>UNIT PRICE</th>
                    <th style='padding:12px;text-align:right;'>TOTAL</th>
                </tr>
            """
            for item in order_items:
                quantity = item.quantity or 0
                foc_qty = item.free_quantity or 0
                total_qty = quantity + foc_qty
                foc_display = f"+{foc_qty}" if foc_qty > 0 else "-"
                table += f"""
                <tr style='background:#f7f8fa;'>
                    <td style='padding:10px;'>{item.product.product_name}<br><small style='color:#666;'>({item.product_code})</small></td>
                    <td style='padding:10px;text-align:center;'>{quantity}</td>
                    <td style='padding:10px;text-align:center;color:#10b981;font-weight:bold;'>{foc_display}</td>
                    <td style='padding:10px;text-align:center;font-weight:bold;'>{total_qty}</td>
                    <td style='padding:10px;text-align:right;'>{item.unit_price:,.2f} MMK</td>
                    <td style='padding:10px;text-align:right;'>{item.total_price:,.2f} MMK</td>
                </tr>"""
            table += "</table>"
            # --- LLM summary ---
            llm = self.llm_service.groq_service.client if hasattr(self.llm_service, 'groq_service') else None
            user_block = f"<b>Order Placed By:</b> {placed_by_user.name} ({placed_by_user.role}) — {placed_by_user.email}<br>Phone: {placed_by_user.phone}" if placed_by_user else ''
            summary = ""
            if llm:
                prompt = f"You are an AI assistant at Quantum Blue. Summarize the following order for a distributor, focusing on clarity, shipment urgency, and next steps.\nOrder ID: {order.order_id}\nCustomer: {placed_by_user.name}\nTotal: {order.total_amount:,.2f} MMK\nArea: {order.mr.area if order.mr else 'N/A'}.\nSay: 'Please confirm or discuss changes/next steps.'\nKeep it one concise, friendly paragraph."
                response = llm.chat.completions.create(
                    model=current_app.config.get('GROQ_MODEL', 'llama-3.3-70b-versatile'),
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.5,
                    max_tokens=200
                )
                summary = response.choices[0].message.content.strip()
            else:
                summary = "Please confirm the following new order and proceed with fulfillment or reply if any changes are needed."
            
            # --- Expired/Insufficient Products Warning Section ---
            expired_warning_html = ""
            if expired_products_info and len(expired_products_info) > 0:
                # Check if we have expired batches or just insufficient stock
                has_expired_batches = any(ep.get('expired_batches') and len(ep.get('expired_batches', [])) > 0 for ep in expired_products_info)
                has_insufficient_stock = any(ep.get('reason') == 'insufficient_stock' for ep in expired_products_info)
                
                if has_expired_batches:
                    expired_warning_html = """
                <div style='background:#fff3cd;border:2px solid #ffc107;border-radius:8px;padding:16px;margin-bottom:20px;'>
                    <h3 style='color:#856404;margin-top:0;'>⚠️ IMPORTANT: EXPIRED PRODUCTS DETECTED</h3>
                    <p style='color:#856404;margin-bottom:12px;font-weight:bold;'>
                        This order contains products with EXPIRED batches. Please review the details below and handle accordingly:
                    </p>
                    <table style='width:100%;border-collapse:collapse;background:white;'>
                        <tr style='background:#dc3545;color:white;'>
                            <th style='padding:10px;text-align:left;'>Product</th>
                            <th style='padding:10px;text-align:left;'>Batch Number</th>
                            <th style='padding:10px;text-align:center;'>Quantity</th>
                            <th style='padding:10px;text-align:center;'>Expiry Date</th>
                            <th style='padding:10px;text-align:center;'>Days Expired</th>
                        </tr>"""
                    
                    for expired_info in expired_products_info:
                        product_name = expired_info.get('product_name', 'Unknown')
                        product_code = expired_info.get('product_code', 'Unknown')
                        
                        for idx, batch in enumerate(expired_info.get('expired_batches', [])):
                            row_color = '#ffe6e6' if idx % 2 == 0 else '#fff'
                            expired_warning_html += f"""
                            <tr style='background:{row_color};'>
                                <td style='padding:10px;'>{product_name if idx == 0 else ''} ({product_code if idx == 0 else ''})</td>
                                <td style='padding:10px;font-weight:bold;'>{batch.get('batch_number', 'N/A')}</td>
                                <td style='padding:10px;text-align:center;'>{batch.get('quantity', 0)} units</td>
                                <td style='padding:10px;text-align:center;color:#dc3545;font-weight:bold;'>{batch.get('expiry_date', 'N/A')}</td>
                                <td style='padding:10px;text-align:center;color:#dc3545;font-weight:bold;'>{batch.get('days_expired', 0)} days</td>
                            </tr>"""
                    
                    expired_warning_html += """
                        </table>
                        <p style='color:#856404;margin-top:12px;margin-bottom:0;font-size:0.95em;'>
                            <strong>Action Required:</strong> Please verify the condition of these expired products before fulfillment. 
                            Contact the customer if replacement or alternative products are needed.
                        </p>
                    </div>"""
                elif has_insufficient_stock:
                    # Show insufficient stock warning
                    expired_warning_html = """
                    <div style='background:#fff3cd;border:2px solid #ffc107;border-radius:8px;padding:16px;margin-bottom:20px;'>
                        <h3 style='color:#856404;margin-top:0;'>⚠️ IMPORTANT: INSUFFICIENT STOCK</h3>
                        <p style='color:#856404;margin-bottom:12px;font-weight:bold;'>
                            This order contains products with INSUFFICIENT STOCK. Please review the details below:
                        </p>
                        <table style='width:100%;border-collapse:collapse;background:white;'>
                            <tr style='background:#dc3545;color:white;'>
                                <th style='padding:10px;text-align:left;'>Product</th>
                                <th style='padding:10px;text-align:center;'>Requested</th>
                                <th style='padding:10px;text-align:center;'>Available</th>
                                <th style='padding:10px;text-align:center;'>Shortage</th>
                            </tr>"""
                    
                    for expired_info in expired_products_info:
                        if expired_info.get('reason') == 'insufficient_stock':
                            product_name = expired_info.get('product_name', 'Unknown')
                            product_code = expired_info.get('product_code', 'Unknown')
                            requested = expired_info.get('requested_qty', 0)
                            available = expired_info.get('available_qty', 0)
                            shortage = requested - available
                            
                            expired_warning_html += f"""
                            <tr style='background:#fff;'>
                                <td style='padding:10px;'>{product_name} ({product_code})</td>
                                <td style='padding:10px;text-align:center;'>{requested} units</td>
                                <td style='padding:10px;text-align:center;'>{available} units</td>
                                <td style='padding:10px;text-align:center;color:#dc3545;font-weight:bold;'>{shortage} units</td>
                            </tr>"""
                    
                    expired_warning_html += """
                        </table>
                        <p style='color:#856404;margin-top:12px;margin-bottom:0;font-size:0.95em;'>
                            <strong>Note:</strong> These products will be automatically ordered when new stock arrives, and the customer will be notified.
                        </p>
                    </div>"""
                
                # Update LLM summary to mention products
                if llm:
                    expired_products_list = ", ".join([f"{ep['product_name']} ({ep['product_code']})" for ep in expired_products_info])
                    if has_expired_batches:
                        summary = f"{summary} IMPORTANT: This order includes expired products: {expired_products_list}. Please review and handle appropriately."
                    elif has_insufficient_stock:
                        summary = f"{summary} IMPORTANT: This order includes products with insufficient stock: {expired_products_list}. These will be auto-ordered when stock arrives."
            
            # --- Build email content with tax information ---
            tax_html = ""
            if hasattr(order, 'subtotal') and order.subtotal:
                tax_html = f"""
                    <div class='success-box' style='margin-top: 20px;'>
                        <h3 style='margin-top: 0; color: #059669;'>💰 Payment Summary</h3>
                        <p style='margin: 5px 0;'><strong>Subtotal:</strong> {order.subtotal:,.2f} MMK</p>
                        <p style='margin: 5px 0;'><strong>Tax (5%):</strong> {order.tax_amount:,.2f} MMK</p>
                        <p style='margin: 5px 0; font-size: 1.2em;'><strong>Grand Total:</strong> {order.total_amount:,.2f} MMK</p>
                    </div>
                """
            else:
                tax_html = f"<div style='margin-top:10px; font-size:1.2em;'><b>Order Total:</b> {order.total_amount:,.2f} MMK</div>"
            
            content = f"""
                <h2 style='color:#1e40af; margin-top: 0;'>New Order Notification 📦</h2>
                
                <div class='info-box'>
                    <p style='margin: 5px 0;'><strong>Order ID:</strong> {order.order_id}</p>
                    <p style='margin: 5px 0;'><strong>Date:</strong> {order.created_at.strftime('%B %d, %Y at %I:%M %p')}</p>
                    <p style='margin: 5px 0;'><strong>Area:</strong> {order.mr.area if order.mr else 'N/A'}</p>
                    <p style='margin: 5px 0;'><strong>Status:</strong> <span style='color:#f59e0b; font-weight: bold;'>{order.status or order.order_stage}</span></p>
                    {user_block}
                </div>
                
                <p style='margin: 20px 0;'>{summary}</p>
                
                {expired_warning_html}
                
                {table}
                
                {tax_html}
                
                <div class='info-box' style='margin-top: 25px;'>
                    <h3 style='margin-top: 0;'>Next Steps</h3>
                    <p>• Review the order details above</p>
                    <p>• Check stock availability</p>
                    <p>• Confirm or reject the order via the chatbot</p>
                    <p>• Contact the MR if you have any questions</p>
                </div>
            """
            
            # Import and use the enhanced template
            from app.email_utils import create_email_template
            html = create_email_template(
                title="New Order Notification",
                content=content,
                footer_text="This notification was sent by Quantum Blue AI. Please respond via the chatbot or reply to this email."
            )
            
            subject = f"New Order Notification - {order.order_id}"
            send_email(
                distributor.email,
                subject,
                html,
                'distributor_notification',
                order_id=order.order_id,
                receiver_name=distributor.name
            )
            self.logger.info(f"Distributor notification sent for order {order.order_id}")
        except Exception as e:
            self.logger.error(f"Error notifying distributor: {str(e)}")
    
    def _generate_invoice(self, order):
        """Generate invoice number"""
        timestamp = datetime.utcnow().strftime('%Y%m%d%H%M%S')
        return f"INV_{order.order_id}_{timestamp}"
    
    def _send_invoice_emails(self, order, distributor):
        """Send invoice emails to all parties"""
        try:
            # Get order details with FOC information
            order_items = []
            for item in order.order_items:
                order_items.append({
                    'product_code': item.product_code,
                    'product_name': item.product.product_name,
                    'quantity': item.quantity,
                    'free_quantity': item.free_quantity or 0,
                    'unit_price': item.unit_price,
                    'total_price': item.total_price
                })
            
            # Email to customer
            customer = User.query.get(order.mr_id)
            if customer:
                subject = f"Invoice Generated - Order {order.order_id}"
                html_content = self._generate_invoice_html(order, order_items, customer, distributor)
                send_email(
                    customer.email, 
                    subject, 
                    html_content, 
                    'invoice_customer',
                    order_id=order.order_id,
                    receiver_name=customer.name
                )
            
            # Email to distributor
            if distributor:
                subject = f"Invoice Copy - Order {order.order_id}"
                html_content = self._generate_invoice_html(order, order_items, customer, distributor, is_distributor=True)
                send_email(
                    distributor.email, 
                    subject, 
                    html_content, 
                    'invoice_distributor',
                    order_id=order.order_id,
                    receiver_name=distributor.name
                )
            
            # Email to company
            admin_email = None
            try:
                from flask import has_app_context
                if has_app_context():
                    admin_email = current_app.config.get('ADMIN_EMAIL')
            except (RuntimeError, AttributeError):
                pass
            
            if admin_email:
                subject = f"Order Invoice - {order.order_id}"
                html_content = self._generate_invoice_html(order, order_items, customer, distributor, is_admin=True)
                send_email(
                    admin_email, 
                    subject, 
                    html_content, 
                    'invoice_admin',
                    order_id=order.order_id,
                    receiver_name='Admin'
                )
            
            self.logger.info(f"Invoice emails sent for order {order.order_id}")
            
        except Exception as e:
            self.logger.error(f"Error sending invoice emails: {str(e)}")
    
    def _send_delivery_assignment_email(self, order, delivery_partner):
        """Send enhanced professional email notification to delivery partner when order is assigned"""
        try:
            from app.email_utils import create_email_template, send_email
            from datetime import datetime
            
            # Get customer details
            customer = None
            customer_name = "Customer Name Not Available"
            customer_phone = "Phone Not Provided"
            customer_email = "Email Not Provided"
            customer_address = "Address Not Provided"
            
            if order.customer_id:
                from app.models import Customer
                customer = Customer.query.get(order.customer_id)
                if customer:
                    customer_name = customer.name
                    customer_phone = customer.phone or "Phone Not Provided"
                    customer_email = customer.email or "Email Not Provided"
                    customer_address = customer.address or "Address Not Provided"
            
            # Get dealer/MR who placed or confirmed the order
            placed_by_name = "N/A"
            placed_by_role = "N/A"
            placed_by_phone = "N/A"
            
            if order.created_by_id:
                created_by = User.query.get(order.created_by_id)
                if created_by:
                    placed_by_name = created_by.name
                    placed_by_role = "Dealer" if created_by.role == 'distributor' else created_by.role.upper()
                    placed_by_phone = created_by.phone or "N/A"
            elif order.mr:
                placed_by_name = order.mr.name
                placed_by_role = "MR"
                placed_by_phone = order.mr.phone or "N/A"
            
            # Get order items
            order_items = OrderItem.query.filter_by(order_id=order.id).all()
            
            # Build detailed order items table
            items_html = ""
            total_items_count = 0
            for idx, item in enumerate(order_items, 1):
                quantity = item.adjusted_quantity if item.adjusted_quantity else item.quantity
                foc_qty = item.free_quantity or 0
                total_qty = quantity + foc_qty
                total_items_count += total_qty
                unit_price = item.unit_price or 0
                total_price = quantity * unit_price
                
                items_html += f"""
                <tr style="border-bottom: 1px solid #e5e7eb; background-color: {'#f9fafb' if idx % 2 == 0 else 'white'};">
                    <td style="padding: 12px; font-size: 14px;">{idx}</td>
                    <td style="padding: 12px; font-weight: 600; color: #1f2937;">{item.product_name}</td>
                    <td style="padding: 12px; font-size: 13px; color: #6b7280; text-align: center;">{item.product_code}</td>
                    <td style="padding: 12px; text-align: center;">
                        <span style="font-weight: 600; color: #059669;">{quantity}</span>
                        {f'<span style="color: #f59e0b; font-size: 12px;"> +{foc_qty} FOC</span>' if foc_qty > 0 else ''}
                    </td>
                    <td style="padding: 12px; text-align: center; font-weight: 600; color: #2563eb;">{total_qty}</td>
                    <td style="padding: 12px; text-align: right; color: #059669;">{unit_price:,.0f} MMK</td>
                    <td style="padding: 12px; text-align: right; font-weight: 600; color: #059669;">{total_price:,.0f} MMK</td>
                </tr>
                """
            
            # Calculate order summary
            subtotal = order.subtotal or 0
            tax_amount = order.tax_amount or 0
            grand_total = order.total_amount or 0
            
            # Get current date/time for professional formatting
            current_datetime = datetime.now().strftime('%B %d, %Y at %I:%M %p')
            order_datetime = order.created_at.strftime('%B %d, %Y at %I:%M %p') if order.created_at else 'N/A'
            
            content = f"""
            <div style="background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%); color: white; padding: 30px; border-radius: 12px 12px 0 0; text-align: center; margin: -20px -20px 20px -20px;">
                <h2 style="margin: 0 0 10px 0; font-size: 28px;">🚚 New Delivery Assignment</h2>
                <p style="margin: 0; font-size: 16px; opacity: 0.95;">Order #{order.order_id}</p>
            </div>
            
            <div style="background-color: #fef3c7; padding: 20px; border-radius: 8px; margin: 20px 0; border-left: 5px solid #f59e0b;">
                <p style="margin: 0; font-size: 15px; color: #92400e;">
                    <strong>🔔 Action Required:</strong> You have been assigned a new order for delivery. 
                    Please review the details below and prepare for pickup from the dealer.
                </p>
            </div>
            
            <div style="background-color: #f0f9ff; padding: 25px; border-radius: 10px; margin: 20px 0; border: 2px solid #bae6fd;">
                <h3 style="margin-top: 0; color: #0c4a6e; font-size: 20px; border-bottom: 2px solid #0ea5e9; padding-bottom: 10px;">
                    <i style="color: #0ea5e9;">📋</i> Order Information
                </h3>
                <table style="width: 100%; font-size: 14px;">
                    <tr>
                        <td style="padding: 8px 0; color: #64748b; width: 40%;"><strong>Order ID:</strong></td>
                        <td style="padding: 8px 0; color: #1e293b; font-weight: 600;">{order.order_id}</td>
                    </tr>
                    <tr>
                        <td style="padding: 8px 0; color: #64748b;"><strong>Order Date:</strong></td>
                        <td style="padding: 8px 0; color: #1e293b;">{order_datetime}</td>
                    </tr>
                    <tr>
                        <td style="padding: 8px 0; color: #64748b;"><strong>Placed By:</strong></td>
                        <td style="padding: 8px 0; color: #1e293b;">{placed_by_role} - {placed_by_name}</td>
                    </tr>
                    <tr>
                        <td style="padding: 8px 0; color: #64748b;"><strong>Contact:</strong></td>
                        <td style="padding: 8px 0; color: #1e293b;">{placed_by_phone}</td>
                    </tr>
                    <tr>
                        <td style="padding: 8px 0; color: #64748b;"><strong>Total Items:</strong></td>
                        <td style="padding: 8px 0; color: #1e293b; font-weight: 600;">{total_items_count} units</td>
                    </tr>
                    <tr style="background-color: #dbeafe;">
                        <td style="padding: 12px 8px; color: #1e40af; font-size: 16px;"><strong>Grand Total:</strong></td>
                        <td style="padding: 12px 8px; color: #1e40af; font-weight: 700; font-size: 18px;">{grand_total:,.2f} MMK</td>
                    </tr>
                </table>
            </div>
            
            <div style="background-color: #ffffff; padding: 25px; border-radius: 10px; margin: 20px 0; border: 2px solid #e5e7eb; box-shadow: 0 2px 8px rgba(0,0,0,0.1);">
                <h3 style="margin-top: 0; color: #059669; font-size: 20px; border-bottom: 2px solid #10b981; padding-bottom: 10px;">
                    <i style="color: #10b981;">📦</i> Items to Deliver
                </h3>
                <table style="width: 100%; border-collapse: collapse; margin-top: 15px; font-size: 14px;">
                    <thead>
                        <tr style="background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%); color: white;">
                            <th style="padding: 12px; text-align: left; border-radius: 8px 0 0 0;">#</th>
                            <th style="padding: 12px; text-align: left;">Product Name</th>
                            <th style="padding: 12px; text-align: center;">Product Code</th>
                            <th style="padding: 12px; text-align: center;">Paid Qty</th>
                            <th style="padding: 12px; text-align: center;">Total Qty</th>
                            <th style="padding: 12px; text-align: right;">Unit Price</th>
                            <th style="padding: 12px; text-align: right; border-radius: 0 8px 0 0;">Total</th>
                        </tr>
                    </thead>
                    <tbody>
                        {items_html}
                        <tr style="background-color: #f0fdf4; border-top: 3px solid #10b981;">
                            <td colspan="6" style="padding: 15px; text-align: right; font-weight: 700; font-size: 15px; color: #065f46;">
                                Total Items to Deliver:
                            </td>
                            <td style="padding: 15px; text-align: right; font-weight: 700; font-size: 16px; color: #059669;">
                                {total_items_count} units
                            </td>
                        </tr>
                    </tbody>
                </table>
            </div>
            
            <div style="background: linear-gradient(135deg, #eff6ff 0%, #dbeafe 100%); padding: 25px; border-radius: 10px; margin: 20px 0; border: 2px solid #93c5fd;">
                <h3 style="margin-top: 0; color: #1e40af; font-size: 20px; border-bottom: 2px solid #3b82f6; padding-bottom: 10px;">
                    <i style="color: #3b82f6;">📍</i> Customer Delivery Details
                </h3>
                <table style="width: 100%; font-size: 14px; margin-top: 15px;">
                    <tr style="background-color: #f0f9ff;">
                        <td style="padding: 12px; color: #1e40af; width: 35%;"><strong><i style="color: #3b82f6;">👤</i> Customer Name:</strong></td>
                        <td style="padding: 12px; color: #1e293b; font-weight: 600; font-size: 15px;">{customer_name}</td>
                    </tr>
                    <tr>
                        <td style="padding: 12px; color: #1e40af;"><strong><i style="color: #3b82f6;">📞</i> Contact Phone:</strong></td>
                        <td style="padding: 12px; color: #1e293b; font-weight: 500;">{customer_phone}</td>
                    </tr>
                    <tr style="background-color: #f0f9ff;">
                        <td style="padding: 12px; color: #1e40af;"><strong><i style="color: #3b82f6;">✉️</i> Email:</strong></td>
                        <td style="padding: 12px; color: #1e293b; font-weight: 500;">{customer_email}</td>
                    </tr>
                    <tr>
                        <td style="padding: 12px; color: #1e40af; vertical-align: top;"><strong><i style="color: #3b82f6;">📮</i> Delivery Address:</strong></td>
                        <td style="padding: 12px; color: #1e293b; font-weight: 500; line-height: 1.6;">{customer_address}</td>
                    </tr>
                </table>
            </div>
            
            <div style="background-color: #fef2f2; padding: 20px; border-radius: 10px; margin: 20px 0; border-left: 5px solid #ef4444;">
                <h4 style="margin-top: 0; color: #991b1b; font-size: 16px;">
                    <i style="color: #dc2626;">⚠️</i> Important Instructions
                </h4>
                <ul style="margin: 10px 0; padding-left: 20px; color: #7f1d1d;">
                    <li style="margin-bottom: 8px;">Please verify all items before pickup from the dealer</li>
                    <li style="margin-bottom: 8px;">Contact customer to confirm delivery time: <strong>{customer_phone}</strong></li>
                    <li style="margin-bottom: 8px;">Collect payment of <strong>{grand_total:,.2f} MMK</strong> upon delivery (if COD)</li>
                    <li style="margin-bottom: 8px;">Update delivery status in your dashboard after completion</li>
                    <li style="margin-bottom: 8px;">For any issues, contact the dealer: <strong>{placed_by_name}</strong> at {placed_by_phone}</li>
                </ul>
            </div>
            
            <div style="background-color: #ecfdf5; padding: 20px; border-radius: 10px; margin: 20px 0; border: 2px solid #10b981;">
                <h4 style="margin-top: 0; color: #065f46; font-size: 16px;">
                    <i style="color: #10b981;">💰</i> Payment Summary
                </h4>
                <table style="width: 100%; font-size: 14px;">
                    <tr>
                        <td style="padding: 8px 0; color: #064e3b;">Subtotal:</td>
                        <td style="padding: 8px 0; text-align: right; color: #064e3b;">{subtotal:,.2f} MMK</td>
                    </tr>
                    <tr>
                        <td style="padding: 8px 0; color: #064e3b;">Tax (5%):</td>
                        <td style="padding: 8px 0; text-align: right; color: #064e3b;">{tax_amount:,.2f} MMK</td>
                    </tr>
                    <tr style="border-top: 2px solid #10b981; background-color: #d1fae5;">
                        <td style="padding: 12px 0; font-weight: 700; font-size: 16px; color: #065f46;">Grand Total:</td>
                        <td style="padding: 12px 0; text-align: right; font-weight: 700; font-size: 18px; color: #059669;">{grand_total:,.2f} MMK</td>
                    </tr>
                </table>
            </div>
            
            <div style="background-color: #f0f9ff; padding: 20px; border-radius: 10px; margin: 20px 0; text-align: center; border: 2px dashed #3b82f6;">
                <p style="margin: 0 0 15px 0; font-size: 15px; color: #1e40af;">
                    <strong>📱 Need Help?</strong>
                </p>
                <p style="margin: 0; font-size: 13px; color: #475569;">
                    Contact our support team or the dealer for any questions about this delivery.
                </p>
                <p style="margin: 10px 0 0 0; font-size: 12px; color: #64748b;">
                    Email sent: {current_datetime}
                </p>
            </div>
            """
            
            html_content = create_email_template(
                title=f"🚚 Delivery Assignment - Order {order.order_id}",
                content=content,
                footer_text="HV (Powered by Quantum Blue AI) - Professional Pharmaceutical Distribution System"
            )
            
            send_email(
                delivery_partner.email,
                f"🚚 New Delivery Assignment - Order {order.order_id} | {total_items_count} Items | {grand_total:,.0f} MMK",
                html_content,
                'delivery_assignment',
                order_id=order.order_id,
                receiver_name=delivery_partner.name
            )
            
            self.logger.info(f"Enhanced delivery assignment email sent to {delivery_partner.email} for order {order.order_id}")
            
        except Exception as e:
            self.logger.error(f"Error sending delivery assignment email: {str(e)}")
    
    def mark_order_as_delivered(self, order_id, delivery_partner_id):
        """
        Mark order as delivered by delivery partner
        Moves stock from out_for_delivery to sold
        """
        try:
            from app.db_locking import lock_order_for_update
            from datetime import datetime
            
            # Lock order for update
            order = lock_order_for_update(order_id, nowait=False)
            if not order:
                return {
                    'success': False,
                    'message': "Order not found"
                }
            
            # Verify delivery partner
            delivery_partner = User.query.get(delivery_partner_id)
            if not delivery_partner or delivery_partner.role != 'delivery_partner':
                return {
                    'success': False,
                    'message': "Invalid delivery partner"
                }
            
            # Verify order is assigned to this delivery partner
            if order.delivery_partner_id != delivery_partner_id:
                return {
                    'success': False,
                    'message': "This order is not assigned to you"
                }
            
            # Check if already delivered
            if order.status == 'delivered':
                return {
                    'success': False,
                    'message': "Order is already marked as delivered"
                }
            
            # Check if order is confirmed (must be confirmed before delivery)
            if order.status != 'confirmed':
                return {
                    'success': False,
                    'message': f"Order must be confirmed before marking as delivered. Current status: {order.status}"
                }
            
            # Move stock from out_for_delivery to sold
            self._move_out_for_delivery_to_sold_for_order(order)
            
            # Update order status
            order.status = 'delivered'
            order.order_stage = 'delivered'
            order.delivered_at = datetime.utcnow()
            order.delivered_by = delivery_partner_id
            
            # Commit changes
            db.session.commit()
            
            # Send notification email to MR and dealer
            try:
                self._send_delivery_completion_email(order, delivery_partner)
            except Exception as email_e:
                self.logger.error(f"Error sending delivery completion email: {str(email_e)}")
            
            self.logger.info(f"Order {order_id} marked as delivered by delivery partner {delivery_partner.unique_id}")
            
            return {
                'success': True,
                'message': f"Order {order_id} has been marked as delivered successfully. Stock has been moved from out_for_delivery to sold."
            }
            
        except Exception as e:
            self.logger.error(f"Error marking order as delivered: {str(e)}")
            db.session.rollback()
            return {
                'success': False,
                'message': f"Error marking order as delivered: {str(e)}"
            }
    
    def _send_delivery_completion_email(self, order, delivery_partner):
        """Send email notification when order is delivered"""
        try:
            from app.email_utils import create_email_template, send_email
            
            # Get MR
            mr = User.query.get(order.mr_id) if order.mr_id else None
            
            # Get customer
            customer = None
            if order.customer_id:
                from app.models import Customer
                customer = Customer.query.get(order.customer_id)
            
            # Send to MR
            if mr and mr.email:
                content = f"""
                <div class="success-box">
                    <h3 style="margin-top: 0; color: #059669;">✅ Order Delivered Successfully!</h3>
                    <p>Your order <strong>{order.order_id}</strong> has been successfully delivered to the customer.</p>
                </div>
                
                <div style="background-color: #f9fafb; padding: 20px; border-radius: 8px; margin: 20px 0;">
                    <p><strong>Order ID:</strong> {order.order_id}</p>
                    <p><strong>Delivered By:</strong> {delivery_partner.name} ({delivery_partner.unique_id})</p>
                    <p><strong>Delivery Date:</strong> {order.delivered_at.strftime('%Y-%m-%d %H:%M:%S') if order.delivered_at else 'N/A'}</p>
                    <p><strong>Customer:</strong> {customer.name if customer else 'N/A'}</p>
                </div>
                """
                
                html_content = create_email_template(
                    title="Order Delivered",
                    content=content,
                    footer_text="Thank you for using HV (Powered by Quantum Blue AI)."
                )
                
                send_email(
                    mr.email,
                    f"Order {order.order_id} Delivered Successfully",
                    html_content,
                    'order_delivered',
                    order_id=order.order_id,
                    receiver_name=mr.name
                )
            
            # Send to dealer
            if order.distributor_confirmed_by:
                distributor = User.query.get(order.distributor_confirmed_by)
                if distributor and distributor.email:
                    content = f"""
                    <div class="success-box">
                        <h3 style="margin-top: 0; color: #059669;">✅ Order Delivered Successfully!</h3>
                        <p>Order <strong>{order.order_id}</strong> has been successfully delivered.</p>
                    </div>
                    
                    <div style="background-color: #f9fafb; padding: 20px; border-radius: 8px; margin: 20px 0;">
                        <p><strong>Order ID:</strong> {order.order_id}</p>
                        <p><strong>Delivered By:</strong> {delivery_partner.name} ({delivery_partner.unique_id})</p>
                        <p><strong>Delivery Date:</strong> {order.delivered_at.strftime('%Y-%m-%d %H:%M:%S') if order.delivered_at else 'N/A'}</p>
                        <p><strong>Stock Status:</strong> Stock has been moved from out_for_delivery to sold.</p>
                    </div>
                    """
                    
                    html_content = create_email_template(
                        title="Order Delivered",
                        content=content,
                        footer_text="Stock has been updated in your inventory."
                    )
                    
                    send_email(
                        distributor.email,
                        f"Order {order.order_id} Delivered",
                        html_content,
                        'order_delivered_distributor',
                        order_id=order.order_id,
                        receiver_name=distributor.name
                    )
            
        except Exception as e:
            self.logger.error(f"Error sending delivery completion email: {str(e)}")
    
    def _generate_invoice_html(self, order, order_items, customer, distributor, is_distributor=False, is_admin=False):
        """Generate HTML invoice content"""
        recipient = "Distributor" if is_distributor else ("Admin" if is_admin else "Customer")
        
        # Generate invoice number
        invoice_number = self._generate_invoice(order)
        
        # Get status and stage with proper formatting
        status_display = (order.status or 'Pending').replace('_', ' ').title()
        stage_display = (order.order_stage or '').replace('_', ' ').title() if order.order_stage else ''
        
        # Determine status color
        status_lower = (order.status or '').lower()
        if 'confirm' in status_lower:
            status_color = '#10b981'  # Green
        elif 'deliver' in status_lower:
            status_color = '#059669'  # Dark green
        elif 'cancel' in status_lower:
            status_color = '#ef4444'  # Red
        elif 'complete' in status_lower:
            status_color = '#3b82f6'  # Blue
        else:
            status_color = '#f59e0b'  # Orange for pending
        
        items_html = ""
        for item in order_items:
            foc_qty = item.get('free_quantity', 0) or 0
            foc_display = f"+{foc_qty}" if foc_qty > 0 else "-"
            total_qty = item['quantity'] + foc_qty
            items_html += f"""
            <tr>
                <td>{item['product_code']}</td>
                <td>{item['product_name']}</td>
                <td style='text-align:center;'>{item['quantity']}</td>
                <td style='text-align:center;color:#10b981;font-weight:bold;'>{foc_display}</td>
                <td style='text-align:center;font-weight:bold;'>{total_qty}</td>
                <td>{item['unit_price']:,.2f} MMK</td>
                <td>{item['total_price']:,.2f} MMK</td>
            </tr>
            """
        
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 800px; margin: 0 auto; padding: 20px; }}
                .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 20px; border-radius: 8px; text-align: center; }}
                .content {{ background: white; padding: 20px; border-radius: 8px; margin-top: 20px; }}
                .invoice-details {{ background: #f8f9fa; padding: 15px; border-radius: 5px; margin: 20px 0; }}
                .status-section {{
                    background: #ffffff;
                    padding: 15px;
                    border-radius: 8px;
                    margin: 15px 0;
                    border-left: 4px solid {status_color};
                    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                }}
                .status-badge {{
                    display: inline-block;
                    padding: 8px 16px;
                    border-radius: 6px;
                    font-weight: 600;
                    font-size: 14px;
                    color: white;
                    background-color: {status_color};
                    margin-left: 10px;
                }}
                table {{ width: 100%; border-collapse: collapse; margin: 20px 0; }}
                th, td {{ border: 1px solid #ddd; padding: 12px; text-align: left; }}
                th {{ background-color: #f2f2f2; }}
                .total {{ font-size: 18px; font-weight: bold; color: #007bff; }}
                .footer {{ margin-top: 30px; padding: 20px; background: #f8f9fa; border-radius: 5px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>🧾 Invoice Generated</h1>
                    <p>HV (Powered by Quantum Blue AI)</p>
                </div>
                
                <div class="content">
                    <h2>Order Confirmation</h2>
                    <div class="invoice-details">
                        <p><strong>Invoice Number:</strong> {invoice_number}</p>
                        <p><strong>Order ID:</strong> {order.order_id}</p>
                        <p><strong>Date:</strong> {order.created_at.strftime('%Y-%m-%d %H:%M:%S')}</p>
                        <p><strong>Area:</strong> {order.mr.area if order.mr else 'N/A'}</p>
                        <p><strong>Customer:</strong> {customer.name if customer else 'N/A'}</p>
                        <p><strong>Distributor:</strong> {distributor.name if distributor else 'N/A'}</p>
                    </div>
                    
                    <div class="status-section">
                        <p style="margin: 0 0 10px 0;"><strong>Order Status:</strong> <span class="status-badge">{status_display}</span></p>
                        {f'<p style="margin: 0;"><strong>Order Stage:</strong> {stage_display}</p>' if stage_display else ''}
                    </div>
                    
                    <h3>Order Items</h3>
                    <table>
                        <thead>
                            <tr>
                                <th>Product Code</th>
                                <th>Product Name</th>
                                <th>Quantity</th>
                                <th>FOC</th>
                                <th>Total Qty</th>
                                <th>Unit Price</th>
                                <th>Total</th>
                            </tr>
                        </thead>
                        <tbody>
                            {items_html}
                        </tbody>
                    </table>
                    
                    <div class="total">
                        <p><strong>Total Amount: {order.total_amount:,.2f} MMK</strong></p>
                    </div>
                    
                    <div class="footer">
                        <p>This invoice has been automatically generated by HV (Powered by Quantum Blue AI) system.</p>
                        <p>Thank you for your business!</p>
                    </div>
                </div>
            </div>
        </body>
        </html>
        """
        
        return html_content
    
    def _block_quantity_for_mr_order(self, user, product_code, quantity):
        """
        Block quantity in dealer_wise_stock_details when MR places an order
        Uses FEFO (First Expiry First Out) to block from earliest expiring stock
        """
        try:
            from datetime import date
            today = date.today()
            
            # Find dealers in the MR's area
            dealers_in_area = User.query.filter_by(
                role='distributor',
                area=user.area
            ).all()
            
            if not dealers_in_area:
                self.logger.warning(f"No dealers found in area {user.area} for MR {user.name}")
                return False
            
            remaining_quantity = quantity
            
            # Get all confirmed stock details for this product from dealers in MR's area
            # Ordered by expiration date (earliest first) for FEFO
            # SQL Server doesn't support NULLS LAST, so we use a different approach
            from sqlalchemy import case
            all_stock_details = DealerWiseStockDetails.query.filter(
                DealerWiseStockDetails.product_code == product_code,
                DealerWiseStockDetails.status == 'confirmed',
                DealerWiseStockDetails.dealer_unique_id.in_([d.unique_id for d in dealers_in_area])
            ).order_by(
                case(
                    (DealerWiseStockDetails.expiry_date.is_(None), 1),
                    else_=0
                ),
                DealerWiseStockDetails.expiry_date.asc()
            ).all()
            
            # Filter to only stock with available_for_sale > 0
            available_stock = [s for s in all_stock_details if s.available_for_sale > 0]
            
            if not available_stock:
                self.logger.warning(f"No available stock found for {product_code} from dealers in area {user.area}")
                return False
            
            # Block quantity using FEFO (earliest expiry first)
            for stock_detail in available_stock:
                if remaining_quantity <= 0:
                    break
                
                available_in_this_stock = stock_detail.available_for_sale
                if available_in_this_stock <= 0:
                    continue
                
                # Calculate how much to block from this stock detail
                quantity_to_block = min(remaining_quantity, available_in_this_stock)
                
                # Block the quantity
                stock_detail.blocked_quantity += quantity_to_block
                stock_detail.update_available_quantity()
                
                self.logger.info(
                    f"Blocked {quantity_to_block} units of {product_code} from dealer {stock_detail.dealer_name} "
                    f"(Stock ID: {stock_detail.id}, Expiry: {stock_detail.expiry_date}, "
                    f"Available now: {stock_detail.available_for_sale})"
                )
                
                remaining_quantity -= quantity_to_block
            
            if remaining_quantity > 0:
                self.logger.warning(
                    f"Could only block {quantity - remaining_quantity} out of {quantity} units "
                    f"for {product_code} (insufficient stock in dealer_wise_stock_details)"
                )
                return False  # Failed to block all requested quantity
            
            db.session.flush()  # Flush changes but don't commit yet (will be committed with order)
            return True  # Successfully blocked all requested quantity
            
        except Exception as e:
            self.logger.error(f"Error blocking quantity for MR order: {str(e)}")
            return False  # Return False on exception
    
    def _block_quantity_for_distributor_order(self, user, product_code, quantity):
        """
        Block quantity in dealer_wise_stock_details when distributor places an order
        Uses FEFO (First Expiry First Out) to block from earliest expiring stock
        """
        try:
            from datetime import date
            today = date.today()
            
            if not user.unique_id:
                self.logger.warning(f"No unique_id found for distributor {user.name}")
                return False
            
            remaining_quantity = quantity
            
            # Get all confirmed stock details for this product from this distributor
            # Ordered by expiration date (earliest first) for FEFO
            from sqlalchemy import case
            all_stock_details = DealerWiseStockDetails.query.filter(
                DealerWiseStockDetails.product_code == product_code,
                DealerWiseStockDetails.status == 'confirmed',
                DealerWiseStockDetails.dealer_unique_id == user.unique_id
            ).order_by(
                case(
                    (DealerWiseStockDetails.expiry_date.is_(None), 1),
                    else_=0
                ),
                DealerWiseStockDetails.expiry_date.asc()
            ).all()
            
            # Filter to only stock with available_for_sale > 0
            available_stock = [s for s in all_stock_details if s.available_for_sale > 0]
            
            if not available_stock:
                self.logger.warning(f"No available stock found for {product_code} from distributor {user.unique_id}")
                return False
            
            # Block quantity using FEFO (earliest expiry first)
            for stock_detail in available_stock:
                if remaining_quantity <= 0:
                    break
                
                available_in_this_stock = stock_detail.available_for_sale
                if available_in_this_stock <= 0:
                    continue
                
                # Calculate how much to block from this stock detail
                quantity_to_block = min(remaining_quantity, available_in_this_stock)
                
                # Block the quantity
                stock_detail.blocked_quantity += quantity_to_block
                stock_detail.update_available_quantity()
                
                self.logger.info(
                    f"Blocked {quantity_to_block} units of {product_code} from distributor {user.unique_id} "
                    f"(Stock ID: {stock_detail.id}, Expiry: {stock_detail.expiry_date}, "
                    f"Available now: {stock_detail.available_for_sale})"
                )
                
                remaining_quantity -= quantity_to_block
            
            if remaining_quantity > 0:
                self.logger.warning(
                    f"Could only block {quantity - remaining_quantity} out of {quantity} units "
                    f"for {product_code} (insufficient stock in dealer_wise_stock_details)"
                )
                return False  # Failed to block all requested quantity
            
            db.session.flush()  # Flush changes but don't commit yet (will be committed with order)
            return True  # Successfully blocked all requested quantity
            
        except Exception as e:
            self.logger.error(f"Error blocking quantity for distributor order: {str(e)}")
            return False  # Return False on exception
    
    def _move_blocked_to_out_for_delivery_for_distributor_order(self, user, cart_items):
        """
        Move blocked quantities to out_for_delivery for distributor's own orders
        Updates available_for_sale accordingly
        Stock will move to sold when delivery partner marks order as delivered
        """
        try:
            from app.models import DealerWiseStockDetails
            
            if not user.unique_id:
                self.logger.warning(f"No unique_id found for distributor {user.name}")
                return
            
            # Process each cart item
            for cart_item in cart_items:
                product_code = cart_item.product_code
                total_quantity_to_move = cart_item.quantity
                
                # Get all stock details with blocked quantity for this product from this distributor
                from sqlalchemy import case
                stock_details = DealerWiseStockDetails.query.filter(
                    DealerWiseStockDetails.product_code == product_code,
                    DealerWiseStockDetails.status == 'confirmed',
                    DealerWiseStockDetails.dealer_unique_id == user.unique_id,
                    DealerWiseStockDetails.blocked_quantity > 0
                ).order_by(
                    case(
                        (DealerWiseStockDetails.expiry_date.is_(None), 1),
                        else_=0
                    ),
                    DealerWiseStockDetails.expiry_date.asc()
                ).all()
                
                remaining_quantity = total_quantity_to_move
                
                # Move blocked to out_for_delivery using FEFO (earliest expiry first)
                for stock_detail in stock_details:
                    if remaining_quantity <= 0:
                        break
                    
                    blocked_in_this_stock = stock_detail.blocked_quantity
                    if blocked_in_this_stock <= 0:
                        continue
                    
                    # Calculate how much to move from this stock detail
                    quantity_to_move_from_stock = min(remaining_quantity, blocked_in_this_stock)
                    
                    # Move from blocked to out_for_delivery (not sold yet)
                    stock_detail.blocked_quantity -= quantity_to_move_from_stock
                    stock_detail.out_for_delivery_quantity += quantity_to_move_from_stock
                    stock_detail.update_available_quantity()
                    
                    self.logger.info(
                        f"Moved {quantity_to_move_from_stock} units of {product_code} from blocked to out_for_delivery "
                        f"(Stock ID: {stock_detail.id}, Dealer: {stock_detail.dealer_name}, "
                        f"Blocked now: {stock_detail.blocked_quantity}, Out for delivery now: {stock_detail.out_for_delivery_quantity}, "
                        f"Available now: {stock_detail.available_for_sale})"
                    )
                    
                    remaining_quantity -= quantity_to_move_from_stock
                
                if remaining_quantity > 0:
                    self.logger.warning(
                        f"Could only move {total_quantity_to_move - remaining_quantity} out of {total_quantity_to_move} units "
                        f"from blocked to out_for_delivery for {product_code} (insufficient blocked quantity)"
                    )
            
            db.session.flush()  # Flush changes
            
        except Exception as e:
            self.logger.error(f"Error moving blocked to out_for_delivery for distributor order: {str(e)}")
    
    def _move_blocked_to_out_for_delivery_for_mr_order(self, user, cart_items):
        """
        Move blocked quantities to out_for_delivery when dealer confirms order and assigns delivery partner
        Updates available_for_sale accordingly
        Stock will move to sold when delivery partner marks order as delivered
        """
        try:
            from app.models import DealerWiseStockDetails
            
            # Find dealers in the MR's area
            dealers_in_area = User.query.filter_by(
                role='distributor',
                area=user.area
            ).all()
            
            if not dealers_in_area:
                self.logger.warning(f"No dealers found in area {user.area} for MR {user.name}")
                return
            
            dealer_unique_ids = [d.unique_id for d in dealers_in_area]
            
            # Process each cart item
            for cart_item in cart_items:
                product_code = cart_item.product_code
                # cart_item.quantity already contains paid + FOC (total_quantity_to_move from order confirmation)
                # This was set when creating cart_like_items in confirm_order_by_distributor
                total_quantity_to_move = cart_item.quantity
                
                # Get all stock details with blocked quantity for this product
                # SQL Server doesn't support NULLS LAST, so we use CASE
                from sqlalchemy import case
                stock_details = DealerWiseStockDetails.query.filter(
                    DealerWiseStockDetails.product_code == product_code,
                    DealerWiseStockDetails.status == 'confirmed',
                    DealerWiseStockDetails.dealer_unique_id.in_(dealer_unique_ids),
                    DealerWiseStockDetails.blocked_quantity > 0
                ).order_by(
                    case(
                        (DealerWiseStockDetails.expiry_date.is_(None), 1),
                        else_=0
                    ),
                    DealerWiseStockDetails.expiry_date.asc()
                ).all()
                
                remaining_quantity = total_quantity_to_move
                
                # Move blocked to out_for_delivery using FEFO (earliest expiry first)
                # This moves both paid quantity and FOC quantity that were blocked together
                for stock_detail in stock_details:
                    if remaining_quantity <= 0:
                        break
                    
                    blocked_in_this_stock = stock_detail.blocked_quantity
                    if blocked_in_this_stock <= 0:
                        continue
                    
                    # Calculate how much to move from this stock detail
                    quantity_to_move_from_stock = min(remaining_quantity, blocked_in_this_stock)
                    
                    # Move from blocked to out_for_delivery (not sold yet)
                    stock_detail.blocked_quantity -= quantity_to_move_from_stock
                    stock_detail.out_for_delivery_quantity += quantity_to_move_from_stock
                    stock_detail.update_available_quantity()
                    
                    self.logger.info(
                        f"Moved {quantity_to_move_from_stock} units of {product_code} from blocked to out_for_delivery "
                        f"(Stock ID: {stock_detail.id}, Dealer: {stock_detail.dealer_name}, "
                        f"Blocked now: {stock_detail.blocked_quantity}, Out for delivery now: {stock_detail.out_for_delivery_quantity}, "
                        f"Available now: {stock_detail.available_for_sale})"
                    )
                    
                    remaining_quantity -= quantity_to_move_from_stock
                
                if remaining_quantity > 0:
                    self.logger.warning(
                        f"Could only move {total_quantity_to_move - remaining_quantity} out of {total_quantity_to_move} units "
                        f"from blocked to out_for_delivery for {product_code} (insufficient blocked quantity)"
                    )
            
            db.session.flush()  # Flush changes
            
        except Exception as e:
            self.logger.error(f"Error moving blocked to out_for_delivery for MR order: {str(e)}")
            # Don't raise - allow order to proceed even if this fails
    
    def _move_out_for_delivery_to_sold_for_order(self, order):
        """
        Move out_for_delivery quantities to sold when delivery partner marks order as delivered
        Updates available_for_sale accordingly
        """
        try:
            from app.models import DealerWiseStockDetails
            
            # Get order items
            order_items = OrderItem.query.filter_by(order_id=order.id).all()
            
            if not order_items:
                self.logger.warning(f"No order items found for order {order.order_id}")
                return
            
            # Find dealers in the MR's area
            if not order.mr or not order.mr.area:
                self.logger.warning(f"Order {order.order_id} missing MR or area information")
                return
            
            dealers_in_area = User.query.filter_by(
                role='distributor',
                area=order.mr.area
            ).all()
            
            if not dealers_in_area:
                self.logger.warning(f"No dealers found in area {order.mr.area} for order {order.order_id}")
                return
            
            dealer_unique_ids = [d.unique_id for d in dealers_in_area]
            
            # Process each order item
            for item in order_items:
                product_code = item.product_code
                # Use adjusted_quantity if available, otherwise use quantity
                quantity_to_move = item.adjusted_quantity if item.adjusted_quantity else item.quantity
                # Include FOC quantity
                foc_quantity = item.free_quantity or 0
                total_quantity_to_move = quantity_to_move + foc_quantity
                
                # Get all stock details with out_for_delivery quantity for this product
                from sqlalchemy import case
                stock_details = DealerWiseStockDetails.query.filter(
                    DealerWiseStockDetails.product_code == product_code,
                    DealerWiseStockDetails.status == 'confirmed',
                    DealerWiseStockDetails.dealer_unique_id.in_(dealer_unique_ids),
                    DealerWiseStockDetails.out_for_delivery_quantity > 0
                ).order_by(
                    case(
                        (DealerWiseStockDetails.expiry_date.is_(None), 1),
                        else_=0
                    ),
                    DealerWiseStockDetails.expiry_date.asc()
                ).all()
                
                remaining_quantity = total_quantity_to_move
                
                # Move out_for_delivery to sold using FEFO (earliest expiry first)
                for stock_detail in stock_details:
                    if remaining_quantity <= 0:
                        break
                    
                    out_for_delivery_in_this_stock = stock_detail.out_for_delivery_quantity
                    if out_for_delivery_in_this_stock <= 0:
                        continue
                    
                    # Calculate how much to move from this stock detail
                    quantity_to_move_from_stock = min(remaining_quantity, out_for_delivery_in_this_stock)
                    
                    # Move from out_for_delivery to sold
                    stock_detail.out_for_delivery_quantity -= quantity_to_move_from_stock
                    stock_detail.sold_quantity += quantity_to_move_from_stock
                    stock_detail.update_available_quantity()
                    
                    self.logger.info(
                        f"Moved {quantity_to_move_from_stock} units of {product_code} from out_for_delivery to sold "
                        f"(Stock ID: {stock_detail.id}, Dealer: {stock_detail.dealer_name}, "
                        f"Out for delivery now: {stock_detail.out_for_delivery_quantity}, Sold now: {stock_detail.sold_quantity}, "
                        f"Available now: {stock_detail.available_for_sale})"
                    )
                    
                    remaining_quantity -= quantity_to_move_from_stock
                
                if remaining_quantity > 0:
                    self.logger.warning(
                        f"Could only move {total_quantity_to_move - remaining_quantity} out of {total_quantity_to_move} units "
                        f"from out_for_delivery to sold for {product_code} (insufficient out_for_delivery quantity)"
                    )
            
            db.session.flush()  # Flush changes
            
        except Exception as e:
            self.logger.error(f"Error moving out_for_delivery to sold for order: {str(e)}")
            raise  # Raise error as this is critical for order completion
    
    def _move_blocked_to_sold_for_mr_order(self, user, cart_items):
        """
        Move blocked quantities to sold when MR confirms order
        Updates available_for_sale accordingly
        NOTE: This is kept for backward compatibility but should not be used for new orders
        New orders should use _move_blocked_to_out_for_delivery_for_mr_order
        """
        try:
            from app.models import DealerWiseStockDetails
            
            # Find dealers in the MR's area
            dealers_in_area = User.query.filter_by(
                role='distributor',
                area=user.area
            ).all()
            
            if not dealers_in_area:
                self.logger.warning(f"No dealers found in area {user.area} for MR {user.name}")
                return
            
            dealer_unique_ids = [d.unique_id for d in dealers_in_area]
            
            # Process each cart item
            for cart_item in cart_items:
                product_code = cart_item.product_code
                quantity_to_move = cart_item.quantity
                
                # Get all stock details with blocked quantity for this product
                # SQL Server doesn't support NULLS LAST, so we use CASE
                from sqlalchemy import case
                stock_details = DealerWiseStockDetails.query.filter(
                    DealerWiseStockDetails.product_code == product_code,
                    DealerWiseStockDetails.status == 'confirmed',
                    DealerWiseStockDetails.dealer_unique_id.in_(dealer_unique_ids),
                    DealerWiseStockDetails.blocked_quantity > 0
                ).order_by(
                    case(
                        (DealerWiseStockDetails.expiry_date.is_(None), 1),
                        else_=0
                    ),
                    DealerWiseStockDetails.expiry_date.asc()
                ).all()
                
                remaining_quantity = quantity_to_move
                
                # Move blocked to sold using FEFO (earliest expiry first)
                for stock_detail in stock_details:
                    if remaining_quantity <= 0:
                        break
                    
                    blocked_in_this_stock = stock_detail.blocked_quantity
                    if blocked_in_this_stock <= 0:
                        continue
                    
                    # Calculate how much to move from this stock detail
                    quantity_to_move_from_stock = min(remaining_quantity, blocked_in_this_stock)
                    
                    # Move from blocked to sold
                    stock_detail.blocked_quantity -= quantity_to_move_from_stock
                    stock_detail.sold_quantity += quantity_to_move_from_stock
                    stock_detail.update_available_quantity()
                    
                    self.logger.info(
                        f"Moved {quantity_to_move_from_stock} units of {product_code} from blocked to sold "
                        f"(Stock ID: {stock_detail.id}, Dealer: {stock_detail.dealer_name}, "
                        f"Blocked now: {stock_detail.blocked_quantity}, Sold now: {stock_detail.sold_quantity}, "
                        f"Available now: {stock_detail.available_for_sale})"
                    )
                    
                    remaining_quantity -= quantity_to_move_from_stock
                
                if remaining_quantity > 0:
                    self.logger.warning(
                        f"Could only move {quantity_to_move - remaining_quantity} out of {quantity_to_move} units "
                        f"from blocked to sold for {product_code} (insufficient blocked quantity)"
                    )
            
            db.session.flush()  # Flush changes
            
        except Exception as e:
            self.logger.error(f"Error moving blocked to sold for MR order: {str(e)}")
            # Don't raise - allow order to proceed even if this fails
    
    def _unblock_quantity_for_mr_order(self, user, product_code, quantity):
        """
        Unblock quantity in dealer_wise_stock_details when MR removes item from cart
        Uses FEFO (First Expiry First Out) to unblock from earliest expiring stock
        """
        try:
            from app.models import DealerWiseStockDetails
            
            # Find dealers in the MR's area
            dealers_in_area = User.query.filter_by(
                role='distributor',
                area=user.area
            ).all()
            
            if not dealers_in_area:
                self.logger.warning(f"No dealers found in area {user.area} for MR {user.name}")
                return
            
            dealer_unique_ids = [d.unique_id for d in dealers_in_area]
            remaining_quantity = quantity
            
            # Get all stock details with blocked quantity for this product
            # Ordered by expiration date (earliest first) for FEFO
            # SQL Server doesn't support NULLS LAST, so we use CASE
            from sqlalchemy import case
            stock_details = DealerWiseStockDetails.query.filter(
                DealerWiseStockDetails.product_code == product_code,
                DealerWiseStockDetails.status == 'confirmed',
                DealerWiseStockDetails.dealer_unique_id.in_(dealer_unique_ids),
                DealerWiseStockDetails.blocked_quantity > 0
            ).order_by(
                case(
                    (DealerWiseStockDetails.expiry_date.is_(None), 1),
                    else_=0
                ),
                DealerWiseStockDetails.expiry_date.asc()
            ).all()
            
            if not stock_details:
                self.logger.warning(f"No blocked stock found for {product_code} from dealers in area {user.area}")
                return
            
            # Unblock quantity using FEFO (earliest expiry first)
            for stock_detail in stock_details:
                if remaining_quantity <= 0:
                    break
                
                blocked_in_this_stock = stock_detail.blocked_quantity
                if blocked_in_this_stock <= 0:
                    continue
                
                # Calculate how much to unblock from this stock detail
                quantity_to_unblock = min(remaining_quantity, blocked_in_this_stock)
                
                # Unblock the quantity
                stock_detail.blocked_quantity -= quantity_to_unblock
                stock_detail.update_available_quantity()
                
                self.logger.info(
                    f"Unblocked {quantity_to_unblock} units of {product_code} from dealer {stock_detail.dealer_name} "
                    f"(Stock ID: {stock_detail.id}, Expiry: {stock_detail.expiry_date}, "
                    f"Blocked now: {stock_detail.blocked_quantity}, Available now: {stock_detail.available_for_sale})"
                )
                
                remaining_quantity -= quantity_to_unblock
            
            if remaining_quantity > 0:
                self.logger.warning(
                    f"Could only unblock {quantity - remaining_quantity} out of {quantity} units "
                    f"for {product_code} (insufficient blocked quantity in dealer_wise_stock_details)"
                )
            
            db.session.flush()  # Flush changes but don't commit yet (will be committed with order confirmation)
            # Note: Commit is handled by the calling function (confirm_order_by_distributor)
            
        except Exception as e:
            self.logger.error(f"Error unblocking quantity for MR order: {str(e)}")
            # Don't raise - allow removal to proceed even if unblocking fails
