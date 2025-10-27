from flask import Blueprint, request, jsonify, current_app
from app import db
from app.models import User, Conversation, ChatSession
from app.whatsapp_service import WhatsAppService
from app.llm_classification_service import LLMClassificationService
from app.groq_service import GroqService
from app.enhanced_order_service import EnhancedOrderService
from app.database_service import DatabaseService
from app.web_search_service import WebSearchService
from app.order_service import OrderService
import logging
import json
from datetime import datetime
import uuid

whatsapp_bp = Blueprint('whatsapp', __name__)

# Initialize logging
logger = logging.getLogger(__name__)

# Initialize services
whatsapp_service = None
classification_service = None
llm_service = None
enhanced_order_service = None
db_service = None
web_search_service = None
order_service = None

def get_whatsapp_service():
    """Get WhatsApp service instance"""
    global whatsapp_service
    if whatsapp_service is None:
        whatsapp_service = WhatsAppService()
    return whatsapp_service

def get_classification_service():
    """Get LLM classification service instance"""
    global classification_service
    if classification_service is None:
        classification_service = LLMClassificationService()
    return classification_service

def get_llm_service():
    """Get LLM service instance"""
    global llm_service
    if llm_service is None:
        llm_service = GroqService()
    return llm_service

def get_enhanced_order_service():
    """Get enhanced order service instance"""
    global enhanced_order_service
    if enhanced_order_service is None:
        enhanced_order_service = EnhancedOrderService()
    return enhanced_order_service

def get_db_service():
    """Get database service instance"""
    global db_service
    if db_service is None:
        db_service = DatabaseService()
    return db_service

def get_web_search_service():
    """Get web search service instance"""
    global web_search_service
    if web_search_service is None:
        web_search_service = WebSearchService()
    return web_search_service

def get_order_service():
    """Get order service instance"""
    global order_service
    if order_service is None:
        order_service = OrderService()
    return order_service

@whatsapp_bp.route('/whatsapp', methods=['GET', 'POST'])
def webhook():
    """WhatsApp webhook endpoint for receiving messages and verification"""
    
    if request.method == 'GET':
        # Webhook verification
        verify_token = request.args.get('hub.verify_token')
        challenge = request.args.get('hub.challenge')
        mode = request.args.get('hub.mode')
        
        expected_token = current_app.config.get('WHATSAPP_VERIFY_TOKEN')
        
        if mode == 'subscribe' and verify_token == expected_token:
            logger.info("WhatsApp webhook verified successfully")
            return challenge, 200
        else:
            logger.warning(f"WhatsApp webhook verification failed. Expected: {expected_token}, Got: {verify_token}")
            return 'Forbidden', 403
    
    elif request.method == 'POST':
        # Handle incoming messages
        try:
            data = request.get_json()
            logger.info(f"Received WhatsApp webhook: {json.dumps(data, indent=2)}")
            
            # Parse the webhook data
            whatsapp_service = get_whatsapp_service()
            parsed_message = whatsapp_service.parse_webhook_message(data)
            
            if not parsed_message:
                # This could be a status update (delivered, read, sent) or other non-message webhook
                # Check if it's a status update to avoid unnecessary warnings
                entries = data.get('entry', [])
                if entries:
                    changes = entries[0].get('changes', [])
                    if changes:
                        value = changes[0].get('value', {})
                        if 'statuses' in value:
                            # This is a status update, not an error
                            logger.debug("Received WhatsApp status update")
                            return jsonify({'status': 'ok'}), 200
                
                logger.warning("Could not parse WhatsApp message")
                return jsonify({'status': 'ok'}), 200
            
            # Extract message details
            from_number = parsed_message['from']
            message_text = parsed_message.get('text', '')
            message_id = parsed_message['message_id']
            contact_name = parsed_message.get('contact_name', 'Unknown')
            
            logger.info(f"Processing WhatsApp message from {from_number}: {message_text}")
            
            # Mark message as read
            whatsapp_service.mark_message_as_read(message_id)
            
            # Find or create user based on WhatsApp number
            user = User.query.filter_by(phone=from_number).first()
            if not user:
                # Create new user for WhatsApp - extract name from WhatsApp JSON
                user = User(
                    name=contact_name or from_number,  # Use WhatsApp contact name or phone as fallback
                    email=f"{from_number}@whatsapp.local",  # Placeholder email
                    phone=from_number,
                    email_verified=False,  # Start with unverified email
                    warehouse_location=None  # No warehouse set initially
                )
                user.set_password("whatsapp_user")  # Set a default password
                db.session.add(user)
                db.session.commit()
                logger.info(f"Created new WhatsApp user: {from_number} with name: {contact_name}")
            else:
                logger.info(f"Found existing WhatsApp user: {from_number} with name: {user.name}")
            
            # Create or get active chat session
            session = ChatSession.query.filter_by(
                user_id=user.id, 
                is_active=True, 
                is_deleted=False
            ).first()
            
            if not session:
                session = ChatSession(
                    session_id=f"WA_{uuid.uuid4().hex[:16].upper()}",
                    user_id=user.id,
                    is_active=True
                )
                db.session.add(session)
                db.session.commit()
            
            # Process the message through the chatbot
            response_text = process_whatsapp_message(user, session, message_text)
            
            # Send response back to WhatsApp
            send_result = whatsapp_service.send_text_message(from_number, response_text)
            
            if send_result['success']:
                # Save conversation to database
                conversation = Conversation(
                    user_id=user.id,
                    session_id=session.id,
                    user_message=message_text,
                    bot_response=response_text,
                    data_sources={'platform': 'whatsapp', 'message_id': message_id}
                )
                db.session.add(conversation)
                db.session.commit()
                
                logger.info(f"Successfully processed and responded to WhatsApp message from {from_number}")
            else:
                logger.error(f"Failed to send WhatsApp response: {send_result.get('error')}")
            
            return jsonify({'status': 'ok'}), 200
            
        except Exception as e:
            logger.error(f"Error processing WhatsApp webhook: {str(e)}")
            return jsonify({'error': 'Internal server error'}), 500

