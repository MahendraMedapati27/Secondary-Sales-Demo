from flask import Blueprint, render_template, request, jsonify, session, current_app, make_response
from app import db 
from app.models import Conversation, User, Warehouse, Product, Order, ChatSession, CartItem
from app.database_service import DatabaseService
from app.llm_classification_service import LLMClassificationService
from app.web_search_service import WebSearchService
from app.enhanced_order_service import EnhancedOrderService
from app.llm_order_service import LLMOrderService
from app.pricing_service import PricingService
from app.groq_service import GroqService 
from app.email_utils import send_otp_email, send_conversation_email
import logging
import time
from datetime import datetime
import json

chatbot_bp = Blueprint('enhanced_chatbot', __name__)

# Initialize logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize services
db_service = None
classification_service = None
web_search_service = None
enhanced_order_service = None
llm_order_service = None
pricing_service = None
llm_service = None

def get_db_service():
    """Get database service instance"""
    global db_service
    if db_service is None:
        db_service = DatabaseService()
    return db_service

def get_classification_service():
    """Get LLM classification service instance"""
    global classification_service
    if classification_service is None:
        classification_service = LLMClassificationService()
    return classification_service

def get_web_search_service():
    """Get web search service instance"""
    global web_search_service
    if web_search_service is None:
        web_search_service = WebSearchService()
    return web_search_service

def get_enhanced_order_service():
    """Get enhanced order service instance"""
    global enhanced_order_service
    if enhanced_order_service is None:
        enhanced_order_service = EnhancedOrderService()
    return enhanced_order_service

def get_llm_order_service():
    """Get LLM order service instance"""
    global llm_order_service
    if llm_order_service is None:
        llm_order_service = LLMOrderService()
    return llm_order_service

def get_pricing_service():
    """Get pricing service instance"""
    global pricing_service
    if pricing_service is None:
        pricing_service = PricingService()
    return pricing_service

def get_llm_service():
    """Get LLM service instance (GroqService)"""
    global llm_service
    if llm_service is None:
        llm_service = GroqService()
    return llm_service

