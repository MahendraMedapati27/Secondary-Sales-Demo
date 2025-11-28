import logging
import os
import re
from flask import current_app
from tavily import TavilyClient

# Single logger initialization - logging.basicConfig should only be called once in __init__.py
logger = logging.getLogger(__name__)

class WebSearchService:
    """Service for web search using Tavily"""
    
    def __init__(self):
        self.logger = logger
        self.client = None
        self._init_client()
    
    def _init_client(self):
        """Initialize Tavily client"""
        try:
            api_key = current_app.config.get('TAVILY_API_KEY')
            if api_key:
                self.client = TavilyClient(api_key=api_key)
                if hasattr(self, 'logger') and self.logger:
                    self.logger.info('Tavily client initialized')
            else:
                if hasattr(self, 'logger') and self.logger:
                    self.logger.warning('Tavily API key not configured - web search will use fallback')
        except Exception as e:
            if hasattr(self, 'logger') and self.logger:
                self.logger.error(f'Failed to initialize Tavily client: {str(e)}')
    
    def search_web(self, query, max_results=5):
        """
        Perform web search using Tavily
        Restricted to allowed domains only
        """
        if not self.client:
            if hasattr(self, 'logger') and self.logger:
                self.logger.warning("Tavily client not available")
            return []
        
        try:
            # Get allowed domains from config
            allowed_domains = current_app.config.get('ALLOWED_SEARCH_DOMAINS', [])
            
            if hasattr(self, 'logger') and self.logger:
                self.logger.info(f"Searching web for: {query}")
                self.logger.info(f"Allowed domains: {allowed_domains}")
            
            # Perform search with domain restrictions
            response = self.client.search(
                query=query,
                search_depth="advanced",
                max_results=max_results,
                include_answer=True,  # Include answer for better results
                include_raw_content=True,  # Include raw content for better extraction
                include_domains=allowed_domains if allowed_domains else None,
                include_images=True  # Include images to capture logos
            )
            
            # Format results
            results = self._format_search_results(response)
            
            if not results:
                if hasattr(self, 'logger') and self.logger:
                    self.logger.warning("No search results found within allowed domains")
                return []
            
            if hasattr(self, 'logger') and self.logger:
                self.logger.info(f"Found {len(results)} search results")
                # Log the actual content for debugging
                for i, result in enumerate(results):
                    self.logger.info(f"Result {i+1}: {result['title']} - {result['content'][:200]}...")
            return results
            
        except Exception as e:
            if hasattr(self, 'logger') and self.logger:
                self.logger.error(f"Web search error: {str(e)}")
            return []
    
    def _format_search_results(self, response):
        """Format Tavily search results"""
        formatted_results = []
        
        if 'results' in response:
            for result in response['results']:
                # Get all available content
                content = result.get('content', '')
                raw_content = result.get('raw_content', '')
                
                # Combine content and raw_content for more comprehensive information
                full_content = content
                if raw_content and raw_content != content:
                    full_content += "\n\n" + raw_content
                
                formatted_result = {
                    'title': result.get('title', ''),
                    'url': result.get('url', ''),
                    'content': full_content,
                    'score': result.get('score', 0),
                    'published_date': result.get('published_date', ''),
                    'source': self._extract_domain(result.get('url', '')),
                    'images': result.get('images', [])  # Include images for logo detection
                }
                formatted_results.append(formatted_result)
        
        return formatted_results
    
    def _extract_domain(self, url):
        """Extract domain from URL"""
        try:
            from urllib.parse import urlparse
            parsed = urlparse(url)
            return parsed.netloc
        except:
            return 'unknown'
    
    def search_with_synthesis(self, query, user_message):
        """
        Perform web search using MCP extraction for allowed domains only
        """
        try:
            user_message_lower = user_message.lower()
            
            # Check if this is a website-specific query
            website_url = self._extract_website_url(user_message_lower)
            
            if website_url:
                # Use MCP extraction for website-specific queries (with domain restriction)
                return self._use_mcp_extraction(website_url, user_message, query)
            else:
                # For general queries, try to identify if it's about a specific allowed website
                if any(keyword in user_message_lower for keyword in ['highvolt', 'high volt']):
                    return self._use_mcp_extraction("https://highvolt.tech", user_message, query)
                elif any(keyword in user_message_lower for keyword in ['investopedia']):
                    return self._use_mcp_extraction("https://investopedia.com", user_message, query)
                elif any(keyword in user_message_lower for keyword in ['financialservices', 'financial services']):
                    return self._use_mcp_extraction("https://financialservices.gov.in", user_message, query)
                else:
                    # For other queries, provide domain restriction message
                    return {
                        'synthesized_response': f"🔒 **Search Restriction:** I can only extract information from these approved websites:\n\n• **investopedia.com** - Financial education and information\n• **financialservices.gov.in** - Government financial services\n• **highvolt.tech** - Business services and solutions\n\nPlease ask about information from one of these websites, or specify which website you'd like me to search.",
                        'search_results': [],
                        'sources_used': []
                    }
            
        except Exception as e:
            if hasattr(self, 'logger') and self.logger:
                self.logger.error(f"Search with synthesis error: {str(e)}")
            return self._get_fallback_response(query, user_message)
    
    def _handle_highvolt_client_query(self, user_message, search_results):
        """
        Special handling for HighVolt client queries with enhanced extraction
        """
        try:
            # Look for HighVolt homepage content specifically
            highvolt_content = ""
            client_names_found = []
            
            for result in search_results:
                if 'highvolt.tech' in result.get('url', '') or 'highvolt' in result.get('title', '').lower():
                    highvolt_content += result.get('content', '')
                    if hasattr(self, 'logger') and self.logger:
                        self.logger.info(f"Found HighVolt content: {result.get('content', '')[:200]}...")
            
            # Check if we have sufficient content to extract client information
            if len(highvolt_content) < 500:  # If we don't have enough content
                if hasattr(self, 'logger') and self.logger:
                    self.logger.info(f"Insufficient HighVolt content from search ({len(highvolt_content)} chars), using enhanced fallback")
                return self._get_enhanced_highvolt_fallback(user_message)
            
            # Use enhanced synthesis for HighVolt content
            if highvolt_content:
                synthesized_response = self._synthesize_highvolt_clients(user_message, highvolt_content, search_results)
            else:
                # Fallback to regular synthesis
                synthesized_response = self._synthesize_results(user_message, search_results)
            
            return {
                'synthesized_response': synthesized_response,
                'search_results': search_results,
                'sources_used': [result['source'] for result in search_results]
            }
            
        except Exception as e:
            if hasattr(self, 'logger') and self.logger:
                self.logger.error(f"HighVolt client query handling error: {str(e)}")
            return self._get_enhanced_highvolt_fallback(user_message)
    
    def _synthesize_highvolt_clients(self, user_message, highvolt_content, search_results):
        """
        Enhanced synthesis specifically for HighVolt client information
        """
        try:
            from app.groq_service import GroqService
            groq_service = GroqService()
            
            if not groq_service.client:
                return self._get_fallback_synthesis(search_results)
            
            # Get all available content from search results
            all_content = highvolt_content
            for result in search_results:
                if 'highvolt.tech' in result.get('url', '') or 'highvolt' in result.get('title', '').lower():
                    all_content += "\n\n" + result.get('content', '')
            
            synthesis_prompt = f"""You are analyzing HighVolt's website content to find their clients and customers. Based on the following comprehensive content from their website, extract and list ALL client names, company names, or business partners mentioned.

User Query: "{user_message}"

HighVolt Website Content (Complete):
{all_content[:4000]}

Instructions:
1. Carefully analyze ALL the content provided to extract client information
2. Look for ANY company names, logos, or business partners mentioned anywhere in the content
3. Look for client testimonials, case studies, or project mentions
4. Look for any business relationships or partnerships mentioned
5. Even if companies are not explicitly called "clients", if they're mentioned in a business context, include them
6. Look for phrases like "trusted business partners", "clients", "customers", "projects", "awards"
7. Check for any company names that appear in the content, including in project names, award sections, or testimonials
8. Look for logos, brand names, or company identifiers
9. Pay special attention to sections like "Our Clients", "Awards", "Projects", "Case Studies", "Client Logos"
10. Look for any visual elements or logo sections that might contain client names

IMPORTANT: Extract ALL company names you find, even if they appear in different contexts like:
- Project names (e.g., "Company Project")
- Award sections
- Client testimonials
- Logo sections
- Case studies
- Business partnerships
- Client logos or brand names
- Any company names mentioned in the content

Look for any company names, brand names, or business entities mentioned in the content.

Be thorough and extract every company name you can find in the content. If you find specific company names, list them clearly with the context where they were mentioned. If the content mentions they have clients but doesn't list specific names, state that clearly.

Respond in a helpful, professional manner with a comprehensive list of all clients and business partners found."""

            response = groq_service.client.chat.completions.create(
                model=current_app.config.get('GROQ_MODEL', 'llama-3.3-70b-versatile'),
                messages=[{"role": "user", "content": synthesis_prompt}],
                temperature=0.3,
                max_tokens=2000  # Increased for more comprehensive responses
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            if hasattr(self, 'logger') and self.logger:
                self.logger.error(f"HighVolt synthesis error: {str(e)}")
            return self._get_fallback_synthesis(search_results)
    
    def _get_enhanced_highvolt_fallback(self, user_message):
        """
        Enhanced fallback specifically for HighVolt client information using dynamic extraction
        """
        try:
            # Use MCP-based dynamic extraction from HighVolt website
            extracted_data = self._extract_highvolt_clients_dynamically()
            return {
                'synthesized_response': extracted_data,
                'search_results': [],
                'sources_used': ['highvolt_dynamic_extraction']
            }
        except Exception as e:
            if hasattr(self, 'logger') and self.logger:
                self.logger.error(f"Dynamic extraction failed: {str(e)}")
            return {
                'synthesized_response': "I apologize, but I'm unable to access the complete client information from the HighVolt website at this time. The web search results don't contain sufficient details about their specific clients and business partners. For the most current and complete client list, I recommend visiting the HighVolt website directly at highvolt.tech or contacting them directly.",
                'search_results': [],
                'sources_used': []
            }
    
    def _get_fallback_response(self, query, user_message):
        """
        Provide fallback response when web search is not available
        """
        query_lower = query.lower()
        user_message_lower = user_message.lower()
        
        # HighVolt client information fallback
        if any(keyword in user_message_lower for keyword in ['highvolt', 'high volt']):
            return self._get_enhanced_highvolt_fallback(user_message)
        
        # Company information fallback
        if any(keyword in query_lower for keyword in ['company', 'about', 'contact', 'phone', 'address', 'email']):
            return {
                'synthesized_response': """Based on available information:

**Quantum Blue** is an advanced AI-powered chatbot platform specializing in warehouse management and order processing.

**Key Features:**
• Smart order placement and tracking
• Real-time inventory management
• AI-powered customer support
• Multi-warehouse operations

**Contact Information:**
• Email: support@quantumblue.com
• Phone: +1-800-QUANTUM
• Address: 123 AI Street, Tech City, TC 12345

**Technology Stack:**
• AI/ML powered order processing
• Real-time inventory tracking
• Advanced chatbot capabilities
• Multi-platform integration

For the most up-to-date information, please visit our official website or contact our support team directly.""",
                'search_results': [],
                'sources_used': ['internal_knowledge']
            }
        
        # General fallback
        return {
            'synthesized_response': f"I don't have access to real-time web search at the moment, but I can help you with information about Quantum Blue's products, services, and order management. Could you please rephrase your question or ask about our specific products and services?",
            'search_results': [],
            'sources_used': []
        }
    
    def _synthesize_results(self, user_message, search_results):
        """Synthesize search results using LLM"""
        try:
            from app.groq_service import GroqService
            groq_service = GroqService()
            
            if not groq_service.client:
                return self._get_fallback_synthesis(search_results)
            
            # Format search results for LLM with more content
            search_context = ""
            for i, result in enumerate(search_results, 1):
                search_context += f"[Source {i}] {result['title']}\n"
                search_context += f"URL: {result['url']}\n"
                # Include more content for better analysis
                content = result.get('content', '')
                if len(content) > 2000:  # Increased from 1000 to 2000
                    content = content[:2000] + "..."
                search_context += f"Content: {content}\n\n"
            
            synthesis_prompt = f"""You are Quantum Blue's AI assistant. Based ONLY on the following search results, provide a comprehensive answer to the user's query.

User Query: "{user_message}"

Search Results:
{search_context}

Instructions:
1. Carefully analyze ALL the search results for the requested information
2. Look for client names, company logos, customer lists, or any mention of clients/customers
3. If you find client information, list them clearly with context
4. If the search results don't contain sufficient information, state this clearly
5. Do not make up information not present in the search results
6. Be specific about what information is available vs. what is not

For client/customer queries specifically:
- Look for logos, company names, client testimonials, case studies
- Check for "Our Clients", "Customers", "Partners" sections
- Look for any company names mentioned in the content
- Pay special attention to the HighVolt homepage content which may contain client logos or names
- Look for phrases like "trusted business partners", "clients", "customers"
- Check for any company names that appear in the content
- Look for visual elements, logos, or brand names
- Check for project names, award sections, testimonials
- Look for any business partnerships or relationships mentioned

IMPORTANT: Extract ALL company names you find in the search results, even if they appear in different contexts like:
- Project names (e.g., "Company Project")
- Award sections
- Client testimonials
- Logo sections
- Case studies
- Business partnerships
- Any company names mentioned anywhere in the content

Look for any company names, brand names, or business entities mentioned in the content.

Be thorough and extract every company name you can find. If you find specific company names, list them clearly with the context where they were mentioned.

Respond in a helpful, professional manner with a comprehensive list of all clients and business partners found."""

            response = groq_service.client.chat.completions.create(
                model=current_app.config.get('GROQ_MODEL', 'llama-3.3-70b-versatile'),
                messages=[{"role": "user", "content": synthesis_prompt}],
                temperature=0.3,
                max_tokens=1500  # Increased for more detailed responses
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            if hasattr(self, 'logger') and self.logger:
                self.logger.error(f"Synthesis error: {str(e)}")
            return self._get_fallback_synthesis(search_results)
    
    def _get_fallback_synthesis(self, search_results):
        """Fallback synthesis when LLM is not available"""
        if not search_results:
            return "No relevant information found in the search results."
        
        response = "Based on the search results:\n\n"
        for i, result in enumerate(search_results[:3], 1):
            response += f"{i}. {result['title']}\n"
            response += f"   {result['content'][:200]}...\n"
            response += f"   Source: {result['source']}\n\n"
        
        return response
    
    def _extract_highvolt_clients_dynamically(self):
        """
        Dynamically extract client information from HighVolt website using MCP extraction service
        """
        try:
            from app.mcp_extraction_service import MCPExtractionService
            
            # Initialize MCP extraction service
            mcp_service = MCPExtractionService()
            
            # Extract client data
            clients_data = mcp_service.extract_highvolt_clients()
            
            # Format the response
            response_text = mcp_service.format_client_response(clients_data)
            
            return response_text
            
        except Exception as e:
            if hasattr(self, 'logger') and self.logger:
                self.logger.error(f"MCP extraction error: {str(e)}")
            return "I was unable to dynamically extract client information from the HighVolt website. Please visit highvolt.tech directly for the most current client information."
    
    def _extract_website_url(self, user_message_lower):
        """Extract website URL from user message"""
        # Look for common website patterns
        url_patterns = [
            r'(https?://[^\s]+)',
            r'(www\.[^\s]+)',
            r'([a-zA-Z0-9-]+\.(?:com|org|net|edu|gov|tech|io|co|uk|au|sg))'
        ]
        
        for pattern in url_patterns:
            matches = re.findall(pattern, user_message_lower)
            if matches:
                url = matches[0]
                if not url.startswith('http'):
                    url = 'https://' + url
                return url
        
        return None
    
    def _use_mcp_extraction(self, website_url, user_message, query):
        """Use MCP extraction for website-specific queries (only allowed domains)"""
        try:
            from app.mcp_extraction_service import MCPExtractionService
            
            # Check if the URL is from an allowed domain
            mcp_service = MCPExtractionService()
            if not mcp_service._is_allowed_domain(website_url):
                return {
                    'synthesized_response': f"❌ **Domain Restriction:** I can only extract information from these allowed websites:\n\n• investopedia.com\n• financialservices.gov.in\n• highvolt.tech\n\nPlease ask about information from one of these websites.",
                    'search_results': [],
                    'sources_used': []
                }
            
            # Determine query type based on user message
            query_type = self._determine_query_type(user_message)
            
            # Extract keywords from user message
            keywords = self._extract_keywords(user_message)
            
            # Extract content from website
            extracted_data = mcp_service.extract_website_content(website_url, query_type, keywords)
            
            # Format response
            response_text = mcp_service.format_generic_response(extracted_data, query_type)
            
            return {
                'synthesized_response': response_text,
                'search_results': [],
                'sources_used': [website_url]
            }
            
        except Exception as e:
            if hasattr(self, 'logger') and self.logger:
                self.logger.error(f"MCP extraction error: {str(e)}")
            return self._get_fallback_response(query, user_message)
    
    def _determine_query_type(self, user_message):
        """Determine the type of query based on user message"""
        message_lower = user_message.lower()
        
        if any(keyword in message_lower for keyword in ['client', 'customer', 'customers', 'clients', 'partner', 'partners']):
            return "clients"
        elif any(keyword in message_lower for keyword in ['service', 'services', 'offering', 'offerings']):
            return "services"
        elif any(keyword in message_lower for keyword in ['contact', 'email', 'phone', 'address', 'reach']):
            return "contact"
        elif any(keyword in message_lower for keyword in ['about', 'mission', 'vision', 'company', 'story']):
            return "about"
        elif any(keyword in message_lower for keyword in ['price', 'pricing', 'cost', 'fee', 'fees']):
            return "pricing"
        elif any(keyword in message_lower for keyword in ['team', 'staff', 'employee', 'people', 'founder']):
            return "team"
        else:
            return "general"
    
    def _extract_keywords(self, user_message):
        """Extract important keywords from user message"""
        # Remove common words and extract meaningful keywords
        common_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by', 'is', 'are', 'was', 'were', 'be', 'been', 'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could', 'should', 'may', 'might', 'can', 'list', 'show', 'tell', 'me', 'about', 'all', 'what', 'how', 'when', 'where', 'why', 'who'}
        
        words = re.findall(r'\b\w+\b', user_message.lower())
        keywords = [word for word in words if word not in common_words and len(word) > 2]
        
        return keywords[:5]  # Limit to 5 keywords
    
    def is_available(self):
        """Check if web search service is available"""
        return self.client is not None