def process_whatsapp_message(user, session, message_text):
    """Process WhatsApp message through the chatbot logic with onboarding flow"""
    try:
        # Debug logging
        logger.info(f"WhatsApp User onboarding status - Email verified: {user.email_verified}, Warehouse: {user.warehouse_location}, Name: {user.name}")
        
        # Check if user has completed onboarding
        # User needs onboarding if they don't have a real email OR email not verified OR no warehouse
        needs_onboarding = (
            not user.email or 
            user.email.endswith('@whatsapp.local') or 
            not user.email_verified or 
            not user.warehouse_location
        )
        
        if needs_onboarding:
            logger.info("WhatsApp User needs onboarding - redirecting to onboarding flow")
            return handle_whatsapp_onboarding(user, session, message_text)
        
        # User has completed onboarding, proceed with normal chat flow
        logger.info("WhatsApp User onboarding complete - redirecting to chat flow")
        return handle_whatsapp_chat(user, session, message_text)
        
    except Exception as e:
        logger.error(f"Error processing WhatsApp message: {str(e)}")
        return "I'm sorry, I encountered an error processing your message. Please try again later."

def handle_whatsapp_onboarding(user, session, message_text):
    """Handle WhatsApp onboarding flow - simplified logic based on user state"""
    try:
        logger.info(f"WhatsApp Onboarding - User: {user.name}, Email: {user.email}, Email verified: {user.email_verified}, Warehouse: {user.warehouse_location}")
        
        # Check if user has a real email (not placeholder)
        has_real_email = user.email and not user.email.endswith('@whatsapp.local')
        
        # Step 1: If user doesn't have a real email, ask for it
        if not has_real_email:
            logger.info("WhatsApp Onboarding - Step 1: Asking for email")
            email = message_text.strip()
            
            # Basic email validation
            if '@' not in email or '.' not in email:
                return "Please enter a valid email address."
            
            # Check if email already exists for another user
            existing_user = User.query.filter_by(email=email).first()
            if existing_user and existing_user.id != user.id:
                return "This email is already registered. Please use a different email address."
            
            # Set the email and generate OTP
            user.email = email
            otp = user.generate_otp()
            db.session.commit()
            
            # Send OTP via email
            try:
                from app.email_utils import send_otp_email
                send_otp_email(user.email, user.name, otp)
                logger.info(f"WhatsApp Onboarding - Step 2: OTP sent to {user.email}")
                return f"Got it! We have sent an OTP to {user.email}. Please enter the 6-digit OTP to verify."
            except Exception as e:
                logger.error(f"Failed to send OTP email: {str(e)}")
                return f"OTP generated: {otp}. Please enter this 6-digit code to verify your email."
        
        # Step 2: If user has email but not verified, verify OTP
        elif not user.email_verified:
            logger.info("WhatsApp Onboarding - Step 2: Verifying OTP")
            otp_input = message_text.strip()
            
            if not otp_input.isdigit() or len(otp_input) != 6:
                return "Please enter a valid 6-digit OTP."
            
            if user.verify_otp(otp_input, expiration=600):  # 10 minutes
                user.verify_email()
                db.session.commit()
                logger.info("WhatsApp Onboarding - Step 3: Email verified, asking for warehouse")
                
                # Get warehouse options
                db_service = get_db_service()
                warehouses = db_service.get_warehouses()
                warehouse_options = [w.location_name for w in warehouses]
                
                return f"Email verified successfully! What's your warehouse location?\n\nAvailable locations:\n" + "\n".join([f"• {w}" for w in warehouse_options]) + "\n\nType the exact name of your preferred location."
            else:
                return "Invalid or expired OTP. Please try again."
        
        # Step 3: If user has verified email but no warehouse, ask for warehouse
        elif not user.warehouse_location:
            logger.info("WhatsApp Onboarding - Step 3: Asking for warehouse")
            
            # Validate warehouse selection
            db_service = get_db_service()
            warehouses = db_service.get_warehouses()
            warehouse_names = [w.location_name.lower() for w in warehouses]
            
            selected_warehouse = message_text.strip()
            if selected_warehouse.lower() not in warehouse_names:
                warehouse_options = [w.location_name for w in warehouses]
                return f"Please select a valid warehouse location:\n\n" + "\n".join([f"• {w}" for w in warehouse_options]) + "\n\nType the exact name of your preferred location."
            
            # Set warehouse location
            user.warehouse_location = selected_warehouse
            user.last_verification = datetime.utcnow()
            db.session.commit()
            logger.info(f"WhatsApp Onboarding - Step 4: Warehouse set to {selected_warehouse}")
            
            return "Perfect! Your warehouse location has been set. You can now:\n• Place orders\n• Track orders\n• Ask questions about our products\n\nHow can I help you today?"
        
        # Step 4: User is fully onboarded, proceed to chat
        else:
            logger.info("WhatsApp Onboarding - Complete, proceeding to chat")
            return handle_whatsapp_chat(user, session, message_text)
            
    except Exception as e:
        logger.error(f"Error in WhatsApp onboarding: {str(e)}")
        return "I'm sorry, there was an error. Please try again."

