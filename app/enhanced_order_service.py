import logging
from datetime import datetime
from flask import current_app
from app import db
from app.models import Order, OrderItem, Product, User, CartItem, DealerWiseStockDetails, Customer, FOC
from app.database_service import DatabaseService
from app.pricing_service import PricingService
from app.llm_order_service import LLMOrderService
from app.email_utils import send_email

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class EnhancedOrderService:
    """Enhanced order service for RB (Powered by Quantum Blue AI) workflow"""
    
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
                        response_message += f"• {item['product_name']} - Qty: {item['quantity']} - ${item['total_price']:.2f}\n"
                
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
                            response_message += f"• {item['product_name']} - Qty: {item['quantity']} - ${item['total_price']:.2f}\n"
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
    
    def place_order(self, user_id, placed_by_user_id=None, customer_id=None):
        """
        Place order from cart with distributor notification workflow
        Includes customer details for MR orders
        """
        try:
            from app.models import Customer
            
            # Get user and cart items
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
            
            # Get customer details if MR and customer_id is provided
            customer = None
            if user.role == 'mr' and customer_id:
                customer = Customer.query.get(customer_id)
                if not customer or customer.mr_unique_id != user.unique_id:
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
                
                # For MRs, check stock from dealer_wise_stock_details
                # For other users, check Product table
                if user.role == 'mr' and user.area:
                    # Find dealers in the MR's area
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
                else:
                    # For non-MRs (distributors), stock info not applicable
                    # Distributors don't place orders through this system
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
                            user_email=user.email
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
            order = Order(
                mr_id=user_id,
                mr_unique_id=user.unique_id,
                status='pending',
                order_stage='placed'
            )
            
            # Add customer details if MR order
            if customer:
                order.customer_id = customer.id
                order.customer_unique_id = customer.unique_id
            
            order.generate_order_id()
            db.session.add(order)
            db.session.commit()
            
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
                    order_item = OrderItem(
                        order_id=order.id,
                        product_id=cart_item.product_id,
                        product_code=cart_item.product_code,
                        product_name=cart_item.product_name,
                        quantity=cart_item.quantity,  # Paid quantity
                        free_quantity=free_quantity,  # FOC quantity
                        unit_price=sales_price,
                        total_price=total_price
                    )
                    db.session.add(order_item)
                    
                    subtotal += total_price
                    
                    # Block quantity in dealer stock using FEFO (First Expiry, First Out)
                    if user.role == 'mr' and user.area:
                        # Block quantity in dealer_wise_stock_details
                        success = self._block_quantity_for_mr_order(
                            user=user,
                            product_code=cart_item.product_code,
                            quantity=cart_item.quantity
                        )
                        
                        if not success:
                            self.logger.error(f"Failed to block quantity for {cart_item.product_code}")
                            raise Exception(f"Failed to block quantity for {cart_item.product_code}")
                        
                        self.logger.info(f"Successfully blocked {cart_item.quantity} units of {cart_item.product_code} in dealer stock")
            
            # Calculate tax (5%) and update order totals
            tax_rate = 0.05  # 5% tax
            tax_amount = subtotal * tax_rate
            grand_total = subtotal + tax_amount
            
            # Store subtotal, tax, and grand total
            order.subtotal = subtotal
            order.tax_amount = tax_amount
            order.tax_rate = tax_rate
            order.total_amount = grand_total  # Grand total includes tax
            
            # For MR orders, status should be 'pending' until dealer confirms
            # For other users, status can be 'in_transit' after distributor notification
            if user.role == 'mr':
                order.status = 'pending'  # MR orders start as pending until dealer confirms
                order.order_stage = 'placed'  # Order is placed, waiting for dealer confirmation
            else:
                order.status = 'in_transit'  # First stage: in transit
                order.order_stage = 'distributor_notified'
            
            # NOTE: Stock is now BLOCKED (not sold yet)
            # It will move from blocked to sold when dealer confirms the order
            
            db.session.commit()
            
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
                        user_email=user.email
                    )
                    if pending_order:
                        pending_products_created.append(pending_order)
            
            # Generate order summary using valid cart items only (before clearing)
            order_summary = self.llm_service.generate_order_summary(valid_cart_items, user)

            # Clear cart
            self.db_service.clear_cart(user_id)
            
            # Notify distributor (include expired products info)
            self._notify_distributor(order, placed_by_user, expired_products_info)
            
            # Generate enhanced confirmation message
            from datetime import datetime
            
            # Get order items details from stored valid_items_details (already calculated)
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
                status_message = f"Your order is currently in the **{stage_display}** stage with status **{status_display}**. The distributor has been notified and will process your order shortly."
            
            confirmation_message = f"""🎉 **Order Placed Successfully!**

**📋 Order Details:**
• **Order ID:** {order.order_id}
• **Order Date:** {order_date_str}
• **Status:** {status_display}
• **Area:** {order.mr.area if order.mr else 'N/A'}
• **Total Items:** {total_items} units

**🛍️ Order Items:**

| Product | Code | Quantity | FOC | Total Qty | Unit Price | Total |
|---------|------|----------|-----|-----------|------------|-------|
"""
            for item in order_items_details:
                # Show FOC in separate column
                paid_qty = item['quantity']
                free_qty = item['free_quantity']
                total_qty = item['total_quantity']
                confirmation_message += f"| {item['name']} | {item['code']} | {paid_qty} | +{free_qty} | **{total_qty}** | ${item['unit_price']:,.2f} | ${item['total']:,.2f} |\n"
            
            confirmation_message += f"""
**💰 Payment Summary:**
• **Subtotal:** ${order.subtotal:,.2f}
• **Tax (5%):** ${order.tax_amount:,.2f}
• **Grand Total:** ${order.total_amount:,.2f}

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
            db.session.rollback()
            return {
                'success': False,
                'message': f"Error placing order: {str(e)}"
            }
    
    def confirm_order_by_distributor(self, order_id, distributor_user_id):
        """
        Confirm order by distributor and generate invoice
        """
        try:
            order = Order.query.filter_by(order_id=order_id).first()
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
            if order.mr.area != distributor.area:
                return {
                    'success': False,
                    'message': "This order doesn't belong to your area."
                }
            # Update order status
            order.distributor_confirmed_at = datetime.utcnow()
            order.distributor_confirmed_by = distributor_user_id
            order.status = 'confirmed'
            order.order_stage = 'confirmed'
            
            # Move blocked quantities to sold when dealer confirms
            # This is where stock transitions from blocked -> sold
            if order.mr and order.mr.area:
                # Get order items to move blocked to sold
                order_items = OrderItem.query.filter_by(order_id=order.id).all()
                # Convert to cart-like items for the method
                cart_like_items = []
                for item in order_items:
                    # Create a simple object with the needed attributes
                    class CartLikeItem:
                        def __init__(self, product_code, quantity):
                            self.product_code = product_code
                            self.quantity = quantity
                    cart_like_items.append(CartLikeItem(item.product_code, item.quantity))
                
                self._move_blocked_to_sold_for_mr_order(order.mr, cart_like_items)
            
            db.session.commit()
            
            # Generate invoice (for records only - not stored in Order model)
            invoice_number = self._generate_invoice(order)

            # Send enhanced confirmation email to MR or customer
            mr = User.query.get(order.mr_id)
            admin_email = current_app.config.get('ADMIN_EMAIL') if current_app else None
            order_items_list = OrderItem.query.filter_by(order_id=order.id).all()
            
            # Build items table with FOC
            table = """<table style='border-collapse:collapse; width:100%; margin:20px 0;'>
                <thead><tr style='background:#3b82f6; color:white;'>
                    <th style='padding:12px; text-align:left;'>Product</th>
                    <th style='padding:12px; text-align:center;'>Qty</th>
                    <th style='padding:12px; text-align:center;'>FOC</th>
                    <th style='padding:12px; text-align:right;'>Unit Price</th>
                    <th style='padding:12px; text-align:right;'>Total</th>
                </tr></thead><tbody>"""
            for item in order_items_list:
                quantity = item.quantity or 0
                foc_qty = item.free_quantity or 0
                foc_display = f"<strong>+{foc_qty}</strong>" if foc_qty > 0 else "-"
                table += f"""<tr style='border-bottom:1px solid #e5e7eb;'>
                    <td style='padding:10px;'>{item.product.product_name} ({item.product_code})</td>
                    <td style='padding:10px; text-align:center;'>{quantity}</td>
                    <td style='padding:10px; text-align:center; color:#10b981;'>{foc_display}</td>
                    <td style='padding:10px; text-align:right;'>${item.unit_price:,.2f}</td>
                    <td style='padding:10px; text-align:right;'>${item.total_price:,.2f}</td>
                </tr>"""
            table += "</tbody></table>"
            
            # Tax information
            tax_html = ""
            if hasattr(order, 'subtotal') and order.subtotal:
                tax_html = f"""
                    <div class='success-box'>
                        <h3 style='margin-top: 0; color: #059669;'>💰 Payment Summary</h3>
                        <p style='margin: 5px 0;'><strong>Subtotal:</strong> ${order.subtotal:,.2f}</p>
                        <p style='margin: 5px 0;'><strong>Tax (5%):</strong> ${order.tax_amount:,.2f}</p>
                        <p style='margin: 5px 0; font-size: 1.2em;'><strong>Grand Total:</strong> ${order.total_amount:,.2f}</p>
                    </div>
                """
            else:
                tax_html = f"<p style='font-size:1.2em;'><strong>Total Amount:</strong> ${order.total_amount:,.2f}</p>"
            
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
                send_email(mr.email, f"✅ Your order {order.order_id} has been confirmed!", email_html, 'order_confirmed_customer')
            send_email(distributor.email, f"Order {order.order_id} confirmed for fulfillment", email_html, 'order_confirmed_distributor')
            if admin_email:
                send_email(admin_email, f"[Admin] Order {order.order_id} confirmed", email_html, 'order_confirmed_admin')

            return {
                'success': True,
                'message': f"Order {order_id} confirmed and invoice generated",
                'invoice_number': invoice_number
            }
        except Exception as e:
            self.logger.error(f"Error confirming order: {str(e)}")
            db.session.rollback()
            return {
                'success': False,
                'message': f"Error confirming order: {str(e)}"
            }
    
    def reject_order_by_distributor(self, order_id, distributor_user_id, rejection_reason=None):
        """
        Reject order by distributor and unblock stock
        """
        try:
            order = Order.query.filter_by(order_id=order_id).first()
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
            
            if order.mr.area != distributor.area:
                return {
                    'success': False,
                    'message': "This order doesn't belong to your area."
                }
            
            # Update order status
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
            
            db.session.commit()
            
            # Send rejection notification to MR with enhanced template
            mr = User.query.get(order.mr_id)
            if mr:
                reason_text = f"<strong>Reason:</strong> {rejection_reason}" if rejection_reason else "No specific reason was provided."
                
                content = f"""
                    <h2 style='color:#dc3545; margin-top:0;'>❌ Order Rejected</h2>
                    <p>Dear <strong>{mr.name}</strong>,</p>
                    <p>We regret to inform you that your order <strong>{order.order_id}</strong> has been rejected by distributor <strong>{distributor.name}</strong>.</p>
                    
                    <div class='warning-box'>
                        <h3 style='margin-top: 0;'>Rejection Details</h3>
                        <p style='margin: 5px 0;'>{reason_text}</p>
                        <p style='margin: 5px 0;'><strong>Order ID:</strong> {order.order_id}</p>
                        <p style='margin: 5px 0;'><strong>Date:</strong> {order.created_at.strftime('%B %d, %Y at %I:%M %p')}</p>
                    </div>
                    
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
                
                send_email(mr.email, f"❌ Order {order.order_id} - Rejected", email_html, 'order_rejected')
            
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
            order = Order.query.filter_by(order_id=order_id).first()
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
        if order.mr.area != distributor.area:
            return {
                'success': False,
                'message': "This order doesn't belong to your area."
            }
        # Compose table
        items = []
        for item in order.order_items:
            quantity = item.quantity or 0
            items.append({
                'product_code': item.product_code,
                'product_name': item.product.product_name,
                'quantity': quantity,
                'unit_price': item.unit_price,
                'total_price': item.total_price
            })
        table = "| Product | Quantity | Unit Price | Total |\n|--------|---------|-----------|-------|\n"
        for row in items:
            table += f"| {row['product_name']} ({row['product_code']}) | {row['quantity']} | ${row['unit_price']} | ${row['total_price']} |\n"
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
            # --- Table ---
            table = """
            <table style='width:100%;border-collapse:collapse;margin-bottom:16px;'>
                <tr style='background:#175DDC;color:white;'><th>PRODUCT</th><th>QUANTITY</th><th>UNIT PRICE</th><th>TOTAL</th></tr>
            """
            for item in order_items:
                quantity = item.quantity or 0
                table += f"<tr style='background:#f7f8fa;'><td>{item.product.product_name} ({item.product_code})</td><td>{quantity}</td><td>${item.unit_price}</td><td>${item.total_price}</td></tr>"
            table += "</table>"
            # --- LLM summary ---
            llm = self.llm_service.groq_service.client if hasattr(self.llm_service, 'groq_service') else None
            user_block = f"<b>Order Placed By:</b> {placed_by_user.name} ({placed_by_user.role}) — {placed_by_user.email}<br>Phone: {placed_by_user.phone}" if placed_by_user else ''
            summary = ""
            if llm:
                prompt = f"You are an AI assistant at Quantum Blue. Summarize the following order for a distributor, focusing on clarity, shipment urgency, and next steps.\nOrder ID: {order.order_id}\nCustomer: {placed_by_user.name}\nTotal: ${order.total_amount}\nArea: {order.mr.area if order.mr else 'N/A'}.\nSay: 'Please confirm or discuss changes/next steps.'\nKeep it one concise, friendly paragraph."
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
                        <p style='margin: 5px 0;'><strong>Subtotal:</strong> ${order.subtotal:,.2f}</p>
                        <p style='margin: 5px 0;'><strong>Tax (5%):</strong> ${order.tax_amount:,.2f}</p>
                        <p style='margin: 5px 0; font-size: 1.2em;'><strong>Grand Total:</strong> ${order.total_amount:,.2f}</p>
                    </div>
                """
            else:
                tax_html = f"<div style='margin-top:10px; font-size:1.2em;'><b>Order Total:</b> ${order.total_amount:,.2f}</div>"
            
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
                'distributor_notification'
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
            # Get order details
            order_items = []
            for item in order.order_items:
                order_items.append({
                    'product_code': item.product_code,
                    'product_name': item.product.product_name,
                    'quantity': item.quantity,
                    'unit_price': item.unit_price,
                    'total_price': item.total_price
                })
            
            # Email to customer
            customer = User.query.get(order.mr_id)
            if customer:
                subject = f"Invoice Generated - Order {order.order_id}"
                html_content = self._generate_invoice_html(order, order_items, customer, distributor)
                send_email(customer.email, subject, html_content, 'invoice_customer')
            
            # Email to distributor
            if distributor:
                subject = f"Invoice Copy - Order {order.order_id}"
                html_content = self._generate_invoice_html(order, order_items, customer, distributor, is_distributor=True)
                send_email(distributor.email, subject, html_content, 'invoice_distributor')
            
            # Email to company
            admin_email = current_app.config.get('ADMIN_EMAIL')
            if admin_email:
                subject = f"Order Invoice - {order.order_id}"
                html_content = self._generate_invoice_html(order, order_items, customer, distributor, is_admin=True)
                send_email(admin_email, subject, html_content, 'invoice_admin')
            
            self.logger.info(f"Invoice emails sent for order {order.order_id}")
            
        except Exception as e:
            self.logger.error(f"Error sending invoice emails: {str(e)}")
    
    def _generate_invoice_html(self, order, order_items, customer, distributor, is_distributor=False, is_admin=False):
        """Generate HTML invoice content"""
        recipient = "Distributor" if is_distributor else ("Admin" if is_admin else "Customer")
        
        items_html = ""
        for item in order_items:
            items_html += f"""
            <tr>
                <td>{item['product_code']}</td>
                <td>{item['product_name']}</td>
                <td>{item['quantity']}</td>
                <td>${item['unit_price']:.2f}</td>
                <td>${item['total_price']:.2f}</td>
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
                    <p>RB (Powered by Quantum Blue AI)</p>
                </div>
                
                <div class="content">
                    <h2>Order Confirmation</h2>
                    <div class="invoice-details">
                        <p><strong>Invoice Number:</strong> {invoice_number}</p>
                        <p><strong>Order ID:</strong> {order.order_id}</p>
                        <p><strong>Date:</strong> {order.created_at.strftime('%Y-%m-%d %H:%M:%S')}</p>
                        <p><strong>Status:</strong> {order.status.title()}</p>
                        <p><strong>Area:</strong> {order.mr.area if order.mr else 'N/A'}</p>
                        <p><strong>Customer:</strong> {customer.name if customer else 'N/A'}</p>
                        <p><strong>Distributor:</strong> {distributor.name if distributor else 'N/A'}</p>
                    </div>
                    
                    <h3>Order Items</h3>
                    <table>
                        <thead>
                            <tr>
                                <th>Product Code</th>
                                <th>Product Name</th>
                                <th>Quantity</th>
                                <th>Unit Price</th>
                                <th>Total</th>
                            </tr>
                        </thead>
                        <tbody>
                            {items_html}
                        </tbody>
                    </table>
                    
                    <div class="total">
                        <p><strong>Total Amount: ${order.total_amount:.2f}</strong></p>
                    </div>
                    
                    <div class="footer">
                        <p>This invoice has been automatically generated by RB (Powered by Quantum Blue AI) system.</p>
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
    
    def _move_blocked_to_sold_for_mr_order(self, user, cart_items):
        """
        Move blocked quantities to sold when MR confirms order
        Updates available_for_sale accordingly
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
            
            db.session.flush()  # Flush changes
            db.session.commit()  # Commit unblocking
            
        except Exception as e:
            self.logger.error(f"Error unblocking quantity for MR order: {str(e)}")
            # Don't raise - allow removal to proceed even if unblocking fails
