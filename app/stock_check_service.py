import logging
from datetime import datetime, date
from flask import current_app
from app import db
from app.models import Product, PendingOrderProducts, Order, OrderItem, User
from app.database_service import DatabaseService
from app.pricing_service import PricingService
from app.email_utils import send_email

logging.basicConfig(level=logging.INFO)
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
                return
            
            self.logger.info(f"Found {len(pending_products)} pending products to check")
            
            fulfilled_orders = []
            
            for pending in pending_products:
                self.logger.info(f"Checking stock for {pending.product_code} (Order: {pending.original_order_id})")
                
                # Check if product is now available in non-expired batches
                availability_result = self._check_product_availability(
                    pending.product_code,
                    pending.warehouse_id,
                    pending.requested_quantity
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
    
    def _check_product_availability(self, product_code, warehouse_id, required_quantity):
        """
        Check if product is available in non-expired batches
        Returns: {'available': bool, 'allocation_info': dict}
        """
        try:
            today = date.today()
            
            # Get all NON-EXPIRED batches of this product in the warehouse
            available_batches = Product.query.filter_by(
                product_code=product_code,
                warehouse_id=warehouse_id,
                is_active=True
            ).filter(
                db.or_(
                    Product.expiry_date >= today,
                    Product.expiry_date.is_(None)
                )
            ).all()
            
            # Sort by expiry date (earliest first) for FEFO
            available_batches = sorted(
                available_batches,
                key=lambda b: (b.expiry_date is None, b.expiry_date or date.max)
            )
            
            # Calculate total available
            total_available = sum(batch.available_for_sale for batch in available_batches if batch.available_for_sale > 0)
            
            if total_available >= required_quantity:
                self.logger.info(f"✅ Product {product_code} is available: {total_available} units (required: {required_quantity})")
                return {
                    'available': True,
                    'total_available': total_available,
                    'batches': available_batches
                }
            else:
                self.logger.info(f"⏳ Product {product_code} not yet available: {total_available} units (required: {required_quantity})")
                return {
                    'available': False,
                    'total_available': total_available,
                    'batches': available_batches
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
            
            # Get warehouse
            warehouse = self.db_service.get_warehouse_by_location(pending_product.warehouse_location)
            if not warehouse:
                return {
                    'success': False,
                    'message': "Warehouse not found"
                }
            
            # Get product
            product = Product.query.filter_by(
                product_code=pending_product.product_code,
                warehouse_id=warehouse.id
            ).first()
            
            if not product:
                return {
                    'success': False,
                    'message': "Product not found"
                }
            
            # Create order
            order = Order(
                user_id=user.id,
                warehouse_id=warehouse.id,
                warehouse_location=warehouse.location_name,
                user_email=user.email,
                placed_by=user.user_type,
                placed_by_user_id=user.id,
                status='in_transit',
                order_stage='distributor_notified'
            )
            order.generate_order_id()
            db.session.add(order)
            db.session.commit()
            
            # Calculate pricing
            pricing = self.pricing_service.calculate_product_pricing(
                product.id,
                pending_product.requested_quantity
            )
            
            if 'error' in pricing:
                return {
                    'success': False,
                    'message': f"Pricing error: {pricing['error']}"
                }
            
            # Create order item
            order_item = OrderItem(
                order_id=order.id,
                product_id=product.id,
                product_code=pending_product.product_code,
                product_quantity_ordered=pending_product.requested_quantity,
                unit_price=product.price_of_product,
                total_price=pricing['pricing']['total_amount'],
                base_price=pricing['base_price'],
                discount_amount=pricing['discount']['amount'],
                scheme_discount_amount=0,
                final_price=pricing['pricing']['final_price'],
                scheme_applied=pricing['scheme']['name'],
                free_quantity=pricing['scheme']['free_quantity'],
                paid_quantity=pricing['scheme']['paid_quantity']
            )
            db.session.add(order_item)
            
            # Allocate quantity using FEFO
            allocations, allocation_message = self.db_service.allocate_quantity_fefo(
                product_code=pending_product.product_code,
                warehouse_id=warehouse.id,
                quantity_to_allocate=pending_product.requested_quantity
            )
            
            if not allocations:
                raise Exception(f"Failed to allocate products: {allocation_message}")
            
            # Update order totals
            order.subtotal_amount = pricing['pricing']['total_amount']
            order.discount_amount = pricing['base_price'] - pricing['pricing']['final_price']
            order.scheme_discount_amount = 0
            order.total_amount = pricing['pricing']['total_amount']
            
            db.session.commit()
            
            # Update pending order status
            self.db_service.update_pending_order_status(
                pending_id=pending_product.id,
                status='fulfilled',
                fulfilled_order_id=order.order_id
            )
            
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
                    <th>Unit Price</th>
                    <th>Total</th>
                </tr>
                <tr>
                    <td>{pending_product.product_name}<br><small>({pending_product.product_code})</small></td>
                    <td>{pending_product.requested_quantity}</td>
                    <td>${pricing['pricing']['final_price']:.2f}</td>
                    <td>${pricing['pricing']['total_amount']:.2f}</td>
                </tr>
            </table>
            
            <p style="margin-top: 20px;"><strong>Order ID:</strong> {new_order.order_id}</p>
            <p><strong>Total Amount:</strong> <span style="font-size: 18px; font-weight: bold; color: #007bff;">${new_order.total_amount:.2f}</span></p>
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
            
            send_email(user.email, subject, html_content, 'pending_order_fulfilled')
            self.logger.info(f"User notification sent for fulfilled pending order {new_order.order_id}")
            
        except Exception as e:
            self.logger.error(f"Error sending user notification: {str(e)}")
    
    def _notify_distributor_fulfilled(self, pending_product, new_order, user):
        """Send email to distributor when a pending order is fulfilled"""
        try:
            # Get distributor
            distributor = self.db_service.get_distributor_for_warehouse(pending_product.warehouse_location)
            
            if not distributor:
                self.logger.warning(f"No distributor found for warehouse {pending_product.warehouse_location}")
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
            <p><strong>Warehouse:</strong> {pending_product.warehouse_location}</p>
            
            <h3>Product Details:</h3>
            <table>
                <tr>
                    <th>Product Name</th>
                    <th>Product Code</th>
                    <th>Quantity</th>
                </tr>
                <tr>
                    <td>{pending_product.product_name}</td>
                    <td>{pending_product.product_code}</td>
                    <td>{pending_product.requested_quantity} units</td>
                </tr>
            </table>
            
            <p><strong>Total Amount:</strong> ${new_order.total_amount:.2f}</p>
            
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
            
            send_email(distributor.email, subject, html_content, 'pending_order_distributor')
            self.logger.info(f"Distributor notification sent for fulfilled pending order {new_order.order_id}")
            
        except Exception as e:
            self.logger.error(f"Error sending distributor notification: {str(e)}")