def handle_whatsapp_order_flow(user, session, message_text, order_session, db_service, enhanced_order_service):
    """Handle WhatsApp-specific order flow without selection boxes"""
    try:
        warehouse_location = user.warehouse_location
        warehouse = db_service.get_warehouse_by_location(warehouse_location)
        
        if not warehouse:
            return "I couldn't find your warehouse information. Please contact support."
        
        products = db_service.get_products_by_warehouse(warehouse.id)
        
        # Check if user wants to place order (finalize)
        if any(keyword in message_text.lower() for keyword in ['confirm order', 'place order', 'checkout', 'finalize']):
            if not order_session['items']:
                return "Your cart is empty! Please add some products first.\n\nType 'add [product name] [quantity]' to add items."
            
            # Create the order
            try:
                order_result = enhanced_order_service.create_order_from_cart(
                    user_email=user.email,
                    cart_items=order_session['items'],
                    warehouse_id=warehouse.id
                )
                
                if order_result.get('success'):
                    order_id = order_result.get('order_id')
                    order_session['status'] = 'completed'
                    order_session['order_id'] = order_id
                    order_session['items'] = []  # Clear cart
                    order_session['total_cost'] = 0
                    order_session['final_total'] = 0
                    
                    return f"""✅ **Order Placed Successfully!**

📋 **Order ID:** {order_id}
📅 **Date:** {datetime.utcnow().strftime('%Y-%m-%d %H:%M')}
🏢 **Warehouse:** {warehouse_location}

**Order Summary:**
{order_result.get('order_summary', 'Order details will be sent via email.')}

**Next Steps:**
• You'll receive an email confirmation shortly
• Track your order anytime by typing 'track my order'
• Contact support if you have any questions

Thank you for choosing Quantum Blue! 🚀"""
                else:
                    return f"❌ **Order Failed:** {order_result.get('error', 'Unknown error occurred')}\n\nPlease try again or contact support."
                    
            except Exception as e:
                logger.error(f"WhatsApp Order creation error: {str(e)}")
                return "❌ **Order Failed:** I encountered an error processing your order. Please try again or contact support."
        
        # Check if user wants to remove items
        elif any(keyword in message_text.lower() for keyword in ['remove', 'delete']):
            import re
            remove_patterns = [
                r'remove\s+(.+?)$',
                r'delete\s+(.+?)$'
            ]
            
            removed_items = []
            for pattern in remove_patterns:
                match = re.search(pattern, message_text.lower())
                if match:
                    product_name = match.group(1).strip()
                    product_name_lower = product_name.lower()
                    
                    # Find and remove the item
                    for i, item in enumerate(order_session['items']):
                        if (product_name_lower == item['product_name'].lower() or 
                            product_name_lower in item['product_name'].lower()):
                            removed_item = order_session['items'].pop(i)
                            order_session['total_cost'] -= removed_item['item_total']
                            order_session['final_total'] -= removed_item['item_total']
                            removed_items.append(removed_item)
                            logger.info(f"WhatsApp Removed item: {removed_item['product_name']}")
                            break
                    break
            
            if removed_items:
                cart_summary = "**Updated Cart:**\n\n"
                for item in order_session['items']:
                    cart_summary += f"📦 {item['product_name']} - {item['quantity']} units - ₹{item['item_total']:,.2f}\n"
                
                response = f"""✅ **Products Removed from Cart!**

{cart_summary}

💰 **New Total: ₹{order_session['final_total']:,.2f}**

**Next Steps:**\n"""
                response += "• Type 'add [product name] [quantity]' to add more items\n"
                response += "• Type 'confirm order' to proceed with checkout\n"
                
                return response
            else:
                return "I couldn't find the product you mentioned to remove. Please check the product name and try again."
        
        # Check if user wants to add items
        elif 'add' in message_text.lower():
            import re
            add_patterns = [
                r'add\s+(\d+)\s+(.+?)(?:\s+to\s+cart)?$',
                r'add\s+(.+?)\s+(\d+)(?:\s+to\s+cart)?$',
                r'add\s+(.+?)(?:\s+to\s+cart)?$'
            ]
            
            added_items = []
            for pattern in add_patterns:
                match = re.search(pattern, message_text.lower())
                if match:
                    if len(match.groups()) == 2:
                        if match.group(1).isdigit():
                            quantity = int(match.group(1))
                            product_name = match.group(2).strip()
                        else:
                            quantity = int(match.group(2))
                            product_name = match.group(1).strip()
                    else:
                        quantity = 1
                        product_name = match.group(1).strip()
                    
                    # Skip if product name is just "to" or "cart" or similar common words
                    if product_name.lower() in ['to', 'cart', 'to the cart', 'the cart']:
                        continue
                    
                    # Enhanced product matching
                    product = None
                    product_name_lower = product_name.lower()
                    
                    # Try exact matches first
                    for p in products:
                        if (product_name_lower == p.product_name.lower() or 
                            product_name_lower == p.product_code.lower()):
                            product = p
                            break
                    
                    # Try partial matches if exact match fails
                    if not product:
                        for p in products:
                            if (product_name_lower in p.product_name.lower() or 
                                p.product_code.lower() in product_name_lower or
                                any(word in p.product_name.lower() for word in product_name_lower.split() if len(word) > 2)):
                                product = p
                                break
                    
                    if product:
                        logger.info(f"WhatsApp Product found: {product.product_name} ({product.product_code})")
                        # Calculate pricing
                        pricing_info = db_service.get_product_pricing(product.id, quantity)
                        
                        # Add to existing cart or create new item
                        existing_item = None
                        for item in order_session['items']:
                            if item['product_code'] == product.product_code:
                                existing_item = item
                                break
                        
                        if existing_item:
                            # Update existing item
                            existing_item['quantity'] += quantity
                            existing_item['item_total'] += pricing_info['total_amount']
                            logger.info(f"WhatsApp Updated existing item: {product.product_name}")
                        else:
                            # Add new item
                            new_item = {
                                'product_name': product.product_name,
                                'product_code': product.product_code,
                                'quantity': quantity,
                                'unit_price': pricing_info['base_price'],
                                'final_price': pricing_info['final_price'],
                                'discount_percentage': pricing_info['discount_percentage'],
                                'scheme_name': pricing_info['scheme_name'],
                                'item_total': pricing_info['total_amount']
                            }
                            order_session['items'].append(new_item)
                            logger.info(f"WhatsApp Added new item: {product.product_name}")
                        
                        # Update totals
                        order_session['total_cost'] += pricing_info['total_amount']
                        order_session['final_total'] += pricing_info['total_amount']
                        
                        added_items.append({
                            'name': product.product_name,
                            'quantity': quantity,
                            'total': pricing_info['total_amount']
                        })
                    else:
                        logger.warning(f"WhatsApp Product not found for: {product_name}")
                    break
            
            if added_items:
                # Create updated cart summary
                cart_summary = "**Updated Cart:**\n\n"
                for item in order_session['items']:
                    cart_summary += f"📦 {item['product_name']} - {item['quantity']} units - ₹{item['item_total']:,.2f}\n"
                
                response = f"""✅ **Products Added to Cart!**

{cart_summary}

💰 **New Total: ₹{order_session['final_total']:,.2f}**

**Updated Order Calculations:**

"""
                
                for item in order_session['items']:
                    response += f"""**{item['product_name']} (QB{item['product_code'][2:]})**
    • Quantity: {item['quantity']} units
    • Base Price: ₹{item['unit_price']:,.2f} each
    • Discount: {item['discount_percentage']:.1f}% off
    • Final Price: ₹{item['final_price']:,.2f} each
    • Scheme: {item['scheme_name']}
    • Item Total: ₹{item['item_total']:,.2f}

"""
                
                # Add recommended products
                if len(order_session['items']) < 3:  # Suggest more if cart is small
                    response += "\n**💡 Recommended Add-ons:**\n"
                    available_products = [p for p in products if not any(item['product_code'] == p.product_code for item in order_session['items'])]
                    for i, product in enumerate(available_products[:3]):
                        response += f"• {product.product_name} - ₹{product.base_price:,.2f}\n"
                
                response += "\n**Next Steps:**\n"
                response += "• Type 'add [product name] [quantity]' to add more items\n"
                response += "• Type 'remove [product name]' to remove items\n"
                response += "• Type 'confirm order' to proceed with checkout\n"
                
                return response
            else:
                return "I couldn't find the product you mentioned. Please check the product name and try again."
        
        # Initial order request - show product catalog
        else:
            if not order_session['items']:
                response = f"""🛒 **Welcome to Quantum Blue Ordering!**

**Your Warehouse:** {warehouse_location}

**Available Products:**

"""
                for product in products[:10]:  # Show first 10 products
                    response += f"📦 **{product.product_name}** (QB{product.product_code[2:]})\n"
                    response += f"   • Price: ₹{product.base_price:,.2f}\n"
                    response += f"   • Description: {product.description[:100]}...\n\n"
                
                if len(products) > 10:
                    response += f"... and {len(products) - 10} more products available!\n\n"
                
                response += """**How to Order:**
• Type 'add [product name] [quantity]' to add items
• Example: 'add Quantum Blue Cable 5'
• Type 'confirm order' when ready to checkout

**Need Help?**
• Type 'catalog' to see all products
• Type 'help' for ordering instructions"""
                
                return response
            else:
                # Show current cart
                cart_summary = "**Current Cart:**\n\n"
                for item in order_session['items']:
                    cart_summary += f"📦 {item['product_name']} - {item['quantity']} units - ₹{item['item_total']:,.2f}\n"
                
                response = f"""🛒 **Your Current Cart:**

{cart_summary}

💰 **Total: ₹{order_session['final_total']:,.2f}**

**Next Steps:**\n"""
                response += "• Type 'add [product name] [quantity]' to add more items\n"
                response += "• Type 'remove [product name]' to remove items\n"
                response += "• Type 'confirm order' to proceed with checkout\n"
                
                return response
                
    except Exception as e:
        logger.error(f"WhatsApp Order flow error: {str(e)}")
        return "I'm sorry, I encountered an error processing your order. Please try again later."

