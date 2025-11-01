import logging
from datetime import datetime
from flask import current_app
from app import db
from app.models import Order, OrderItem, Product, User, CartItem
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
            
            # Get user's warehouse
            warehouse = None
            if user.nearest_warehouse:
                warehouse = self.db_service.get_warehouse_by_location(user.nearest_warehouse)
            
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
                
                # Find product - search in user's warehouse first, then globally
                product = None
                if warehouse:
                    product = self.db_service.get_product_by_code_and_warehouse(product_code, warehouse.id)
                
                if not product:
                    # Fallback to global search
                    product = self.db_service.get_product_by_code(product_code)
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
                # Check availability across all batches using FEFO logic
                total_available = 0
                if warehouse:
                    # Get all batches for this product in the warehouse
                    all_batches = Product.query.filter_by(
                        product_code=product_code,
                        warehouse_id=warehouse.id,
                        is_active=True
                    ).all()
                    
                    total_available = sum(batch.available_for_sale for batch in all_batches if batch.available_for_sale > 0)
                else:
                    # Fallback to single product check
                    total_available = product.available_for_sale
                
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
                cart_item, message = self.db_service.add_to_cart(
                    user_id, 
                    product.id, 
                    quantity, 
                    {
                        'base_price': pricing['base_price'],
                        'discount_amount': pricing['discount']['amount'],
                        'scheme_discount_amount': 0,  # Will be calculated by scheme
                        'final_price': pricing['pricing']['final_price'],
                        'scheme_name': pricing['scheme']['name'],
                        'free_quantity': pricing['scheme']['free_quantity'],
                        'paid_quantity': pricing['scheme']['paid_quantity']
                    }
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
    
    def place_order(self, user_id, placed_by_user_id=None):
        """
        Place order from cart with distributor notification workflow
        """
        try:
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
            
            # Get warehouse
            warehouse = self.db_service.get_warehouse_by_location(user.nearest_warehouse)
            if not warehouse:
                return {
                    'success': False,
                    'message': "Warehouse not found for your location"
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
                today = date.today()
                
                # Get all batches of this product in the warehouse
                all_batches = Product.query.filter_by(
                    product_code=cart_item.product_code,
                    warehouse_id=warehouse.id,
                    is_active=True
                ).all()
                
                # Check if any non-expired batches exist
                non_expired_batches = [b for b in all_batches if not b.expiry_date or b.expiry_date >= today]
                expired_batches = [b for b in all_batches if b.expiry_date and b.expiry_date < today]
                
                # Calculate available quantities
                non_expired_qty = sum(b.available_for_sale for b in non_expired_batches)
                expired_qty = sum(b.available_for_sale for b in expired_batches)
                
                # Check three scenarios:
                # 1. Has both expired and non-expired but not enough total - treat as expired
                # 2. Has only non-expired but insufficient quantity - treat as expired (insufficient stock)
                # 3. Has enough non-expired stock - add to valid
                
                if non_expired_qty < cart_item.product_quantity:
                    # Not enough non-expired stock - treat as expired/insufficient
                    expired_cart_items.append(cart_item)
                    
                    # Track info for notification
                    product_name = product.product_name if product else cart_item.product_code
                    
                    expired_info = {
                        'product_code': cart_item.product_code,
                        'product_name': product_name,
                        'expired_batches': [],
                        'available_qty': non_expired_qty,
                        'requested_qty': cart_item.product_quantity,
                        'reason': 'expired' if expired_batches else 'insufficient_stock'
                    }
                    
                    # Track expired batches if any
                    for batch in expired_batches:
                        if batch.available_for_sale > 0:
                            days_expired = (today - batch.expiry_date).days if batch.expiry_date else 0
                            
                            expired_info['expired_batches'].append({
                                'batch_number': batch.batch_number or 'N/A',
                                'quantity': batch.available_for_sale,
                                'expiry_date': batch.expiry_date.isoformat() if batch.expiry_date else None,
                                'days_expired': days_expired
                            })
                    
                    # Always add to expired_products_info for notification
                    expired_products_info.append(expired_info)
                    
                    # Log the issue
                    if expired_batches:
                        self.logger.warning(f"⚠️ EXPIRED/INSUFFICIENT PRODUCT: {cart_item.product_code} - Requested: {cart_item.product_quantity}, Non-expired available: {non_expired_qty}, Expired available: {expired_qty}, creating pending order")
                    else:
                        self.logger.warning(f"⚠️ INSUFFICIENT STOCK: {cart_item.product_code} - Requested: {cart_item.product_quantity}, Available: {non_expired_qty}, creating pending order")
                else:
                    # Has enough non-expired stock - add to valid list
                    valid_cart_items.append(cart_item)
                    
                    # Still track any expired batches for notification
                    if expired_batches:
                        expired_batches_info = []
                        for batch in expired_batches:
                            if batch.available_for_sale > 0:
                                expired_batches_info.append({
                                    'batch_number': batch.batch_number or 'N/A',
                                    'quantity': batch.available_for_sale,
                                    'expiry_date': batch.expiry_date.isoformat() if batch.expiry_date else None,
                                    'days_expired': (today - batch.expiry_date).days if batch.expiry_date else 0
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
                            'quantity': expired_item.product_quantity,
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
                            requested_quantity=expired_item.product_quantity,
                            user_id=user.id,
                            user_email=user.email,
                            warehouse_id=warehouse.id,
                            warehouse_location=warehouse.location_name
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
                user_id=user_id,
                warehouse_id=warehouse.id,
                warehouse_location=user.nearest_warehouse,
                user_email=user.email,
                placed_by=placed_by_user.user_type,
                placed_by_user_id=placed_by_user.id,
                status='pending',
                order_stage='placed'
            )
            order.generate_order_id()
            db.session.add(order)
            db.session.commit()
            
            # Add order items and calculate totals only for valid cart items
            subtotal = 0
            discount_total = 0
            scheme_discount_total = 0
            
            for cart_item in valid_cart_items:
                # Calculate final pricing
                pricing = self.pricing_service.calculate_product_pricing(
                    cart_item.product_id, 
                    cart_item.product_quantity
                )
                
                if 'error' not in pricing:
                    # Create order item
                    order_item = OrderItem(
                    order_id=order.id,
                        product_id=cart_item.product_id,
                        product_code=cart_item.product_code,
                        product_quantity_ordered=cart_item.product_quantity,
                        unit_price=cart_item.unit_price,
                        total_price=pricing['pricing']['total_amount'],
                        base_price=pricing['base_price'],
                        discount_amount=pricing['discount']['amount'],
                        scheme_discount_amount=0,  # Will be calculated
                        final_price=pricing['pricing']['final_price'],
                        scheme_applied=pricing['scheme']['name'],
                        free_quantity=pricing['scheme']['free_quantity'],
                        paid_quantity=pricing['scheme']['paid_quantity']
                    )
                    db.session.add(order_item)
                    
                    subtotal += pricing['pricing']['total_amount']
                    discount_total += (pricing['base_price'] * pricing['scheme']['paid_quantity']) - pricing['pricing']['total_amount']
                    
                    # Allocate quantity using FEFO (First Expiry, First Out) logic
                    product = Product.query.get(cart_item.product_id)
                    if product:
                        # First try user's warehouse
                        allocations, allocation_message = self.db_service.allocate_quantity_fefo(
                            product_code=cart_item.product_code,
                            warehouse_id=warehouse.id,
                            quantity_to_allocate=cart_item.product_quantity
                        )
                        
                        # If not found in user's warehouse, try the product's actual warehouse
                        if not allocations and product.warehouse_id != warehouse.id:
                            self.logger.warning(f"Product {cart_item.product_code} not in user's warehouse ({warehouse.id}), trying product's warehouse ({product.warehouse_id})")
                            allocations, allocation_message = self.db_service.allocate_quantity_fefo(
                                product_code=cart_item.product_code,
                                warehouse_id=product.warehouse_id,
                                quantity_to_allocate=cart_item.product_quantity
                            )
                            
                            if allocations:
                                self.logger.info(f"✓ Successfully allocated from product's warehouse ({product.warehouse_id}) instead of user's warehouse ({warehouse.id})")
                        
                        if not allocations:
                            self.logger.error(f"FEFO allocation failed for {cart_item.product_code}: {allocation_message}")
                            raise Exception(f"Failed to allocate products: {allocation_message}")
                        
                        # Log allocation details
                        batch_info = ", ".join([
                            f"Batch {alloc['batch_number']} ({alloc['quantity']} units, expires: {alloc['expiry_date']})"
                            for alloc in allocations
                        ])
                        self.logger.info(f"FEFO allocation for {cart_item.product_code}: {batch_info}")
            
            # Update order totals
            # Note: subtotal already contains the final pricing (with discounts applied)
            order.subtotal_amount = subtotal
            order.discount_amount = discount_total
            order.scheme_discount_amount = scheme_discount_total
            # Total amount is just the subtotal (discounts already applied in pricing calculation)
            order.total_amount = subtotal
            order.status = 'in_transit'  # First stage: in transit
            order.order_stage = 'distributor_notified'
            
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
                        'quantity': expired_item.product_quantity,
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
                        cart_item.product_quantity
                    )
                    if 'error' not in pricing:
                        valid_items_details.append({
                            'name': product.product_name,
                            'code': cart_item.product_code,
                            'quantity': cart_item.product_quantity,
                            'free': pricing['scheme']['free_quantity'],
                            'unit_price': pricing['pricing']['final_price'],
                            'total': pricing['pricing']['total_amount'],
                            'scheme': pricing['scheme']['name']
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
                        requested_quantity=expired_item.product_quantity,
                        user_id=user.id,
                        user_email=user.email,
                        warehouse_id=warehouse.id,
                        warehouse_location=warehouse.location_name
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
            # Total items should include both paid and free quantities
            total_items = sum(item['quantity'] + item.get('free', 0) for item in valid_items_details)
            
            # Format order date
            order_date_str = order.order_date.strftime('%B %d, %Y at %I:%M %p') if order.order_date else datetime.now().strftime('%B %d, %Y at %I:%M %p')
            
            # Build enhanced confirmation message
            confirmation_message = f"""🎉 **Order Placed Successfully!**

**📋 Order Details:**
• **Order ID:** {order.order_id}
• **Order Date:** {order_date_str}
• **Total Amount:** ${order.total_amount:,.2f}
• **Subtotal:** ${order.subtotal_amount:,.2f}
• **Total Discounts:** ${order.discount_amount + order.scheme_discount_amount:,.2f}
• **Status:** {order.status.replace('_', ' ').title()}
• **Order Stage:** {order.order_stage.replace('_', ' ').title()}
• **Warehouse:** {order.warehouse_location}
• **Total Items:** {total_items} units

**🛍️ Order Items:**
"""
            for item in order_items_details:
                qty_display = f"{item['quantity']} + {item['free']} free" if item['free'] > 0 else str(item['quantity'])
                confirmation_message += f"• **{item['name']} ({item['code']})**: {qty_display} units @ ${item['unit_price']:,.2f} each\n"
                confirmation_message += f"  Scheme: {item['scheme']} | Item Total: ${item['total']:,.2f}\n\n"
            
            confirmation_message += f"""**💰 Financial Summary:**
• Subtotal: ${order.subtotal_amount:,.2f}
• Discounts: ${order.discount_amount:,.2f}
• Scheme Savings: ${order.scheme_discount_amount:,.2f}
• **Final Total: ${order.total_amount:,.2f}**

**📊 Current Status:**
Your order is currently in the **"{order.order_stage.replace('_', ' ').title()}"** stage with status **"{order.status.replace('_', ' ').title()}"**. The distributor has been notified and will confirm your order shortly.

**📧 Email Confirmation:**
A detailed order confirmation has been sent to {user.email}. Please check your inbox for complete order information and tracking details.
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
These products will be automatically ordered when new stock arrives, and you'll receive an email notification. Your order ID for tracking is: **{order.order_id}**.

"""
            
            confirmation_message += """**🚀 What's Next?**
• You'll receive email updates as your order progresses through each stage
• Use Order ID **{order.order_id}** to track your order anytime
• Our team will process your order within 24 hours
• Expected delivery: 3-5 business days from confirmation
• For any questions, please contact support with your Order ID

**💎 Thank you for choosing Quantum Blue!**
We're excited to deliver cutting-edge technology to you."""
            
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
            if not distributor or distributor.user_type != 'distributor':
                return {
                    'success': False,
                    'message': "Invalid distributor"
                }
            if order.warehouse_location != distributor.nearest_warehouse:
                return {
                    'success': False,
                    'message': "This order doesn't belong to your warehouse."
                }
            # Update order status
            order.distributor_confirmed = True
            order.distributor_confirmed_at = datetime.utcnow()
            order.distributor_confirmed_by = distributor_user_id
            order.status = 'confirmed'
            order.order_stage = 'distributor_confirmed'
            # Move blocked quantities to confirmed
            order_items = OrderItem.query.filter_by(order_id=order.id).all()
            for item in order_items:
                product = Product.query.get(item.product_id)
                if product:
                    product.confirmed_quantity += item.product_quantity_ordered
                    product.blocked_quantity -= item.product_quantity_ordered
                    product.available_for_sale = product.product_quantity - product.blocked_quantity - product.confirmed_quantity
            db.session.commit()
            # Generate invoice
            invoice_number = self._generate_invoice(order)
            order.invoice_generated = True
            order.invoice_generated_at = datetime.utcnow()
            order.invoice_number = invoice_number
            order.order_stage = 'invoice_generated'
            db.session.commit()

            # Send enhanced confirmation email to MR or customer
            mr = User.query.get(order.user_id)
            admin_email = current_app.config.get('ADMIN_EMAIL') if current_app else None
            order_items_list = OrderItem.query.filter_by(order_id=order.id).all()
            table = """<table style='border-collapse:collapse; width:100%;'><tr style='background:#f2f2f2;'><th>Product</th><th>Quantity</th><th>Unit Price</th><th>Discount</th><th>Scheme</th><th>Total</th></tr>"""
            for item in order_items_list:
                paid = item.paid_quantity or (item.product_quantity_ordered or 0)
                free = item.free_quantity or 0
                q_s = f"{paid} + {free} = {paid + free}" if free else str(paid)
                table += f"<tr><td>{item.product.product_name} ({item.product_code})</td><td>{q_s}</td><td>${item.unit_price}</td><td>${item.discount_amount}</td><td>{item.scheme_applied}</td><td>${item.total_price}</td></tr>"
            table += "</table>"
            email_body = f"""
                <h2 style='color:#175DDC;'>Order Confirmed by Distributor</h2>
                <p>Dear {mr.name},</p>
                <p>Your order <b>{order.order_id}</b> has been <b>confirmed</b> by distributor <b>{distributor.name}</b> ({distributor.email}, {distributor.phone}).</p>
                <p><b>Order Details:</b><br>
                   Date: {order.order_date.strftime('%Y-%m-%d %H:%M:%S')}<br>
                   Warehouse: {order.warehouse_location}<br>
                   Status: <b>Confirmed</b>
                </p>
                {table}
                <p><b>Total Amount:</b> ${order.total_amount}</p>
                <p>If you have questions, reply to this email or contact your distributor above directly.</p>
                <p style='color:#686262;font-size:13px;'>Thank you for choosing Quantum Blue!</p>
            """
            if mr:
                send_email(mr.email, f"Your order {order.order_id} has been confirmed!", email_body, 'order_confirmed_customer')
            send_email(distributor.email, f"Order {order.order_id} confirmed for fulfillment", email_body, 'order_confirmed_distributor')
            if admin_email:
                send_email(admin_email, f"Order {order.order_id} confirmed (system copy)", email_body, 'order_confirmed_admin')

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
            if user_id and order.user_id != user_id:
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
                    'quantity': item.product_quantity_ordered,
                    'unit_price': item.unit_price,
                    'total_price': item.total_price,
                    'discount_amount': item.discount_amount,
                    'scheme_applied': item.scheme_applied,
                    'free_quantity': item.free_quantity,
                    'paid_quantity': item.paid_quantity
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
            
            return {
                'success': True,
                'order': {
                    'order_id': order.order_id,
                    'status': order.status,
                    'order_stage': order.order_stage,
                    'total_amount': order.total_amount,
                    'subtotal_amount': order.subtotal_amount,
                    'discount_amount': order.discount_amount,
                    'scheme_discount_amount': order.scheme_discount_amount,
                    'order_date': order.order_date.isoformat(),
                    'warehouse_location': order.warehouse_location,
                    'placed_by': order.placed_by,
                    'distributor_confirmed': order.distributor_confirmed,
                    'distributor_confirmed_at': order.distributor_confirmed_at.isoformat() if order.distributor_confirmed_at else None,
                    'invoice_generated': order.invoice_generated,
                    'invoice_number': order.invoice_number,
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
        if not distributor or distributor.user_type != "distributor":
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
        if order.warehouse_location != distributor.nearest_warehouse:
            return {
                'success': False,
                'message': "This order doesn't belong to your warehouse."
            }
        # Compose table
        items = []
        for item in order.order_items:
            paid = item.paid_quantity or (item.product_quantity_ordered or 0)
            free = item.free_quantity or 0
            items.append({
                'product_code': item.product_code,
                'product_name': item.product.product_name,
                'quantity': f"{paid} + {free} = {paid + free}",
                'unit_price': item.unit_price,
                'total_price': item.total_price,
                'scheme_applied': item.scheme_applied,
                'discount_amount': item.discount_amount,
            })
        table = "| Product | Quantity | Unit Price | Discount | Scheme | Total |\n|--------|---------|-----------|----------|--------|-------|\n"
        for row in items:
            table += f"| {row['product_name']} ({row['product_code']}) | {row['quantity']} | ${row['unit_price']} | ${row['discount_amount']} | {row['scheme_applied']} | ${row['total_price']} |\n"
        status = order.status
        
        summary = f"**Order ID:** {order.order_id}\n**Status:** {status}\n**Placed By:** {order.user.name} ({order.user.user_type})\n\n" + table
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
                if dist.nearest_warehouse == order.warehouse_location:
                    distributor = dist
                    break
            if not distributor:
                self.logger.warning(f"No distributor found for warehouse {order.warehouse_location}")
                return
            order_items = OrderItem.query.filter_by(order_id=order.id).all()
            # --- Table ---
            table = """
            <table style='width:100%;border-collapse:collapse;margin-bottom:16px;'>
                <tr style='background:#175DDC;color:white;'><th>PRODUCT</th><th>QUANTITY</th><th>UNIT PRICE</th><th>DISCOUNT</th><th>SCHEME</th><th>TOTAL</th></tr>
            """
            for item in order_items:
                paid = item.paid_quantity or item.product_quantity_ordered or 0
                free = item.free_quantity or 0
                q_s = f"{paid} + {free} = {paid + free}" if free else str(paid)
                table += f"<tr style='background:#f7f8fa;'><td>{item.product.product_name} ({item.product_code})</td><td>{q_s}</td><td>${item.unit_price}</td><td>${item.discount_amount}</td><td>{item.scheme_applied}</td><td>${item.total_price}</td></tr>"
            table += "</table>"
            # --- LLM summary ---
            llm = self.llm_service.groq_service.client if hasattr(self.llm_service, 'groq_service') else None
            user_block = f"<b>Order Placed By:</b> {placed_by_user.name} ({placed_by_user.user_type}) — {placed_by_user.email}<br>Phone: {placed_by_user.phone}" if placed_by_user else ''
            summary = ""
            if llm:
                prompt = f"You are an AI assistant at Quantum Blue. Summarize the following order for a distributor, focusing on clarity, shipment urgency, and next steps.\nOrder ID: {order.order_id}\nCustomer: {placed_by_user.name}\nTotal: ${order.total_amount}\nWarehouse: {order.warehouse_location}.\nSay: 'Please confirm or discuss changes/next steps.'\nKeep it one concise, friendly paragraph."
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
            
            # --- Email body ---
            html = f"""
                <div style='background:#f2f3f5;padding:24px;border-radius:12px;'>
                    <div style='text-align:center;'><img src='https://i.ibb.co/mG6qYxw/quantum-blue-logo.png' alt='Quantum Blue Logo' height='60'/></div>
                    <h2 style='color:#175DDC;'>New Order Notification</h2>
                    <div style='font-size:1.08em;margin-bottom:18px;color:#222;'>Order ID: <b>{order.order_id}</b><br>
                    Date: {order.order_date.strftime('%Y-%m-%d %H:%M:%S')}<br>
                    Warehouse: {order.warehouse_location}<br>
                    Status: <b style='color:#ff9500;'>{order.status or order.order_stage}</b><br>{user_block}</div>
                    <div style='margin-bottom:15px;color:#222;'>{summary}</div>
                    {expired_warning_html}
                    {table}
                    <div style='margin-top:10px;'><b>Order Total:</b> ${order.total_amount}</div>
                    <div style='font-size:13px;margin-top:20px;color:#444;'>This notification was sent by Quantum Blue AI Assistant (Powered by Quantum Blue AI). For questions, reply to this email or contact Quantum Blue support.</div>
                </div>"""
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
                    'quantity': item.product_quantity_ordered,
                    'unit_price': item.unit_price,
                    'total_price': item.total_price
                })
            
            # Email to customer
            customer = User.query.get(order.user_id)
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
                    <h2>Invoice Details</h2>
                    <div class="invoice-details">
                        <p><strong>Invoice Number:</strong> {order.invoice_number}</p>
                        <p><strong>Order ID:</strong> {order.order_id}</p>
                        <p><strong>Date:</strong> {order.invoice_generated_at.strftime('%Y-%m-%d %H:%M:%S')}</p>
                        <p><strong>Status:</strong> {order.status.title()}</p>
                        <p><strong>Warehouse:</strong> {order.warehouse_location}</p>
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
                        <p><strong>Subtotal: ${order.subtotal_amount:.2f}</strong></p>
                        <p><strong>Discount: -${order.discount_amount:.2f}</strong></p>
                        <p><strong>Scheme Discount: -${order.scheme_discount_amount:.2f}</strong></p>
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