@chatbot_bp.route('/')
def chat():
    """Enhanced chat interface"""
    # Force reload template from disk (bypass any caching)
    from flask import current_app, request
    import os
    
    # NUCLEAR OPTION: Completely disable Jinja2 caching
    if hasattr(current_app, 'jinja_env'):
        current_app.jinja_env.cache = None
        current_app.jinja_env.auto_reload = True
        # Clear the get_template cache if it exists
        if hasattr(current_app.jinja_env, 'get_template'):
            # Force template reload by updating file timestamp
            template_path = os.path.join(current_app.template_folder, 'enhanced_chat.html')
            if os.path.exists(template_path):
                # Update file modification time to force reload
                os.utime(template_path, None)
                # Also verify file content matches what we expect
                with open(template_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    if 'THREE-MODULE-LOADER' not in content:
                        import logging
                        logging.error(f"CRITICAL: Template file at {template_path} does NOT contain THREE-MODULE-LOADER!")
                        logging.error(f"File contains {len(content)} characters")
    
    # Add cache-busting timestamp to template
    cache_buster = int(time.time() * 1000)  # Milliseconds for better uniqueness
    
    # Log to server console for debugging
    import logging
    logging.info(f"[TEMPLATE-RELOAD] Rendering enhanced_chat.html with cache_buster={cache_buster}")
    logging.info(f"[TEMPLATE-RELOAD] Template folder: {current_app.template_folder}")
    
    # Read template directly to ensure we're using the right file
    template_path = os.path.join(current_app.template_folder, 'enhanced_chat.html')
    if os.path.exists(template_path):
        with open(template_path, 'r', encoding='utf-8') as f:
            raw_content = f.read()
            logging.info(f"[TEMPLATE-RELOAD] Template file size: {len(raw_content)} bytes")
            logging.info(f"[TEMPLATE-RELOAD] Contains THREE-MODULE-LOADER: {'THREE-MODULE-LOADER' in raw_content}")
            logging.info(f"[TEMPLATE-RELOAD] Contains old code (three.min.js): {'three.min.js' in raw_content or '<script' in raw_content and 'three@0.149' in raw_content and 'querySelector' not in raw_content}")
    
    response = make_response(render_template('enhanced_chat.html', user=None, cache_buster=cache_buster))
    
    # Aggressively disable ALL caching to ensure fresh template
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate, max-age=0, private, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Accel-Expires'] = '0'  # For nginx if used
    response.headers['Last-Modified'] = time.strftime('%a, %d %b %Y %H:%M:%S GMT', time.gmtime())
    
    # Add version header with timestamp - change every time
    version_timestamp = int(time.time())
    response.headers['X-Page-Version'] = f'threejs-v3-{version_timestamp}'
    response.headers['X-Server-Cache-Buster'] = str(cache_buster)
    response.headers['ETag'] = f'"threejs-{version_timestamp}"'  # Quotes for proper ETag format
    
    # Vary header to prevent caching based on different factors
    response.headers['Vary'] = 'Cache-Control'
    
    return response

@chatbot_bp.route('/debug-template')
def debug_template():
    """Debug endpoint to verify template file content"""
    import os
    from flask import current_app
    
    template_path = os.path.join(current_app.template_folder, 'enhanced_chat.html')
    
    result = {
        'template_path': template_path,
        'exists': os.path.exists(template_path),
        'file_size': os.path.getsize(template_path) if os.path.exists(template_path) else 0,
        'contains_three_min_js': False,
        'contains_three_module_loader': False,
        'contains_library_check': False,
        'first_200_chars': ''
    }
    
    if os.path.exists(template_path):
        with open(template_path, 'r', encoding='utf-8') as f:
            content = f.read()
            result['contains_three_min_js'] = 'three.min.js' in content or 'three@0.149' in content
            result['contains_three_module_loader'] = 'THREE-MODULE-LOADER' in content
            result['contains_library_check'] = 'Library Loading Check' in content
            result['first_200_chars'] = content[:200]
    
    return result, 200

@chatbot_bp.route('/static/js/three_avatar.js')
def serve_three_avatar():
    """Serve three_avatar.js with correct MIME type for ES modules"""
    from flask import send_from_directory, current_app, Response
    import os
    
    static_folder = current_app.static_folder
    js_file_path = os.path.join(static_folder, 'js', 'three_avatar.js')
    
    # Read the file and serve with correct MIME type
    if os.path.exists(js_file_path):
        with open(js_file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        response = Response(content, mimetype='application/javascript')
        response.headers['Content-Type'] = 'application/javascript; charset=utf-8'
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
        
        return response
    else:
        from flask import abort
        abort(404)

@chatbot_bp.route('/test-vrm')
def test_vrm():
    """Test route to verify VRM file is accessible"""
    from flask import send_from_directory
    import os
    from pathlib import Path
    
    static_path = Path(__file__).resolve().parent.parent / 'static'
    vrm_path = static_path / 'avatars' / 'avatar.vrm'
    
    if vrm_path.exists():
        return send_from_directory(
            str(static_path / 'avatars'),
            'avatar.vrm',
            mimetype='application/octet-stream',
            as_attachment=False
        )
    else:
        return f"VRM file not found at: {vrm_path}", 404

@chatbot_bp.route('/message', methods=['POST'])
def process_message():
    """Process chat message with enhanced RB (Powered by Quantum Blue AI) logic"""
    try:
        data = request.get_json()
        user_message = data.get('message', '').strip()
        
        if not user_message:
            return jsonify({'error': 'Message cannot be empty'}), 400
        
        # Enhanced onboarding flow with unique ID
        if 'onboarding_state' not in session:
            session['onboarding_state'] = 'ask_unique_id'

        state = session['onboarding_state']

        if 'onboarding' not in session:
            session['onboarding'] = {}

        # Onboarding states
        if state == 'ask_unique_id':
            session['onboarding_state'] = 'get_unique_id'
            return jsonify({
                'response': 'Hello! Welcome to RB (Powered by Quantum Blue AI). Please enter your unique ID to continue.'
            }), 200

        if state == 'get_unique_id':
            unique_id = user_message.strip()
            db_service = get_db_service()
            user = db_service.get_user_by_unique_id(unique_id)
            
            if not user:
                return jsonify({
                    'response': 'Unique ID not found. Please check your ID and try again, or contact support for assistance.'
                }), 200
            
            if not user.is_active:
                return jsonify({
                    'response': 'Your account is inactive. Please contact support for assistance.'
                }), 200
            
            # Set user session
            session['user_id'] = user.id
            session['unique_id'] = user.unique_id
            session['user_type'] = user.user_type
            session['warehouse_location'] = user.nearest_warehouse
            session['onboarding_state'] = 'ask_intent'
            
            # Create chat session
            chat_session = db_service.create_chat_session(user.id)
            session['session_id'] = chat_session.session_id
            
            # Generate welcome message with intent question
            welcome_message = generate_welcome_message(user)
            intent_message = "How can I help you today? Would you like to:\n• Place an order\n• Track an order\n• Get product information\n• Company information\n• Or something else?"
            
            full_message = f"{welcome_message}\n\n{intent_message}"
            
            return jsonify({
                'response': full_message,
                'user_info': {
                    'name': user.name,
                    'user_type': user.user_type,
                    'role': user.role,
                    'warehouse': user.nearest_warehouse
                }
            }), 200

        # Ask for user intent after verification
        if state == 'ask_intent':
            # Use LLM to understand what user wants to do
            db_service = get_db_service()
            user = User.query.get(session.get('user_id'))
            
            llm_service = get_llm_service()
            if llm_service and llm_service.client:
                intent_prompt = f"""You are an AI assistant for RB (Powered by Quantum Blue AI). A user just logged in and you asked them what they would like to do.

User's message: "{user_message}"

Based on the user's response, classify their intent into one of these categories:
1. PLACE_ORDER - User wants to place an order (e.g., "place order", "order products", "buy", "purchase", "I want to order")
2. TRACK_ORDER - User wants to track an order (e.g., "track order", "check order status", "where is my order")
3. PRODUCT_INFO - User wants product information (e.g., "show products", "what products do you have", "product list")
4. COMPANY_INFO - User wants company information (e.g., "about company", "company info", "tell me about quantum blue")
5. OTHER - Any other request (general conversation, questions, etc.)

Respond with ONLY a JSON object:
{{
    "intent": "PLACE_ORDER" | "TRACK_ORDER" | "PRODUCT_INFO" | "COMPANY_INFO" | "OTHER",
    "confidence": 0.0-1.0,
    "next_state": "ready" if intent is PLACE_ORDER/TRACK_ORDER/PRODUCT_INFO/COMPANY_INFO, else "continue_conversation"
}}"""

                try:
                    response = llm_service.client.chat.completions.create(
                        model=current_app.config.get('GROQ_MODEL', 'llama-3.3-70b-versatile'),
                        messages=[{"role": "user", "content": intent_prompt}],
                        temperature=0.1,
                        max_tokens=200
                    )
                    
                    result_text = response.choices[0].message.content.strip()
                    # Clean JSON response
                    if result_text.startswith('```'):
                        lines = result_text.split('\n')
                        if len(lines) > 2:
                            result_text = '\n'.join(lines[1:-1])
                    
                    intent_result = json.loads(result_text)
                    detected_intent = intent_result.get('intent', 'OTHER')
                    next_state = intent_result.get('next_state', 'continue_conversation')
                    
                    # Set state based on intent and prepare appropriate response
                    session['onboarding_state'] = 'completed'
                    session['user_intent'] = detected_intent
                    
                    # Generate appropriate response based on intent
                    if detected_intent == 'PLACE_ORDER':
                        return jsonify({
                            'response': 'Great! I can help you place an order. Please tell me which products you would like to order and their quantities.\n\nFor example: "Order 50 Quantum Processor, 30 Neural Network Module, and 100 AI Memory Card" or "Order 60 units of product 001, 25 units of 002"'
                        }), 200
                    elif detected_intent == 'TRACK_ORDER':
                        return jsonify({
                            'response': 'I can help you track your order. Please provide your Order ID, or I can show you your recent orders.'
                        }), 200
                    elif detected_intent == 'PRODUCT_INFO':
                        # Show available products
                        warehouse = db_service.get_warehouse_by_location(user.nearest_warehouse) if user.nearest_warehouse else None
                        products = db_service.get_products_by_warehouse(warehouse.id) if warehouse else db_service.get_products_by_warehouse(1)  # Fallback to warehouse 1
                        product_list = "\n".join([f"• {p.product_name} ({p.product_code}) - ${p.price_of_product} - Available: {p.available_for_sale}" for p in products[:10]])
                        return jsonify({
                            'response': f'Here are our available products:\n\n{product_list}\n\nWould you like to place an order for any of these products?'
                        }), 200
                    elif detected_intent == 'COMPANY_INFO':
                        company_info = db_service.get_company_info()
                        info_text = f"About {company_info['company_name']}:\n{company_info['description']}\n\nFeatures:\n" + "\n".join([f"• {f}" for f in company_info['features']])
                        return jsonify({
                            'response': info_text
                        }), 200
                    
                    # For OTHER intent, continue to normal flow
                except Exception as e:
                    logger.error(f"Error classifying intent: {str(e)}")
                    # Fall through to normal flow
                    session['onboarding_state'] = 'completed'
            else:
                # Fallback: simple keyword matching
                message_lower = user_message.lower()
                session['onboarding_state'] = 'completed'
                if any(kw in message_lower for kw in ['order', 'buy', 'purchase', 'place order']):
                    session['user_intent'] = 'PLACE_ORDER'
                    return jsonify({
                        'response': 'Great! I can help you place an order. Please tell me which products you would like to order and their quantities.\n\nFor example: "Order 50 Quantum Processor, 30 Neural Network Module, and 100 AI Memory Card"'
                    }), 200
                elif any(kw in message_lower for kw in ['track', 'status', 'where is']):
                    session['user_intent'] = 'TRACK_ORDER'
                    return jsonify({
                        'response': 'I can help you track your order. Please provide your Order ID, or I can show you your recent orders.'
                    }), 200
                else:
                    session['user_intent'] = 'OTHER'

        # Main chat flow (verified user)
        session_user_id = session.get('user_id')
        if not session_user_id:
            return jsonify({'response': 'Please complete the onboarding process first.'}), 200

        # Get services
        db_service = get_db_service()
        classification_service = get_classification_service()
        web_search_service = get_web_search_service()
        enhanced_order_service = get_enhanced_order_service()
        llm_order_service = get_llm_order_service()
        pricing_service = get_pricing_service()

        # Get user context
        user = User.query.get(session_user_id)
        warehouse_location = session.get('warehouse_location')
        
        # Get user's warehouse
        warehouse = db_service.get_warehouse_by_location(warehouse_location)
        context_data = {
            'user_warehouse': warehouse_location,
            'user_email': user.email,
            'user_type': user.user_type,
            'user_role': user.role
        }

        # Get recent orders for context
        recent_orders = db_service.get_orders_by_email(user.email)
        context_data['recent_orders'] = recent_orders[:3]

        # Get conversation history
        conversation_history = db_service.get_conversation_history(session_user_id, limit=10)

        # Use LLM to analyze if user wants to confirm order or add products
        # Get cart items to check if user has items to confirm
        cart_items = db_service.get_cart_items(session_user_id)
        
        # If user has items in cart, use LLM to determine intent
        if cart_items:
            llm_service = get_llm_service()
            if llm_service and llm_service.client:
                try:
                    intent_prompt = f"""You are an AI assistant analyzing user intent in an e-commerce chatbot.

User's message: "{user_message}"

Context:
- The user has items in their shopping cart
- The system just showed them their cart with total price

Determine the user's intent:

1. **CONFIRM_ORDER** - User wants to place/confirm/finalize the order for items already in cart
   Examples: "confirm my order", "place the order", "proceed", "yes", "ok", "go ahead", "finalize"
   
2. **ADD_TO_CART** - User wants to add more products to the cart
   Examples: "add 5 quantum sensors", "ok add more items", "put 10 processors", "include product 001"
   
3. **MODIFY_CART** - User wants to modify existing cart items (remove, update quantity)
   Examples: "remove product x", "change quantity", "update cart"

4. **PRODUCT_INFO** - User wants to see product information or list products
   Examples: "list all products", "show products available", "what products do you have", "list products in database"

5. **DATABASE_QUERY** - User wants to query database for specific information
   Examples: "show me all products in database", "list available products", "what's in stock"

Important Rules:
- If message asks to "list", "show", "display" products/database → PRODUCT_INFO or DATABASE_QUERY
- If message contains product names/codes AND action words like "add", "put", "include" → ADD_TO_CART
- If message is a simple confirmation like "ok", "yes", "proceed" WITHOUT product mentions → CONFIRM_ORDER
- If message explicitly says "confirm order", "place order" → CONFIRM_ORDER
- NEVER treat product listing requests as order confirmations

Respond with ONLY a JSON object:
{{
    "intent": "CONFIRM_ORDER" | "ADD_TO_CART" | "MODIFY_CART" | "PRODUCT_INFO" | "DATABASE_QUERY",
    "confidence": 0.0-1.0,
    "reasoning": "brief explanation"
}}"""

                    response = llm_service.client.chat.completions.create(
                        model=current_app.config.get('GROQ_MODEL', 'llama-3.3-70b-versatile'),
                        messages=[{"role": "user", "content": intent_prompt}],
                        temperature=0.1,
                        max_tokens=200
                    )
                    
                    result_text = response.choices[0].message.content.strip()
                    # Clean JSON response
                    if result_text.startswith('```'):
                        lines = result_text.split('\n')
                        if len(lines) > 2:
                            result_text = '\n'.join(lines[1:-1])
                    
                    intent_result = json.loads(result_text)
                    detected_intent = intent_result.get('intent', 'ADD_TO_CART')
                    confidence = intent_result.get('confidence', 0.5)
                    reasoning = intent_result.get('reasoning', '')
                    
                    logger.info(f"LLM Intent Analysis: {detected_intent} (confidence: {confidence:.2f}) - {reasoning}")
                    
                    # Handle different intents
                    if detected_intent == 'CONFIRM_ORDER' and confidence >= 0.7:
                        return handle_order_confirmation(user, session_user_id)
                    elif detected_intent in ['PRODUCT_INFO', 'DATABASE_QUERY']:
                        # Handle product listing/database queries
                        logger.info(f"LLM detected {detected_intent} intent - handling database query")
                        return handle_product_info_or_query(user_message, user, context_data)
                    elif detected_intent == 'ADD_TO_CART':
                        # Continue to normal flow to handle adding products
                        logger.info("LLM detected ADD_TO_CART intent - proceeding with order processing")
                except Exception as e:
                    logger.error(f"Error analyzing intent with LLM: {str(e)}")
                    # Fallback to keyword matching if LLM fails
                    message_lower = user_message.lower().strip()
                    add_keywords = ['add', 'put', 'include']
                    has_add_word = any(keyword in message_lower for keyword in add_keywords)
                    has_product_mention = any(keyword in message_lower for keyword in [
                        'quantum', 'processor', 'sensor', 'memory', 'neural', 'controller',
                        'rb001', 'rb002', 'rb003', 'rb004', 'rb005',
                        '001', '002', '003', '004', '005'
                    ])
                    
                    # Only confirm if no "add" keyword with product mention
                    if not (has_add_word and has_product_mention):
                        confirmation_keywords = ['yes proceed', 'confirm order', 'place order', 'proceed', 'confirm', 'yes', 'ok']
                        if any(keyword in message_lower for keyword in confirmation_keywords):
                            return handle_order_confirmation(user, session_user_id)
        
        # Classify user intent using LLM
        classification_result = classification_service.classify_user_intent(user_message, context_data)
        intent = classification_result.get('classification', 'OTHER')
        
        logger.info(f"Intent classified as: {intent}")

        # Process based on classification
        if intent == 'PLACE_ORDER':
            return handle_place_order(user_message, user, context_data, conversation_history)
        elif intent == 'TRACK_ORDER':
            return handle_track_order(user_message, user, context_data)
        elif intent == 'CALCULATE_COST':
            return handle_calculate_cost(user_message, user, context_data, conversation_history)
        elif intent == 'COMPANY_INFO':
            return handle_company_info(user_message, user)
        elif intent == 'WEB_SEARCH':
            return handle_web_search(user_message, user, context_data)
        elif intent == 'PRODUCT_INFO':
            return handle_product_info_or_query(user_message, user, context_data)
        else:
            return handle_general_conversation(user_message, user, context_data)

    except Exception as e:
        logger.error(f"Error processing message: {str(e)}")
        return jsonify({'response': 'Sorry, I encountered an error. Please try again.'}), 500

def handle_order_confirmation(user, user_id):
    """Handle order confirmation and placement"""
    try:
        enhanced_order_service = get_enhanced_order_service()
        
        # Place order from cart
        result = enhanced_order_service.place_order(user_id)
        
        if result['success']:
            save_conversation(user.id, "confirm order", result['message'])
            
            return jsonify({
                'response': result['message'],
                'order_id': result.get('order_id'),
                'order_summary': result.get('order_summary', {}),
                'next_steps': result.get('next_steps', ''),
                'action_buttons': [
                    {'text': 'Track Order', 'action': 'track_order'},
                    {'text': 'Place New Order', 'action': 'place_order'}
                ]
            }), 200
        else:
            save_conversation(user.id, "confirm order", result['message'])
            return jsonify({
                'response': result['message'],
                'action_buttons': [
                    {'text': 'View Cart', 'action': 'view_cart'},
                    {'text': 'Get Help', 'action': 'help'}
                ]
            }), 200
            
    except Exception as e:
        logger.error(f"Error handling order confirmation: {str(e)}")
        return jsonify({'response': 'Sorry, I encountered an error placing your order. Please try again.'}), 500

def handle_place_order(user_message, user, context_data, conversation_history):
    """Handle order placement requests"""
    try:
        enhanced_order_service = get_enhanced_order_service()
        
        # Process order request using LLM extraction
        result = enhanced_order_service.process_order_request(
            user_message, 
            user.id, 
            conversation_history
        )
        
        if result['success']:
            # Save conversation
            save_conversation(user.id, user_message, result['message'])
            
            return jsonify({
                'response': result['message'],
                'cart_items': result.get('cart_items', []),
                'order_summary': result.get('order_summary', {}),
                'errors': result.get('errors', []),
                'suggestions': result.get('suggestions', []),
                'action_buttons': [
                    {'text': 'View Cart', 'action': 'view_cart'},
                    {'text': 'Place Order', 'action': 'place_order'},
                    {'text': 'Add More Items', 'action': 'add_items'}
                ]
            }), 200
        else:
            save_conversation(user.id, user_message, result['message'])
            return jsonify({
                'response': result['message'],
                'suggestions': result.get('suggestions', []),
                'action_buttons': [
                    {'text': 'View Products', 'action': 'view_products'},
                    {'text': 'Get Help', 'action': 'help'}
                ]
            }), 200
            
    except Exception as e:
        logger.error(f"Error handling place order: {str(e)}")
        return jsonify({'response': 'Sorry, I encountered an error processing your order. Please try again.'}), 500

def handle_track_order(user_message, user, context_data):
    db_service = get_db_service()
    enhanced_order_service = get_enhanced_order_service()
    try:
        import re
        message_lower = user_message.lower()
        order_id_pat = r'([A-Z]{2}\d{8}\w+)'  # e.g. QB20251030F475CA7D
        match_id = re.search(order_id_pat, user_message)
        order_id = match_id.group(1) if match_id else None
        
        # Check if this is a confirmation request (more flexible)
        is_confirm_request = any(keyword in message_lower for keyword in ['confirm order', 'confirm the order']) and order_id
        
        # If distributor and confirm intent
        if user.user_type == 'distributor' and order_id and is_confirm_request:
            # Attempt to confirm:
            confirm_res = enhanced_order_service.confirm_order_by_distributor(order_id, user.id)
            if confirm_res['success']:
                # After confirmation, present the order table with updated status
                stat = enhanced_order_service.get_order_status_for_distributor(order_id, user.id)
                response_msg = stat['message'] + "\n\n✅ **Order successfully confirmed!**"
                return jsonify({'response': response_msg, 'action_buttons': []}), 200
            else:
                return jsonify({'response': confirm_res['message']}), 200
        
        # Otherwise, follow normal track logic
        if user.user_type == 'distributor':
            if order_id:
                order_stat = enhanced_order_service.get_order_status_for_distributor(order_id, user.id)
                if order_stat['success']:
                    msg = order_stat['message']
                    actions = []
                    if order_stat.get('can_confirm'):
                        actions.append({'text':'Confirm Order','action':f'confirm_order_{order_id}'})
                    return jsonify({'response':msg, 'action_buttons':actions}), 200
                else:
                    return jsonify({'response':order_stat['message']}), 200
            else:
                # Check if user is asking for specific status
                message_lower = user_message.lower()
                status_filter = None
                filter_description = "all orders"
                
                # Detect status filter in message
                if 'pending' in message_lower:
                    # Special handling for pending orders - show PendingOrderProducts
                    pending_items = db_service.get_pending_order_products(warehouse_location=user.nearest_warehouse, status='pending')
                    if not pending_items:
                        return jsonify({'response': 'No pending orders found in your warehouse.'}), 200
                    
                    summary = "**Pending orders for your warehouse:**\n\n"
                    summary += "| Product Code | Product Name | Requested Qty | Customer | Order ID | Requested Date |\n"
                    summary += "|--------------|--------------|---------------|----------|----------|----------------|\n"
                    for item in pending_items:
                        customer = User.query.get(item.user_id)
                        customer_name = customer.name if customer else 'Unknown'
                        order_ref = item.original_order_id if item.original_order_id else 'N/A'
                        summary += f"| {item.product_code} | {item.product_name} | {item.requested_quantity} | {customer_name} | {order_ref} | {item.created_at.strftime('%Y-%m-%d')} |\n"
                    summary += '\n**Note:** These products are waiting for stock to arrive. They will be automatically ordered when available.'
                    return jsonify({'response': summary}), 200
                elif 'confirmed' in message_lower:
                    status_filter = ['confirmed', 'distributor_confirmed']
                    filter_description = "confirmed orders"
                elif 'in transit' in message_lower or 'transit' in message_lower:
                    status_filter = ['in_transit', 'distributor_notified']
                    filter_description = "in-transit orders"
                elif 'shipped' in message_lower:
                    status_filter = ['shipped']
                    filter_description = "shipped orders"
                elif 'delivered' in message_lower:
                    status_filter = ['delivered']
                    filter_description = "delivered orders"
                
                orders = db_service.get_orders_for_distributor(user, status_filter)
                
                if not orders:
                    status_msg = f"No {filter_description} found in your warehouse." if status_filter else "No orders found in your warehouse."
                    return jsonify({'response': status_msg}), 200
                
                # Create a proper table with headers
                summary = f"**{filter_description.replace('orders', 'Orders').title()} for your warehouse:**\n\n"
                summary += "| Order ID | Status | Total Amount | Order Date |\n"
                summary += "|----------|--------|--------------|------------|\n"
                for o in orders:
                    status_display = (o.status or o.order_stage or 'Unknown').replace('_', ' ').title()
                    summary += f"| {o.order_id} | {status_display} | ${o.total_amount:.2f} | {o.order_date.strftime('%Y-%m-%d')} |\n"
                summary += '\n**To see details or confirm:** `track order <order_id>` or `confirm order <order_id>`'
                return jsonify({'response': summary}), 200
        # fall back to self-tracking for non-distributors
        if order_id:
            status = enhanced_order_service.get_order_status(order_id, user.id)
            if status['success']:
                table = '| Product | Qty | Unit Price | Discount | Scheme | Total |\n|--------|-----|-----------|----------|--------|-------|\n'
                for i in status['order']['items']:
                    pq = i.get('paid_quantity')
                    fq = i.get('free_quantity',0)
                    qty = f"{pq} + {fq} = {pq+fq}" if fq else str(pq)
                    table += f"| {i['product_name']} ({i['product_code']}) | {qty} | ${i['unit_price']} | ${i['discount_amount']} | {i['scheme_applied']} | ${i['total_price']} |\n"
                msg = f"**Track Order - {order_id}:**\n**Status:** {status['order']['status']}\n**Total:** ${status['order']['total_amount']}\n\n{table}"
                return jsonify({'response':msg}), 200
            else:
                return jsonify({'response':status['message']}), 200
        orders = db_service.get_orders_by_email(user.email)
        if not orders:
            return jsonify({'response':'No orders found in your account.'}), 200
        # Create a proper table with headers
        summary = '**Your recent orders:**\n\n'
        summary += '| Order ID | Status | Total Amount | Order Date |\n'
        summary += '|----------|--------|--------------|------------|\n'
        for o in orders[:5]:
            status_display = (o.status or o.order_stage or 'Unknown').replace('_', ' ').title()
            summary += f"| {o.order_id} | {status_display} | ${o.total_amount:.2f} | {o.order_date.strftime('%Y-%m-%d')} |\n"
        summary += '\n**To see details:** `track order <order_id>`'
        return jsonify({'response':summary}), 200
    except Exception as e:
        import traceback
        traceback.print_exc()
        logger.error(f"Error handling track order: {str(e)}")
        return jsonify({'response':'Sorry, I encountered an error tracking your order. Please try again.'}), 500

def handle_calculate_cost(user_message, user, context_data, conversation_history):
    """Handle cost calculation requests"""
    try:
        # Get cart items
        cart_items = db_service.get_cart_items(user.id)
        
        if not cart_items:
            response = "Your cart is empty. Would you like to add some products first?"
            save_conversation(user.id, user_message, response)
            return jsonify({
                'response': response,
                'action_buttons': [
                    {'text': 'Add Products', 'action': 'place_order'},
                    {'text': 'View Products', 'action': 'view_products'}
                ]
            }), 200
        
        # Generate order summary with pricing
        llm_order_service = get_llm_order_service()
        order_summary = llm_order_service.generate_order_summary(cart_items, user)
        
        response = order_summary['summary']
        save_conversation(user.id, user_message, response)
        
        return jsonify({
            'response': response,
            'order_summary': order_summary,
            'action_buttons': [
                {'text': 'Place Order', 'action': 'place_order'},
                {'text': 'Modify Cart', 'action': 'view_cart'},
                {'text': 'Add More Items', 'action': 'add_items'}
            ]
        }), 200
        
    except Exception as e:
        logger.error(f"Error handling calculate cost: {str(e)}")
        return jsonify({'response': 'Sorry, I encountered an error calculating the cost. Please try again.'}), 500

def handle_company_info(user_message, user):
    """Handle company information requests"""
    try:
        company_info = db_service.get_company_info()
        
        response = f"Welcome to {company_info['company_name']}!\n\n"
        response += f"{company_info['description']}\n\n"
        response += "Our features include:\n"
        for feature in company_info['features']:
            response += f"• {feature}\n"
        
        response += f"\nContact Information:\n"
        response += f"Email: {company_info['contact_info']['email']}\n"
        response += f"Phone: {company_info['contact_info']['phone']}\n"
        response += f"Address: {company_info['contact_info']['address']}\n"
        
        save_conversation(user.id, user_message, response)
        return jsonify({
            'response': response,
            'action_buttons': [
                {'text': 'Place Order', 'action': 'place_order'},
                {'text': 'Track Order', 'action': 'track_order'},
                {'text': 'Get Help', 'action': 'help'}
            ]
        }), 200
        
    except Exception as e:
        logger.error(f"Error handling company info: {str(e)}")
        return jsonify({'response': 'Sorry, I encountered an error retrieving company information.'}), 500

def handle_product_info_or_query(user_message, user, context_data):
    """Handle product information and database queries"""
    try:
        db_service = get_db_service()
        llm_service = get_llm_service()
        
        # For distributors, handle dynamic database queries
        if user.user_type == 'distributor':
            # Check if this is a complex database query
            message_lower = user_message.lower()
            
            # Check for complex queries like "how many orders", "total revenue", "top products", etc.
            complex_query_indicators = [
                'how many', 'total', 'count', 'sum', 'average', 'top', 'most', 
                'least', 'analyze', 'statistics', 'stats', 'report', 'summary',
                'revenue', 'sales', 'quantity', 'amount'
            ]
            
            is_complex_query = any(indicator in message_lower for indicator in complex_query_indicators)
            
            if is_complex_query:
                # Use LLM to generate SQL or provide analytics
                return handle_distributor_analytics(user_message, user, db_service, llm_service)
        
        # For all users, handle simple product listing
        # Get user's warehouse for filtering
        warehouse = db_service.get_warehouse_by_location(user.nearest_warehouse) if user.nearest_warehouse else None
        
        # Get all products from user's warehouse or all products
        if warehouse:
            products = db_service.get_products_by_warehouse(warehouse.id)
        else:
            # Get all products if no warehouse
            products = Product.query.filter_by(is_active=True).all()
        
        if not products:
            response = "No products are currently available in the database."
        else:
            # Build product list response
            response = f"Here are all the products available in the database:\n\n"
            
            # Group by product code (handle duplicates)
            unique_products = {}
            for product in products:
                if product.product_code not in unique_products:
                    unique_products[product.product_code] = {
                        'name': product.product_name,
                        'code': product.product_code,
                        'price': product.price_of_product,
                        'available': product.available_for_sale,
                        'warehouse': product.warehouse.location_name if product.warehouse else 'N/A'
                    }
                else:
                    # If duplicate, add to available quantity
                    unique_products[product.product_code]['available'] += product.available_for_sale
            
            # Display products
            for code, info in unique_products.items():
                response += f"**{info['name']} ({info['code']})**\n"
                response += f"  • Price: ${info['price']:.2f}\n"
                response += f"  • Available Stock: {info['available']} units\n"
                response += f"  • Warehouse: {info['warehouse']}\n\n"
            
            response += f"\n**Total Products:** {len(unique_products)}\n"
            response += "\nWould you like to place an order for any of these products?"
        
        save_conversation(user.id, user_message, response)
        return jsonify({
            'response': response,
            'action_buttons': [
                {'text': 'Place Order', 'action': 'place_order'},
                {'text': 'View Products', 'action': 'view_products'},
                {'text': 'Get Help', 'action': 'help'}
            ]
        }), 200
        
    except Exception as e:
        logger.error(f"Error handling product info/query: {str(e)}")
        return jsonify({'response': 'Sorry, I encountered an error retrieving product information. Please try again.'}), 500

def handle_distributor_analytics(user_message, user, db_service, llm_service):
    """Handle dynamic database queries and analytics for distributors"""
    try:
        from app.models import Order, OrderItem, Product, User
        
        # Build warehouse context
        warehouse_location = user.nearest_warehouse
        
        # Get relevant data for analytics
        warehouse_orders = Order.query.filter_by(warehouse_location=warehouse_location).all()
        
        # Create context for LLM
        analytics_context = f"""
Warehouse: {warehouse_location}
Total Orders: {len(warehouse_orders)}
Recent Orders: {min(10, len(warehouse_orders))} orders
Order Statuses: {', '.join(set(o.status for o in warehouse_orders[:10]))}

Available Tables and Data:
- orders: Order information (order_id, status, total_amount, order_date, user_email, warehouse_location)
- order_items: Order line items (product_code, quantity, unit_price, total_price)
- products: Product information (product_code, product_name, price_of_product, available_for_sale, warehouse_id)
- pending_order_products: Pending orders waiting for stock (product_code, requested_quantity, customer, status)
- users: Customer information (name, email, user_type, warehouse_location)

User Query: {user_message}
"""
        
        # Use LLM to generate SQL or provide insights
        llm_prompt = f"""You are an AI assistant helping a distributor query their database.
        
Context:
{analytics_context}

Based on the user's query, provide a helpful response using the database information available.
You can answer questions about:
- Order statistics and totals
- Product availability and inventory
- Customer information
- Revenue and sales analytics
- Pending orders

Respond in a conversational but informative way, providing specific numbers and insights.
If the query requires data that might not be available, provide a helpful alternative response.

User Query: "{user_message}"

Provide a direct answer:"""
        
        response_obj = llm_service.client.chat.completions.create(
            model='llama-3.3-70b-versatile',
            messages=[{"role": "user", "content": llm_prompt}],
            temperature=0.2,
            max_tokens=500
        )
        
        response_text = response_obj.choices[0].message.content.strip()
        
        # Try to enhance with actual data
        if 'how many orders' in user_message.lower() or 'count of orders' in user_message.lower():
            response_text += f"\n\n**Actual Data:**\n"
            response_text += f"• Total orders in warehouse: {len(warehouse_orders)}\n"
            
            # Count by status
            from collections import Counter
            status_counts = Counter(o.status for o in warehouse_orders)
            for status, count in status_counts.items():
                response_text += f"• {status}: {count}\n"
        
        save_conversation(user.id, user_message, response_text)
        return jsonify({
            'response': response_text,
            'action_buttons': [
                {'text': 'View Orders', 'action': 'track_order'},
                {'text': 'View Products', 'action': 'view_products'}
            ]
        }), 200
        
    except Exception as e:
        logger.error(f"Error handling distributor analytics: {str(e)}")
        return jsonify({'response': 'Sorry, I encountered an error processing your analytics request. Please try again.'}), 500

def handle_web_search(user_message, user, context_data):
    """Handle web search requests"""
    try:
        web_search_service = get_web_search_service()
        search_result = web_search_service.search(user_message)
        
        if search_result['success']:
            response = f"Here's what I found about '{user_message}':\n\n"
            response += search_result['content']
            save_conversation(user.id, user_message, response)
            return jsonify({
                'response': response,
                'sources': search_result.get('sources', [])
            }), 200
        else:
            response = f"I couldn't find specific information about '{user_message}'. Please try rephrasing your question or ask about our products and services."
            save_conversation(user.id, user_message, response)
            return jsonify({
                'response': response,
                'action_buttons': [
                    {'text': 'View Products', 'action': 'view_products'},
                    {'text': 'Get Help', 'action': 'help'}
                ]
            }), 200
            
    except Exception as e:
        logger.error(f"Error handling web search: {str(e)}")
        return jsonify({'response': 'Sorry, I encountered an error with the web search.'}), 500

def handle_general_conversation(user_message, user, context_data):
    """Handle general conversation using LLM"""
    try:
        llm_service = get_llm_service()
        
        if not llm_service.client:
            response = "I'm here to help you with orders, tracking, and company information. How can I assist you today?"
            save_conversation(user.id, user_message, response)
            return jsonify({
                'response': response,
                'action_buttons': [
                    {'text': 'Place Order', 'action': 'place_order'},
                    {'text': 'Track Order', 'action': 'track_order'},
                    {'text': 'Company Info', 'action': 'company_info'}
                ]
            }), 200
        
        # Generate contextual response
        context_prompt = f"""You are Quantum Blue's AI assistant for RB (Powered by Quantum Blue AI). 
        
User: {user_message}

User Context:
- Name: {user.name}
- Type: {user.user_type}
- Role: {user.role or 'N/A'}
- Warehouse: {user.nearest_warehouse or 'N/A'}

Your task:
1. Provide a helpful, friendly response
2. Guide the user toward our main services (ordering, tracking, company info)
3. Be conversational but professional
4. If the user seems confused, offer to help with specific tasks

Respond naturally and helpfully."""

        response_obj = llm_service.client.chat.completions.create(
            model=current_app.config.get('GROQ_MODEL', 'mixtral-8x7b-32768'),
            messages=[{"role": "user", "content": context_prompt}],
            temperature=0.7,
            max_tokens=500
        )
        
        response = response_obj.choices[0].message.content
        save_conversation(user.id, user_message, response)
        
        return jsonify({
            'response': response,
            'action_buttons': [
                {'text': 'Place Order', 'action': 'place_order'},
                {'text': 'Track Order', 'action': 'track_order'},
                {'text': 'Company Info', 'action': 'company_info'},
                {'text': 'Get Help', 'action': 'help'}
            ]
        }), 200
        
    except Exception as e:
        logger.error(f"Error handling general conversation: {str(e)}")
        response = "I'm here to help you with orders, tracking, and company information. How can I assist you today?"
        save_conversation(user.id, user_message, response)
        return jsonify({
            'response': response,
            'action_buttons': [
                {'text': 'Place Order', 'action': 'place_order'},
                {'text': 'Track Order', 'action': 'track_order'},
                {'text': 'Company Info', 'action': 'company_info'}
            ]
        }), 200

def generate_welcome_message(user):
    """Generate personalized welcome message based on user type"""
    if user.user_type == 'customer':
        return f"Welcome back, {user.name}! I'm here to help you with your orders and answer any questions about our products. What would you like to do today?"
    elif user.user_type == 'mr':
        return f"Hello {user.name}! As a Medical Representative, you can place orders for your clients and track deliveries. How can I assist you today?"
    elif user.user_type == 'distributor':
        return f"Welcome {user.name}! As a Distributor, you can manage orders, confirm deliveries, and track inventory. What would you like to do?"
    elif user.user_type == 'pharmacy':
        return f"Hello {user.name}! As a Pharmacy, you can place orders and track your deliveries. How can I help you today?"
    else:
        return f"Welcome back, {user.name}! I'm here to help you with your orders and answer any questions. What would you like to do today?"

def save_conversation(user_id, user_message, bot_response):
    """Save conversation to database"""
    try:
        db_service = get_db_service()
        session_id = session.get('session_id')
        
        if session_id:
            db_service.save_conversation(
                user_id=user_id,
                session_id=session_id,
                user_message=user_message,
                bot_response=bot_response
            )
    except Exception as e:
        logger.error(f"Error saving conversation: {str(e)}")

@chatbot_bp.route('/place_order', methods=['POST'])
def place_order():
    """Place order from cart"""
    try:
        user_id = session.get('user_id')
        if not user_id:
            return jsonify({'error': 'User not logged in'}), 401
        
        enhanced_order_service = get_enhanced_order_service()
        result = enhanced_order_service.place_order(user_id)
        
        if result['success']:
            return jsonify({
                'success': True,
                'message': result['message'],
                'order_id': result['order_id'],
                'order_summary': result['order_summary']
            }), 200
        else:
            return jsonify({
                'success': False,
                'message': result['message']
            }), 400
            
    except Exception as e:
        logger.error(f"Error placing order: {str(e)}")
        return jsonify({'error': 'Error placing order'}), 500

@chatbot_bp.route('/cart', methods=['GET'])
def get_cart():
    """Get user's cart items"""
    try:
        user_id = session.get('user_id')
        if not user_id:
            return jsonify({'error': 'User not logged in'}), 401
        
        cart_items = db_service.get_cart_items(user_id)
        cart_data = []
        
        for item in cart_items:
            cart_data.append({
                'id': item.id,
                'product_code': item.product_code,
                'product_name': item.product.product_name,
                'quantity': item.product_quantity,
                'unit_price': item.unit_price,
                'total_price': item.total_price,
                'base_price': item.base_price,
                'discount_amount': item.discount_amount,
                'final_price': item.final_price,
                'scheme_applied': item.scheme_applied,
                'free_quantity': item.free_quantity,
                'paid_quantity': item.paid_quantity
            })
        
        return jsonify({'cart_items': cart_data}), 200
        
    except Exception as e:
        logger.error(f"Error getting cart: {str(e)}")
        return jsonify({'error': 'Error getting cart'}), 500

@chatbot_bp.route('/cart/<int:item_id>', methods=['DELETE'])
def remove_from_cart(item_id):
    """Remove item from cart"""
    try:
        user_id = session.get('user_id')
        if not user_id:
            return jsonify({'error': 'User not logged in'}), 401
        
        success, message = db_service.remove_from_cart(item_id)
        
        if success:
            return jsonify({'message': message}), 200
        else:
            return jsonify({'error': message}), 400
            
    except Exception as e:
        logger.error(f"Error removing from cart: {str(e)}")
        return jsonify({'error': 'Error removing from cart'}), 500

@chatbot_bp.route('/distributor/confirm_order', methods=['POST'])
def distributor_confirm_order():
    """Distributor confirm order endpoint"""
    try:
        data = request.get_json()
        order_id = data.get('order_id')
        distributor_user_id = session.get('user_id')
        
        if not distributor_user_id:
            return jsonify({'error': 'User not logged in'}), 401
        
        user = User.query.get(distributor_user_id)
        if not user or user.user_type != 'distributor':
            return jsonify({'error': 'Access denied. Distributor access required.'}), 403
        
        enhanced_order_service = get_enhanced_order_service()
        result = enhanced_order_service.confirm_order_by_distributor(order_id, distributor_user_id)
        
        if result['success']:
            return jsonify({
                'success': True,
                'message': result['message'],
                'invoice_number': result['invoice_number']
            }), 200
        else:
            return jsonify({
                'success': False,
                'message': result['message']
            }), 400
            
    except Exception as e:
        logger.error(f"Error confirming order: {str(e)}")
        return jsonify({'error': 'Error confirming order'}), 500