def handle_whatsapp_tracking_flow(user, session, message_text, tracking_session, db_service):
    """Handle WhatsApp-specific order tracking flow"""
    try:
        orders = db_service.get_orders_by_email(user.email)
        
        if not orders:
            return """📋 **No Orders Found**

You haven't placed any orders yet. 

**To place your first order:**
• Type 'place order' to start ordering
• Type 'add [product name] [quantity]' to add items to cart
• Type 'confirm order' when ready to checkout

Need help? Type 'help' for more information."""
        
        # Check if user is asking for specific order details
        import re
        order_id_patterns = [r'QB\d+', r'order\s+(\d+)', r'track\s+(\d+)']
        specific_order_id = None
        
        for pattern in order_id_patterns:
            match = re.search(pattern, message_text.upper())
            if match:
                if pattern == r'QB\d+':
                    specific_order_id = match.group(0)
                else:
                    specific_order_id = f"QB{match.group(1)}"
                break
        
        if specific_order_id:
            # Find specific order
            target_order = None
            for order in orders:
                if order.order_id == specific_order_id:
                    target_order = order
                    break
            
            if target_order:
                # Show detailed order information
                response = f"""📋 **Order Details**

**Order ID:** {target_order.order_id}
**Status:** {target_order.status}
**Date:** {target_order.order_date.strftime('%Y-%m-%d %H:%M')}
**Warehouse:** {target_order.warehouse_location}
**Total Amount:** ₹{target_order.total_amount:,.2f}

**Order Items:**
"""
                
                # Get order items
                try:
                    order_items = db_service.get_order_items(target_order.id)
                    for item in order_items:
                        response += f"• {item.product_name} - {item.quantity} units - ₹{item.total_price:,.2f}\n"
                except Exception as e:
                    logger.error(f"Error getting order items: {str(e)}")
                    response += "• Order items details not available\n"
                
                response += f"""
**Next Steps:**
• Type 'track my order' to see all your orders
• Type 'place order' to place a new order
• Contact support if you have questions about this order"""
                
                return response
            else:
                return f"""❌ **Order Not Found**

I couldn't find order {specific_order_id} in your account.

**Your Recent Orders:**
"""
        
        # Show all orders in a WhatsApp-friendly format
        response = f"""📋 **Your Orders ({len(orders)} total)**

"""
        
        for i, order in enumerate(orders[:5]):  # Show last 5 orders
            status_emoji = {
                'pending': '⏳',
                'confirmed': '✅',
                'processing': '🔄',
                'shipped': '🚚',
                'delivered': '📦',
                'cancelled': '❌'
            }.get(order.status.lower(), '📋')
            
            response += f"""{status_emoji} **{order.order_id}**
    • Status: {order.status}
    • Date: {order.order_date.strftime('%Y-%m-%d')}
    • Amount: ₹{order.total_amount:,.2f}
    • Warehouse: {order.warehouse_location}

"""
        
        if len(orders) > 5:
            response += f"... and {len(orders) - 5} more orders\n\n"
        
        response += """**To get details of a specific order:**
• Type 'track QB[order_number]'
• Example: 'track QB12345'

**Other options:**
• Type 'place order' to place a new order
• Type 'help' for more information"""
        
        return response
        
    except Exception as e:
        logger.error(f"WhatsApp Tracking flow error: {str(e)}")
        return "I'm sorry, I encountered an error retrieving your orders. Please try again later."

