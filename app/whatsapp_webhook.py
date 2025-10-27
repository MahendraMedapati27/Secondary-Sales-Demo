from flask import Blueprint, request, jsonify, current_app
from app import db
from app.models import User, Conversation, ChatSession
from app.whatsapp_service import WhatsAppService
from app.llm_classification_service import LLMClassificationService
from app.groq_service import GroqService
from app.enhanced_order_service import EnhancedOrderService
from app.database_service import DatabaseService
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
                # Create new user for WhatsApp
                user = User(
                    name=contact_name,
                    email=f"{from_number}@whatsapp.local",  # Placeholder email
                    phone=from_number,
                    email_verified=True,  # Skip email verification for WhatsApp users
                    warehouse_location="Default"  # Set default warehouse
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
    """Process WhatsApp message through the chatbot logic"""
    try:
        # Get services
        classification_service = get_classification_service()
        llm_service = get_llm_service()
        enhanced_order_service = get_enhanced_order_service()
        db_service = get_db_service()
        
        # Classify the message
        classification_result = classification_service.classify_message(message_text)
        intent = classification_result.get('classification', 'OTHER')
        confidence = classification_result.get('confidence', 0.0)
        
        logger.info(f"Classified WhatsApp message: {intent} (confidence: {confidence})")
        
        # Process based on intent
        if intent == 'PLACE_ORDER':
            # For WhatsApp, provide a simple order response
            response = "I'd be happy to help you place an order! Please visit our website or contact our sales team for detailed order processing. For now, I can help you with product information or answer any questions you have."
        elif intent == 'COMPANY_INFO':
            # Get product information
            products = db_service.get_products_by_warehouse(user.warehouse_location)
            if products:
                product_list = "\n".join([
                    f"• {p.product_name} - ₹{p.price_of_product} (Stock: {p.available_for_sale})"
                    for p in products[:10]  # Limit to 10 products
                ])
                response = f"Here are our available products:\n\n{product_list}\n\nType 'order [product name]' to place an order!"
            else:
                response = "I don't have product information available right now. Please try again later."
        elif intent == 'TRACK_ORDER':
            # Get user's orders
            orders = db_service.get_orders_by_user(user.id)
            if orders:
                order_list = "\n".join([
                    f"• Order {order.order_id} - Status: {order.status} - Amount: ₹{order.total_amount}"
                    for order in orders[:5]  # Show last 5 orders
                ])
                response = f"Your recent orders:\n\n{order_list}\n\nFor detailed tracking, please provide your order ID."
            else:
                response = "You don't have any orders yet. Start by browsing our products!"
        else:
            # General conversation using LLM
            system_prompt = f"""You are Quantum Blue, an AI assistant for a pharmaceutical distribution company. 
            The user is chatting via WhatsApp. Be helpful, professional, and concise.
            You can help with:
            - Product inquiries
            - Order placement
            - Order tracking
            - General questions about our services
            
            User's warehouse location: {user.warehouse_location}
            Current session: {session.session_id}"""
            
            llm_response = llm_service.generate_response(
                user_message=message_text,
                conversation_history=[]
            )
            response = llm_response.get('response', 'I apologize, but I encountered an error generating a response.')
        
        return response
        
    except Exception as e:
        logger.error(f"Error processing WhatsApp message: {str(e)}")
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
