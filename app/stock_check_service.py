import logging
from datetime import datetime, date
from flask import current_app
from app import db
from app.models import Product, PendingOrderProducts, Order, OrderItem, User, DealerWiseStockDetails
from app.database_service import DatabaseService
from app.pricing_service import PricingService
from app.email_utils import send_email

# Single logger initialization - logging.basicConfig should only be called once in __init__.py
logger = logging.getLogger(__name__)

class StockCheckService:
    """Service to check stock availability and auto-place orders for pending products"""
    
    def __init__(self):
        self.db_service = DatabaseService()
        self.pricing_service = PricingService()
        self.logger = logger
    
    def check_and_fulfill_pending_orders(self):
        """
        Main method to check stock availability for all pending orders
        and automatically place orders when stock becomes available
        """
        try:
            self.logger.info("🔍 Starting stock check for pending orders...")
            
            # Get all pending products
            pending_products = self.db_service.get_all_pending_products()
            
            if not pending_products:
                self.logger.info("No pending products to check")
                return {
                    'success': True,
                    'fulfilled_count': 0,
                    'fulfilled_orders': []
                }
            
            self.logger.info(f"Found {len(pending_products)} pending products to check")
            
            fulfilled_orders = []
            
            for pending in pending_products:
                self.logger.info(f"Checking stock for {pending.product_code} (Order: {pending.original_order_id})")
                
                # Get user to find their area
                user = User.query.get(pending.user_id)
                if not user or not user.area:
                    self.logger.warning(f"User or area not found for pending product {pending.id}")
                    continue
                
                # CRITICAL: Check availability for BOTH paid quantity AND FOC quantity
                # FOC is stored with pending order and needs to be included in stock check
                original_foc_qty = pending.original_foc_quantity or 0
                total_quantity_needed = pending.requested_quantity + original_foc_qty
                
                # Check if product is now available in dealer stock for this area (including FOC)
                availability_result = self._check_product_availability(
                    pending.product_code,
                    user.area,
                    total_quantity_needed  # Check for paid + FOC quantity
                )
                
                if availability_result['available']:
                    self.logger.info(f"✅ Stock available for {pending.product_code}! Fulfilling order...")
                    
                    # Place the order for this product
                    order_result = self._place_pending_order(pending)
                    
                    if order_result['success']:
                        fulfilled_orders.append(order_result)
                        self.logger.info(f"✅ Successfully placed order for {pending.product_code}")
                    else:
                        self.logger.error(f"❌ Failed to place order for {pending.product_code}: {order_result.get('message', 'Unknown error')}")
            
            if fulfilled_orders:
                self.logger.info(f"🎉 Successfully fulfilled {len(fulfilled_orders)} pending orders!")
            
            return {
                'success': True,
                'fulfilled_count': len(fulfilled_orders),
                'fulfilled_orders': fulfilled_orders
            }
            
        except Exception as e:
            self.logger.error(f"Error in stock check service: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def _check_product_availability(self, product_code, user_area, required_quantity):
        """
        Check if product is available in dealer stock for the user's area
        Returns: {'available': bool, 'allocation_info': dict}
        """
        try:
            today = date.today()
            
            # Find dealers in the user's area
            dealers_in_area = User.query.filter_by(
                role='distributor',
                area=user_area
            ).all()
            
            if not dealers_in_area:
                self.logger.warning(f"No dealers found in area {user_area}")
                return {
                    'available': False,
                    'total_available': 0,
                    'batches': []
                }
            
            # Get all NON-EXPIRED stock from dealers in this area
            available_stock = DealerWiseStockDetails.query.filter(
                DealerWiseStockDetails.product_code == product_code,
                DealerWiseStockDetails.status == 'confirmed',
                DealerWiseStockDetails.dealer_unique_id.in_([d.unique_id for d in dealers_in_area]),
                DealerWiseStockDetails.available_for_sale > 0
            ).filter(
                db.or_(
                    DealerWiseStockDetails.expiry_date >= today,
                    DealerWiseStockDetails.expiry_date.is_(None)
                )
            ).all()
            
            # Sort by expiry date (earliest first) for FEFO
            available_stock = sorted(
                available_stock,
                key=lambda s: (s.expiry_date is None, s.expiry_date or date.max)
            )
            
            # Calculate total available
            total_available = sum(stock.available_for_sale for stock in available_stock if stock.available_for_sale > 0)
            
            if total_available >= required_quantity:
                self.logger.info(f"✅ Product {product_code} is available: {total_available} units (required: {required_quantity})")
                return {
                    'available': True,
                    'total_available': total_available,
                    'stock_details': available_stock
                }
            else:
                self.logger.info(f"⏳ Product {product_code} not yet available: {total_available} units (required: {required_quantity})")
                return {
                    'available': False,
                    'total_available': total_available,
                    'stock_details': available_stock
                }
                
        except Exception as e:
            self.logger.error(f"Error checking product availability: {str(e)}")
            return {
                'available': False,
                'error': str(e)
            }
    
    def _place_pending_order(self, pending_product):
        """
        Place an order for a pending product that is now available
        """
        try:
            # Get user information
            user = User.query.get(pending_product.user_id)
            if not user:
                return {
                    'success': False,
                    'message': "User not found"
                }
            
            # Get product by product_code or product_name
            # Method 1: Try to find via DealerWiseStockDetails by product_code, then get Product
            product = None
            stock_detail = DealerWiseStockDetails.query.filter_by(
                product_code=pending_product.product_code,
                status='confirmed'
            ).first()
            
            if stock_detail and stock_detail.product_id:
                product = Product.query.get(stock_detail.product_id)
            
            # Method 2: If not found, try to find Product by product_name (exact match)
            if not product:
                product = Product.query.filter_by(
                    product_name=pending_product.product_name
                ).first()
            
            # Method 3: If still not found, try case-insensitive partial match
            if not product:
                from sqlalchemy import func
                product = Product.query.filter(
                    func.lower(Product.product_name).contains(func.lower(pending_product.product_name))
                ).first()
            
            if not product:
                return {
                    'success': False,
                    'message': "Product not found"
                }
            
            # CRITICAL: Get original order to copy customer details
            original_order = None
            if pending_product.original_order_id:
                original_order = Order.query.filter_by(order_id=pending_product.original_order_id).first()
            
            # Create order (for MR users)
            # Note: This order will need distributor confirmation, but stock is blocked immediately
            order = Order(
                mr_id=user.id,
                mr_unique_id=user.unique_id,
                status='pending',
                order_stage='placed'
            )
            
            # CRITICAL: Copy customer details from original order if available
            if original_order:
                if original_order.customer_id:
                    order.customer_id = original_order.customer_id
                    order.customer_unique_id = original_order.customer_unique_id
                    self.logger.info(f"Copied customer details from original order {original_order.order_id} to new order (customer_id: {original_order.customer_id}, customer_unique_id: {original_order.customer_unique_id})")
            
            order.generate_order_id()
            db.session.add(order)
            db.session.flush()  # Get order.id
            
            # CRITICAL: Use original FOC from pending order, don't recalculate
            # FOC is stored with pending order and will be dispatched when stock arrives
            # Example: Original order 10 → 1 FOC. If 2 is pending, it gets 1 FOC (stored with pending)
            original_foc_qty = pending_product.original_foc_quantity or 0
            
            # Calculate pricing for the pending quantity (paid only, FOC is separate)
            pricing = self.pricing_service.calculate_product_pricing(
                product.id,
                pending_product.requested_quantity
            )
            
            if 'error' in pricing:
                return {
                    'success': False,
                    'message': f"Pricing error: {pricing['error']}"
                }
            
            # Create order item - use original FOC stored with pending order
            sales_price = pricing['pricing']['final_price']
            # Total price is based on paid quantity only (FOC is free)
            total_price = sales_price * pending_product.requested_quantity
            
            # Use original FOC from pending order (stored when order was split)
            free_quantity = original_foc_qty
            
            self.logger.info(f"Fulfilling pending order: {pending_product.requested_quantity} paid + {free_quantity} FOC (from original order, stored with pending). Total: {pending_product.requested_quantity + free_quantity}")
            
            order_item = OrderItem(
                order_id=order.id,
                product_id=product.id,
                product_code=pending_product.product_code,
                product_name=pending_product.product_name,
                quantity=pending_product.requested_quantity,
                free_quantity=free_quantity,  # Use original FOC stored with pending order
                unit_price=sales_price,
                total_price=total_price
            )
            db.session.add(order_item)
            
            # CRITICAL: Calculate order totals including tax (consistent with place_order)
            # pricing['pricing']['total_amount'] is subtotal only, we need to add tax
            from flask import current_app
            subtotal = pricing['pricing']['total_amount']  # This is the subtotal (paid quantity * unit price)
            tax_rate = current_app.config.get('TAX_RATE', 0.05)  # Get from config, default 5%
            tax_amount = subtotal * tax_rate
            grand_total = subtotal + tax_amount
            
            # Update order totals (consistent with place_order logic)
            order.subtotal = subtotal
            order.tax_amount = tax_amount
            order.tax_rate = tax_rate
            order.total_amount = grand_total  # Grand total includes tax
            
            # CRITICAL: Block stock for the fulfilled pending order (including FOC)
            # Stock needs to be blocked for both paid quantity and FOC quantity
            total_quantity_to_block = pending_product.requested_quantity + free_quantity
            
            # Block stock using the same logic as place_order
            from app.enhanced_order_service import EnhancedOrderService
            order_service = EnhancedOrderService()
            
            if user.role == 'mr' and user.area:
                # For MRs, block quantity from dealers in their area
                success = order_service._block_quantity_for_mr_order(
                    user=user,
                    product_code=pending_product.product_code,
                    quantity=total_quantity_to_block  # Block paid + FOC quantity
                )
                if not success:
                    self.logger.error(f"Failed to block stock for fulfilled pending order {pending_product.product_code}")
                    db.session.rollback()
                    return {
                        'success': False,
                        'message': f"Failed to block stock for {pending_product.product_code}"
                    }
                self.logger.info(f"Blocked {total_quantity_to_block} units ({pending_product.requested_quantity} paid + {free_quantity} FOC) for fulfilled pending order")
            elif user.role == 'distributor' and user.unique_id:
                # For distributors, block quantity from their own stock
                success = order_service._block_quantity_for_distributor_order(
                    user=user,
                    product_code=pending_product.product_code,
                    quantity=total_quantity_to_block  # Block paid + FOC quantity
                )
                if not success:
                    self.logger.error(f"Failed to block stock for fulfilled pending order {pending_product.product_code}")
                    db.session.rollback()
                    return {
                        'success': False,
                        'message': f"Failed to block stock for {pending_product.product_code}"
                    }
                self.logger.info(f"Blocked {total_quantity_to_block} units ({pending_product.requested_quantity} paid + {free_quantity} FOC) for fulfilled pending order")
            
            db.session.commit()
            
            # Update pending order status
            self.db_service.update_pending_order_status(
                pending_id=pending_product.id,
                status='fulfilled',
                fulfilled_order_id=order.order_id
            )
            
            # Update fulfilled_at timestamp
            pending_product.fulfilled_at = datetime.utcnow()
            db.session.commit()
            
            self.logger.info(f"Pending order {pending_product.id} fulfilled and linked to new order {order.order_id} (original: {pending_product.original_order_id})")
            
            # Send notifications
            self._send_fulfillment_notifications(pending_product, order, pricing, user)
            
            return {
                'success': True,
                'order_id': order.order_id,
                'pending_id': pending_product.id
            }
            
        except Exception as e:
            self.logger.error(f"Error placing pending order: {str(e)}")
            db.session.rollback()
            return {
                'success': False,
                'message': str(e)
            }
    
    def _send_fulfillment_notifications(self, pending_product, new_order, pricing, user):
        """Send email notifications when a pending order is fulfilled"""
        try:
            # Notify user
            self._notify_user_fulfilled(pending_product, new_order, pricing, user)
            
            # Notify distributor
            self._notify_distributor_fulfilled(pending_product, new_order, user)
            
            # Mark notifications as sent
            self.db_service.mark_pending_order_notified(pending_product.id, 'user')
            self.db_service.mark_pending_order_notified(pending_product.id, 'distributor')
            
        except Exception as e:
            self.logger.error(f"Error sending fulfillment notifications: {str(e)}")
    
    def _notify_user_fulfilled(self, pending_product, new_order, pricing, user):
        """Send email to user when their pending order is fulfilled"""
        try:
            subject = f"Good News! Your Previously Ordered Products Are Now Available - Order {new_order.order_id}"
            
            html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px; }}
        .container {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); border-radius: 10px; padding: 30px; }}
        .content {{ background-color: white; border-radius: 8px; padding: 30px; margin-top: 20px; }}
        .success-icon {{ text-align: center; font-size: 60px; margin: 20px 0; }}
        .order-box {{ background: #f8f9fa; padding: 20px; border-radius: 8px; margin: 20px 0; }}
        table {{ width: 100%; border-collapse: collapse; margin: 20px 0; }}
        th, td {{ border: 1px solid #ddd; padding: 12px; text-align: left; }}
        th {{ background-color: #f2f2f2; }}
        .highlight {{ background-color: #fff3cd; padding: 15px; border-left: 4px solid #ffc107; margin: 20px 0; }}
    </style>
</head>
<body>
    <div class="container">
        <h1 style="text-align: center; color: white; margin: 0;">🎉 Great News!</h1>
    </div>
    
    <div class="content">
        <div class="success-icon">✅</div>
        
        <h2 style="color: #28a745; text-align: center;">Your Previously Ordered Products Are Now Available!</h2>
        
        <p>Hello <strong>{user.name}</strong>,</p>
        
        <div class="highlight">
            <strong>📦 Product Now Available:</strong><br>
            We're happy to inform you that the product(s) you ordered previously are now back in stock!
            We've automatically placed your order for fulfillment.
        </div>
        
        <div class="order-box">
            <h3>📋 Order Details:</h3>
            <table>
                <tr>
                    <th>Product Name</th>
                    <th>Quantity</th>
                    <th>FOC</th>
                    <th>Total Qty</th>
                    <th>Unit Price</th>
                    <th>Total</th>
                </tr>
                <tr>
                    <td>{pending_product.product_name}<br><small>({pending_product.product_code})</small></td>
                    <td>{pending_product.requested_quantity}</td>
                    <td style='color:#10b981;font-weight:bold;'>{pending_product.original_foc_quantity or 0}</td>
                    <td style='font-weight:bold;'>{pending_product.requested_quantity + (pending_product.original_foc_quantity or 0)}</td>
                    <td>{pricing['pricing']['final_price']:,.2f} MMK</td>
                    <td>{pricing['pricing']['total_amount']:,.2f} MMK</td>
                </tr>
            </table>
            
            <p style="margin-top: 20px;"><strong>Order ID:</strong> {new_order.order_id}</p>
            <p><strong>Total Amount:</strong> <span style="font-size: 18px; font-weight: bold; color: #007bff;">{new_order.total_amount:,.2f} MMK</span></p>
            
            <div class="highlight" style="margin-top: 15px;">
                <strong>🎁 FOC Information:</strong><br>
                This order includes <strong>{pending_product.original_foc_quantity or 0} FREE</strong> units as part of the original order's FOC benefit.
                The FOC was preserved from your original order and will be dispatched along with the paid quantity.
            </div>
        </div>
        
        <div class="highlight">
            <strong>📝 Note:</strong><br>
            This order was automatically placed because you had previously requested these products when they were out of stock.
            Your original order ID was: {pending_product.original_order_id}
        </div>
        
        <p>You'll receive separate updates as this order progresses through fulfillment.</p>
        
        <p style="margin-top: 30px; text-align: center;">
            <strong>Thank you for your patience and continued trust in Quantum Blue!</strong>
        </p>
    </div>
</body>
</html>
"""
            
            send_email(
                user.email, 
                subject, 
                html_content, 
                'pending_order_fulfilled',
                order_id=new_order.order_id,
                receiver_name=user.name
            )
            self.logger.info(f"User notification sent for fulfilled pending order {new_order.order_id}")
            
        except Exception as e:
            self.logger.error(f"Error sending user notification: {str(e)}")
    
    def _notify_distributor_fulfilled(self, pending_product, new_order, user):
        """Send email to distributor when a pending order is fulfilled"""
        try:
            # Get user to find area
            user = User.query.get(pending_product.user_id)
            if not user or not user.area:
                self.logger.warning(f"User or area not found for pending product {pending_product.id}")
                return
            
            # Get distributor from user's area
            distributor = User.query.filter_by(
                role='distributor',
                area=user.area
            ).first()
            
            if not distributor:
                self.logger.warning(f"No distributor found for area {user.area}")
                return
            
            subject = f"Pending Order Fulfilled - Order {new_order.order_id}"
            
            html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 800px; margin: 0 auto; padding: 20px; }}
        .container {{ background: #f2f3f5; padding: 24px; border-radius: 12px; }}
        .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 25px; border-radius: 8px; text-align: center; margin-bottom: 20px; }}
        .content {{ background-color: white; border-radius: 8px; padding: 30px; }}
        .info-box {{ background: #e7f3ff; border-left: 4px solid #007bff; padding: 15px; margin: 20px 0; }}
        table {{ width: 100%; border-collapse: collapse; margin: 20px 0; }}
        th, td {{ border: 1px solid #ddd; padding: 12px; text-align: left; }}
        th {{ background-color: #f2f2f2; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h2 style="margin: 0;">Pending Order Fulfilled</h2>
            <p style="margin: 10px 0 0 0; opacity: 0.9;">Stock is now available</p>
        </div>
        
        <div class="content">
            <div class="info-box">
                <strong>📦 Product is now available!</strong><br>
                A pending order has been automatically placed for a product that was previously out of stock.
            </div>
            
            <h3>Order Information:</h3>
            <p><strong>New Order ID:</strong> {new_order.order_id}</p>
            <p><strong>Original Order ID:</strong> {pending_product.original_order_id}</p>
            <p><strong>Customer:</strong> {user.name} ({user.email})</p>
            <p><strong>Phone:</strong> {user.phone}</p>
            <p><strong>Area:</strong> {user.area if user else 'N/A'}</p>
            
            <h3>Product Details:</h3>
            <table>
                <tr>
                    <th>Product Name</th>
                    <th>Product Code</th>
                    <th>Quantity</th>
                    <th>FOC</th>
                    <th>Total Qty</th>
                </tr>
                <tr>
                    <td>{pending_product.product_name}</td>
                    <td>{pending_product.product_code}</td>
                    <td>{pending_product.requested_quantity} units</td>
                    <td style='color:#10b981;font-weight:bold;'>{pending_product.original_foc_quantity or 0} units</td>
                    <td style='font-weight:bold;'>{pending_product.requested_quantity + (pending_product.original_foc_quantity or 0)} units</td>
                </tr>
            </table>
            
            <p><strong>Total Amount:</strong> {new_order.total_amount:,.2f} MMK</p>
            
            <div class="info-box" style="margin-top: 15px;">
                <p style="margin: 5px 0;"><strong>Note:</strong> This order includes {pending_product.original_foc_quantity or 0} FOC (Free of Cost) units that were part of the original order.</p>
            </div>
            
            <div class="info-box">
                <strong>⚠️ Important:</strong><br>
                This order was placed because the customer had previously requested this product when it was out of stock.
                Please confirm and proceed with fulfillment as usual.
            </div>
            
            <p style="margin-top: 20px; color: #666; font-size: 14px;">
                This notification was sent by Quantum Blue AI Assistant (Powered by Quantum Blue AI).
            </p>
        </div>
    </div>
</body>
</html>
"""
            
            send_email(
                distributor.email, 
                subject, 
                html_content, 
                'pending_order_distributor',
                order_id=new_order.order_id,
                receiver_name=distributor.name
            )
            self.logger.info(f"Distributor notification sent for fulfilled pending order {new_order.order_id}")
            
        except Exception as e:
            self.logger.error(f"Error sending distributor notification: {str(e)}")