def handle_whatsapp_chat(user, session, message_text):
    """Handle WhatsApp chat after onboarding is complete - implementing same flow as web interface"""
    try:
        # Get all services like in web interface
        db_service = get_db_service()
        classification_service = get_classification_service()
        web_search_service = get_web_search_service()
        order_service = get_order_service()
        llm_service = get_llm_service()
        enhanced_order_service = get_enhanced_order_service()
        
        # Get user context
        warehouse_location = user.warehouse_location
        warehouse = db_service.get_warehouse_by_location(warehouse_location)
        context_data = {
            'user_warehouse': warehouse_location,
            'user_email': user.email
        }
        
        # Get recent orders for context
        recent_orders = db_service.get_orders_by_email(user.email)
        context_data['recent_orders'] = recent_orders[:3]  # Last 3 orders
        
        # Initialize WhatsApp session data (similar to web session)
        whatsapp_session_data = {
            'order_session': {
                'status': 'idle',  # idle, browsing, calculating, confirming, completed
                'items': [],
                'total_cost': 0,
                'discount_applied': 0,
                'final_total': 0,
                'order_id': None,
                'cart_id': None,
                'last_updated': datetime.utcnow().isoformat(),
                'user_selections': [],
                'pending_confirmation': False
            },
            'tracking_session': {
                'status': 'idle',  # idle, selecting, viewing, completed
                'selected_order_id': None,
                'order_details': None,
                'available_orders': []
            }
        }
        
        # Store session data in user model (since WhatsApp doesn't have Flask sessions)
        if hasattr(user, 'whatsapp_session_data'):
            if user.whatsapp_session_data is None:
                user.whatsapp_session_data = whatsapp_session_data
            else:
                whatsapp_session_data = user.whatsapp_session_data
        else:
            # If column doesn't exist, use a simple fallback approach
            whatsapp_session_data = {
                'order_session': {'status': 'idle', 'items': [], 'total_cost': 0, 'discount_applied': 0, 'final_total': 0, 'order_id': None, 'cart_id': None, 'last_updated': datetime.utcnow().isoformat(), 'user_selections': [], 'pending_confirmation': False},
                'tracking_session': {'status': 'idle', 'selected_order_id': None, 'order_details': None, 'available_orders': []}
            }
        
        order_session = whatsapp_session_data['order_session']
        tracking_session = whatsapp_session_data['tracking_session']
        
        # Classify user intent using LLM (same as web interface)
        classification_result = classification_service.classify_user_intent(message_text, context_data)
        intent = classification_result.get('classification', 'OTHER')
        
        logger.info(f"WhatsApp Intent classified as: {intent}")
        logger.info(f"WhatsApp Order session status: {order_session['status']}")
        logger.info(f"WhatsApp Order session items: {len(order_session['items'])}")
        
        # Process based on classification - WhatsApp-specific flow
        if intent == 'CALCULATE_COST' or 'add' in message_text.lower() or 'place order' in message_text.lower():
            return handle_whatsapp_order_flow(user, session, message_text, order_session, db_service, enhanced_order_service)
        
        elif intent == 'PLACE_ORDER':
            # This should be handled by the CALCULATE_COST condition above
            # But if it reaches here, redirect to order flow
            return handle_whatsapp_order_flow(user, session, message_text, order_session, db_service, enhanced_order_service)
            
        # Handle removing products from cart
        elif 'remove' in message_text.lower() and order_session['status'] in ['confirming', 'calculating']:
            import re
            remove_patterns = [
                r'remove\s+(.+?)$',
                r'delete\s+(.+?)$'
            ]
            
            removed_items = []
            for pattern in remove_patterns:
                match = re.search(pattern, message_text.lower())
                if match:
                    product_name = match.group(1).strip()
                    
                    # Find matching item in cart
                    item_to_remove = None
                    for item in order_session['items']:
                        if (product_name.lower() in item['product_name'].lower() or 
                            product_name.upper() in item['product_code']):
                            item_to_remove = item
                            break
                    
                    if item_to_remove:
                        # Remove from cart
                        order_session['items'].remove(item_to_remove)
                        order_session['total_cost'] -= item_to_remove['item_total']
                        order_session['final_total'] -= item_to_remove['item_total']
                        
                        removed_items.append(item_to_remove['product_name'])
                    break
            
            if removed_items:
                if order_session['items']:
                    # Create updated cart summary
                    cart_summary = "**Updated Cart:**\n\n"
                    for item in order_session['items']:
                        cart_summary += f"📦 {item['product_name']} - {item['quantity']} units - ₹{item['item_total']:,.2f}\n"
                    
                    response = f"""✅ **Products Removed from Cart!**

{cart_summary}

💰 **New Total: ₹{order_session['final_total']:,.2f}**

**Next Steps:**
• Type 'add [product name]' to include more items
• Type 'place order' to finalize your selection"""
                else:
                    response = "✅ **Cart Cleared!**\n\nYour cart is now empty. Would you like to browse our products?"
                    order_session['status'] = 'idle'
            else:
                response = "I couldn't find that product in your cart. Please check the product name and try again."
            
            # Save session data back to user
            if hasattr(user, 'whatsapp_session_data'):
                user.whatsapp_session_data = whatsapp_session_data
                db.session.commit()
            return response
        
        elif intent == 'TRACK_ORDER':
            return handle_whatsapp_tracking_flow(user, session, message_text, tracking_session, db_service)
        
        elif intent == 'COMPANY_INFO':
            # Use web search for real-time company information - same as web interface
            search_result = web_search_service.search_with_synthesis(message_text, message_text)
            if search_result.get('synthesized_response'):
                response = search_result.get('synthesized_response')
            else:
                # Fallback to database company info
                company_info = db_service.get_company_info()
                response = f"""Welcome to {company_info['company_name']}!

{company_info['description']}

Our features:
{chr(10).join([f"• {feature}" for feature in company_info['features']])}

Contact us:
• Email: {company_info['contact_info']['email']}
• Phone: {company_info['contact_info']['phone']}
• Address: {company_info['contact_info']['address']}

How can I help you today?"""
            return response
            
        elif intent == 'WEB_SEARCH':
            # Perform web search - same as web interface
            search_result = web_search_service.search_with_synthesis(message_text, message_text)
            response = search_result.get('synthesized_response', 'I couldn\'t find sufficient information to answer your query.')
            return response
            
        else:
            # General conversation with professional tone - same as web interface
            response = llm_service.generate_response(
                message_text,
                conversation_history=[],
                context_data=context_data
            ).get('response', """Hello! I'm your Quantum Blue assistant, and I'm here to help you with:

• **Product Information** - Learn about our cutting-edge products
• **Order Placement** - Place orders with our advanced AI system
• **Order Tracking** - Track your existing orders
• **Company Information** - Get details about Quantum Blue
• **General Questions** - Ask me anything!

How can I assist you today?""")
        return response
        
    except Exception as e:
        logger.error(f"WhatsApp Error in chat: {str(e)}")
        return "I'm sorry, I encountered an error processing your message. Please try again later."

