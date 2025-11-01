import logging
import json
from datetime import datetime
from app import db
from app.models import Product

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class PricingService:
    """Service for calculating product pricing with discounts and schemes"""
    
    def __init__(self):
        self.logger = logger
    
    def calculate_product_pricing(self, product_id, quantity):
        """
        Calculate pricing for a product with discounts and schemes
        Returns detailed pricing breakdown
        """
        try:
            product = Product.query.get(product_id)
            if not product:
                return {
                    'error': 'Product not found',
                    'final_price': 0,
                    'total_amount': 0
                }
            
            base_price = float(product.price_of_product)
            quantity = int(quantity)
            
            # Calculate discount
            discount_result = self._calculate_discount(
                base_price, 
                product.discount_type, 
                product.discount_value, 
                quantity
            )
            
            # Calculate scheme
            scheme_result = self._calculate_scheme(
                discount_result['price_after_discount'],
                product.scheme_type,
                product.scheme_value,
                quantity
            )
            
            # Final calculation
            final_price = scheme_result['final_price']
            total_amount = scheme_result['total_amount']
            
            result = {
                'product_id': product_id,
                'product_code': product.product_code,
                'product_name': product.product_name,
                'base_price': round(base_price, 2),
                'quantity': quantity,
                'discount': {
                    'type': product.discount_type,
                    'value': product.discount_value,
                    'name': product.discount_name,
                    'amount': round(discount_result['discount_amount'], 2),
                    'percentage': round(discount_result['discount_percentage'], 2)
                },
                'scheme': {
                    'type': product.scheme_type,
                    'value': product.scheme_value,
                    'name': product.scheme_name,
                    'applied': scheme_result['scheme_applied'],
                    'free_quantity': scheme_result['free_quantity'],
                    'paid_quantity': scheme_result['paid_quantity'],
                    'total_quantity': scheme_result['total_quantity']
                },
                'pricing': {
                    'price_after_discount': round(discount_result['price_after_discount'], 2),
                    'final_price': round(final_price, 2),
                    'total_amount': round(total_amount, 2),
                    'savings': round((base_price * quantity) - total_amount, 2)
                }
            }
            
            self.logger.info(f"Pricing calculated for {product.product_code}: {result['pricing']['total_amount']}")
            return result
            
        except Exception as e:
            self.logger.error(f"Error calculating pricing for product {product_id}: {str(e)}")
            return {
                'error': f'Pricing calculation error: {str(e)}',
                'final_price': 0,
                'total_amount': 0
            }
    
    def _calculate_discount(self, base_price, discount_type, discount_value, quantity):
        """Calculate discount based on type and value"""
        discount_amount = 0
        discount_percentage = 0
        
        if discount_type == 'percentage' and discount_value > 0:
            discount_percentage = discount_value
            discount_amount = (base_price * discount_value) / 100
        elif discount_type == 'fixed' and discount_value > 0:
            discount_amount = discount_value
            discount_percentage = (discount_value / base_price) * 100
        elif discount_type == 'bulk' and discount_value > 0:
            # Bulk discount - apply if quantity meets threshold
            if quantity >= 10:  # Example threshold
                discount_percentage = discount_value
                discount_amount = (base_price * discount_value) / 100
        
        price_after_discount = base_price - discount_amount
        
        return {
            'discount_amount': discount_amount,
            'discount_percentage': discount_percentage,
            'price_after_discount': price_after_discount
        }
    
    def _calculate_scheme(self, price_after_discount, scheme_type, scheme_value, quantity):
        """Calculate scheme benefits based on type and value"""
        final_price = price_after_discount
        total_quantity = quantity
        paid_quantity = quantity
        free_quantity = 0
        scheme_applied = False
        
        if not scheme_type or not scheme_value:
            return {
                'final_price': final_price,
                'total_amount': final_price * quantity,
                'total_quantity': total_quantity,
                'paid_quantity': paid_quantity,
                'free_quantity': free_quantity,
                'scheme_applied': scheme_applied
            }
        
        try:
            scheme_data = json.loads(scheme_value) if isinstance(scheme_value, str) else scheme_value
            
            if scheme_type == 'buy_x_get_y':
                buy_quantity = scheme_data.get('buy', 1)
                get_quantity = scheme_data.get('get', 0)
                is_free = scheme_data.get('free', True)
                discount_percent = scheme_data.get('discount_percent', 0)

                if buy_quantity <= 0:
                    buy_quantity = 1

                # Scheme applies if quantity meets minimum requirement
                # For "Buy X Get Y", minimum is X items (for free) or X+Y items (for discount%)
                if is_free:
                    scheme_applied = quantity >= buy_quantity
                else:
                    # For discount schemes, need at least X+Y items to form one complete group
                    min_required = buy_quantity + get_quantity if get_quantity > 0 else buy_quantity
                    scheme_applied = quantity >= min_required

                if is_free:
                    # Buy X Get Y Free: For every X items bought, get Y items free
                    # Example: Buy 2 Get 1 Free with quantity 6
                    # - Number of qualifying groups = 6 // 2 = 3 groups
                    # - Free items = 3 * 1 = 3 free
                    # - User pays for all 6 items ordered, receives 6 + 3 = 9 total
                    qualifying_groups = quantity // buy_quantity  # Number of complete "buy X" groups
                    free_quantity = qualifying_groups * get_quantity  # Free items = groups * Y
                    paid_quantity = quantity  # User pays for the quantity they ordered
                    total_quantity = paid_quantity + free_quantity  # Total items received
                    final_price = price_after_discount
                    total_amount = final_price * paid_quantity  # Pay only for ordered quantity
                else:
                    # Buy X Get Y at discount_percent%
                    # Example: "Buy 1 Get 1 at 50% Off" means:
                    # - For every (X + Y) items, you get X at full price and Y at discount%
                    # - If quantity = 4, groups = 4 // (1+1) = 2 groups
                    # - Full price items = 2 * 1 = 2, Discounted items = 2 * 1 = 2
                    # - Remainder items (quantity % (X+Y)) pay full price
                    group_size = buy_quantity + get_quantity
                    qualifying_groups = quantity // group_size if group_size > 0 else 0
                    remainder_items = quantity % group_size if group_size > 0 else quantity
                    
                    # Calculate full price and discounted items
                    full_price_items = (qualifying_groups * buy_quantity) + remainder_items
                    discounted_count = qualifying_groups * get_quantity
                    
                    # Validation: Ensure full_price_items + discounted_count = quantity
                    # This should always be true, but add safety check
                    calculated_total_items = full_price_items + discounted_count
                    if calculated_total_items != quantity:
                        self.logger.warning(f"Scheme calculation mismatch: qty={quantity}, "
                                           f"full_price_items={full_price_items}, discounted_count={discounted_count}, "
                                           f"sum={calculated_total_items}. Adjusting...")
                        # Recalculate to ensure exact match
                        if calculated_total_items < quantity:
                            # Add remainder to full price items
                            full_price_items += (quantity - calculated_total_items)
                        elif calculated_total_items > quantity:
                            # Reduce from discounted items first
                            excess = calculated_total_items - quantity
                            if discounted_count >= excess:
                                discounted_count -= excess
                            else:
                                # If not enough discounted items, reduce from full price
                                discounted_count = 0
                                full_price_items = quantity
                    
                    paid_quantity = quantity  # All items are paid (some at discount)
                    free_quantity = 0
                    total_quantity = quantity  # No free items, all paid
                    
                    discounted_price = price_after_discount * (1 - max(discount_percent, 0) / 100)
                    # Calculate total: full price items at regular price + discounted items at discount price
                    total_amount = (price_after_discount * full_price_items) + (discounted_price * discounted_count)
                    final_price = price_after_discount  # unit price for full-paid units
                    
                    # Log for debugging
                    self.logger.info(f"Buy X Get Y at discount% scheme: Buy={buy_quantity}, Get={get_quantity}, "
                                   f"Discount={discount_percent}%, Qty={quantity}, Groups={qualifying_groups}, "
                                   f"FullPriceItems={full_price_items}, DiscountedItems={discounted_count}, "
                                   f"Total=${total_amount:.2f}")
            
            elif scheme_type == 'percentage_off':
                # "Buy X Get Y% Off" means: Buy X items at full price, get additional items at Y% off
                # Example: "Buy 1 Get 20% Off" with quantity 3:
                # - 1 item at full price
                # - 2 items at 20% off
                percentage = scheme_data.get('percentage', 0)
                min_quantity = scheme_data.get('min_quantity', 1)  # Number of items to buy at full price
                
                if quantity >= min_quantity and percentage > 0:
                    scheme_applied = True
                    
                    # Calculate full price items and discounted items
                    full_price_items = min(quantity, min_quantity)  # First X items at full price
                    discounted_items = max(0, quantity - min_quantity)  # Remaining items at discount
                    
                    # Calculate prices
                    full_price_total = price_after_discount * full_price_items
                    discounted_price = price_after_discount * (1 - percentage / 100)
                    discounted_total = discounted_price * discounted_items
                    
                    # Final calculation
                    total_amount = full_price_total + discounted_total
                    # Average unit price (for display purposes)
                    final_price = total_amount / quantity if quantity > 0 else price_after_discount
                    paid_quantity = quantity
                    free_quantity = 0
                    total_quantity = quantity
                    
                    # Log for debugging
                    self.logger.info(f"Buy X Get Y% Off scheme: Buy {min_quantity} at full, Get {discounted_items} at {percentage}% off, "
                                   f"Qty={quantity}, FullPriceItems={full_price_items}, DiscountedItems={discounted_items}, "
                                   f"Total=${total_amount:.2f}")
                else:
                    # Scheme doesn't apply - all items at full price
                    scheme_applied = False
                    final_price = price_after_discount
                    paid_quantity = quantity
                    free_quantity = 0
                    total_quantity = quantity
                    total_amount = final_price * paid_quantity
            
            elif scheme_type == 'free_shipping':
                # This would typically be handled at order level, not product level
                scheme_applied = True
                paid_quantity = quantity
                free_quantity = 0
                total_quantity = quantity
            
        except (json.JSONDecodeError, KeyError, TypeError) as e:
            self.logger.warning(f"Error parsing scheme data: {str(e)}")
            # Fallback to no scheme
            final_price = price_after_discount
            paid_quantity = quantity
            free_quantity = 0
            total_quantity = quantity
        
        # If total_amount was precomputed above (for discount scheme), keep it; otherwise compute now
        try:
            total_amount
        except NameError:
            total_amount = final_price * paid_quantity
        
        return {
            'final_price': final_price,
            'total_amount': total_amount,
            'total_quantity': total_quantity,
            'paid_quantity': paid_quantity,
            'free_quantity': free_quantity,
            'scheme_applied': scheme_applied
        }
    
    def calculate_cart_total(self, cart_items):
        """Calculate total for all cart items"""
        try:
            total_amount = 0
            total_savings = 0
            items_breakdown = []
            
            for item in cart_items:
                pricing = self.calculate_product_pricing(item.product_id, item.product_quantity)
                
                if 'error' not in pricing:
                    item_total = pricing['pricing']['total_amount']
                    item_savings = pricing['pricing']['savings']
                    
                    total_amount += item_total
                    total_savings += item_savings
                    
                    items_breakdown.append({
                        'product_code': pricing['product_code'],
                        'product_name': pricing['product_name'],
                        'quantity': pricing['quantity'],
                        'unit_price': pricing['base_price'],
                        'final_price': pricing['pricing']['final_price'],
                        'total_amount': item_total,
                        'savings': item_savings,
                        'discount': pricing['discount'],
                        'scheme': pricing['scheme']
                    })
            
            return {
                'items': items_breakdown,
                'subtotal': round(total_amount, 2),
                'total_savings': round(total_savings, 2),
                'final_total': round(total_amount, 2),
                'item_count': len(items_breakdown)
            }
            
        except Exception as e:
            self.logger.error(f"Error calculating cart total: {str(e)}")
            return {
                'error': f'Cart calculation error: {str(e)}',
                'items': [],
                'subtotal': 0,
                'total_savings': 0,
                'final_total': 0,
                'item_count': 0
            }
    
    def get_available_discounts(self):
        """Get all available discount types"""
        return [
            {
                'type': 'percentage',
                'name': 'Percentage Discount',
                'description': 'Apply a percentage discount to the base price'
            },
            {
                'type': 'fixed',
                'name': 'Fixed Amount Discount',
                'description': 'Apply a fixed amount discount to the base price'
            },
            {
                'type': 'bulk',
                'name': 'Bulk Purchase Discount',
                'description': 'Apply discount for bulk purchases (min 10 units)'
            }
        ]
    
    def get_available_schemes(self):
        """Get all available scheme types"""
        return [
            {
                'type': 'buy_x_get_y',
                'name': 'Buy X Get Y Free',
                'description': 'Buy X items and get Y items free'
            },
            {
                'type': 'percentage_off',
                'name': 'Percentage Off',
                'description': 'Get percentage off on purchases above minimum quantity'
            },
            {
                'type': 'free_shipping',
                'name': 'Free Shipping',
                'description': 'Free shipping on orders (handled at order level)'
            }
        ]
