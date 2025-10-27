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
                # Create new user for WhatsApp - start onboarding process
                user = User(
                    name=contact_name,
                    email=f"{from_number}@whatsapp.local",  # Placeholder email
                    phone=from_number,
                    email_verified=False,  # Start with unverified email
                    warehouse_location=None,  # No warehouse set initially
                    onboarding_state='ask_name'  # Start onboarding flow
                )
                user.set_password("whatsapp_user")  # Set a default password
                db.session.add(user)
                db.session.commit()
                logger.info(f"Created new WhatsApp user: {from_number}")
            
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
        # Check if user has completed onboarding
        if not user.email_verified or not user.warehouse_location:
            return handle_whatsapp_onboarding(user, session, message_text)
        
        # User has completed onboarding, proceed with normal chat flow
        return handle_whatsapp_chat(user, session, message_text)
        
    except Exception as e:
        logger.error(f"Error processing WhatsApp message: {str(e)}")
        return "I'm sorry, I encountered an error processing your message. Please try again later."

def handle_whatsapp_onboarding(user, session, message_text):
    """Handle WhatsApp onboarding flow"""
    try:
        # Check onboarding state from user's phone number as session key
        onboarding_state = user.onboarding_state or 'ask_name'
        
        if onboarding_state == 'ask_name':
            # Update user's onboarding state
            user.onboarding_state = 'get_name'
            db.session.commit()
            return "Hi! Welcome to Quantum Blue. What's your name?"
        
        elif onboarding_state == 'get_name':
            # Store name and move to email
            user.name = message_text[:100]
            user.onboarding_state = 'ask_email'
            db.session.commit()
            return "Thanks! Please share your email address."
        
        elif onboarding_state == 'ask_email':
            # Store email and move to phone verification
            email = message_text[:120]
            user.email = email
            user.onboarding_state = 'ask_phone'
            db.session.commit()
            return "Got it! What's your phone number?"
        
        elif onboarding_state == 'ask_phone':
            # Phone is already set, generate OTP
            user.onboarding_state = 'await_otp'
            otp = user.generate_otp()
            db.session.commit()
            
            # Send OTP via email
            from app.email_utils import send_otp_email
            send_otp_email(user.email, user.name, otp)
            
            return "We have sent an OTP to your email. Please enter the 6-digit OTP to verify."
        
        elif onboarding_state == 'await_otp':
            # Verify OTP
            if user.verify_otp(message_text, expiration=600):  # 10 minutes
                user.verify_email()
                user.onboarding_state = 'ask_warehouse'
                db.session.commit()
                
                # Get warehouse options
                db_service = get_db_service()
                warehouses = db_service.get_warehouses()
                warehouse_options = [w.location_name for w in warehouses]
                
                return f"Email verified successfully! What's your warehouse location?\n\nAvailable locations:\n" + "\n".join([f"• {w}" for w in warehouse_options])
            else:
                return "Invalid or expired OTP. Please try again."
        
        elif onboarding_state == 'ask_warehouse':
            # Set warehouse location
            user.warehouse_location = message_text
            user.onboarding_state = 'completed'
            user.last_verification = datetime.utcnow()
            db.session.commit()
            
            return "Perfect! Your warehouse location has been set. You can now:\n• Place orders\n• Track orders\n• Ask questions about our products\n\nHow can I help you today?"
        
        else:
            # Fallback to ask name
            user.onboarding_state = 'ask_name'
            db.session.commit()
            return "Hi! Welcome to Quantum Blue. What's your name?"
            
    except Exception as e:
        logger.error(f"Error in WhatsApp onboarding: {str(e)}")
        return "I'm sorry, there was an error. Please try again."

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
        if not hasattr(user, 'whatsapp_session_data') or user.whatsapp_session_data is None:
            user.whatsapp_session_data = whatsapp_session_data
        else:
            whatsapp_session_data = user.whatsapp_session_data
        
        order_session = whatsapp_session_data['order_session']
        tracking_session = whatsapp_session_data['tracking_session']
        
        # Classify user intent using LLM (same as web interface)
        classification_result = classification_service.classify_user_intent(message_text, context_data)
        intent = classification_result.get('classification', 'OTHER')
        
        logger.info(f"WhatsApp Intent classified as: {intent}")
        logger.info(f"WhatsApp Order session status: {order_session['status']}")
        logger.info(f"WhatsApp Order session items: {len(order_session['items'])}")
        
        # Process based on classification (same logic as web interface)
        if intent == 'CALCULATE_COST' or 'add' in message_text.lower():
            # Handle adding products to cart - same logic as web interface
            if 'add' in message_text.lower():
                # If order session is not in the right state, initialize it
                if order_session['status'] not in ['confirming', 'calculating']:
                    order_session['status'] = 'confirming'
                    order_session['pending_confirmation'] = True
                
                # Load products from warehouse for product matching
                products = []
                if warehouse:
                    products = db_service.get_products_by_warehouse(warehouse.id)
                
                # Parse add product request with enhanced pattern matching
                import re
                add_patterns = [
                    r'add\s+(\d+)\s+(.+?)(?:\s+to\s+cart)?$',
                    r'add\s+(.+?)\s+(\d+)(?:\s+to\s+cart)?$',
                    r'add\s+(.+?)$'
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
                        
                        # Enhanced product matching with better logic
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
                    
                    response += f"""💰 **Total Order Amount: ₹{order_session['final_total']:,.2f}**

**🎯 Recommended Add-ons:**

1. **Quantum Sensors (QB004)** - ₹1,800.00
   - Perfect companion for Quantum Processors
   - Scheme: Buy 1 Get 15% Off

2. **Neural Network Module (QB002)** - ₹1,200.00  
   - Enhances AI Controller performance
   - Scheme: Buy 1 Get 20% Off

3. **AI Memory Card (QB003)** - ₹800.00
   - Additional storage for your AI systems
   - Scheme: Buy 3 Get 2 Free

**📝 Next Steps:**
• Type 'add [product name]' to include additional items
• Type 'place order' to finalize your current selection
• Type 'remove [product name]' to remove items

Would you like to add more products or proceed with your order?"""
                    
                else:
                    # Get available products for better error message
                    available_products = []
                    for p in products:
                        available_products.append(f"• {p.product_name} ({p.product_code})")
                    
                    response = f"""I apologize, but I couldn't identify the specific product you want to add. 

To help you better, please use one of these formats:
• 'add 2 Quantum Sensors'
• 'add Neural Network Module' 
• 'add 1 AI Memory Card'

**Available Products:**
{chr(10).join(available_products)}

**Debug Info:**
• You said: "{message_text}"
• Order session status: {order_session['status']}
• Current cart items: {len(order_session['items'])}

Please try again with the exact product name, and I'll be happy to add it to your order!"""
                
                # Save session data back to user
                user.whatsapp_session_data = whatsapp_session_data
                db.session.commit()
                return response
            
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
                user.whatsapp_session_data = whatsapp_session_data
                db.session.commit()
                return response
        
        elif intent == 'PLACE_ORDER':
            # Handle order placement - same logic as web interface
            if warehouse:
                products = db_service.get_products_by_warehouse(warehouse.id)
                
                # Check if this is a simple order confirmation
                is_simple_confirmation = ('confirm my order' in message_text.lower() or 'process the items in my cart' in message_text.lower()) and not any(product in message_text for product in ['Quantum Processor', 'AI Controller', 'Quantum Sensors', 'AI Memory Card', 'Neural Network Module'])
                
                # Check if user is trying to finalize an order
                finalize_keywords = ['finalize', 'proceed', 'confirm', 'place the order', 'place my order', 'place order', 'yes proceed', 'yes it is correct', 'yes', 'ok']
                is_finalizing = any(keyword in message_text.lower() for keyword in finalize_keywords)
                
                # Check if we have order session data
                has_order_session = (order_session['status'] in ['calculating', 'confirming'] and order_session['items']) or (order_session.get('items') and len(order_session['items']) > 0)
                
                # Handle initial order request - show product selection
                if not has_order_session and not is_simple_confirmation and not is_finalizing:
                    # User wants to place order for the first time
                    order_session['status'] = 'browsing'
                    
                    response = f"""🛒 **Welcome to Quantum Blue Ordering System!**

I'm excited to help you place your order! We have an amazing selection of cutting-edge products available.

**Our Premium Product Line:**
• **Quantum Processor (QB001)** - ₹2,500.00 - Advanced AI processing power
• **Neural Network Module (QB002)** - ₹1,200.00 - Enhanced machine learning capabilities  
• **AI Memory Card (QB003)** - ₹800.00 - High-speed data storage
• **Quantum Sensors (QB004)** - ₹1,800.00 - Precision measurement technology
• **AI Controller (QB005)** - ₹950.00 - Intelligent system management

**Special Offers Available:**
🎯 All products come with exclusive discount schemes
🎯 Bulk order discounts available
🎯 Free shipping on orders over ₹5,000

**How to Order:**
1. Type 'add [product name] [quantity]' to add products
2. Adjust quantities as needed  
3. Review your order summary with pricing
4. Add more products or proceed to checkout

Let's get started! Please select the products you'd like to order."""
                    
                    # Save session data back to user
                    user.whatsapp_session_data = whatsapp_session_data
                    db.session.commit()
                    return response
                
                # Handle cart confirmation with existing items
                elif is_simple_confirmation and has_order_session:
                    # User wants to confirm their existing cart
                    order_items = order_session.get('items', [])
                    total_amount = order_session.get('final_total', 0)
                    
                    logger.info(f"WhatsApp Cart confirmation - Items count: {len(order_items)}")
                    logger.info(f"WhatsApp Cart confirmation - Total amount: {total_amount}")
                    
                    # Create professional cart summary
                    cart_summary = "**📋 Your Complete Order Summary:**\n\n"
                    for item in order_items:
                        cart_summary += f"""**{item['product_name']} (QB{item['product_code'][2:]})**
   • Quantity: {item['quantity']} units
   • Base Price: ₹{item['unit_price']:,.2f} each
   • Discount: {item['discount_percentage']:.1f}% off ({item['scheme_name']})
   • Final Price: ₹{item['final_price']:,.2f} each
   • Item Total: ₹{item['item_total']:,.2f}

"""
                    
                    cart_summary += f"""**💰 Total Order Amount: ₹{total_amount:,.2f}**

**🎯 Recommended Add-ons:**
1. **Quantum Sensors (QB004)** - ₹1,800.00
   - Perfect companion for Quantum Processors
   - Scheme: Buy 1 Get 15% Off

2. **Neural Network Module (QB002)** - ₹1,200.00  
   - Enhances AI Controller performance
   - Scheme: Buy 1 Get 20% Off

3. **AI Memory Card (QB003)** - ₹800.00
   - Additional storage for your AI systems
   - Scheme: Buy 3 Get 2 Free

**📝 Next Steps:**
• Type 'add [product name]' to include additional items
• Type 'place order' to finalize your current selection
• Type 'remove [product name]' to remove items

Would you like to add more products or proceed with your order?"""
                    
                    return cart_summary
                
                # Handle order finalization
                elif is_finalizing and has_order_session:
                    # Handle order finalization using existing cart data
                    try:
                        # Use existing order session data
                        order_items = order_session['items']
                        total_amount = order_session.get('final_total', 0)
                        
                        # Create order using the enhanced order service
                        enhanced_order_service = get_enhanced_order_service()
                        
                        # Convert order session items to cart format
                        cart_items = []
                        for item in order_items:
                            cart_items.append({
                                'product_code': item['product_code'],
                                'quantity': item['quantity']
                            })
                        
                        # Create the order
                        order, message = enhanced_order_service.create_order_from_cart(
                            user_id=user.id,
                            cart_items=cart_items,
                            warehouse_id=warehouse.id,
                            warehouse_location=warehouse_location,
                            user_email=user.email
                        )
                        
                        if order:
                            # Update order session to completed
                            order_session['status'] = 'completed'
                            order_session['order_id'] = order.order_id
                            
                            # Clear the cart after successful order
                            enhanced_order_service.force_clear_cart()
                            
                            response = f"""🎉 **Order Placed Successfully!**

**📋 Order Details:**
• **Order ID:** {order.order_id}
• **Total Amount:** ₹{order.total_amount:,.2f}
• **Status:** {order.status.title()}
• **Warehouse:** {warehouse_location}
• **Order Date:** {order.order_date.strftime('%B %d, %Y at %I:%M %p')}

**🛍️ Order Summary:**

"""
                            
                            for item in order_items:
                                response += f"""**{item['product_name']} (QB{item['product_code'][2:]})**
   • Quantity: {item['quantity']} units
   • Final Price: ₹{item['final_price']:,.2f} each
   • Item Total: ₹{item['item_total']:,.2f}

"""
                            
                            response += f"""**💰 Total Order Amount: ₹{order.total_amount:,.2f}**

**📧 Confirmation Email Sent**
Your order confirmation has been sent to {user.email}. Please check your inbox for detailed order information and tracking details.

**🚀 What's Next?**
• You'll receive email updates as your order progresses
• Use Order ID **{order.order_id}** to track your order
• Our team will process your order within 24 hours
• Expected delivery: 3-5 business days

**💎 Thank you for choosing Quantum Blue!**
We're excited to deliver cutting-edge technology to you. If you have any questions, feel free to ask!"""
                        else:
                            response = f"❌ Order failed: {message}"
                            
                        # Save session data back to user
                        user.whatsapp_session_data = whatsapp_session_data
                        db.session.commit()
                        return response
                        
                    except Exception as e:
                        logger.error(f"WhatsApp Error processing order finalization: {str(e)}")
                        return "I apologize, but I couldn't process your order. Please try again or contact support."
            else:
                response = "I couldn't find your warehouse. Please contact support."
                return response
        
        elif intent == 'TRACK_ORDER':
            # Handle order tracking - same logic as web interface
            orders = db_service.get_orders_by_email(user.email)
            
            # Check if user is asking for specific order details
            order_id_patterns = ['QB', 'order', 'track']
            has_order_id = any(pattern in message_text.upper() for pattern in order_id_patterns)
            
            if has_order_id and orders:
                # User mentioned specific order - try to find it
                tracking_session['status'] = 'selecting'
                try:
                    tracking_session['available_orders'] = [order.to_dict() for order in orders]
                except AttributeError as e:
                    logger.error(f"WhatsApp Error calling to_dict on Order object: {e}")
                    # Fallback: create dict manually
                    tracking_session['available_orders'] = []
                    for order in orders:
                        tracking_session['available_orders'].append({
                            'id': order.id,
                            'order_id': order.order_id,
                            'user_email': order.user_email,
                            'warehouse_location': order.warehouse_location,
                            'total_amount': order.total_amount,
                            'status': order.status,
                            'order_date': order.order_date.isoformat(),
                            'updated_at': order.updated_at.isoformat()
                        })
                
                # Look for order ID in the message
                import re
                order_id_match = re.search(r'QB[A-Z0-9]+', message_text.upper())
                if order_id_match:
                    order_id = order_id_match.group()
                    # Find the specific order
                    specific_order = next((order for order in orders if order.order_id == order_id), None)
                    if specific_order:
                        tracking_session['status'] = 'viewing'
                        tracking_session['selected_order_id'] = order_id
                        try:
                            tracking_session['order_details'] = specific_order.to_dict()
                        except AttributeError as e:
                            logger.error(f"WhatsApp Error calling to_dict on specific Order object: {e}")
                            # Fallback: create dict manually
                            tracking_session['order_details'] = {
                                'id': specific_order.id,
                                'order_id': specific_order.order_id,
                                'user_email': specific_order.user_email,
                                'warehouse_location': specific_order.warehouse_location,
                                'total_amount': specific_order.total_amount,
                                'status': specific_order.status,
                                'order_date': specific_order.order_date.isoformat(),
                                'updated_at': specific_order.updated_at.isoformat()
                            }
                        
                        # Get detailed order information
                        order_details, message = order_service.get_order_status(order_id)
                        if order_details:
                            items_text = ""
                            for item in order_details['items']:
                                items_text += f"• {item['product_name']} (QB{item['product_code'][2:]}) - {item['quantity']} units × ₹{item['unit_price']:,.2f} = ₹{item['total_price']:,.2f}\n"
                            
                            response = f"""📦 Order Details for {order_id}:

Status: {order_details['status'].title()}
Order Date: {order_details['order_date'][:10]}
Warehouse: {order_details['warehouse_location']}

Items:
{items_text}
Total Amount: ₹{order_details['total_amount']:,.2f}

Would you like to track another order or need more information?"""
                        else:
                            response = f"Order {order_id} not found. Here are your available orders:"
                            for order in orders[:5]:
                                response += f"\n• {order.order_id} - {order.status} (₹{order.total_amount:,.2f})"
                    else:
                        response = f"Order {order_id} not found. Here are your available orders:"
                        for order in orders[:5]:
                            response += f"\n• {order.order_id} - {order.status} (₹{order.total_amount:,.2f})"
                else:
                    # Show available orders for selection
                    response = "Here are your recent orders. Please select one to track:\n\n"
                    for i, order in enumerate(orders[:5], 1):
                        response += f"{i}. Order {order.order_id} - {order.status} (₹{order.total_amount:,.2f}) - {order.order_date.strftime('%Y-%m-%d')}\n"
                    response += "\nPlease specify the order ID or number to track."
            else:
                # General tracking request - show available orders
                tracking_session['status'] = 'selecting'
                try:
                    tracking_session['available_orders'] = [order.to_dict() for order in orders]
                except AttributeError as e:
                    logger.error(f"WhatsApp Error calling to_dict on Order objects: {e}")
                    # Fallback: create dict manually
                    tracking_session['available_orders'] = []
                    for order in orders:
                        tracking_session['available_orders'].append({
                            'id': order.id,
                            'order_id': order.order_id,
                            'user_email': order.user_email,
                            'warehouse_location': order.warehouse_location,
                            'total_amount': order.total_amount,
                            'status': order.status,
                            'order_date': order.order_date.isoformat(),
                            'updated_at': order.updated_at.isoformat()
                        })
                
                if orders:
                    response = "Here are your recent orders. Please select one to track:\n\n"
                    for i, order in enumerate(orders[:5], 1):
                        response += f"{i}. Order {order.order_id} - {order.status} (₹{order.total_amount:,.2f}) - {order.order_date.strftime('%Y-%m-%d')}\n"
                    response += "\nPlease specify the order ID or number to track."
                else:
                    response = "You don't have any orders yet. Would you like to place a new order?"
            
            # Save session data back to user
            user.whatsapp_session_data = whatsapp_session_data
            db.session.commit()
            return response
        
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