@whatsapp_bp.route('/send-message', methods=['POST'])
def send_message():
    """Send a message to WhatsApp (for testing or manual sending)"""
    try:
        data = request.get_json()
        to_number = data.get('to')
        message = data.get('message')
        
        if not to_number or not message:
            return jsonify({'error': 'Missing required fields: to, message'}), 400
        
        whatsapp_service = get_whatsapp_service()
        result = whatsapp_service.send_text_message(to_number, message)
        
        if result['success']:
            return jsonify({'success': True, 'message_id': result['message_id']}), 200
        else:
            return jsonify({'error': result['error']}), 500
            
    except Exception as e:
        logger.error(f"Error sending WhatsApp message: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@whatsapp_bp.route('/send-template', methods=['POST'])
def send_template():
    """Send a template message to WhatsApp"""
    try:
        data = request.get_json()
        to_number = data.get('to')
        template_name = data.get('template_name')
        language_code = data.get('language_code', 'en_US')
        components = data.get('components')
        
        if not to_number or not template_name:
            return jsonify({'error': 'Missing required fields: to, template_name'}), 400
        
        whatsapp_service = get_whatsapp_service()
        result = whatsapp_service.send_template_message(to_number, template_name, language_code, components)
        
        if result['success']:
            return jsonify({'success': True, 'message_id': result['message_id']}), 200
        else:
            return jsonify({'error': result['error']}), 500
            
    except Exception as e:
        logger.error(f"Error sending WhatsApp template: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500
