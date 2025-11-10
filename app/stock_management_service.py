"""
Stock Management Service
Handles stock arrival notifications, confirmations, and quantity adjustments
"""

import logging
from datetime import datetime, date
from sqlalchemy.orm.attributes import flag_modified
from sqlalchemy import text
from app import db
from app.models import DealerWiseStockDetails, Product, User
from app.email_utils import send_stock_arrival_notification, send_quantity_discrepancy_email

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class StockManagementService:
    """Service for managing stock arrivals and confirmations"""
    
    def __init__(self):
        self.logger = logger
    
    def notify_dealer_of_stock_arrival(self, stock_detail_id):
        """
        Notify dealer when new stock arrives
        Stock is in 'blocked' state until dealer confirms
        """
        try:
            stock_detail = DealerWiseStockDetails.query.get(stock_detail_id)
            if not stock_detail:
                return {'success': False, 'message': 'Stock detail not found'}
            
            # Get dealer user
            dealer = User.query.filter_by(unique_id=stock_detail.dealer_unique_id, user_type='distributor').first()
            if not dealer:
                return {'success': False, 'message': 'Dealer not found'}
            
            # Send notification email
            try:
                send_stock_arrival_notification(
                    dealer_email=dealer.email,
                    dealer_name=dealer.name,
                    product_code=stock_detail.product_code,
                    product_name=stock_detail.product_name,
                    quantity=stock_detail.quantity,
                    dispatch_date=stock_detail.dispatch_date,
                    lot_number=stock_detail.lot_number,
                    expiration_date=stock_detail.expiration_date
                )
            except Exception as e:
                self.logger.error(f"Error sending stock arrival notification: {str(e)}")
            
            return {
                'success': True,
                'message': f'Dealer {dealer.name} has been notified of stock arrival',
                'stock_detail_id': stock_detail_id,
                'status': 'blocked'
            }
            
        except Exception as e:
            self.logger.error(f"Error notifying dealer of stock arrival: {str(e)}")
            return {'success': False, 'message': f'Error: {str(e)}'}
    
    def get_pending_stock_arrivals(self, dealer_unique_id, invoice_id=None, date_filter=None):
        """Get all pending stock arrivals for a dealer, optionally filtered by invoice_id and/or date"""
        try:
            query = DealerWiseStockDetails.query.filter_by(
                dealer_unique_id=dealer_unique_id,
                status='blocked'
            )
            
            # Filter by invoice_id if provided
            if invoice_id:
                query = query.filter_by(invoice_id=invoice_id)
            
            # Filter by date if provided
            if date_filter:
                from datetime import datetime
                try:
                    filter_date = datetime.strptime(date_filter, '%Y-%m-%d').date()
                    query = query.filter(DealerWiseStockDetails.dispatch_date == filter_date)
                except ValueError:
                    self.logger.warning(f"Invalid date format: {date_filter}")
            
            pending_stocks = query.order_by(DealerWiseStockDetails.dispatch_date.desc()).all()
            
            stock_list = []
            invoice_ids = set()  # Track unique invoice IDs
            dispatch_dates = set()  # Track unique dispatch dates
            for stock in pending_stocks:
                stock_dict = stock.to_dict()
                stock_list.append(stock_dict)
                if stock.invoice_id:
                    invoice_ids.add(stock.invoice_id)
                if stock.dispatch_date:
                    dispatch_dates.add(stock.dispatch_date.strftime('%Y-%m-%d'))
            
            return {
                'success': True,
                'stocks': stock_list,
                'count': len(stock_list),
                'invoice_ids': sorted(list(invoice_ids)),  # Return available invoice IDs
                'dispatch_dates': sorted(list(dispatch_dates), reverse=True)  # Return available dispatch dates (newest first)
            }
            
        except Exception as e:
            self.logger.error(f"Error getting pending stock arrivals: {str(e)}")
            return {'success': False, 'message': f'Error: {str(e)}', 'stocks': []}
    
    def confirm_stock_arrival(self, stock_detail_id, dealer_user_id, received_quantity=None, adjustment_reason=None):
        """
        Confirm stock arrival by dealer
        If received_quantity differs from sent quantity, create adjustment record and send email
        """
        try:
            stock_detail = DealerWiseStockDetails.query.get(stock_detail_id)
            if not stock_detail:
                return {'success': False, 'message': 'Stock detail not found'}
            
            # Verify dealer
            dealer = User.query.get(dealer_user_id)
            if not dealer or dealer.unique_id != stock_detail.dealer_unique_id:
                return {'success': False, 'message': 'Unauthorized: You can only confirm your own stock'}
            
            # Check if already confirmed
            if stock_detail.status == 'confirmed':
                return {'success': False, 'message': 'Stock already confirmed'}
            
            # Use received_quantity if provided, otherwise use sent quantity
            actual_received = received_quantity if received_quantity is not None else stock_detail.quantity
            
            # Check for quantity discrepancy
            has_discrepancy = (actual_received != stock_detail.quantity)
            
            # Determine adjustment reason
            final_adjustment_reason = None
            if has_discrepancy:
                if adjustment_reason:
                    final_adjustment_reason = adjustment_reason.strip()
                else:
                    final_adjustment_reason = f'Received {actual_received} units instead of {stock_detail.quantity} units'
                
                self.logger.info(f"Quantity adjusted for stock {stock_detail_id}: {stock_detail.quantity} -> {actual_received}, Reason: {final_adjustment_reason}")
                
                # Send email notification to company about discrepancy
                try:
                    send_quantity_discrepancy_email(
                        dealer_name=dealer.name,
                        dealer_email=dealer.email,
                        product_code=stock_detail.product_code,
                        product_name=stock_detail.product_name,
                        sent_quantity=stock_detail.quantity,
                        received_quantity=actual_received,
                        dispatch_date=stock_detail.dispatch_date,
                        reason=final_adjustment_reason
                    )
                except Exception as e:
                    self.logger.error(f"Error sending quantity discrepancy email: {str(e)}")
            
            # Calculate available_for_sale
            available_for_sale = max(0, actual_received - stock_detail.blocked_quantity - stock_detail.sold_quantity)
            
            # Use direct SQL UPDATE to ensure fields persist correctly
            # This avoids ORM issues with BIT and nullable fields
            update_sql = text("""
                UPDATE dealer_wise_stock_details
                SET received_quantity = :received_qty,
                    quantity_adjusted = :qty_adjusted,
                    adjustment_reason = :adj_reason,
                    status = :status,
                    confirmed_at = :confirmed_at,
                    confirmed_by = :confirmed_by,
                    available_for_sale = :available
                WHERE id = :stock_id
            """)
            
            db.session.execute(update_sql, {
                'received_qty': actual_received,
                'qty_adjusted': 1 if has_discrepancy else 0,
                'adj_reason': final_adjustment_reason,
                'status': 'confirmed',
                'confirmed_at': datetime.utcnow(),
                'confirmed_by': dealer_user_id,
                'available': available_for_sale,
                'stock_id': stock_detail_id
            })
            
            self.logger.info(f"Direct SQL UPDATE executed - Received: {actual_received}, Adjusted: {1 if has_discrepancy else 0}, Reason: {final_adjustment_reason}, Available: {available_for_sale}")
            
            # Commit all changes
            try:
                db.session.commit()
                
                # Query fresh from database to get updated record
                saved_stock = DealerWiseStockDetails.query.get(stock_detail_id)
                
                self.logger.info(f"Stock confirmation committed successfully - ID: {stock_detail_id}")
                self.logger.info(f"  Received Qty: {saved_stock.received_quantity}")
                self.logger.info(f"  Quantity Adjusted: {saved_stock.quantity_adjusted}")
                self.logger.info(f"  Adjustment Reason: {saved_stock.adjustment_reason}")
                self.logger.info(f"  Available for Sale: {saved_stock.available_for_sale}")
                
                stock_detail = saved_stock
                    
            except Exception as commit_error:
                self.logger.error(f"Error committing stock confirmation: {str(commit_error)}")
                import traceback
                self.logger.error(traceback.format_exc())
                db.session.rollback()
                raise
            
            return {
                'success': True,
                'message': 'Stock arrival confirmed successfully',
                'stock_detail': stock_detail.to_dict(),
                'quantity_adjusted': stock_detail.quantity_adjusted
            }
            
        except Exception as e:
            db.session.rollback()
            self.logger.error(f"Error confirming stock arrival: {str(e)}")
            return {'success': False, 'message': f'Error: {str(e)}'}
    
    def _add_stock_to_products(self, stock_detail):
        """
        Legacy method - Stock is now managed in dealer_wise_stock_details table only
        No need to sync to products table since dealer_wise_stock_details is the source of truth
        """
        try:
            # Stock is already managed in dealer_wise_stock_details
            # The available_for_sale column in dealer_wise_stock_details is the source of truth
            # Products table is just a master catalog (id, name, price, team)
            
            quantity_to_add = stock_detail.received_quantity if stock_detail.received_quantity is not None else stock_detail.quantity
            self.logger.info(f"Stock confirmed in dealer_wise_stock_details - Product: {stock_detail.product_code}, Qty: {quantity_to_add}")
            
        except Exception as e:
            self.logger.error(f"Error in stock confirmation: {str(e)}")
            # Don't raise - this is non-critical now that dealer_wise_stock_details is the source of truth
    
    def adjust_stock_quantity(self, stock_detail_id, dealer_user_id, new_quantity, reason):
        """
        Adjust stock quantity after confirmation
        Send email notification to company
        """
        try:
            stock_detail = DealerWiseStockDetails.query.get(stock_detail_id)
            if not stock_detail:
                return {'success': False, 'message': 'Stock detail not found'}
            
            # Verify dealer
            dealer = User.query.get(dealer_user_id)
            if not dealer or dealer.unique_id != stock_detail.dealer_unique_id:
                return {'success': False, 'message': 'Unauthorized'}
            
            # Can only adjust if status is confirmed
            if stock_detail.status != 'confirmed':
                return {'success': False, 'message': 'Can only adjust confirmed stock'}
            
            old_quantity = stock_detail.received_quantity or stock_detail.quantity
            stock_detail.received_quantity = new_quantity
            stock_detail.quantity_adjusted = True
            stock_detail.adjustment_reason = reason
            stock_detail.updated_at = datetime.utcnow()
            
            # Update product quantity
            self._update_product_quantity(stock_detail, old_quantity, new_quantity)
            
            # Send email notification
            try:
                send_quantity_discrepancy_email(
                    dealer_name=dealer.name,
                    dealer_email=dealer.email,
                    product_code=stock_detail.product_code,
                    product_name=stock_detail.product_name,
                    sent_quantity=stock_detail.quantity,
                    received_quantity=new_quantity,
                    dispatch_date=stock_detail.dispatch_date,
                    reason=reason
                )
            except Exception as e:
                self.logger.error(f"Error sending adjustment email: {str(e)}")
            
            db.session.commit()
            
            return {
                'success': True,
                'message': 'Stock quantity adjusted successfully',
                'stock_detail': stock_detail.to_dict()
            }
            
        except Exception as e:
            db.session.rollback()
            self.logger.error(f"Error adjusting stock quantity: {str(e)}")
            return {'success': False, 'message': f'Error: {str(e)}'}
    
    def _update_product_quantity(self, stock_detail, old_quantity, new_quantity):
        """Update product quantity after adjustment"""
        try:
            dealer = User.query.filter_by(unique_id=stock_detail.dealer_unique_id).first()
            if not dealer:
                return
            
            # Get warehouse by area
            from app.database_service import DatabaseService
            db_service = DatabaseService()
            warehouse = db_service.get_warehouse_by_area(dealer.area)
            if not warehouse:
                return
            
            product = Product.query.filter_by(
                product_code=stock_detail.product_code,
                warehouse_id=warehouse.id,
                batch_number=stock_detail.lot_number,
                expiry_date=stock_detail.expiration_date
            ).first()
            
            if product:
                quantity_diff = new_quantity - old_quantity
                product.product_quantity += quantity_diff
                product.available_for_sale += quantity_diff
                self.logger.info(f"Adjusted product quantity: {quantity_diff} units")
            
        except Exception as e:
            self.logger.error(f"Error updating product quantity: {str(e)}")
            raise

