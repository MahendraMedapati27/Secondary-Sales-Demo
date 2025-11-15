"""
Azure AI Search Service for Product Information
Handles searching product information from PDF documents indexed in Azure AI Search
"""
import os
import logging
from typing import List, Dict, Optional
from azure.search.documents import SearchClient
from azure.core.credentials import AzureKeyCredential

logger = logging.getLogger(__name__)

class AzureSearchService:
    """Service for interacting with Azure AI Search"""
    
    def __init__(self):
        """Initialize Azure AI Search client"""
        self.endpoint = os.getenv('AZURE_SEARCH_ENDPOINT')
        self.api_key = os.getenv('AZURE_SEARCH_API_KEY')
        self.index_name = os.getenv('AZURE_SEARCH_INDEX_NAME', 'products-index')
        
        if not self.endpoint or not self.api_key:
            logger.warning("Azure AI Search credentials not configured. Product search will be unavailable.")
            self.client = None
        else:
            try:
                credential = AzureKeyCredential(self.api_key)
                self.client = SearchClient(
                    endpoint=self.endpoint,
                    index_name=self.index_name,
                    credential=credential
                )
                logger.info(f"Azure AI Search client initialized for index: {self.index_name}")
            except Exception as e:
                logger.error(f"Failed to initialize Azure AI Search client: {str(e)}")
                self.client = None
    
    def is_available(self) -> bool:
        """Check if Azure AI Search is available"""
        return self.client is not None
    
    def search_products(self, search_query: str, top: int = 10) -> List[Dict]:
        """
        Search for products in Azure AI Search
        
        Args:
            search_query: Search query string
            top: Maximum number of results to return
            
        Returns:
            List of product documents matching the search query
        """
        if not self.is_available():
            logger.warning("Azure AI Search is not available")
            return []
        
        try:
            # Perform simple search using the correct SDK method
            # The search method accepts search_text and optional parameters
            results = self.client.search(
                search_text=search_query,
                top=top,
                include_total_count=True
            )
            
            products = []
            for result in results:
                product = dict(result)
                products.append(product)
            
            logger.info(f"Found {len(products)} products for query: {search_query}")
            return products
            
        except Exception as e:
            logger.error(f"Error searching products: {str(e)}")
            return []
    
    def get_all_products(self, top: int = 100) -> List[Dict]:
        """
        Get all products from the index
        
        Args:
            top: Maximum number of results to return
            
        Returns:
            List of all product documents
        """
        if not self.is_available():
            logger.warning("Azure AI Search is not available")
            return []
        
        try:
            # Get all documents by searching with empty string or wildcard
            # Empty string returns all documents when fields are searchable
            results = self.client.search(
                search_text="*",
                top=top,
                include_total_count=True
            )
            
            products = []
            for result in results:
                product = dict(result)
                products.append(product)
            
            logger.info(f"Retrieved {len(products)} products from index")
            return products
            
        except Exception as e:
            logger.error(f"Error retrieving all products: {str(e)}")
            return []
    
    def get_product_by_name(self, product_name: str) -> Optional[Dict]:
        """
        Get a specific product by name
        
        Args:
            product_name: Name of the product to retrieve
            
        Returns:
            Product document if found, None otherwise
        """
        if not self.is_available():
            return None
        
        try:
            results = self.client.search(
                search_text=f'"{product_name}"',
                top=1,
                include_total_count=True
            )
            
            for result in results:
                return dict(result)
            
            return None
            
        except Exception as e:
            logger.error(f"Error retrieving product {product_name}: {str(e)}")
            return None
    
    def _has_semantic_config(self) -> bool:
        """Check if semantic configuration is available (simplified check)"""
        # In a real implementation, you might check the index schema
        # For now, we'll try semantic search and fall back if it fails
        # Return False to use simple search by default (semantic requires special configuration)
        return False

# Global instance
_search_service = None

def get_search_service() -> AzureSearchService:
    """Get or create the global Azure Search service instance"""
    global _search_service
    if _search_service is None:
        _search_service = AzureSearchService()
    return _search_service

