import logging
import json
from flask import current_app
from app.groq_service import GroqService

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class LLMClassificationService:
    """Service for LLM-driven intent classification"""
    
    def __init__(self):
        self.groq_service = GroqService()
        self.logger = logger
    
    def _clean_json_response(self, result_text):
        """
        Clean up markdown code blocks from LLM responses
        """
        if result_text.startswith('```') and result_text.endswith('```'):
            # Remove markdown code block formatting
            lines = result_text.split('\n')
            if len(lines) > 2:
                result_text = '\n'.join(lines[1:-1])  # Remove first and last lines
            else:
                result_text = result_text.replace('```', '').strip()
        elif '```json' in result_text:
            # Handle ```json code blocks
            start_idx = result_text.find('```json') + 7
            end_idx = result_text.rfind('```')
            if end_idx > start_idx:
                result_text = result_text[start_idx:end_idx].strip()
        
        return result_text
    
    def classify_message(self, user_message, context_data=None):
        """
        Alias for classify_user_intent for backward compatibility
        """
        return self.classify_user_intent(user_message, context_data)
    
    def classify_user_intent(self, user_message, context_data=None):
        """
        Classify user intent using LLM
        Returns classification with percentages
        """
        if not self.groq_service.client:
            self.logger.warning("Groq client not available for classification")
            return self._get_fallback_classification(user_message)
        
        try:
            # Build context for classification
            context_info = ""
            if context_data:
                if 'user_warehouse' in context_data:
                    context_info += f"User's warehouse: {context_data['user_warehouse']}\n"
                if 'recent_orders' in context_data:
                    context_info += f"Recent orders: {len(context_data['recent_orders'])} found\n"
            
            classification_prompt = f"""You are an AI intent classifier for "Quantum Blue" chatbot. 
Analyze the user's message and classify it into one of these categories with confidence percentages:

Categories:
1. PLACE_ORDER - User wants to place an order, buy products, add to cart
2. CALCULATE_COST - User wants to know the cost/price of products or calculate order total
3. TRACK_ORDER - User wants to check order status, track delivery, order history
4. COMPANY_INFO - User asks about company, services, contact info, FAQ
5. WEB_SEARCH - User needs current/real-time information not in database
6. OTHER - General conversation, greetings, unclear requests

User Message: "{user_message}"

Context: {context_info}

Respond with ONLY a JSON object in this exact format:
{{
    "classification": "CATEGORY_NAME",
    "confidence": 0.85,
    "reasoning": "Brief explanation of why this classification was chosen",
    "percentages": {{
        "PLACE_ORDER": 0.15,
        "CALCULATE_COST": 0.20,
        "TRACK_ORDER": 0.15,
        "COMPANY_INFO": 0.10,
        "WEB_SEARCH": 0.05,
        "OTHER": 0.35
    }}
}}

Be precise and consider the context provided."""

            response = self.groq_service.client.chat.completions.create(
                model=current_app.config.get('GROQ_MODEL', 'mixtral-8x7b-32768'),
                messages=[{"role": "user", "content": classification_prompt}],
                temperature=0.1,
                max_tokens=500
            )
            
            result_text = response.choices[0].message.content.strip()
            result_text = self._clean_json_response(result_text)
            
            # Try to parse JSON response
            try:
                classification_result = json.loads(result_text)
                self.logger.info(f"Intent classified as: {classification_result.get('classification')} with confidence {classification_result.get('confidence')}")
                return classification_result
            except json.JSONDecodeError:
                self.logger.error(f"Failed to parse classification JSON: {result_text}")
                return self._get_fallback_classification(user_message)
                
        except Exception as e:
            self.logger.error(f"Classification error: {str(e)}")
            return self._get_fallback_classification(user_message)
    
    def _get_fallback_classification(self, user_message):
        """Fallback classification when LLM is not available"""
        message_lower = user_message.lower()
        
        # Simple keyword-based classification
        if any(word in message_lower for word in ['order', 'buy', 'purchase', 'cart', 'add']):
            return {
                "classification": "PLACE_ORDER",
                "confidence": 0.7,
                "reasoning": "Keyword-based classification",
                "percentages": {
                    "PLACE_ORDER": 0.7,
                    "CALCULATE_COST": 0.1,
                    "TRACK_ORDER": 0.1,
                    "COMPANY_INFO": 0.1,
                    "WEB_SEARCH": 0.0,
                    "OTHER": 0.0
                }
            }
        elif any(word in message_lower for word in ['cost', 'price', 'total', 'calculate', 'final cost', 'how much', 'amount']):
            return {
                "classification": "CALCULATE_COST",
                "confidence": 0.8,
                "reasoning": "Keyword-based classification for cost calculation",
                "percentages": {
                    "PLACE_ORDER": 0.1,
                    "CALCULATE_COST": 0.8,
                    "TRACK_ORDER": 0.0,
                    "COMPANY_INFO": 0.0,
                    "WEB_SEARCH": 0.0,
                    "OTHER": 0.1
                }
            }
        elif any(word in message_lower for word in ['track', 'status', 'delivery', 'history']):
            return {
                "classification": "TRACK_ORDER",
                "confidence": 0.7,
                "reasoning": "Keyword-based classification",
                "percentages": {
                    "PLACE_ORDER": 0.1,
                    "CALCULATE_COST": 0.1,
                    "TRACK_ORDER": 0.7,
                    "COMPANY_INFO": 0.1,
                    "WEB_SEARCH": 0.0,
                    "OTHER": 0.0
                }
            }
        elif any(word in message_lower for word in ['company', 'about', 'contact', 'help', 'info']):
            return {
                "classification": "COMPANY_INFO",
                "confidence": 0.6,
                "reasoning": "Keyword-based classification",
                "percentages": {
                    "PLACE_ORDER": 0.1,
                    "CALCULATE_COST": 0.1,
                    "TRACK_ORDER": 0.1,
                    "COMPANY_INFO": 0.6,
                    "WEB_SEARCH": 0.1,
                    "OTHER": 0.0
                }
            }
        else:
            return {
                "classification": "OTHER",
                "confidence": 0.5,
                "reasoning": "Default classification",
                "percentages": {
                    "PLACE_ORDER": 0.1,
                    "CALCULATE_COST": 0.1,
                    "TRACK_ORDER": 0.1,
                    "COMPANY_INFO": 0.2,
                    "WEB_SEARCH": 0.1,
                    "OTHER": 0.4
                }
            }
    
    def should_perform_web_search(self, classification_result, user_message):
        """
        Determine if web search is needed based on classification
        """
        if classification_result.get('classification') == 'WEB_SEARCH':
            return True
        
        # Additional logic for web search
        message_lower = user_message.lower()
        web_search_keywords = [
            'latest', 'current', 'today', 'recent', 'news', 'update',
            'price', 'market', 'trend', 'forecast'
        ]
        
        if any(keyword in message_lower for keyword in web_search_keywords):
            return True
        
        return False
    
    def generate_order_flow_response(self, user_message, products, user_warehouse):
        """
        Generate response for order placement flow
        """
        if not self.groq_service.client:
            return self._get_fallback_order_response(products)
        
        try:
            # Format products for LLM
            products_info = ""
            for product in products[:10]:  # Limit to 10 products
                products_info += f"- {product.product_name} (Code: {product.product_code}) - ${product.price_of_product} - Available: {product.available_for_sale}\n"
            
            order_prompt = f"""You are Quantum Blue's AI assistant helping with order placement.

User Message: "{user_message}"

Available Products in {user_warehouse}:
{products_info}

Your task:
1. Understand what the user wants to order
2. Suggest relevant products with upsells
3. Highlight any discounts or schemes
4. Be conversational and motivating
5. Ask for confirmation before finalizing

Respond in a friendly, sales-oriented manner. If the user's request is unclear, ask clarifying questions."""

            response = self.groq_service.client.chat.completions.create(
                model=current_app.config.get('GROQ_MODEL', 'mixtral-8x7b-32768'),
                messages=[{"role": "user", "content": order_prompt}],
                temperature=0.7,
                max_tokens=1000
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            self.logger.error(f"Order flow response error: {str(e)}")
            return self._get_fallback_order_response(products)
    
    def parse_order_details(self, user_message, products, conversation_history=None):
        """
        Parse order details from user message and return cart items
        """
        if not self.groq_service.client:
            return self._parse_order_fallback(user_message, products)
        
        try:
            # Format products for LLM
            products_info = ""
            for product in products:
                products_info += f"- {product.product_name} (Code: {product.product_code}) - ${product.price_of_product} - Available: {product.available_for_sale}\n"
            
            # Build conversation context if available
            conversation_context = ""
            if conversation_history:
                conversation_context = "Recent conversation:\n"
                for msg in conversation_history[-5:]:  # Last 5 messages
                    conversation_context += f"User: {msg.get('user_message', '')}\n"
                    conversation_context += f"Bot: {msg.get('bot_response', '')}\n"
            
            parse_prompt = f"""You are an order parser for Quantum Blue. Parse the user's order request and extract the products and quantities they want to order.

Current User Message: "{user_message}"

{conversation_context}

Available Products:
{products_info}

Extract the following information:
1. Product codes and quantities the user wants to order
2. Only include products that are available in the list above
3. If quantities are not specified, assume 1
4. If product names are mentioned, match them to the correct product codes
5. Look at the conversation history to find order details if the current message is just confirmation

Common product mappings:
- "quantum processor" or "processor" → QB001
- "neural network module" or "neural module" → QB002  
- "ai memory card" or "memory card" → QB003
- "quantum sensors" or "sensors" → QB004
- "ai controller" or "controller" → QB005

Respond with ONLY a JSON object in this exact format:
{{
    "cart_items": [
        {{"product_code": "QB001", "quantity": 100}},
        {{"product_code": "QB004", "quantity": 50}}
    ],
    "total_items": 2,
    "order_ready": true
}}

If the user's message is unclear or doesn't contain specific order details, set "order_ready" to false."""

            response = self.groq_service.client.chat.completions.create(
                model=current_app.config.get('GROQ_MODEL', 'mixtral-8x7b-32768'),
                messages=[{"role": "user", "content": parse_prompt}],
                temperature=0.1,
                max_tokens=500
            )
            
            result_text = response.choices[0].message.content.strip()
            result_text = self._clean_json_response(result_text)
            
            # Try to parse JSON response
            try:
                import json
                order_data = json.loads(result_text)
                return order_data
            except json.JSONDecodeError:
                self.logger.error(f"Failed to parse order JSON: {result_text}")
                return self._parse_order_fallback(user_message, products)
                
        except Exception as e:
            self.logger.error(f"Order parsing error: {str(e)}")
            return self._parse_order_fallback(user_message, products)
    
    def _parse_order_fallback(self, user_message, products):
        """
        Fallback order parsing using simple keyword matching
        """
        message_lower = user_message.lower()
        cart_items = []
        
        # Simple keyword matching for common products
        product_mappings = {
            'quantum processor': 'QB001',
            'neural network module': 'QB002', 
            'ai memory card': 'QB003',
            'quantum sensors': 'QB004',
            'ai controller': 'QB005'
        }
        
        # Extract quantities and products
        import re
        quantity_pattern = r'(\d+)\s*(?:units?|pieces?|items?)?\s*(?:of\s*)?'
        
        for product_name, product_code in product_mappings.items():
            if product_name in message_lower:
                # Look for quantity before the product name
                quantity_match = re.search(rf'(\d+)\s*(?:units?|pieces?|items?)?\s*(?:of\s*)?{product_name}', message_lower)
                quantity = int(quantity_match.group(1)) if quantity_match else 1
                
                cart_items.append({
                    "product_code": product_code,
                    "quantity": quantity
                })
        
        return {
            "cart_items": cart_items,
            "total_items": len(cart_items),
            "order_ready": len(cart_items) > 0
        }
    
    def calculate_order_cost(self, user_message, products, conversation_history=None):
        """
        Calculate the cost of an order based on user message and conversation history
        """
        if not self.groq_service.client:
            return self._calculate_cost_fallback(user_message, products)
        
        try:
            # Format products for LLM
            products_info = ""
            for product in products:
                products_info += f"- {product.product_name} (Code: {product.product_code}) - ${product.price_of_product} - Available: {product.available_for_sale}\n"
            
            # Build conversation context if available
            conversation_context = ""
            if conversation_history:
                conversation_context = "Recent conversation:\n"
                for msg in conversation_history[-5:]:  # Last 5 messages
                    conversation_context += f"User: {msg.get('user_message', '')}\n"
                    conversation_context += f"Bot: {msg.get('bot_response', '')}\n"
            
            cost_prompt = f"""You are a cost calculator for Quantum Blue. Calculate the total cost of the user's order based on their request and conversation history.

Current User Message: "{user_message}"

{conversation_context}

Available Products:
{products_info}

Calculate the following:
1. Identify the products and quantities the user wants
2. Calculate the unit price × quantity for each item
3. Calculate the subtotal
4. Apply any applicable discounts (5% for orders over $5000, bulk discounts, etc.)
5. Calculate the final total

Common product mappings:
- "quantum processor" or "processor" → QB001 ($2500)
- "neural network module" or "neural module" → QB002 ($1200)  
- "ai memory card" or "memory card" → QB003 ($800)
- "quantum sensors" or "sensors" → QB004 ($1800)
- "ai controller" or "controller" → QB005 ($950)

Respond with ONLY a JSON object in this exact format:
{{
    "order_items": [
        {{"product_name": "Quantum Processor", "product_code": "QB001", "quantity": 100, "unit_price": 2500, "item_total": 250000}},
        {{"product_name": "AI Controller", "product_code": "QB005", "quantity": 100, "unit_price": 950, "item_total": 95000}}
    ],
    "subtotal": 345000,
    "discount_amount": 17250,
    "discount_percentage": 5,
    "final_total": 327750,
    "order_ready": true
}}

If the user's message is unclear or doesn't contain specific order details, set "order_ready" to false."""

            response = self.groq_service.client.chat.completions.create(
                model=current_app.config.get('GROQ_MODEL', 'mixtral-8x7b-32768'),
                messages=[{"role": "user", "content": cost_prompt}],
                temperature=0.1,
                max_tokens=800
            )
            
            result_text = response.choices[0].message.content.strip()
            result_text = self._clean_json_response(result_text)
            
            # Try to parse JSON response
            try:
                import json
                cost_data = json.loads(result_text)
                return cost_data
            except json.JSONDecodeError:
                self.logger.error(f"Failed to parse cost JSON: {result_text}")
                return self._calculate_cost_fallback(user_message, products)
                
        except Exception as e:
            self.logger.error(f"Cost calculation error: {str(e)}")
            return self._calculate_cost_fallback(user_message, products)
    
    def _calculate_cost_fallback(self, user_message, products):
        """
        Fallback cost calculation using simple keyword matching
        """
        message_lower = user_message.lower()
        
        # Simple keyword matching for common products
        product_mappings = {
            'quantum processor': {'code': 'QB001', 'price': 2500, 'name': 'Quantum Processor'},
            'neural network module': {'code': 'QB002', 'price': 1200, 'name': 'Neural Network Module'}, 
            'ai memory card': {'code': 'QB003', 'price': 800, 'name': 'AI Memory Card'},
            'quantum sensors': {'code': 'QB004', 'price': 1800, 'name': 'Quantum Sensors'},
            'ai controller': {'code': 'QB005', 'price': 950, 'name': 'AI Controller'}
        }
        
        order_items = []
        subtotal = 0
        
        # Extract quantities and products
        import re
        for product_name, product_info in product_mappings.items():
            if product_name in message_lower:
                # Look for quantity before the product name
                quantity_match = re.search(rf'(\d+)\s*(?:units?|pieces?|items?)?\s*(?:of\s*)?{product_name}', message_lower)
                quantity = int(quantity_match.group(1)) if quantity_match else 1
                
                item_total = product_info['price'] * quantity
                subtotal += item_total
                
                order_items.append({
                    "product_name": product_info['name'],
                    "product_code": product_info['code'],
                    "quantity": quantity,
                    "unit_price": product_info['price'],
                    "item_total": item_total
                })
        
        # Apply discount if applicable
        discount_amount = 0
        discount_percentage = 0
        if subtotal > 5000:
            discount_percentage = 5
            discount_amount = subtotal * 0.05
        
        final_total = subtotal - discount_amount
        
        return {
            "order_items": order_items,
            "subtotal": subtotal,
            "discount_amount": discount_amount,
            "discount_percentage": discount_percentage,
            "final_total": final_total,
            "order_ready": len(order_items) > 0
        }
    
    def _get_fallback_order_response(self, products):
        """Fallback response for order flow"""
        if not products:
            return "I don't see any products available in your warehouse. Please contact support."
        
        response = "Here are some products available for order:\n\n"
        for product in products[:5]:
            response += f"• {product.product_name} - ${product.price_of_product} (Available: {product.available_for_sale})\n"
        
        response += "\nWould you like to place an order for any of these products?"
        return response
    
    def generate_tracking_response(self, user_message, orders):
        """
        Generate response for order tracking
        """
        if not self.groq_service.client:
            return self._get_fallback_tracking_response(orders)
        
        try:
            # Format orders for LLM
            orders_info = ""
            for order in orders[:5]:  # Limit to 5 recent orders
                orders_info += f"- Order {order.order_id}: {order.status} (${order.total_amount}) - {order.order_date.strftime('%Y-%m-%d')}\n"
            
            tracking_prompt = f"""You are Quantum Blue's AI assistant helping with order tracking.

User Message: "{user_message}"

Recent Orders:
{orders_info}

Your task:
1. Provide order status information
2. Be helpful and informative
3. If no specific order is mentioned, show recent orders
4. Offer to help with specific order details

Respond in a helpful, professional manner."""

            response = self.groq_service.client.chat.completions.create(
                model=current_app.config.get('GROQ_MODEL', 'mixtral-8x7b-32768'),
                messages=[{"role": "user", "content": tracking_prompt}],
                temperature=0.5,
                max_tokens=800
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            self.logger.error(f"Tracking response error: {str(e)}")
            return self._get_fallback_tracking_response(orders)
    
    def _get_fallback_tracking_response(self, orders):
        """Fallback response for order tracking"""
        if not orders:
            return "I don't see any orders in your account. Would you like to place a new order?"
        
        response = "Here are your recent orders:\n\n"
        for order in orders[:3]:
            response += f"• Order {order.order_id}: {order.status} - ${order.total_amount}\n"
        
        response += "\nWould you like more details about any specific order?"
        return response
