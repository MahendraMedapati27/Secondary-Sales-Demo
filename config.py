import os
from dotenv import load_dotenv

# Ensure environment variables are loaded from the .env file
load_dotenv()

class Config:
    """Application configuration"""
    
    # Flask settings
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')
    SECURITY_PASSWORD_SALT = os.getenv('SECURITY_PASSWORD_SALT', 'dev-salt')
    
    # ------------------------------------------------------------------------
    ## GROQ LLM SERVICE CONFIGURATION (Replacing Azure OpenAI)
    # ------------------------------------------------------------------------
    GROQ_API_KEY = os.getenv('GROQ_API_KEY')
    # Defaulting to a high-speed Groq model
    GROQ_MODEL = os.getenv('GROQ_MODEL', 'llama-3.3-70b-versatile')
    
    # NOTE: Azure OpenAI configuration removed/commented out for Groq usage.
    # AZURE_OPENAI_ENDPOINT = os.getenv('AZURE_OPENAI_ENDPOINT')
    # AZURE_OPENAI_KEY = os.getenv('AZURE_OPENAI_KEY')
    # AZURE_OPENAI_DEPLOYMENT = os.getenv('AZURE_OPENAI_DEPLOYMENT', 'gpt-4o')
    # AZURE_OPENAI_API_VERSION = os.getenv('AZURE_OPENAI_API_VERSION', '2024-08-01-preview')
    
    # ------------------------------------------------------------------------
    ## AZURE AI SEARCH CONFIGURATION
    # ------------------------------------------------------------------------
    AZURE_SEARCH_ENDPOINT = os.getenv('AZURE_SEARCH_ENDPOINT')
    AZURE_SEARCH_API_KEY = os.getenv('AZURE_SEARCH_API_KEY')
    AZURE_SEARCH_INDEX_NAME = os.getenv('AZURE_SEARCH_INDEX_NAME', 'products-index')
    
    # ------------------------------------------------------------------------
    ## AZURE BLOB STORAGE CONFIGURATION
    # ------------------------------------------------------------------------
    AZURE_STORAGE_CONNECTION_STRING = os.getenv('AZURE_STORAGE_CONNECTION_STRING')
    AZURE_STORAGE_CONTAINER_NAME = os.getenv('AZURE_STORAGE_CONTAINER_NAME', 'chatbot-data')
    
    # ------------------------------------------------------------------------
    ## DATABASE CONFIGURATION
    # ------------------------------------------------------------------------
    SQL_SERVER = os.getenv('SQL_SERVER')
    SQL_DATABASE = os.getenv('SQL_DATABASE')
    SQL_USERNAME = os.getenv('SQL_USERNAME')
    SQL_PASSWORD = os.getenv('SQL_PASSWORD')
    
    REQUIRE_AZURE_DB = os.getenv('REQUIRE_AZURE_DB', 'false').lower() == 'true'

    if SQL_SERVER:
        from urllib.parse import quote_plus
        encoded_password = quote_plus(SQL_PASSWORD)
        
        # Enhanced Azure SQL connection string with proper encoding
        SQLALCHEMY_DATABASE_URI = (
            f"mssql+pymssql://{SQL_USERNAME}:{encoded_password}@{SQL_SERVER}/{SQL_DATABASE}"
            f"?charset=utf8&tds_version=7.4&timeout=30&login_timeout=15"
        )
    else:
        SQLALCHEMY_DATABASE_URI = 'sqlite:///chatbot.db'
    
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_pre_ping': True,
        'pool_size': int(os.getenv('DB_POOL_SIZE', 5)),
        'max_overflow': int(os.getenv('DB_MAX_OVERFLOW', 10)),
        'pool_recycle': int(os.getenv('DB_POOL_RECYCLE', 1800)),
        'pool_timeout': int(os.getenv('DB_POOL_TIMEOUT', 30)),
    }
    
    if SQL_SERVER:
        SQLALCHEMY_ENGINE_OPTIONS['connect_args'] = {
            'login_timeout': int(os.getenv('DB_LOGIN_TIMEOUT', 15)),
            'timeout': int(os.getenv('DB_QUERY_TIMEOUT', 30)),
            'tds_version': os.getenv('DB_TDS_VERSION', '7.4'),
            'charset': os.getenv('DB_CHARSET', 'utf8'),
            'autocommit': True,
            'as_dict': False,
            # Note: 'use_mars' is not supported by pymssql driver
        }
    
    # ------------------------------------------------------------------------
    ## EMAIL/SMTP CONFIGURATION
    # ------------------------------------------------------------------------
    MAIL_SERVER = os.getenv('MAIL_SERVER', 'smtp.gmail.com')
    MAIL_PORT = int(os.getenv('MAIL_PORT', 587))
    MAIL_USE_TLS = os.getenv('MAIL_USE_TLS', 'True').lower() == 'true'
    MAIL_USE_SSL = os.getenv('MAIL_USE_SSL', 'False').lower() == 'true'
    MAIL_USERNAME = os.getenv('MAIL_USERNAME')
    MAIL_PASSWORD = os.getenv('MAIL_PASSWORD')
    MAIL_DEFAULT_SENDER = os.getenv('MAIL_DEFAULT_SENDER', os.getenv('MAIL_USERNAME'))
    ADMIN_EMAIL = os.getenv('ADMIN_EMAIL')
    COMPANY_EMAIL = os.getenv('COMPANY_EMAIL', 'mahendra@highvolt.tech')
    
    # ------------------------------------------------------------------------
    ## AUTHENTICATION SETTINGS
    # ------------------------------------------------------------------------
    OTP_EXPIRATION = int(os.getenv('OTP_EXPIRATION', 600))  # 10 minutes
    TOKEN_EXPIRATION = int(os.getenv('TOKEN_EXPIRATION', 3600))
    
    # ------------------------------------------------------------------------
    ## WEB SEARCH APIs (Tavily for Quantum Blue)
    # ------------------------------------------------------------------------
    TAVILY_API_KEY = os.getenv('TAVILY_API_KEY')
    
    # 🚨 New setting to constrain web search for Quantum Blue
    _DOMAIN_STRING = os.getenv('ALLOWED_SEARCH_DOMAINS', 'investopedia.com,financialservices.gov.in,highvolt.tech')
    ALLOWED_SEARCH_DOMAINS = [
        d.strip() for d in _DOMAIN_STRING.split(',') if d.strip()
    ]
    
    # Other search keys are kept but are not used in the current LLM-only architecture
    BRAVE_SEARCH_API_KEY = os.getenv('BRAVE_SEARCH_API_KEY')
    SERPER_API_KEY = os.getenv('SERPER_API_KEY')
    GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')
    GOOGLE_CSE_ID = os.getenv('GOOGLE_CSE_ID')
    
    # Website list (kept for original purpose, but not used by the LLM-powered search anymore)
    MONITORED_WEBSITES = [
        'https://www.investopedia.com/',
        'https://financialservices.gov.in/beta/en',
        'https://highvolt.tech/'
    ]
    
    # ------------------------------------------------------------------------
    ## WHATSAPP BUSINESS API CONFIGURATION
    # ------------------------------------------------------------------------
    WHATSAPP_ACCESS_TOKEN = os.getenv('WHATSAPP_ACCESS_TOKEN')
    WHATSAPP_PHONE_NUMBER_ID = os.getenv('WHATSAPP_PHONE_NUMBER_ID')
    WHATSAPP_VERIFY_TOKEN = os.getenv('WHATSAPP_VERIFY_TOKEN', 'quantum_blue_verify_token')
    WHATSAPP_WEBHOOK_URL = os.getenv('WHATSAPP_WEBHOOK_URL', 'https://your-domain.com/webhook/whatsapp')
    WHATSAPP_API_VERSION = os.getenv('WHATSAPP_API_VERSION', 'v22.0')
    WHATSAPP_BASE_URL = f"https://graph.facebook.com/{WHATSAPP_API_VERSION}"