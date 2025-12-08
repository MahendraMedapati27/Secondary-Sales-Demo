import logging
import requests
from bs4 import BeautifulSoup
import re
import json
from typing import List, Dict, Any
from flask import current_app

# Single logger initialization - logging.basicConfig should only be called once in __init__.py
logger = logging.getLogger(__name__)

class MCPExtractionService:
    """Service for MCP-based dynamic content extraction from any website"""
    
    def __init__(self):
        self.logger = logger
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        })
    
    def extract_website_content(self, url: str, query_type: str = "general", specific_keywords: List[str] = None) -> Dict[str, Any]:
        """
        Generic method to extract content from allowed websites only
        """
        try:
            # Check if the URL is from an allowed domain
            if not self._is_allowed_domain(url):
                return {'error': f'Domain not allowed. Only these domains are permitted: investopedia.com, financialservices.gov.in, highvolt.tech (R&B)', 'url': url}
            
            # Fetch the webpage
            page_data = self._fetch_page(url)
            
            # Extract content based on query type
            extracted_data = {
                'url': url,
                'query_type': query_type,
                'content': {},
                'metadata': {}
            }
            
            # Get page metadata
            extracted_data['metadata'] = self._extract_metadata(page_data)
            
            # Extract content based on query type
            if query_type == "clients" or "client" in query_type.lower():
                extracted_data['content'] = self._extract_client_information(page_data, specific_keywords)
            elif query_type == "services" or "service" in query_type.lower():
                extracted_data['content'] = self._extract_services_information(page_data)
            elif query_type == "contact" or "contact" in query_type.lower():
                extracted_data['content'] = self._extract_contact_information(page_data)
            elif query_type == "about" or "about" in query_type.lower():
                extracted_data['content'] = self._extract_about_information(page_data)
            elif query_type == "pricing" or "price" in query_type.lower():
                extracted_data['content'] = self._extract_pricing_information(page_data)
            elif query_type == "team" or "staff" in query_type.lower():
                extracted_data['content'] = self._extract_team_information(page_data)
            else:
                # General extraction for any query
                extracted_data['content'] = self._extract_general_information(page_data, specific_keywords)
            
            return extracted_data
            
        except Exception as e:
            self.logger.error(f"Error extracting content from {url}: {str(e)}")
            return {'error': str(e), 'url': url}
    
    def _is_allowed_domain(self, url: str) -> bool:
        """Check if the URL is from an allowed domain"""
        from urllib.parse import urlparse
        
        try:
            parsed_url = urlparse(url)
            domain = parsed_url.netloc.lower()
            
            # Remove 'www.' prefix if present
            if domain.startswith('www.'):
                domain = domain[4:]
            
            # Check against allowed domains
            allowed_domains = ['investopedia.com', 'financialservices.gov.in', 'highvolt.tech']
            return domain in allowed_domains
            
        except Exception:
            return False
    
    def extract_highvolt_clients(self) -> Dict[str, Any]:
        """
        Extract client information from R&B website using MCP approach
        """
        try:
            # Fetch the main page
            main_page_data = self._fetch_page("https://highvolt.tech")
            
            # Extract client information using multiple strategies
            clients_data = {
                'companies': [],
                'projects': [],
                'testimonials': [],
                'awards': [],
                'statistics': {},
                'services': []
            }
            
            # Strategy 1: Extract from main page content
            clients_data.update(self._extract_from_main_page(main_page_data))
            
            # Strategy 2: Look for specific client sections
            clients_data.update(self._extract_client_sections(main_page_data))
            
            # Strategy 3: Extract from links and references
            clients_data.update(self._extract_from_links(main_page_data))
            
            # Strategy 4: Look for project and award mentions
            clients_data.update(self._extract_projects_and_awards(main_page_data))
            
            return clients_data
            
        except Exception as e:
            self.logger.error(f"Error extracting R&B clients: {str(e)}")
            return {'error': str(e)}
    
    def _fetch_page(self, url: str) -> BeautifulSoup:
        """Fetch and parse a webpage"""
        try:
            response = self.session.get(url, timeout=15)
            response.raise_for_status()
            return BeautifulSoup(response.content, 'html.parser')
        except Exception as e:
            self.logger.error(f"Error fetching {url}: {str(e)}")
            raise
    
    def _extract_from_main_page(self, soup: BeautifulSoup) -> Dict[str, Any]:
        """Extract client information from main page content"""
        data = {
            'companies': [],
            'projects': [],
            'testimonials': [],
            'statistics': {}
        }
        
        # Get all text content
        page_text = soup.get_text()
        
        # Look for company names using dynamic patterns (no hardcoded names)
        company_patterns = [
            r'(?:Company|Corp|Inc|LLC|Ltd|Pvt|Limited)\s*:?\s*([A-Z][a-zA-Z\s&]+)',
            r'([A-Z][a-zA-Z\s&]+)\s*(?:Company|Corp|Inc|LLC|Ltd|Pvt|Limited)',
            r'(?:Client|Partner|Customer)\s*:?\s*([A-Z][a-zA-Z\s&]+)',
            r'([A-Z][a-zA-Z\s&]+)\s*(?:Client|Partner|Customer)',
            r'(?:Working with|Serving|Partnered with)\s+([A-Z][a-zA-Z\s&]+)',
            r'([A-Z][a-zA-Z\s&]+)\s*(?:Project|Case Study|Success Story)'
        ]
        
        for pattern in company_patterns:
            matches = re.findall(pattern, page_text, re.IGNORECASE)
            for match in matches:
                if isinstance(match, tuple):
                    match = match[0] if match[0] else match[1]
                clean_name = match.strip()
                if clean_name and len(clean_name) > 2 and len(clean_name) < 50:
                    # Filter out common words that aren't company names
                    if not any(word in clean_name.lower() for word in ['our', 'the', 'and', 'with', 'for', 'from', 'to', 'in', 'on', 'at', 'by']):
                        data['companies'].append(clean_name)
        
        # Look for project mentions using dynamic patterns
        project_patterns = [
            r'([A-Z][a-zA-Z\s&]+)\s+Project',
            r'Project\s+([A-Z][a-zA-Z\s&]+)',
            r'([A-Z][a-zA-Z\s&]+)\s+Case\s+Study',
            r'([A-Z][a-zA-Z\s&]+)\s+Success\s+Story',
            r'([A-Z][a-zA-Z\s&]+)\s+Implementation',
            r'([A-Z][a-zA-Z\s&]+)\s+Solution'
        ]
        
        for pattern in project_patterns:
            matches = re.findall(pattern, page_text, re.IGNORECASE)
            for match in matches:
                if isinstance(match, tuple):
                    match = match[0] if match[0] else match[1]
                clean_name = match.strip()
                if clean_name and len(clean_name) > 2 and len(clean_name) < 50:
                    data['projects'].append(clean_name)
        
        # Look for testimonial names using dynamic patterns
        testimonial_patterns = [
            r'([A-Z][a-z]+\s+[A-Z][a-z]+)\s*(?:Managing Director|CEO|CTO|CFO|Founder|Partner|Manager)',
            r'(?:Managing Director|CEO|CTO|CFO|Founder|Partner|Manager)\s*([A-Z][a-z]+\s+[A-Z][a-z]+)',
            r'([A-Z][a-z]+\s+[A-Z][a-z]+)\s*(?:says|said|quoted|testimonial)',
            r'(?:says|said|quoted|testimonial)\s*([A-Z][a-z]+\s+[A-Z][a-z]+)'
        ]
        
        for pattern in testimonial_patterns:
            matches = re.findall(pattern, page_text, re.IGNORECASE)
            for match in matches:
                if isinstance(match, tuple):
                    match = match[0] if match[0] else match[1]
                clean_name = match.strip()
                if clean_name and len(clean_name) > 2 and len(clean_name) < 50:
                    data['testimonials'].append(clean_name)
        
        # Look for statistics
        stats_patterns = [
            r'(\d+%)\s+client\s+retention',
            r'(\d+)\+\s+business\s+cases',
            r'(\d+)\+\s+clients?'
        ]
        
        for pattern in stats_patterns:
            matches = re.findall(pattern, page_text, re.IGNORECASE)
            if matches:
                data['statistics'][pattern] = matches
        
        return data
    
    def _extract_client_sections(self, soup: BeautifulSoup) -> Dict[str, Any]:
        """Extract information from client-specific sections"""
        data = {
            'companies': [],
            'projects': [],
            'testimonials': []
        }
        
        # Look for sections with client-related classes or IDs
        client_selectors = [
            '[class*="client"]',
            '[class*="partner"]',
            '[class*="customer"]',
            '[id*="client"]',
            '[id*="partner"]',
            '[id*="customer"]'
        ]
        
        for selector in client_selectors:
            sections = soup.select(selector)
            for section in sections:
                text = section.get_text()
                
                # Extract company names from these sections using dynamic patterns
                company_patterns = [
                    r'(?:Company|Corp|Inc|LLC|Ltd|Pvt|Limited)\s*:?\s*([A-Z][a-zA-Z\s&]+)',
                    r'([A-Z][a-zA-Z\s&]+)\s*(?:Company|Corp|Inc|LLC|Ltd|Pvt|Limited)',
                    r'(?:Client|Partner|Customer)\s*:?\s*([A-Z][a-zA-Z\s&]+)',
                    r'([A-Z][a-zA-Z\s&]+)\s*(?:Client|Partner|Customer)'
                ]
                
                for pattern in company_patterns:
                    matches = re.findall(pattern, text, re.IGNORECASE)
                    for match in matches:
                        if isinstance(match, tuple):
                            match = match[0] if match[0] else match[1]
                        clean_name = match.strip()
                        if clean_name and len(clean_name) > 2 and len(clean_name) < 50:
                            if not any(word in clean_name.lower() for word in ['our', 'the', 'and', 'with', 'for', 'from', 'to', 'in', 'on', 'at', 'by']):
                                data['companies'].append(clean_name)
        
        return data
    
    def _extract_from_links(self, soup: BeautifulSoup) -> Dict[str, Any]:
        """Extract client information from links and references"""
        data = {
            'companies': [],
            'projects': []
        }
        
        # Look for external links that might be client websites (dynamic extraction)
        links = soup.find_all('a', href=True)
        
        for link in links:
            href = link.get('href', '')
            text = link.get_text(strip=True)
            
            # Extract domain from href if it's an external link
            if href.startswith('http') and not any(domain in href for domain in ['highvolt.tech', 'investopedia.com', 'financialservices.gov.in']):
                try:
                    from urllib.parse import urlparse
                    domain = urlparse(href).netloc
                    if domain and text:
                        # Use the link text as company name if available
                        data['companies'].append(text)
                    elif domain:
                        # Use domain name as fallback
                        company_name = domain.replace('www.', '').split('.')[0]
                        if company_name and len(company_name) > 2:
                            data['companies'].append(company_name.title())
                except:
                    pass
        
        return data
    
    def _extract_projects_and_awards(self, soup: BeautifulSoup) -> Dict[str, Any]:
        """Extract project and award information"""
        data = {
            'projects': [],
            'awards': []
        }
        
        # Look for award sections
        award_sections = soup.find_all(['div', 'section'], class_=re.compile(r'award|achievement|project', re.I))
        
        for section in award_sections:
            text = section.get_text()
            
            # Look for project names using dynamic patterns
            project_patterns = [
                r'([A-Z][a-zA-Z\s&]+)\s+Project',
                r'Project\s+([A-Z][a-zA-Z\s&]+)',
                r'([A-Z][a-zA-Z\s&]+)\s+Case\s+Study',
                r'([A-Z][a-zA-Z\s&]+)\s+Success\s+Story',
                r'([A-Z][a-zA-Z\s&]+)\s+Implementation',
                r'([A-Z][a-zA-Z\s&]+)\s+Solution'
            ]
            
            for pattern in project_patterns:
                matches = re.findall(pattern, text, re.IGNORECASE)
                for match in matches:
                    if isinstance(match, tuple):
                        match = match[0] if match[0] else match[1]
                    clean_name = match.strip()
                    if clean_name and len(clean_name) > 2 and len(clean_name) < 50:
                        data['projects'].append(clean_name)
            
            # Look for award mentions
            award_patterns = [
                r'(x\d+)\s+(award|project)',
                r'(\d+)\s+(award|project)',
                r'(best|top|leading)\s+[^.!?]*'
            ]
            
            for pattern in award_patterns:
                matches = re.findall(pattern, text, re.IGNORECASE)
                data['awards'].extend(matches)
        
        return data
    
    def _extract_metadata(self, soup: BeautifulSoup) -> Dict[str, Any]:
        """Extract basic metadata from the webpage"""
        metadata = {}
        
        # Title
        title_tag = soup.find('title')
        if title_tag:
            metadata['title'] = title_tag.get_text().strip()
        
        # Description
        desc_tag = soup.find('meta', attrs={'name': 'description'})
        if desc_tag:
            metadata['description'] = desc_tag.get('content', '').strip()
        
        # Keywords
        keywords_tag = soup.find('meta', attrs={'name': 'keywords'})
        if keywords_tag:
            metadata['keywords'] = keywords_tag.get('content', '').strip()
        
        # Headings
        headings = []
        for i in range(1, 7):
            heading_tags = soup.find_all(f'h{i}')
            for tag in heading_tags:
                headings.append({'level': i, 'text': tag.get_text().strip()})
        metadata['headings'] = headings
        
        return metadata
    
    def _extract_client_information(self, soup: BeautifulSoup, keywords: List[str] = None) -> Dict[str, Any]:
        """Extract client/customer information from webpage"""
        return self._extract_from_main_page(soup)
    
    def _extract_services_information(self, soup: BeautifulSoup) -> Dict[str, Any]:
        """Extract services information from webpage"""
        data = {'services': [], 'features': [], 'offerings': []}
        
        page_text = soup.get_text()
        
        # Look for service-related sections
        service_sections = soup.find_all(['div', 'section'], class_=re.compile(r'service|feature|offering|product', re.I))
        
        for section in service_sections:
            text = section.get_text()
            # Extract service names (look for common patterns)
            service_patterns = [
                r'(Virtual\s+\w+\s+Services?)',
                r'(CFO\s+Services?)',
                r'(Finance\s+Manager\s+Services?)',
                r'(Accountant\s+Services?)',
                r'(Business\s+Consultation)',
                r'(Financial\s+Analysis)',
                r'(Strategic\s+Planning)'
            ]
            
            for pattern in service_patterns:
                matches = re.findall(pattern, text, re.IGNORECASE)
                data['services'].extend(matches)
        
        return data
    
    def _extract_contact_information(self, soup: BeautifulSoup) -> Dict[str, Any]:
        """Extract contact information from webpage"""
        data = {'email': [], 'phone': [], 'address': [], 'social': []}
        
        page_text = soup.get_text()
        
        # Extract email addresses
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        emails = re.findall(email_pattern, page_text)
        data['email'] = list(set(emails))
        
        # Extract phone numbers
        phone_patterns = [
            r'\+?\d{1,3}[-.\s]?\d{1,4}[-.\s]?\d{1,4}[-.\s]?\d{1,9}',
            r'\(\d{3}\)\s?\d{3}-\d{4}',
            r'\d{3}-\d{3}-\d{4}'
        ]
        
        for pattern in phone_patterns:
            phones = re.findall(pattern, page_text)
            data['phone'].extend(phones)
        
        # Extract addresses
        address_patterns = [
            r'\d+\s+[A-Za-z\s]+(?:Street|St|Avenue|Ave|Road|Rd|Drive|Dr|Lane|Ln|Boulevard|Blvd)',
            r'\d+\s+[A-Za-z\s]+(?:Singapore|SG|Malaysia|MY|Australia|AU)'
        ]
        
        for pattern in address_patterns:
            addresses = re.findall(pattern, page_text)
            data['address'].extend(addresses)
        
        return data
    
    def _extract_about_information(self, soup: BeautifulSoup) -> Dict[str, Any]:
        """Extract about/company information from webpage"""
        data = {'mission': [], 'vision': [], 'values': [], 'history': []}
        
        page_text = soup.get_text()
        
        # Look for mission statements
        mission_patterns = [
            r'(?:mission|purpose)[:\s]*([^.!?]*)',
            r'(?:our\s+mission)[:\s]*([^.!?]*)'
        ]
        
        for pattern in mission_patterns:
            matches = re.findall(pattern, page_text, re.IGNORECASE)
            data['mission'].extend(matches)
        
        # Look for vision statements
        vision_patterns = [
            r'(?:vision)[:\s]*([^.!?]*)',
            r'(?:our\s+vision)[:\s]*([^.!?]*)'
        ]
        
        for pattern in vision_patterns:
            matches = re.findall(pattern, page_text, re.IGNORECASE)
            data['vision'].extend(matches)
        
        return data
    
    def _extract_pricing_information(self, soup: BeautifulSoup) -> Dict[str, Any]:
        """Extract pricing information from webpage"""
        data = {'prices': [], 'plans': [], 'packages': []}
        
        page_text = soup.get_text()
        
        # Look for price patterns
        price_patterns = [
            r'\$\d+(?:,\d{3})*(?:\.\d{2})?',
            r'(?:A\$|USD|SGD)\s*\d+(?:,\d{3})*(?:\.\d{2})?',
            r'(?:price|cost)[:\s]*\$?\d+(?:,\d{3})*(?:\.\d{2})?'
        ]
        
        for pattern in price_patterns:
            prices = re.findall(pattern, page_text, re.IGNORECASE)
            data['prices'].extend(prices)
        
        return data
    
    def _extract_team_information(self, soup: BeautifulSoup) -> Dict[str, Any]:
        """Extract team/staff information from webpage"""
        data = {'team_members': [], 'roles': [], 'departments': []}
        
        page_text = soup.get_text()
        
        # Look for team member names using dynamic patterns (no hardcoded names)
        name_patterns = [
            r'([A-Z][a-z]+\s+[A-Z][a-z]+)\s*(?:CPA|Chartered Accountant|Partner|Manager|Director|Founder|CEO|CTO|CFO)',
            r'(?:CPA|Chartered Accountant|Partner|Manager|Director|Founder|CEO|CTO|CFO)\s*([A-Z][a-z]+\s+[A-Z][a-z]+)',
            r'([A-Z][a-z]+\s+[A-Z][a-z]+)\s*(?:Team|Staff|Employee|Member)',
            r'(?:Team|Staff|Employee|Member)\s*([A-Z][a-z]+\s+[A-Z][a-z]+)',
            r'([A-Z][a-z]+\s+[A-Z][a-z]+)\s*(?:Accountant|Consultant|Advisor|Specialist)',
            r'(?:Accountant|Consultant|Advisor|Specialist)\s*([A-Z][a-z]+\s+[A-Z][a-z]+)'
        ]
        
        for pattern in name_patterns:
            matches = re.findall(pattern, page_text, re.IGNORECASE)
            for match in matches:
                if isinstance(match, tuple):
                    match = match[0] if match[0] else match[1]
                clean_name = match.strip()
                if clean_name and len(clean_name) > 2 and len(clean_name) < 50:
                    # Filter out common words that aren't names
                    if not any(word in clean_name.lower() for word in ['our', 'the', 'and', 'with', 'for', 'from', 'to', 'in', 'on', 'at', 'by', 'team', 'staff', 'member']):
                        data['team_members'].append(clean_name)
        
        # Look for roles/titles
        role_patterns = [
            r'(CPA|Chartered Accountant|Partner|Manager|Director|Founder|CEO|CTO|CFO)',
            r'(Account Admin|Finance Consultant|Accountant)'
        ]
        
        for pattern in role_patterns:
            roles = re.findall(pattern, page_text, re.IGNORECASE)
            data['roles'].extend(roles)
        
        return data
    
    def _extract_general_information(self, soup: BeautifulSoup, keywords: List[str] = None) -> Dict[str, Any]:
        """Extract general information based on keywords"""
        data = {'key_points': [], 'important_info': [], 'highlights': []}
        
        page_text = soup.get_text()
        
        if keywords:
            # Look for sections containing specific keywords
            for keyword in keywords:
                keyword_pattern = rf'.*{re.escape(keyword)}.*'
                matches = re.findall(keyword_pattern, page_text, re.IGNORECASE | re.DOTALL)
                data['key_points'].extend(matches[:3])  # Limit to 3 matches per keyword
        
        # Extract important information (headings, bullet points, etc.)
        headings = soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6'])
        for heading in headings:
            data['highlights'].append(heading.get_text().strip())
        
        return data
    
    def format_client_response(self, clients_data: Dict[str, Any]) -> str:
        """Format the extracted client data into a readable response"""
        if 'error' in clients_data:
            return f"I encountered an error while extracting client information: {clients_data['error']}"
        
        response = "Based on my dynamic analysis of R&B's website, here is the client information I found:\n\n"
        
        # Companies - clean up and remove duplicates
        companies = clients_data.get('companies', [])
        # Remove duplicates and clean up company names
        cleaned_companies = []
        seen = set()
        
        for company in companies:
            # Clean up the company name
            clean_name = company.strip()
            if clean_name and clean_name.lower() not in seen:
                # Prefer full company names over domain names
                if not any(ext in clean_name.lower() for ext in ['.com', '.au', '.org']):
                    cleaned_companies.append(clean_name)
                    seen.add(clean_name.lower())
        
        if cleaned_companies:
            response += "## **Client Companies:**\n"
            for i, company in enumerate(cleaned_companies, 1):
                response += f"{i}. **{company}**\n"
            response += "\n"
        
        # Projects
        projects = list(set(clients_data.get('projects', [])))
        if projects:
            response += "## **Projects Mentioned:**\n"
            for project in projects:
                response += f"- **{project}**\n"
            response += "\n"
        
        # Testimonials
        testimonials = list(set(clients_data.get('testimonials', [])))
        if testimonials:
            response += "## **Client Testimonials:**\n"
            for testimonial in testimonials:
                response += f"- **{testimonial}**\n"
            response += "\n"
        
        # Awards
        awards = list(set(clients_data.get('awards', [])))
        if awards:
            response += "## **Awards & Recognition:**\n"
            for award in awards:
                response += f"- **{award}**\n"
            response += "\n"
        
        # Statistics
        stats = clients_data.get('statistics', {})
        if stats:
            response += "## **Key Statistics:**\n"
            for stat_type, values in stats.items():
                response += f"- {stat_type}: {', '.join(values)}\n"
            response += "\n"
        
        response += "For the most current and complete client information, please visit highvolt.tech directly."
        
        return response
    
    def format_generic_response(self, extracted_data: Dict[str, Any], query_type: str) -> str:
        """Format extracted data into a clean, readable response based on query type"""
        if 'error' in extracted_data:
            return f"❌ **Error:** {extracted_data['error']}"
        
        url = extracted_data.get('url', 'the website')
        metadata = extracted_data.get('metadata', {})
        content = extracted_data.get('content', {})
        
        # Clean response formatting
        response = f"📊 **Dynamic Analysis Results**\n\n"
        
        # Add website info
        if metadata.get('title'):
            response += f"🌐 **Website:** {metadata['title']}\n\n"
        
        # Format content based on query type
        if query_type == "clients" or "client" in query_type.lower():
            response += self._format_client_content(content)
        elif query_type == "services" or "service" in query_type.lower():
            response += self._format_services_content(content)
        elif query_type == "contact" or "contact" in query_type.lower():
            response += self._format_contact_content(content)
        elif query_type == "about" or "about" in query_type.lower():
            response += self._format_about_content(content)
        elif query_type == "pricing" or "price" in query_type.lower():
            response += self._format_pricing_content(content)
        elif query_type == "team" or "staff" in query_type.lower():
            response += self._format_team_content(content)
        else:
            response += self._format_general_content(content)
        
        # Add footer
        response += f"\n---\n"
        response += f"💡 *For the most current information, visit the website directly.*"
        
        return response
    
    def _format_client_content(self, content: Dict[str, Any]) -> str:
        """Format client-related content with clean formatting"""
        response = ""
        
        companies = content.get('companies', [])
        if companies:
            cleaned_companies = []
            seen = set()
            for company in companies:
                clean_name = company.strip()
                if clean_name and clean_name.lower() not in seen:
                    if not any(ext in clean_name.lower() for ext in ['.com', '.au', '.org']):
                        cleaned_companies.append(clean_name)
                        seen.add(clean_name.lower())
            
            if cleaned_companies:
                response += "👥 **Client Companies:**\n"
                for i, company in enumerate(cleaned_companies, 1):
                    response += f"   {i}. {company}\n"
                response += "\n"
        
        projects = list(set(content.get('projects', [])))
        if projects:
            response += "🎯 **Projects Mentioned:**\n"
            for project in projects:
                response += f"   • {project}\n"
            response += "\n"
        
        testimonials = list(set(content.get('testimonials', [])))
        if testimonials:
            response += "💬 **Client Testimonials:**\n"
            for testimonial in testimonials:
                response += f"   • {testimonial}\n"
            response += "\n"
        
        return response
    
    def _format_services_content(self, content: Dict[str, Any]) -> str:
        """Format services-related content with clean formatting"""
        response = ""
        
        services = list(set(content.get('services', [])))
        if services:
            response += "🛠️ **Services Offered:**\n"
            for i, service in enumerate(services, 1):
                response += f"   {i}. {service}\n"
            response += "\n"
        
        return response
    
    def _format_contact_content(self, content: Dict[str, Any]) -> str:
        """Format contact-related content with clean formatting"""
        response = ""
        
        emails = content.get('email', [])
        if emails:
            response += "📧 **Email Addresses:**\n"
            for email in emails:
                response += f"   • {email}\n"
            response += "\n"
        
        phones = content.get('phone', [])
        if phones:
            response += "📞 **Phone Numbers:**\n"
            for phone in phones:
                response += f"   • {phone}\n"
            response += "\n"
        
        addresses = content.get('address', [])
        if addresses:
            response += "📍 **Addresses:**\n"
            for address in addresses:
                response += f"   • {address}\n"
            response += "\n"
        
        return response
    
    def _format_about_content(self, content: Dict[str, Any]) -> str:
        """Format about-related content with clean formatting"""
        response = ""
        
        mission = content.get('mission', [])
        if mission:
            response += "🎯 **Mission:**\n"
            for m in mission:
                response += f"   • {m}\n"
            response += "\n"
        
        vision = content.get('vision', [])
        if vision:
            response += "👁️ **Vision:**\n"
            for v in vision:
                response += f"   • {v}\n"
            response += "\n"
        
        return response
    
    def _format_pricing_content(self, content: Dict[str, Any]) -> str:
        """Format pricing-related content with clean formatting"""
        response = ""
        
        prices = list(set(content.get('prices', [])))
        if prices:
            response += "💰 **Pricing Information:**\n"
            for price in prices:
                response += f"   • {price}\n"
            response += "\n"
        
        return response
    
    def _format_team_content(self, content: Dict[str, Any]) -> str:
        """Format team-related content with clean formatting"""
        response = ""
        
        team_members = list(set(content.get('team_members', [])))
        if team_members:
            response += "👥 **Team Members:**\n"
            for member in team_members:
                response += f"   • {member}\n"
            response += "\n"
        
        roles = list(set(content.get('roles', [])))
        if roles:
            response += "💼 **Roles & Positions:**\n"
            for role in roles:
                response += f"   • {role}\n"
            response += "\n"
        
        return response
    
    def _format_general_content(self, content: Dict[str, Any]) -> str:
        """Format general content with clean formatting"""
        response = ""
        
        highlights = content.get('highlights', [])
        if highlights:
            response += "📋 **Key Information:**\n"
            for highlight in highlights[:10]:  # Limit to 10 highlights
                response += f"   • {highlight}\n"
            response += "\n"
        
        key_points = content.get('key_points', [])
        if key_points:
            response += "💡 **Important Points:**\n"
            for point in key_points[:5]:  # Limit to 5 points
                response += f"   • {point[:200]}...\n"  # Truncate long points
            response += "\n"
        
        return response
