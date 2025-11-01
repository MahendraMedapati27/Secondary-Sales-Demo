import logging
import json
from datetime import datetime
from flask import current_app
from app.groq_service import GroqService
from app.database_service import DatabaseService
from app.pricing_service import PricingService
from app.models import Product

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class LLMOrderService:
    """Enhanced LLM service for order processing and product extraction"""
    
    def __init__(self):
        self.groq_service = GroqService()
        self.db_service = DatabaseService()
        self.pricing_service = PricingService()
        self.logger = logger
    
    def extract_products_from_message(self, user_message, user_id=None, conversation_history=None):
        """
        Extract products and quantities from user message using LLM
        Returns structured data for cart management
        """
        if not self.groq_service.client:
            return self._extract_products_fallback(user_message)
        
        try:
            # Get available products dynamically from database
            products = self._get_available_products(user_id)
            products_info = self._format_products_for_llm(products)
            
            # Build product mapping dynamically
            product_code_map = {}
            for product in products:
                code = product.product_code
                name = product.product_name
                if code not in product_code_map:
                    product_code_map[code] = {
                        'name': name,
                        'variations': self._generate_product_variations(name, code)
                    }
            
            # Build conversation context
            conversation_context = ""
            if conversation_history:
                conversation_context = "Recent conversation:\n"
                for msg in conversation_history[-5:]:  # Last 5 messages
                    # Handle both Conversation objects and dictionaries
                    if hasattr(msg, 'user_message'):
                        user_msg = msg.user_message or ''
                        bot_msg = msg.bot_response or ''
                    else:
                        user_msg = msg.get('user_message', '')
                        bot_msg = msg.get('bot_response', '')
                    conversation_context += f"User: {user_msg}\n"
                    conversation_context += f"Bot: {bot_msg}\n"
            
            extraction_prompt = f"""You are an AI assistant for RB (Powered by Quantum Blue AI) that extracts product orders from user messages.

CRITICAL EXTRACTION RULES:
1. Extract quantities EXACTLY as written in the user's message - do NOT multiply, add, or modify numbers
2. If user says "6", extract 6 - NOT 60, NOT 600
3. If user says "10", extract 10 - NOT 100
4. If user says "5", extract 5 - NOT 50, NOT 500
5. DO NOT confuse numbers with product codes - product codes are like "001", "002" etc.

Current User Message: "{user_message}"

{conversation_context}

Available Products:
{products_info}

EXTRACTION RULES - READ CAREFULLY:

QUANTITY EXTRACTION (MOST IMPORTANT):
1. Read numbers EXACTLY as written in the user message
2. If user writes "6", the quantity is 6 (NOT 60, NOT 600)
3. If user writes "10", the quantity is 10 (NOT 100)
4. If user writes "5", the quantity is 5 (NOT 50, NOT 500)
5. Count the digits: single digit = single digit value, double digit = double digit value
6. NEVER multiply quantities by 10
7. NEVER confuse product codes "(001)" with quantities
8. If you see "- 6 Quantum Processor (001)" in a list, quantity is 6, product code is RB001

REMOVE OPERATIONS (CRITICAL - READ CAREFULLY):
9. If user message contains words like "remove", "delete", "take out", "subtract" → ONLY extract the product(s) EXPLICITLY mentioned
10. DO NOT extract products that are NOT mentioned in the remove request
11. If user says "remove 5 Quantum Sensors" → ONLY extract RB004 with quantity -5 (NOT other products)
12. If user says "remove 5 Neural Network Module Pro" → ONLY extract RB002 with quantity -5 (NOT other products)
13. If user says "remove only X" or "remove just X" → ONLY extract that specific product
14. NEVER extract multiple products for a single product remove request
15. ALWAYS set quantity to NEGATIVE for remove operations

PRODUCT MATCHING:
16. Match product names to the correct product codes from the available list
17. If quantity is not specified, default to 1
18. FOR REMOVE OPERATIONS: Extract ONLY the product(s) explicitly mentioned in the user's message
19. FOR ADD/ORDER OPERATIONS: Extract EVERY product mentioned in the message
20. HANDLE REMOVE OPERATIONS: If user says "remove X product", extract ONLY that product with NEGATIVE X quantity
21. HANDLE ADD OPERATIONS: If user says "add X product", set quantity to POSITIVE X

AVAILABLE PRODUCTS FROM DATABASE:
{products_info}

CRITICAL PRODUCT MATCHING RULES:
1. Match user's product mentions to the EXACT product names and codes listed above
2. Extract quantities carefully - if user says "60 Quantum Processor", quantity is 60
3. If user mentions product codes like "(001)", "(002)", match to the corresponding product code in the list above
4. Product codes can be in format "RB001" or "001" - both should match to the same product
5. Use fuzzy matching for product names - "quantum processor" should match "Quantum Blue AI Processor"
6. If product name is partially mentioned, match to the closest product in the list
7. BE VERY PRECISE with quantities - extract exact numbers mentioned by user

PRODUCT CODE HANDLING:
- User might say: "product 001", "RB001", "(001)", "code 001"
- All of these should match to the product code in the database
- Extract the numeric part and match it to the corresponding product code above

EXTRACTION EXAMPLES - FOLLOW THESE EXACTLY:

Example 1:
User Message: "Order 6 Quantum Processor (001)"
CORRECT Extraction: {{"product_code": "RB001", "quantity": 6, ...}}
WRONG Extraction: {{"product_code": "RB001", "quantity": 60, ...}} ← NEVER DO THIS

Example 2:
User Message: "Order 10 Neural Network Module Pro (002)"
CORRECT Extraction: {{"product_code": "RB002", "quantity": 10, ...}}
WRONG Extraction: {{"product_code": "RB002", "quantity": 25, ...}} ← NEVER DO THIS

Example 3 (Order):
User Message: "Order the following: - 6 Quantum Processor (001) - 10 Neural Network Module Pro (002)"
CORRECT Extraction:
[
  {{"product_code": "RB001", "quantity": 6, ...}},
  {{"product_code": "RB002", "quantity": 10, ...}}
]

Example 4 (Remove - Single Product):
User Message: "remove 5 Quantum Sensors Advanced"
CORRECT Extraction:
[
  {{"product_code": "RB004", "quantity": -5, ...}}  ← ONLY RB004, NEGATIVE for remove
]
WRONG Extraction (DO NOT DO THIS):
[
  {{"product_code": "RB001", "quantity": -6, ...}},  ← WRONG - user didn't mention RB001
  {{"product_code": "RB004", "quantity": -5, ...}}
]

Example 5 (Remove - Single Product):
User Message: "remove 5 Neural Network Module Pro"
CORRECT Extraction:
[
  {{"product_code": "RB002", "quantity": -5, ...}}  ← ONLY RB002, NEGATIVE for remove
]
WRONG Extraction (DO NOT DO THIS):
[
  {{"product_code": "RB001", "quantity": -6, ...}},  ← WRONG - user didn't mention RB001
  {{"product_code": "RB002", "quantity": -5, ...}}
]

Example 6 (Remove - User Clarifies):
User Message: "i have asked you to remove only network module pro"
CORRECT Extraction:
[
  {{"product_code": "RB002", "quantity": -10, ...}}  ← ONLY RB002, all quantity, NEGATIVE
]
WRONG Extraction (DO NOT DO THIS):
[
  {{"product_code": "RB001", "quantity": -6, ...}},  ← WRONG - user explicitly said "only network module pro"
  {{"product_code": "RB002", "quantity": -10, ...}},
  {{"product_code": "RB004", "quantity": -15, ...}}  ← WRONG - user explicitly said "only network module pro"
]

CRITICAL REMOVE OPERATION RULES:
- If user mentions ONE product to remove → Extract ONLY that product
- If user says "only X" or "just X" → Extract ONLY that product (ignore any other products)
- NEVER extract products that are NOT explicitly mentioned in remove requests
- ALWAYS set quantity to NEGATIVE for remove operations

CRITICAL QUANTITY EXTRACTION RULES:
- Read the number EXACTLY as written: "6" = 6, "10" = 10, "15" = 15, "5" = 5
- NEVER multiply by 10: if user says "6", NEVER extract "60"
- NEVER use product codes as quantities: "(001)" is a product code, NOT a quantity
- REMOVE operations MUST have NEGATIVE quantities: "remove 5" → quantity: -5
- ADD/ORDER operations have POSITIVE quantities: "order 5" → quantity: 5

Respond with ONLY a JSON object in this exact format (use actual product codes and names from the list above):
{{
    "extracted_products": [
        {{
            "product_code": "[EXACT_CODE_FROM_LIST]",
            "product_name": "[EXACT_NAME_FROM_LIST]",
            "quantity": [NUMBER],
            "confidence": 0.0-1.0,
            "original_text": "[text user mentioned]"
        }}
    ],
    "total_products": [number],
    "order_ready": true/false,
    "unclear_requests": [],
    "suggestions": []
}}

IMPORTANT: 
- product_code MUST match exactly one of the codes in the product list above
- product_name MUST match exactly one of the names in the product list above
- DO NOT use placeholder values - use real codes and names from the database list

If the user's message is unclear or doesn't contain specific order details, set "order_ready" to false and provide suggestions in the "suggestions" array."""

            response = self.groq_service.client.chat.completions.create(
                model=current_app.config.get('GROQ_MODEL', 'llama-3.3-70b-versatile'),
                messages=[{"role": "user", "content": extraction_prompt}],
                temperature=0.1,
                max_tokens=1000
            )
            
            result_text = response.choices[0].message.content.strip()
            result_text = self._clean_json_response(result_text)
            
            try:
                extraction_result = json.loads(result_text)
                
                # Normalize product codes (handle both RB001 and 001 formats)
                def normalize_product_code(code):
                    if not code:
                        return None
                    code = str(code).strip().upper()
                    # If it's just numbers (001, 002, etc.), add RB prefix
                    if code.isdigit() and len(code) <= 3:
                        return f"RB{code.zfill(3)}"
                    # If it already has RB prefix, return as is
                    if code.startswith('RB'):
                        return code
                    # Try to extract numeric part and add RB prefix
                    import re
                    numeric_part = re.search(r'\d+', code)
                    if numeric_part:
                        return f"RB{numeric_part.group().zfill(3)}"
                    return code
                
                # Process extracted products
                msg_lower = user_message.lower()
                
                # Check if this is a remove operation
                is_remove_operation = any(keyword in msg_lower for keyword in ['remove', 'delete', 'take out', 'subtract', 'minus', 'rm'])
                
                if is_remove_operation:
                    self.logger.info(f"🔍 Remove operation detected in message: '{user_message[:50]}...'")
                
                # For remove operations, extract explicitly mentioned product names/terms
                explicitly_mentioned_products = set()
                explicitly_mentioned_text = ""
                is_strict_remove = False  # For "only" or "just" keywords
                if is_remove_operation:
                    # Extract product-related terms from user message after "remove"/"delete" keywords
                    remove_keywords = ['remove', 'delete', 'take out', 'subtract', 'minus']
                    for keyword in remove_keywords:
                        if keyword in msg_lower:
                            # Get text after the keyword
                            idx = msg_lower.find(keyword)
                            text_after = user_message[idx + len(keyword):].strip()
                            explicitly_mentioned_text = text_after.lower()
                            
                            # Extract product identifiers (codes like 001, 002, or product name words)
                            import re
                            # Extract product codes mentioned
                            codes_mentioned = re.findall(r'\(?\s*0*(\d{1,3})\s*\)?|(?:RB|rb)?0*(\d{1,3})', text_after)
                            for code_match in codes_mentioned:
                                code = code_match[0] or code_match[1]
                                if code:
                                    explicitly_mentioned_products.add(f"RB{code.zfill(3)}")
                            
                            # Extract product name keywords (common product terms)
                            product_keywords = ['processor', 'sensor', 'memory', 'network', 'module', 'controller', 'neural', 'quantum']
                            for kw in product_keywords:
                                if kw in text_after.lower():
                                    explicitly_mentioned_products.add(kw)
                            
                            # Check for "only" or "just" - very strict matching
                            if 'only' in text_after.lower() or 'just' in text_after.lower():
                                is_strict_remove = True
                                self.logger.info(f"⚠️ 'only'/'just' keyword detected - strict product matching enabled")
                            
                            break
                
                filtered = []
                aggregate = {}
                
                for item in extraction_result.get('extracted_products', []):
                    code = item.get('product_code')
                    if not code:
                        continue
                    
                    # Normalize product code
                    normalized_code = normalize_product_code(code)
                    if not normalized_code:
                        continue
                    
                    qty = int(item.get('quantity', 0))
                    if qty == 0:
                        continue
                    
                    # CRITICAL: If remove operation detected and quantity is positive, make it negative
                    if is_remove_operation and qty > 0:
                        self.logger.warning(f"⚠️ Remove operation detected but LLM extracted positive qty={qty} for {normalized_code}. Converting to negative.")
                        qty = -qty
                    
                    # Get product name
                    product_name = item.get('product_name', '')
                    original_text = item.get('original_text', '')
                    
                    # Check if this product is mentioned in the message (more lenient matching)
                    is_mentioned = False
                    if original_text:
                        # Check if any part of original_text is in the message
                        original_words = original_text.lower().split()
                        for word in original_words:
                            if len(word) > 3 and word in msg_lower:  # Only check words longer than 3 chars
                                is_mentioned = True
                                break
                    
                    # Also check product name and code in message
                    if not is_mentioned:
                        if product_name:
                            product_name_words = product_name.lower().split()
                            for word in product_name_words:
                                if len(word) > 3 and word in msg_lower:
                                    is_mentioned = True
                                    break
                    
                    # Check if product code is in message (handle both formats)
                    if not is_mentioned:
                        code_variations = [
                            normalized_code.lower(),
                            normalized_code.replace('RB', '').lower(),
                            normalized_code.replace('RB', '').zfill(3).lower(),
                            code.lower()
                        ]
                        for var in code_variations:
                            if var in msg_lower or f"({var})" in msg_lower or f"- {var}" in msg_lower:
                                is_mentioned = True
                                break
                    
                    # For remove operations: STRICT FILTERING - only include if explicitly mentioned
                    # Only apply strict filtering if we found explicitly mentioned products
                    if is_remove_operation and len(explicitly_mentioned_products) > 0:
                        # Check if this product matches any explicitly mentioned product
                        product_matches = False
                        
                        # Check by product code
                        if normalized_code in explicitly_mentioned_products:
                            product_matches = True
                        
                        # Check by product name keywords
                        if not product_matches and product_name:
                            product_name_lower = product_name.lower()
                            
                            # First, check if the explicitly mentioned text (after "remove") is in the product name
                            if explicitly_mentioned_text:
                                # Remove quantity numbers and common words
                                text_for_matching = re.sub(r'\d+', '', explicitly_mentioned_text)
                                text_for_matching = re.sub(r'\b(only|just|the|a|an|from|cart|item|items|product|products)\b', '', text_for_matching)
                                text_for_matching = text_for_matching.strip()
                                
                                # Check if key words from the text are in product name
                                if text_for_matching:
                                    key_words = [w for w in text_for_matching.split() if len(w) > 3]
                                    if key_words:
                                        # Check if at least 2 key words match, or if single word matches well
                                        matches = sum(1 for word in key_words if word in product_name_lower)
                                        if matches >= min(2, len(key_words)) or (len(key_words) == 1 and key_words[0] in product_name_lower):
                                            product_matches = True
                            
                            # Also check individual mentioned terms
                            if not product_matches:
                                for mentioned_term in explicitly_mentioned_products:
                                    # If mentioned term is a keyword (not a code), check if it's in product name
                                    if not mentioned_term.startswith('RB') and mentioned_term in product_name_lower:
                                        product_matches = True
                                        break
                                    # Also check if key parts of product name match
                                    if 'network' in mentioned_term and 'network' in product_name_lower and 'module' in product_name_lower:
                                        product_matches = True
                                        break
                                    if 'processor' in mentioned_term and 'processor' in product_name_lower:
                                        product_matches = True
                                        break
                                    if 'sensor' in mentioned_term and 'sensor' in product_name_lower:
                                        product_matches = True
                                        break
                                    if 'memory' in mentioned_term and 'memory' in product_name_lower:
                                        product_matches = True
                                        break
                                    if 'controller' in mentioned_term and 'controller' in product_name_lower:
                                        product_matches = True
                                        break
                        
                        # If it doesn't match explicitly mentioned products, skip it
                        if not product_matches:
                            self.logger.warning(f"⚠️ Filtering out {normalized_code} ({product_name}) - not explicitly mentioned in remove request")
                            continue
                    
                    # If product is mentioned, add to aggregate
                    # IMPORTANT: Use the quantity from extraction, but ensure we're not double-counting
                    if is_mentioned:
                        # Only aggregate if the same code appears multiple times in CURRENT extraction
                        # This handles cases where user mentions same product twice in one message
                        aggregate[normalized_code] = aggregate.get(normalized_code, 0) + qty
                        
                        # Log for debugging
                        self.logger.info(f"Product {normalized_code} mentioned: extracted qty={qty}, "
                                       f"aggregated total={aggregate[normalized_code]}")
                
                # Post-extraction validation: Check if quantities match what user actually said
                def extract_quantity_from_message(msg, product_code):
                    """Try to find the actual quantity mentioned in user message for a product"""
                    import re
                    # Keep original case for better matching
                    code_num = product_code.replace('RB', '').replace('rb', '').strip()
                    
                    if not code_num:
                        return None
                    
                    # Pattern 1: List format "- 6 Product (001)" - MOST COMMON FORMAT
                    # Matches: "- 6 Quantum Processor (001)"
                    list_pattern = rf'-\s*(\d+)\s+[^-]*?\([^)]*?{code_num}[^)]*?\)'
                    
                    # Pattern 2: Direct format "6 Quantum Processor (001)"
                    direct_pattern = rf'(\d+)\s+[^\d\(]*?\([^)]*?{code_num}[^)]*?\)'
                    
                    # Pattern 3: With RB prefix "6 Product (RB001)"
                    rb_pattern = rf'(\d+)\s+[^\d\(]*?\(RB0*{code_num}\)'
                    
                    # Pattern 4: Number before any mention of code
                    number_before_pattern = rf'(\d+)\s+[^-\d]*?\([^)]*?0*{code_num}\)'
                    
                    # Try all patterns (order matters - most specific first)
                    patterns = [
                        list_pattern,           # "- 6 Product (001)" - most common
                        rb_pattern,            # "6 Product (RB001)"
                        direct_pattern,        # "6 Product (001)"
                        number_before_pattern, # General fallback
                    ]
                    
                    for pattern in patterns:
                        matches = re.findall(pattern, msg, re.IGNORECASE)
                        if matches:
                            try:
                                found_qty = int(matches[0])
                                # If found quantity is reasonable (1-999), return it
                                if 1 <= found_qty <= 999:
                                    self.logger.info(f"Validation: Found quantity {found_qty} for {product_code} using pattern matching")
                                    return found_qty
                            except (ValueError, IndexError):
                                continue
                    
                    self.logger.debug(f"Validation: Could not find quantity for {product_code} in message")
                    return None
                
                # Build final filtered list with validation
                for code, qty in aggregate.items():
                    # Find representative item for this code
                    rep = next((i for i in extraction_result.get('extracted_products', []) 
                               if normalize_product_code(i.get('product_code')) == code), None)
                    
                    if rep:
                        # Validate quantity: Check if it matches user message
                        validated_qty = qty
                        actual_qty_in_msg = extract_quantity_from_message(user_message, code)
                        
                        if actual_qty_in_msg is not None:
                            if actual_qty_in_msg != qty:
                                # LLM extracted wrong quantity, use the one from message
                                self.logger.warning(f"⚠️ QUANTITY CORRECTION for {code}: LLM extracted {qty}, but user message shows {actual_qty_in_msg}. CORRECTING to {actual_qty_in_msg}.")
                                validated_qty = actual_qty_in_msg
                            else:
                                self.logger.info(f"✓ Quantity validation passed for {code}: {qty}")
                        
                        filtered.append({
                            "product_code": code,
                            "product_name": rep.get('product_name', ''),
                            "quantity": validated_qty,
                            "confidence": rep.get('confidence', 0.9),
                            "original_text": rep.get('original_text', '')
                        })
                    else:
                        # Fallback: try to get product name from database
                        from app.models import Product
                        product = Product.query.filter_by(product_code=code).first()
                        if product:
                            filtered.append({
                                "product_code": code,
                                "product_name": product.product_name,
                                "quantity": qty,
                                "confidence": 0.85,
                                "original_text": user_message
                            })
                
                # If no products found through strict matching, try direct extraction without filtering
                if not filtered and extraction_result.get('extracted_products'):
                    self.logger.warning("No products passed filtering, trying direct extraction")
                    for item in extraction_result.get('extracted_products', []):
                        code = normalize_product_code(item.get('product_code'))
                        if code and int(item.get('quantity', 0)) > 0:
                            filtered.append({
                                "product_code": code,
                                "product_name": item.get('product_name', ''),
                                "quantity": int(item.get('quantity', 0)),
                                "confidence": item.get('confidence', 0.8),
                                "original_text": item.get('original_text', user_message)
                            })
                
                normalized = {
                    "extracted_products": filtered,
                    "total_products": len(filtered),
                    "order_ready": len(filtered) > 0,
                    "unclear_requests": extraction_result.get('unclear_requests', []),
                    "suggestions": extraction_result.get('suggestions', [])
                }
                self.logger.info(f"Products extracted: {len(normalized.get('extracted_products', []))}")
                if filtered:
                    self.logger.info(f"Extracted products: {[(p.get('product_code'), p.get('quantity')) for p in filtered]}")
                return normalized
            except json.JSONDecodeError:
                self.logger.error(f"Failed to parse extraction JSON: {result_text}")
                return self._extract_products_fallback(user_message, user_id)
                
        except Exception as e:
            error_msg = str(e)
            self.logger.error(f"Product extraction error: {error_msg}")
            # Check if it's a connection error - use fallback but warn user
            if 'Connection' in error_msg or 'timeout' in error_msg.lower():
                self.logger.warning("LLM connection failed, using database-based fallback extraction")
            return self._extract_products_fallback(user_message, user_id)
    
    def generate_order_summary(self, cart_items, user_info=None):
        """
        Generate a comprehensive order summary with pricing details
        """
        if not self.groq_service.client:
            return self._generate_summary_fallback(cart_items)
        
        try:
            # Calculate pricing for all items
            pricing_details = []
            total_amount = 0
            total_savings = 0
            
            for item in cart_items:
                pricing = self.pricing_service.calculate_product_pricing(
                    item.product_id, 
                    item.product_quantity
                )
                
                if 'error' not in pricing:
                    # Log detailed pricing for debugging
                    self.logger.info(f"Pricing for {pricing['product_code']}: Qty={pricing['quantity']}, Base=${pricing['base_price']}, "
                                   f"Final Price=${pricing['pricing']['final_price']}, Total Amount=${pricing['pricing']['total_amount']}, "
                                   f"Scheme={pricing['scheme'].get('name', 'None')}, Free Qty={pricing['scheme'].get('free_quantity', 0)}")
                    pricing_details.append(pricing)
                    total_amount += pricing['pricing']['total_amount']
                    total_savings += pricing['pricing']['savings']
                else:
                    # Log error but still try to include item in table with error message
                    self.logger.warning(f"Pricing error for cart item {item.id} (product_id: {item.product_id}): {pricing.get('error', 'Unknown error')}")
                    # Still add to details but mark as error for display
                    pricing_details.append({
                        'product_id': item.product_id,
                        'product_code': getattr(item.product, 'product_code', 'N/A'),
                        'product_name': getattr(item.product, 'product_name', 'Unknown Product'),
                        'quantity': item.product_quantity,
                        'base_price': 0,
                        'error': pricing.get('error', 'Pricing error'),
                        'pricing': {'total_amount': 0, 'savings': 0},
                        'discount': {'name': 'None', 'amount': 0},
                        'scheme': {'name': 'None', 'free_quantity': 0, 'paid_quantity': item.product_quantity}
                    })
            
            # Format pricing details for LLM in table format with discount and scheme
            pricing_info = "| Product | Qty | Unit Price | Discount | Scheme | Total |\n"
            pricing_info += "|---------|-----|------------|----------|--------|-------|\n"
            
            # Log total items for debugging
            self.logger.info(f"Generating order summary: {len(cart_items)} cart items, {len(pricing_details)} pricing details")
            
            # Verify all items are included
            if len(pricing_details) != len(cart_items):
                self.logger.warning(f"⚠️ MISMATCH: {len(cart_items)} cart items but only {len(pricing_details)} pricing details!")
            
            item_count = 0
            for pricing in pricing_details:
                item_count += 1
                self.logger.info(f"Adding table row #{item_count}: {pricing.get('product_code', 'N/A')} - Qty: {pricing.get('quantity', 0)}")
                # Include all items in table, even if there are errors (will show with $0.00)
                if 'error' in pricing:
                    self.logger.warning(f"Including item {pricing.get('product_name', 'Unknown')} with error: {pricing.get('error')}")
                    
                # Truncate long product names
                product_name = pricing['product_name']
                if len(product_name) > 20:
                    product_name = product_name[:17] + "..."
                
                product_display = f"{product_name} ({pricing['product_code']})"
                
                # Show actual ordered quantity, then free items separately
                ordered_qty = pricing['quantity']  # This is the actual quantity user ordered
                free_q = pricing['scheme'].get('free_quantity', 0)
                
                # Display: "6" or "6 + 2 free" format
                if free_q > 0:
                    quantity_display = f"{ordered_qty} + {free_q} free"
                else:
                    quantity_display = str(ordered_qty)
                
                # Discount display
                discount_amount = pricing['discount'].get('amount', 0)
                discount_name = pricing['discount'].get('name', 'None') if pricing['discount'].get('name') else 'None'
                if discount_amount > 0:
                    discount_display = f"{discount_name} (${discount_amount:.2f})"
                else:
                    discount_display = "None"
                
                # Scheme display
                scheme_name = pricing['scheme'].get('name', 'None') if pricing['scheme'].get('name') != "No Scheme" else "None"
                
                # Ensure we're using total_amount (not unit price)
                total_amt = pricing['pricing'].get('total_amount', 0)
                # Verify calculation: should be final_price * paid_quantity (or quantity for percentage schemes)
                final_unit_price = pricing['pricing'].get('final_price', 0)
                paid_qty = pricing['scheme'].get('paid_quantity', ordered_qty)
                calculated_total = final_unit_price * paid_qty
                
                # Detailed logging for debugging
                self.logger.info(f"Table row for {pricing['product_code']}: Qty={ordered_qty}, Base=${pricing['base_price']:.2f}, "
                               f"Final Unit Price=${final_unit_price:.2f}, Paid Qty={paid_qty}, "
                               f"Total Amount=${total_amt:.2f}, Calculated Total=${calculated_total:.2f}")
                
                # Log for debugging if mismatch (with tolerance for floating point errors)
                if abs(total_amt - calculated_total) > 0.02:  # Increased tolerance for rounding differences
                    self.logger.error(f"PRICING ERROR for {pricing['product_code']}: total_amount={total_amt} does NOT match "
                                    f"calculated (final_price * paid_qty)={calculated_total}. "
                                    f"Details: final_price={final_unit_price}, paid_qty={paid_qty}, quantity={ordered_qty}")
                    # Use calculated total if there's a mismatch
                    total_amt = calculated_total
                elif abs(total_amt - calculated_total) > 0.01:
                    # Just log as warning for small floating point differences
                    self.logger.warning(f"Minor pricing rounding difference for {pricing['product_code']}: "
                                      f"total_amount={total_amt} vs calculated={calculated_total} (diff: {abs(total_amt - calculated_total):.4f})")
                
                pricing_info += f"| {product_display} | {quantity_display} | ${pricing['base_price']:.2f} | {discount_display} | {scheme_name} | ${total_amt:.2f} |\n"
            
            user_context = ""
            if user_info:
                # Handle both User object and dictionary
                if hasattr(user_info, 'name'):
                    # It's a User object
                    user_context = f"""
User Information:
- Name: {user_info.name or 'N/A'}
- Type: {user_info.user_type or 'customer'}
- Role: {user_info.role or 'N/A'}
- Delivery Zone: {user_info.delivery_zone or 'N/A'}
- Nearest Warehouse: {user_info.nearest_warehouse or 'N/A'}
"""
                else:
                    # It's a dictionary
                    user_context = f"""
User Information:
- Name: {user_info.get('name', 'N/A')}
- Type: {user_info.get('user_type', 'customer')}
- Role: {user_info.get('role', 'N/A')}
- Delivery Zone: {user_info.get('delivery_zone', 'N/A')}
- Nearest Warehouse: {user_info.get('nearest_warehouse', 'N/A')}
"""
            
            # Count how many rows should be in the table
            row_count = len(pricing_details)

            summary_prompt = f"""You are Quantum Blue's AI assistant generating a concise order summary for RB (Powered by Quantum Blue AI).

Order Details Table (THIS TABLE HAS EXACTLY {row_count} ROWS - YOU MUST INCLUDE ALL {row_count} ROWS):
{pricing_info}

CRITICAL REQUIREMENTS:
1. The table above has EXACTLY {row_count} product rows - you MUST include ALL {row_count} rows in your response
2. Copy the table EXACTLY as shown - DO NOT remove any rows, DO NOT change any values
3. After the table, add EXACTLY 3 lines (not more, not less) as shown below

Order Summary Values:
- Total Amount: ${total_amount:.2f}
- Total Savings: ${total_savings:.2f}

REQUIRED OUTPUT FORMAT (copy this structure EXACTLY):
```
{pricing_info}
Total: ${total_amount:.2f}
Savings: ${total_savings:.2f}

Would you like to add more items, remove items, or confirm your order?
```

RULES:
- Include ALL {row_count} table rows - do NOT skip any
- After the table, add exactly 3 lines (Total, Savings, Question)
- DO NOT add any other text, explanations, or content
- DO NOT modify any numbers or values from the table"""

            response = self.groq_service.client.chat.completions.create(
                model=current_app.config.get('GROQ_MODEL', 'llama-3.3-70b-versatile'),
                messages=[{"role": "user", "content": summary_prompt}],
                temperature=0.1,  # Very low temperature for strict adherence
                max_tokens=300  # Slightly increased to ensure all rows fit
            )
            
            summary_text = response.choices[0].message.content
            
            # Validate that all rows are present in the summary
            expected_row_count = len(pricing_details)
            # Count table rows by counting the pattern "| ProductName |"
            lines = summary_text.split('\n')
            table_row_count = sum(1 for line in lines if line.strip().startswith('|') and 'Product' not in line and 'Qty' not in line and '---' not in line)
            
            if table_row_count < expected_row_count:
                self.logger.warning(f"⚠️ Table row count mismatch: Expected {expected_row_count} rows, found {table_row_count} rows in LLM response. Rebuilding table...")
                # Rebuild the summary with the correct table and exactly 3 lines after
                summary_text = pricing_info.rstrip() + f"\n\nTotal: ${total_amount:.2f}\nSavings: ${total_savings:.2f}\n\nWould you like to add more items, remove items, or confirm your order?"
                self.logger.info(f"✓ Rebuilt summary with {expected_row_count} table rows and exactly 3 lines after table")
            else:
                self.logger.info(f"✓ LLM response contains {table_row_count} table rows (expected {expected_row_count})")
            
            return {
                'summary': summary_text,
                'pricing_details': pricing_details,
                'total_amount': total_amount,
                'total_savings': total_savings,
                'item_count': len(pricing_details)
            }
            
        except Exception as e:
            self.logger.error(f"Order summary generation error: {str(e)}")
            return self._generate_summary_fallback(cart_items)
    
    def generate_stock_availability_message(self, stock_warnings, user_message, added_items):
        """
        Generate a friendly, natural message about stock availability issues using LLM
        """
        if not stock_warnings:
            return ""
        
        if not self.groq_service.client:
            # Fallback without LLM
            messages = []
            for warning in stock_warnings:
                messages.append(
                    f"Sorry, {warning['product_name']} ({warning['product_code']}) has only "
                    f"{warning['available']} units available, but you requested {warning['requested']}."
                )
            return "\n".join(messages)
        
        try:
            # Build context about stock issues
            stock_context = "Stock Availability Issues:\n"
            for warning in stock_warnings:
                stock_context += f"- {warning['product_name']} ({warning['product_code']}): " \
                               f"Requested {warning['requested']} units, but only {warning['available']} units available.\n"
            
            added_context = ""
            if added_items:
                added_context = "\nSuccessfully Added Items:\n"
                for item in added_items:
                    added_context += f"- {item['product_name']}: {item['quantity']} units\n"
            
            prompt = f"""You are Quantum Blue's AI assistant. A user has placed an order, but some products have insufficient stock.

{stock_context}
{added_context}

Generate a friendly, conversational message to inform the user about the stock availability issues. 

Requirements:
1. Be polite and empathetic
2. Clearly state which products have insufficient stock and what's available
3. Mention that other products (if any) were successfully added to their cart
4. Suggest they can proceed with available items or adjust quantities
5. Keep it concise (3-4 sentences maximum)
6. Be natural and conversational, not robotic

DO NOT use hardcoded templates. Generate a natural, friendly response."""

            response = self.groq_service.client.chat.completions.create(
                model=current_app.config.get('GROQ_MODEL', 'llama-3.3-70b-versatile'),
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                max_tokens=200
            )
            
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            self.logger.error(f"Error generating stock availability message: {str(e)}")
            # Fallback
            messages = []
            for warning in stock_warnings:
                messages.append(
                    f"Sorry, {warning['product_name']} ({warning['product_code']}) has only "
                    f"{warning['available']} units available, but you requested {warning['requested']}."
                )
            return "\n".join(messages)
    
    def generate_distributor_notification(self, order, order_items, placed_by_user):
        """
        Generate notification message for distributor about new order
        """
        if not self.groq_service.client:
            return self._generate_distributor_notification_fallback(order, order_items, placed_by_user)
        
        try:
            # Format order details
            order_details = f"""
Order ID: {order.order_id}
Order Date: {order.order_date.strftime('%Y-%m-%d %H:%M:%S')}
Status: {order.status}
Warehouse: {order.warehouse_location}

Placed By:
- Name: {placed_by_user.name}
- Type: {placed_by_user.user_type}
- Role: {placed_by_user.role or 'N/A'}
- Email: {placed_by_user.email}
- Phone: {placed_by_user.phone}
- Company: {placed_by_user.company_name or 'N/A'}

Order Items:"""
            
            for item in order_items:
                order_details += f"""
- {item.product.product_name} ({item.product_code})
  Quantity: {item.product_quantity_ordered}
  Unit Price: ${item.unit_price}
  Total: ${item.total_price}"""
            
            order_details += f"""

Total Amount: ${order.total_amount}
Order Stage: {order.order_stage}

Please review this order and confirm if the products and quantities are correct.
You can accept or modify the order as needed."""

            notification_prompt = f"""You are Quantum Blue's AI assistant generating a distributor notification for RB (Powered by Quantum Blue AI).

Order Details:
{order_details}

Your task:
1. Create a professional notification for the distributor
2. Clearly present all order information
3. Make it easy for the distributor to understand what needs to be done
4. Be professional but friendly
5. Include clear next steps for the distributor

Respond in a clear, professional manner suitable for business communication."""

            response = self.groq_service.client.chat.completions.create(
                model=current_app.config.get('GROQ_MODEL', 'llama-3.3-70b-versatile'),
                messages=[{"role": "user", "content": notification_prompt}],
                temperature=0.3,
                max_tokens=600
            )
            
            return {
                'notification': response.choices[0].message.content,
                'order_details': order_details
            }
            
        except Exception as e:
            self.logger.error(f"Distributor notification generation error: {str(e)}")
            return self._generate_distributor_notification_fallback(order, order_items, placed_by_user)
    
    def _get_available_products(self, user_id=None):
        """Get available products for the user"""
        if user_id:
            # Handle different user_id types
            if isinstance(user_id, str):
                # Try unique_id first
                user = self.db_service.get_user_by_unique_id(user_id)
            elif isinstance(user_id, int):
                # Direct user ID lookup
                from app.models import User
                user = User.query.get(user_id)
            else:
                user = None
            
            if user and user.nearest_warehouse:
                warehouse = self.db_service.get_warehouse_by_location(user.nearest_warehouse)
                if warehouse:
                    return self.db_service.get_products_by_warehouse(warehouse.id)
        
        # Fallback to all products
        return Product.query.filter_by(is_active=True).all()
    
    def _format_products_for_llm(self, products):
        """Format products for LLM consumption"""
        products_info = ""
        # Group by product_code to avoid duplicates
        seen_codes = set()
        for product in products[:50]:  # Limit to 50 products
            if product.product_code not in seen_codes:
                seen_codes.add(product.product_code)
                products_info += f"- Product Name: \"{product.product_name}\" | Product Code: \"{product.product_code}\" | Price: ${product.price_of_product} | Available Stock: {product.available_for_sale}\n"
        return products_info
    
    def _generate_product_variations(self, product_name, product_code):
        """Generate common variations of product name for matching"""
        name_lower = product_name.lower()
        variations = [product_name.lower()]
        
        # Split product name into words
        words = name_lower.split()
        
        # Generate variations
        if len(words) > 0:
            # First word
            variations.append(words[0])
            # Last word
            if len(words) > 1:
                variations.append(words[-1])
            # Key words (skip common words)
            skip_words = {'the', 'a', 'an', 'for', 'with', 'and', 'or', 'of', 'in', 'on', 'at', 'to'}
            key_words = [w for w in words if w not in skip_words]
            variations.extend(key_words)
            
            # Common abbreviations
            if 'quantum' in name_lower and 'processor' in name_lower:
                variations.extend(['processor', 'processors', 'quantum processor'])
            if 'neural' in name_lower and 'network' in name_lower:
                variations.extend(['neural network', 'neural module', 'neural networks'])
            if 'memory' in name_lower and 'card' in name_lower:
                variations.extend(['memory card', 'memory cards', 'ai memory'])
            if 'sensor' in name_lower:
                variations.extend(['sensors', 'sensor'])
            if 'controller' in name_lower:
                variations.extend(['controller', 'controllers', 'ai controller'])
        
        return list(set(variations))  # Remove duplicates
    
    def _clean_json_response(self, result_text):
        """Clean up markdown code blocks from LLM responses"""
        if result_text.startswith('```') and result_text.endswith('```'):
            lines = result_text.split('\n')
            if len(lines) > 2:
                result_text = '\n'.join(lines[1:-1])
            else:
                result_text = result_text.replace('```', '').strip()
        elif '```json' in result_text:
            start_idx = result_text.find('```json') + 7
            end_idx = result_text.rfind('```')
            if end_idx > start_idx:
                result_text = result_text[start_idx:end_idx].strip()
        return result_text
    
    def _extract_products_fallback(self, user_message, user_id=None):
        """Fallback product extraction using database and simple keyword matching"""
        import re
        message_lower = user_message.lower()
        cart_items = []
        
        # Get products dynamically from database instead of hardcoding
        try:
            products = self._get_available_products(user_id)
            # Build dynamic product mappings from database
            product_mappings = {}
            for product in products:
                code = product.product_code
                if code not in product_mappings:
                    variations = self._generate_product_variations(product.product_name, code)
                    product_mappings[code] = {
                        'name': product.product_name,
                        'keywords': variations + [code.lower(), code.replace('RB', '').lower()]
                    }
        except Exception as e:
            self.logger.error(f"Error fetching products for fallback extraction: {str(e)}")
            # Use minimal fallback if database fails
        product_mappings = {
                'RB001': {'name': 'Quantum Blue AI Processor', 'keywords': ['quantum processor', 'processors', 'processor', '001']},
                'RB002': {'name': 'Neural Network Module Pro', 'keywords': ['neural network', 'neural', '002']},
                'RB003': {'name': 'AI Memory Card Ultra', 'keywords': ['memory card', 'memory', '003']},
                'RB004': {'name': 'Quantum Sensors Advanced', 'keywords': ['sensors', 'sensor', '004']},
                'RB005': {'name': 'AI Controller Master', 'keywords': ['controller', 'controllers', '005']}
            }
        
        # First, try to extract product codes with quantities (e.g., "60 Quantum Processor (001)")
        # Pattern: number + product name + (code) or just code patterns
        code_pattern = r'(\d+)\s+(?:.*?)\s*\(?(\d{3}|RB\d{3}|RB\d{1,3})\)?'
        code_matches = re.finditer(code_pattern, user_message, re.IGNORECASE)
        
        for match in code_matches:
            quantity = int(match.group(1))
            code_part = match.group(2).upper().strip()
            
            # Normalize code
            if code_part.isdigit():
                code = f"RB{code_part.zfill(3)}"
            elif code_part.startswith('RB'):
                code = f"RB{code_part.replace('RB', '').zfill(3)}"
            else:
                continue
            
            if code in product_mappings:
                cart_items.append({
                    "product_code": code,
                    "product_name": product_mappings[code]['name'],
                    "quantity": quantity,
                    "confidence": 0.85,
                    "original_text": match.group(0)
                })
        
        # Also try patterns like "- 60 Quantum Processor (001)"
        bullet_pattern = r'[-•]\s*(\d+)\s+(?:.*?)(?:\((\d{3}|RB\d{3}|RB\d{1,3})\)|(quantum processor|neural network|memory card|sensors|controller|data analyzer|interface hub|security module))'
        bullet_matches = re.finditer(bullet_pattern, message_lower)
        
        for match in bullet_matches:
            quantity = int(match.group(1))
            code_part = match.group(2)
            keyword = match.group(3)
            
            if code_part:
                # Extract code
                code_part = code_part.upper().strip()
                if code_part.isdigit():
                    code = f"RB{code_part.zfill(3)}"
                elif code_part.startswith('RB'):
                    code = f"RB{code_part.replace('RB', '').zfill(3)}"
                else:
                    continue
            elif keyword:
                # Match by keyword
                code = None
                for prod_code, prod_info in product_mappings.items():
                    if any(kw in keyword for kw in prod_info['keywords']):
                        code = prod_code
                        break
                if not code:
                    continue
            else:
                continue
            
            if code and code in product_mappings:
                # Check if already added
                if not any(item['product_code'] == code for item in cart_items):
                    cart_items.append({
                        "product_code": code,
                        "product_name": product_mappings[code]['name'],
                        "quantity": quantity,
                        "confidence": 0.85,
                        "original_text": match.group(0)
                    })
        
        # If no products found with code patterns, try name-based matching
        if not cart_items:
            quantity_patterns = [
                (r'(\d+)\s+(?:quantum\s+blue\s+ai\s+)?processors?', 'RB001'),
                (r'(\d+)\s+(?:neural\s+network\s+module\s+pro|neural\s+networks?|neural\s+modules?)', 'RB002'),
                (r'(\d+)\s+(?:ai\s+memory\s+card\s+ultra|memory\s+cards?|ai\s+memory)', 'RB003'),
                (r'(\d+)\s+(?:quantum\s+sensors\s+advanced|sensors?)', 'RB004'),
                (r'(\d+)\s+(?:ai\s+controller\s+master|controllers?|ai\s+controllers?)', 'RB005'),
                (r'(\d+)\s+(?:quantum\s+blue\s+data\s+analyzer|data\s+analyzers?|analyzers?)', 'RB006'),
                (r'(\d+)\s+(?:neural\s+interface\s+hub|interface\s+hubs?|neural\s+hubs?)', 'RB007'),
                (r'(\d+)\s+(?:quantum\s+blue\s+security\s+module|security\s+modules?|security)', 'RB008')
            ]
            
            for pattern, code in quantity_patterns:
                matches = re.finditer(pattern, message_lower)
                for match in matches:
                    quantity = int(match.group(1))
                    if code in product_mappings:
                        cart_items.append({
                            "product_code": code,
                            "product_name": product_mappings[code]['name'],
                            "quantity": quantity,
                            "confidence": 0.8,
                            "original_text": match.group(0)
                        })
        
        return {
            "extracted_products": cart_items,
            "total_products": len(cart_items),
            "order_ready": len(cart_items) > 0,
            "unclear_requests": [],
            "suggestions": []
        }
    
    def _generate_summary_fallback(self, cart_items):
        """Fallback order summary generation"""
        if not cart_items:
            return {
                'summary': "Your cart is empty. Would you like to add some products?",
                'pricing_details': [],
                'total_amount': 0,
                'total_savings': 0,
                'item_count': 0
            }
        
        summary = "Order Summary:\n\n"
        summary += "| Product | Qty | Unit Price | Discount | Scheme | Total |\n"
        summary += "|---------|-----|------------|----------|--------|-------|\n"
        
        total_amount = 0
        total_savings = 0
        
        for item in cart_items:
            # Recalculate pricing for accurate totals
            pricing = self.pricing_service.calculate_product_pricing(item.product_id, item.product_quantity)
            
            if 'error' not in pricing:
                item_total = pricing['pricing']['total_amount']
                item_savings = pricing['pricing']['savings']
                total_amount += item_total
                total_savings += item_savings
                
                # Truncate long product names
                product_name = pricing['product_name']
                if len(product_name) > 20:
                    product_name = product_name[:17] + "..."
                
                # Format quantity with free items
                ordered_qty = pricing['quantity']
                free_q = pricing['scheme'].get('free_quantity', 0)
                quantity_display = f"{ordered_qty} + {free_q} free" if free_q > 0 else str(ordered_qty)
                
                # Discount display
                discount_amount = pricing['discount'].get('amount', 0)
                discount_name = pricing['discount'].get('name', 'None') if pricing['discount'].get('name') else 'None'
                discount_display = f"{discount_name} (${discount_amount:.2f})" if discount_amount > 0 else "None"
                
                # Scheme display
                scheme_name = pricing['scheme'].get('name', 'None') if pricing['scheme'].get('name') != "No Scheme" else "None"
                
                summary += f"| {product_name} ({pricing['product_code']}) | {quantity_display} | ${pricing['base_price']:.2f} | {discount_display} | {scheme_name} | ${item_total:.2f} |\n"
        
        summary += f"\nTotal: ${total_amount:.2f}\n"
        if total_savings > 0:
            summary += f"Savings: ${total_savings:.2f}\n"
        summary += f"\nWould you like to add more items, remove items, or confirm your order?"
        
        return {
            'summary': summary,
            'pricing_details': [],
            'total_amount': total_amount,
            'total_savings': 0,
            'item_count': len(cart_items)
        }
    
    def _generate_distributor_notification_fallback(self, order, order_items, placed_by_user):
        """Fallback distributor notification generation"""
        notification = f"""New Order Notification

Order ID: {order.order_id}
Date: {order.order_date.strftime('%Y-%m-%d %H:%M:%S')}
Status: {order.status}
Warehouse: {order.warehouse_location}

Placed By: {placed_by_user.name} ({placed_by_user.user_type})
Email: {placed_by_user.email}
Phone: {placed_by_user.phone}

Order Items:
"""
        
        for item in order_items:
            notification += f"- {item.product.product_name} ({item.product_code}) - Qty: {item.product_quantity_ordered} - ${item.total_price}\n"
        
        notification += f"\nTotal Amount: ${order.total_amount}\n\nPlease review and confirm this order."
        
        return {
            'notification': notification,
            'order_details': f"Order {order.order_id} - ${order.total_amount}"
        }
