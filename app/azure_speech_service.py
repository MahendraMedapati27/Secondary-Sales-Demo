"""
Azure Speech Service for Voice Interaction
Handles Text-to-Speech (TTS) and provides token generation for client-side Speech-to-Text (STT)
"""
import os
import logging
import requests
from typing import Optional, Dict
from io import BytesIO
import time

logger = logging.getLogger(__name__)

class AzureSpeechService:
    """Service for Azure Speech Services integration"""
    
    def __init__(self):
        """Initialize Azure Speech Service"""
        self.speech_key = os.getenv('AZURE_SPEECH_KEY')
        self.speech_region = os.getenv('AZURE_SPEECH_REGION', 'eastus')
        
        if not self.speech_key:
            logger.warning("Azure Speech Key not found. Voice features will be disabled.")
            self.enabled = False
        else:
            self.enabled = True
            self.token_endpoint = f"https://{self.speech_region}.api.cognitive.microsoft.com/sts/v1.0/issueToken"
            self.tts_endpoint = f"https://{self.speech_region}.tts.speech.microsoft.com/cognitiveservices/v1"
            
        # Voice mapping for different languages
        self.voice_map = {
            'en': os.getenv('AZURE_SPEECH_VOICE_EN', 'en-US-AriaNeural'),
            'hi': os.getenv('AZURE_SPEECH_VOICE_HI', 'hi-IN-SwaraNeural'),
            'te': os.getenv('AZURE_SPEECH_VOICE_TE', 'te-IN-MohiniNeural'),
            'my': os.getenv('AZURE_SPEECH_VOICE_MY', 'my-MM-NilarNeural'),
        }
        
        # Cache for access token
        self._access_token = None
        self._token_expiry = 0
    
    def get_access_token(self) -> Optional[str]:
        """
        Get Azure Speech Service access token
        Token is valid for 10 minutes, we'll cache it
        """
        if not self.enabled:
            return None
        
        # Return cached token if still valid (with 1 minute buffer)
        current_time = time.time()
        if self._access_token and current_time < self._token_expiry - 60:
            return self._access_token
        
        try:
            headers = {
                'Ocp-Apim-Subscription-Key': self.speech_key
            }
            
            response = requests.post(self.token_endpoint, headers=headers, timeout=10)
            response.raise_for_status()
            
            self._access_token = response.text
            # Token expires in 10 minutes (600 seconds)
            self._token_expiry = current_time + 600
            
            logger.info("Azure Speech access token obtained successfully")
            return self._access_token
            
        except Exception as e:
            logger.error(f"Failed to get Azure Speech access token: {str(e)}")
            return None
    
    def text_to_speech(self, text: str, language: str = 'en', ssml: bool = False) -> Optional[BytesIO]:
        """
        Convert text to speech using Azure TTS
        
        Args:
            text: Text to convert to speech
            language: Language code (en, hi, te, my)
            ssml: Whether the text is SSML formatted
        
        Returns:
            BytesIO object containing audio data (WAV format) or None if failed
        """
        if not self.enabled:
            logger.warning("Azure Speech Service not enabled")
            return None
        
        if not text or not text.strip():
            logger.warning("Empty text provided for TTS")
            return None
        
        try:
            # Get voice for language
            voice = self.voice_map.get(language, self.voice_map['en'])
            
            # Prepare SSML if needed
            if ssml:
                ssml_text = text
            else:
                # Escape XML characters
                escaped_text = text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;').replace("'", '&apos;')
                
                # Get proper language code for SSML (e.g., 'en' -> 'en-US')
                lang_codes = {
                    'en': 'en-US',
                    'hi': 'hi-IN',
                    'te': 'te-IN',
                    'my': 'my-MM'
                }
                ssml_lang = lang_codes.get(language, 'en-US')
                
                ssml_text = f'''<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" xml:lang="{ssml_lang}">
                    <voice name="{voice}">
                        {escaped_text}
                    </voice>
                </speak>'''
            
            headers = {
                'Ocp-Apim-Subscription-Key': self.speech_key,
                'Content-Type': 'application/ssml+xml',
                'X-Microsoft-OutputFormat': 'audio-16khz-128kbitrate-mono-mp3',  # MP3 format for better compatibility
                'User-Agent': 'HighVolt-Chatbot'
            }
            
            # Encode SSML as UTF-8
            ssml_bytes = ssml_text.encode('utf-8')
            
            logger.debug(f"Sending TTS request: {len(ssml_bytes)} bytes SSML, voice: {voice}, lang: {language}")
            
            response = requests.post(
                self.tts_endpoint,
                headers=headers,
                data=ssml_bytes,
                timeout=30
            )
            
            # Check response status
            if response.status_code != 200:
                error_msg = f"Azure TTS API returned {response.status_code}: {response.text[:200]}"
                logger.error(error_msg)
                raise Exception(error_msg)
            
            # Validate response content
            if not response.content or len(response.content) == 0:
                logger.error("Azure TTS returned empty response")
                raise Exception("Empty audio response from Azure TTS")
            
            # Check if response is actually audio (starts with MP3 header or audio magic bytes)
            if not (response.content.startswith(b'\xff\xfb') or response.content.startswith(b'ID3') or 
                    response.content.startswith(b'\x49\x44\x33') or len(response.content) > 100):
                # Might be an error message in JSON
                try:
                    error_json = response.json()
                    error_msg = error_json.get('error', {}).get('message', 'Unknown Azure TTS error')
                    logger.error(f"Azure TTS error: {error_msg}")
                    raise Exception(f"Azure TTS error: {error_msg}")
                except:
                    error_text = response.text[:200] if hasattr(response, 'text') else str(response.content[:200])
                    logger.error(f"Azure TTS returned non-audio: {error_text}")
                    raise Exception(f"Invalid response from Azure TTS: {error_text[:100]}")
            
            # Return audio as BytesIO
            audio_data = BytesIO(response.content)
            audio_data.seek(0)
            
            logger.info(f"TTS successful: {len(response.content)} bytes generated for {len(text)} characters")
            return audio_data
            
        except Exception as e:
            logger.error(f"TTS failed: {str(e)}")
            return None
    
    def get_voice_for_language(self, language: str) -> str:
        """Get the voice name for a given language code"""
        return self.voice_map.get(language, self.voice_map['en'])
    
    def is_enabled(self) -> bool:
        """Check if Azure Speech Service is enabled"""
        return self.enabled


# Singleton instance
_speech_service = None

def get_speech_service() -> AzureSpeechService:
    """Get singleton instance of Azure Speech Service"""
    global _speech_service
    if _speech_service is None:
        _speech_service = AzureSpeechService()
    return _speech_service

