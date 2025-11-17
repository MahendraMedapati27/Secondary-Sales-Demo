import time
import logging
import json
from flask import current_app
from groq import Groq # Import Groq Client
# REMOVED: from groq.lib.chat_completion_service import ChatCompletion # This line caused the error

# --- Dependency Check ---
try:
    from groq import Groq
    GROQ_AVAILABLE = True
except ImportError:
    GROQ_AVAILABLE = False
    logger = logging.getLogger(__name__)
    logger.error("Groq package not installed. Install with: pip install groq")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class GroqService:
    """Groq API service integration, replacing Azure OpenAI."""
    
    def __init__(self):
        """Initialize Groq client"""
        self.client = None
        self._init_client()
    
    def _init_client(self):
        """Initialize Groq client"""
        try:
            api_key = current_app.config.get('GROQ_API_KEY')
            
            if api_key:
                # Use the newer API format without proxies parameter
                self.client = Groq(api_key=api_key)
                logger.info('Groq client initialized')
            else:
                logger.warning('Groq API configuration missing - using fallback responses')
        except Exception as e:
            logger.error(f'Failed to initialize Groq client: {str(e)}')

    # ------------------------------------------------------------------------
    ## LLM ROUTER (NEW FEATURE)
    # ------------------------------------------------------------------------
    
    def _should_search_web(self, user_message, internal_search_results):
        """
        Uses Groq to decide if an external web search is necessary based on internal results.
        Returns True/False.
        """
        if not self.client:
            logger.warning("Groq client not available. Skipping LLM routing decision.")
            return False

        # Format internal results for the LLM prompt
        internal_context = "No relevant documents found in the internal knowledge base."
        if internal_search_results:
            snippets = [
                f"Title: {r.get('title', 'N/A')}. Content: {r.get('content', 'N/A')[:100]}..." 
                for r in internal_search_results[:3]
            ]
            internal_context = f"Found {len(internal_search_results)} documents. Snippets:\n" + "\n".join(snippets)

        router_prompt = f"""You are an AI router designed to decide whether a user query requires external web access.

Internal Search Results (from the company database):
---
{internal_context}
---

User Query: "{user_message}"

**INSTRUCTIONS:**
1.  If the query is generic (e.g., 'hello', 'how are you', 'tell me a joke') OR if the Internal Search Results clearly and sufficiently answer the query, output: NO_SEARCH
2.  If the query asks for current/real-time information (e.g., 'latest news', 'today', 'recent') OR if the query relates to the company's domain but the Internal Search Results are insufficient (fewer than 2 highly relevant documents, or the content is clearly dated/irrelevant), output: PERFORM_SEARCH

Output **ONLY** one of the following two words: **PERFORM_SEARCH** or **NO_SEARCH**."""
        
        try:
            groq_model = current_app.config.get('GROQ_MODEL', 'llama-3.3-70b-versatile')
            response = self.client.chat.completions.create(
                model=groq_model,
                messages=[{"role": "user", "content": router_prompt}],
                temperature=0.0,
                max_tokens=10,
            )
            
            decision = response.choices[0].message.content.strip().upper()
            
            if "PERFORM_SEARCH" in decision:
                logger.info("LLM Router Decision: PERFORM_SEARCH")
                return True
            
            logger.info(f"LLM Router Decision: {decision}")
            return False

        except Exception as e:
            logger.error(f"Groq Router failed: {str(e)}. Defaulting to NO_SEARCH.")
            return False

    # ------------------------------------------------------------------------
    ## RAG GENERATION LOGIC
    # ------------------------------------------------------------------------
    
    def generate_response(self, user_message, conversation_history=None, context_data=None):
        """Generate response using Groq with timeout and circuit breaker"""
        from app.timeout_utils import with_timeout, get_timeout
        from app.circuit_breaker import get_circuit_breaker
        from app.error_handling import ExternalServiceError
        
        start_time = time.time()
        
        if not self.client:
            return self._generate_fallback_response(user_message, context_data, start_time)
        
        # Get circuit breaker for Groq
        breaker = get_circuit_breaker('groq', failure_threshold=5, recovery_timeout=60)
        
        # Define the actual API call function
        @with_timeout(get_timeout('llm'), 'Groq API call')
        def _call_groq_api():
            system_message = self._build_system_message(context_data)
            messages = [{"role": "system", "content": system_message}]
            
            if conversation_history:
                for conv in conversation_history[-5:]: 
                    messages.append({"role": "user", "content": conv.user_message})
                    messages.append({"role": "assistant", "content": conv.bot_response})
            
            messages.append({"role": "user", "content": user_message})
            
            groq_model = current_app.config.get('GROQ_MODEL', 'llama-3.3-70b-versatile')

            response = self.client.chat.completions.create(
                model=groq_model,
                messages=messages,
                temperature=0.7,
                max_tokens=2000,
                top_p=0.95
            )
            
            return response.choices[0].message.content
        
        try:
            # Call with circuit breaker protection
            assistant_message = breaker.call(
                _call_groq_api,
                fallback=lambda: None  # Will use fallback response below
            )
            
            if assistant_message is None:
                # Circuit breaker used fallback
                return self._generate_fallback_response(user_message, context_data, start_time)
            
            response_time = time.time() - start_time
            
            if self._should_format_as_table(user_message):
                assistant_message = self._format_as_table(assistant_message)
            
            return {
                'response': assistant_message,
                'response_time': response_time,
                'data_sources': self._extract_data_sources(context_data)
            }
        
        except Exception as e:
            logger.error(f'Groq API error: {str(e)}', exc_info=True)
            return self._generate_fallback_response(user_message, context_data, start_time)
    
    def _build_system_message(self, context_data):
        """Build system message with context, including product count."""
        
        base_prompt = """You are a helpful AI assistant with access to company data and web information.

Your role is to:
1. Answer user questions accurately using ONLY the provided CONTEXT DATA. **If the user asks for a count (e.g., 'how many products'), you MUST use the count derived from the 'Product Data' context.**
2. Be concise but informative.
3. Format responses in tables using Markdown when dealing with structured data.
4. Cite sources when using specific data.
5. Be professional and friendly.
6. If you don't have specific data to answer a question, say so clearly, referencing the lack of data in the provided context.

IMPORTANT: Use ONLY the data provided below. Do not make up or assume any information not explicitly provided in the data sources.

"""
        
        if context_data:
            base_prompt += "\n\n--- CONTEXT DATA ---\n"
            
            company_info = context_data.get('company_info')
            if company_info and isinstance(company_info, dict):
                base_prompt += "\n1. Company Information:\n"
                base_prompt += f"  Name: {company_info.get('company_name', 'N/A')}\n"
                if company_info.get('content'):
                    base_prompt += f"  Content Snippet: {company_info['content'][:200]}...\n"

            products = context_data.get('products')
            if products and isinstance(products, list):
                product_count = len(products)
                base_prompt += f"\n2. Product Data ({product_count} items):\n"
                base_prompt += f"  **THE TOTAL NUMBER OF PRODUCTS IN THE DATABASE IS: {product_count}**\n"
                
                if product_count > 0:
                    base_prompt += "  Sample Products (Title/Source):\n"
                    for i, product in enumerate(products[:5]):
                         item_name = product.get('title') or product.get('name') or 'Product N/A'
                         base_prompt += f"  - {item_name} (Source: {product.get('source', 'Index')})\n"
            
            internal_search = context_data.get('internal_search')
            if internal_search and isinstance(internal_search, list):
                base_prompt += f"\n3. Internal Document Search Results ({len(internal_search)} documents):\n"
                for i, result in enumerate(internal_search[:3], 1):
                    base_prompt += f"  {i}. Title: {result.get('title', 'Untitled')}\n"
                    base_prompt += f"    Content: {result.get('content', '')[:200]}...\n"
                    base_prompt += f"    Source: {result.get('source', 'Unknown')}\n"
            
            web_search = context_data.get('web_search')
            if web_search and isinstance(web_search, list):
                base_prompt += "\n4. External Web Search Summary:\n"
                base_prompt += web_search[0].get('snippet', 'No web summary found.') + "\n"
            
            base_prompt += "---------------------------------\n"
        
        return base_prompt

    # --- Utility and Fallback Methods ---

    def _should_format_as_table(self, message):
        table_keywords = ['table', 'list', 'compare', 'comparison', 'show me', 'data', 'statistics', 'numbers', 'breakdown', 'summary']
        return any(keyword in message.lower() for keyword in table_keywords)
    
    def _format_as_table(self, response):
        lines = response.strip().split('\n')
        if len(lines) > 2 and ('|' in response or '\t' in response):
            return response
        return response
    
    def _extract_data_sources(self, context_data):
        sources = set()
        
        if context_data:
            if 'internal_search' in context_data:
                for result in context_data['internal_search']:
                    if result.get('source'):
                        sources.add(result['source'])
            if 'products' in context_data and context_data['products']:
                sources.add(f"Azure AI Index (Products - {len(context_data['products'])} items)")
            if 'company_info' in context_data and context_data['company_info']:
                 if context_data['company_info'].get('content'):
                     sources.add(context_data['company_info'].get('source', 'Azure AI Index (Company Info)'))
                 else:
                     sources.add('Azure AI Index (Company Info)')
            if 'web_search' in context_data:
                sources.add('External Web Search (Tavily/Groq)')
        return list(sources)
    
    def generate_completion(self, messages, temperature=0.7, max_tokens=2000):
        """Generate completion using Groq for LLM search (Synthesis)"""
        if not self.client:
            logger.warning("Groq client not available for generate_completion")
            return ""
        
        try:
            groq_model = current_app.config.get('GROQ_MODEL', 'llama-3.3-70b-versatile')
            response = self.client.chat.completions.create(
                model=groq_model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                top_p=0.95
            )
            return response.choices[0].message.content
        
        except Exception as e:
            logger.error(f'Groq API error in generate_completion: {str(e)}')
            return ""
    
    def _generate_fallback_response(self, user_message, context_data, start_time):
        """Generate fallback response when Groq is not available"""
        response_time = time.time() - start_time
        message_lower = user_message.lower()
        products = context_data.get('products') if context_data else None
        
        if any(word in message_lower for word in ['how many', 'count', 'number']) and products:
            response = f"I found **{len(products)}** product entries in the internal database. This is a basic count provided by the search index."
        
        elif any(word in message_lower for word in ['hello', 'hi', 'hey', 'greetings']):
            response = "Hello! I'm your AI assistant. I'm currently running in demo mode. For full AI capabilities, please configure the Groq API."
        
        else:
            response = f"I received your message: '{user_message}'. I am currently running in **demo mode** without full AI reasoning. To get intelligent, context-aware responses, please ensure the Groq API is fully configured."
        
        return {
            'response': response,
            'response_time': response_time,
            'data_sources': self._extract_data_sources(context_data)
        }