"""
Azure Translator Service for Real-time Translation
Translates chatbot responses and user messages in real-time
"""
import os
import logging
from typing import Optional
import requests
import hashlib
import json

logger = logging.getLogger(__name__)

class TranslationService:
    """Service for real-time translation using Azure Translator"""
    
    def __init__(self):
        """Initialize Azure Translator service"""
        self.endpoint = os.getenv('AZURE_TRANSLATOR_ENDPOINT')
        self.api_key = os.getenv('AZURE_TRANSLATOR_API_KEY')
        self.region = os.getenv('AZURE_TRANSLATOR_REGION', 'eastus2')
        
        # Translation cache to reduce API calls
        self.cache = {}
        self.cache_file = 'translation_cache.json'
        self.load_cache()
        
        if not self.endpoint or not self.api_key:
            logger.warning("Azure Translator credentials not configured. Translation will be disabled.")
            self.available = False
        else:
            self.available = True
            logger.info("Azure Translator service initialized")
    
    def load_cache(self):
        """Load translation cache from file"""
        try:
            if os.path.exists(self.cache_file):
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    self.cache = json.load(f)
                logger.info(f"Loaded {len(self.cache)} cached translations")
        except Exception as e:
            logger.warning(f"Could not load translation cache: {str(e)}")
            self.cache = {}
    
    def save_cache(self):
        """Save translation cache to file"""
        try:
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(self.cache, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning(f"Could not save translation cache: {str(e)}")
    
    def _get_cache_key(self, text: str, target_lang: str) -> str:
        """Generate cache key for translation"""
        key_string = f"{text}|{target_lang}"
        return hashlib.md5(key_string.encode('utf-8')).hexdigest()
    
    def is_available(self) -> bool:
        """Check if translation service is available"""
        return self.available
    
    def translate(self, text: str, target_language: str, source_language: str = 'en') -> str:
        """
        Translate text to target language
        
        Args:
            text: Text to translate
            target_language: Target language code (en, hi, te, my)
            source_language: Source language code (default: en)
            
        Returns:
            Translated text, or original text if translation fails
        """
        if not self.available:
            return text
        
        if not text or not text.strip():
            return text
        
        # If target language is English, no translation needed
        if target_language == 'en':
            return text
        
        # Map language codes to Azure Translator format
        # Azure Translator uses: en, hi, te, my (Burmese)
        language_map = {
            'en': 'en',
            'hi': 'hi',
            'te': 'te',
            'my': 'my'  # Burmese
        }
        
        # Get Azure language code
        azure_target_lang = language_map.get(target_language, target_language)
        
        # Check cache first
        cache_key = self._get_cache_key(text, azure_target_lang)
        if cache_key in self.cache:
            return self.cache[cache_key]
        
        try:
            # Azure Translator API endpoint - use global endpoint
            # The global endpoint works better: https://api.cognitive.microsofttranslator.com/translate
            url = "https://api.cognitive.microsofttranslator.com/translate"
            
            # API version
            params = {
                'api-version': '3.0',
                'from': source_language,
                'to': azure_target_lang
            }
            
            headers = {
                'Ocp-Apim-Subscription-Key': self.api_key,
                'Ocp-Apim-Subscription-Region': self.region,
                'Content-Type': 'application/json'
            }
            
            body = [{
                'text': text
            }]
            
            from app.timeout_utils import get_timeout
            from app.circuit_breaker import get_circuit_breaker
            
            # Use circuit breaker for translation
            breaker = get_circuit_breaker('azure_translator', failure_threshold=5, recovery_timeout=60)
            
            def _call_translator():
                response = requests.post(
                    url, 
                    params=params, 
                    headers=headers, 
                    json=body, 
                    timeout=get_timeout('translation')
                )
                response.raise_for_status()
                return response.json()
            
            # Call with circuit breaker
            result = breaker.call(_call_translator, fallback=lambda: None)
            
            if result is None:
                # Circuit breaker is open, return original text
                return text
            
            # result is already the JSON response
            if result and len(result) > 0 and 'translations' in result[0]:
                translated_text = result[0]['translations'][0]['text']
                
                # Cache the translation
                self.cache[cache_key] = translated_text
                if len(self.cache) > 1000:  # Limit cache size
                    # Remove oldest entries (simple FIFO)
                    oldest_keys = list(self.cache.keys())[:100]
                    for key in oldest_keys:
                        del self.cache[key]
                self.save_cache()
                
                return translated_text
            else:
                logger.warning(f"Unexpected translation response: {result}")
                return text
                
        except Exception as e:
            logger.error(f"Error translating text: {str(e)}")
            return text  # Return original text on error
    
    def translate_batch(self, texts: list, target_language: str, source_language: str = 'en') -> list:
        """
        Translate multiple texts at once (more efficient)
        
        Args:
            texts: List of texts to translate
            target_language: Target language code
            source_language: Source language code
            
        Returns:
            List of translated texts
        """
        if not self.available or target_language == 'en':
            return texts
        
        translated = []
        for text in texts:
            translated.append(self.translate(text, target_language, source_language))
        
        return translated
    
    def translate_dict(self, data: dict, target_language: str, keys_to_translate: list = None) -> dict:
        """
        Translate values in a dictionary
        
        Args:
            data: Dictionary to translate
            target_language: Target language code
            keys_to_translate: List of keys to translate (if None, translates all string values)
            
        Returns:
            Dictionary with translated values
        """
        if not self.available or target_language == 'en':
            return data
        
        translated_data = data.copy()
        
        if keys_to_translate:
            # Translate specific keys
            for key in keys_to_translate:
                if key in translated_data and isinstance(translated_data[key], str):
                    translated_data[key] = self.translate(translated_data[key], target_language)
        else:
            # Translate all string values
            for key, value in translated_data.items():
                if isinstance(value, str) and value.strip():
                    translated_data[key] = self.translate(value, target_language)
        
        return translated_data

# Global instance
_translation_service = None

def get_translation_service() -> TranslationService:
    """Get or create the global translation service instance"""
    global _translation_service
    if _translation_service is None:
        _translation_service = TranslationService()
    return _translation_service

