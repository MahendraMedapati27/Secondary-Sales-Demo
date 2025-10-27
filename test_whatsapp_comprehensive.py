#!/usr/bin/env python3
"""
Comprehensive WhatsApp Testing Script
Tests all WhatsApp functionality locally without deployment
"""

import os
import sys
import json
import time
from datetime import datetime
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(project_root))

def setup_test_environment():
    """Set up test environment variables"""
    os.environ['FLASK_ENV'] = 'testing'
    os.environ['FLASK_DEBUG'] = 'true'
    os.environ['DATABASE_URL'] = 'mssql+pyodbc://sqladmin:QuantumBlue@2024@chatbotsql2121.database.windows.net:1433/chatbot_db?driver=ODBC+Driver+17+for+SQL+Server'
    
    # WhatsApp test credentials (use dummy values for local testing)
    os.environ['WHATSAPP_ACCESS_TOKEN'] = 'test_token'
    os.environ['WHATSAPP_PHONE_NUMBER_ID'] = 'test_phone_id'
    os.environ['WHATSAPP_VERIFY_TOKEN'] = 'quantum_blue_verify_token'
    os.environ['WHATSAPP_WEBHOOK_URL'] = 'http://localhost:8000/webhook/whatsapp'
    
    # Groq API key (use your actual key)
    os.environ['GROQ_API_KEY'] = 'gsk_your_groq_api_key_here'  # Replace with actual key
    
    print("✅ Test environment variables set")

def test_imports():
    """Test all imports work correctly"""
    try:
        from app import create_app, db
        from app.models import User, Product, Order, Warehouse
        from app.whatsapp_webhook import handle_whatsapp_onboarding, handle_whatsapp_chat, handle_whatsapp_order_flow, handle_whatsapp_tracking_flow
        from app.database_service import DatabaseService
        from app.order_service import OrderService
        from app.groq_service import GroqService
        from app.llm_classification_service import LLMClassificationService
        from app.web_search_service import WebSearchService
        from app.whatsapp_service import WhatsAppService
        print("✅ All imports successful")
        return True
    except Exception as e:
        print(f"❌ Import error: {e}")
        return False

def test_app_creation():
    """Test Flask app creation"""
    try:
        from app import create_app
        app = create_app()
        print("✅ Flask app created successfully")
        return app
    except Exception as e:
        print(f"❌ App creation error: {e}")
        return None

def test_database_connection(app):
    """Test database connection"""
    try:
        with app.app_context():
            from app.models import User, Product, Warehouse
            # Test basic queries
            user_count = User.query.count()
            product_count = Product.query.count()
            warehouse_count = Warehouse.query.count()
            print(f"✅ Database connection successful - Users: {user_count}, Products: {product_count}, Warehouses: {warehouse_count}")
            return True
    except Exception as e:
        print(f"❌ Database connection error: {e}")
        return False

def test_whatsapp_services(app):
    """Test WhatsApp-related services"""
    try:
        with app.app_context():
            from app.database_service import DatabaseService
            from app.order_service import OrderService
            from app.groq_service import GroqService
            from app.llm_classification_service import LLMClassificationService
            from app.web_search_service import WebSearchService
            from app.whatsapp_service import WhatsAppService
            
            # Initialize services
            db_service = DatabaseService()
            order_service = OrderService()
            groq_service = GroqService()
            llm_service = LLMClassificationService()
            web_search_service = WebSearchService()
            whatsapp_service = WhatsAppService()
            
            print("✅ All WhatsApp services initialized successfully")
            return True
    except Exception as e:
        print(f"❌ Service initialization error: {e}")
        return False

def test_product_model_attributes(app):
    """Test Product model attributes match database schema"""
    try:
        with app.app_context():
            from app.models import Product
            from app.database_service import DatabaseService
            
            db_service = DatabaseService()
            products = db_service.get_products_by_warehouse(1)  # Test with warehouse 1
            
            if products:
                product = products[0]
                # Test all required attributes exist
                required_attrs = ['id', 'product_code', 'product_name', 'product_description', 
                                'price_of_product', 'discount', 'scheme', 'warehouse_id']
                
                for attr in required_attrs:
                    if not hasattr(product, attr):
                        print(f"❌ Product missing attribute: {attr}")
                        return False
                
                # Test attribute values
                print(f"✅ Product attributes test passed - Sample: {product.product_name} (₹{product.price_of_product})")
                return True
            else:
                print("⚠️ No products found in warehouse 1")
                return False
    except Exception as e:
        print(f"❌ Product model test error: {e}")
        return False

def test_whatsapp_onboarding_flow(app):
    """Test WhatsApp onboarding flow"""
    try:
        with app.app_context():
            from app.models import User
            from app.whatsapp_webhook import handle_whatsapp_onboarding
            
            # Create test user
            test_user = User(
                name="Test User",
                email="test@whatsapp.local",
                phone="919999999999",
                email_verified=False,
                warehouse_location=None
            )
            
            # Test onboarding steps
            session = {}
            
            # Step 1: Ask for email
            response1 = handle_whatsapp_onboarding(test_user, session, "test@example.com")
            print(f"✅ Onboarding Step 1: {response1[:50]}...")
            
            # Step 2: Verify OTP (simulate)
            test_user.email = "test@example.com"
            test_user.generate_otp()
            response2 = handle_whatsapp_onboarding(test_user, session, "123456")
            print(f"✅ Onboarding Step 2: {response2[:50]}...")
            
            return True
    except Exception as e:
        print(f"❌ Onboarding flow test error: {e}")
        return False

def test_whatsapp_order_flow(app):
    """Test WhatsApp order flow"""
    try:
        with app.app_context():
            from app.models import User
            from app.whatsapp_webhook import handle_whatsapp_order_flow
            from app.database_service import DatabaseService
            from app.order_service import OrderService
            
            # Create test user with warehouse
            test_user = User(
                name="Test User",
                email="test@example.com",
                phone="919999999999",
                email_verified=True,
                warehouse_location="Mumbai Central"
            )
            
            # Initialize services
            db_service = DatabaseService()
            order_service = OrderService()
            
            # Test order flow
            session = {}
            order_session = {
                'status': 'idle',
                'items': [],
                'total_cost': 0,
                'final_total': 0
            }
            
            # Test initial order request
            response = handle_whatsapp_order_flow(test_user, session, "place an order", order_session, db_service, order_service)
            print(f"✅ Order flow test passed: {response[:100]}...")
            
            return True
    except Exception as e:
        print(f"❌ Order flow test error: {e}")
        return False

def test_whatsapp_webhook_parsing():
    """Test WhatsApp webhook message parsing"""
    try:
        from app.whatsapp_service import WhatsAppService
        
        whatsapp_service = WhatsAppService()
        
        # Test message webhook
        message_webhook = {
            "object": "whatsapp_business_account",
            "entry": [{
                "id": "1133168128944313",
                "changes": [{
                    "value": {
                        "messaging_product": "whatsapp",
                        "metadata": {
                            "display_phone_number": "15556370308",
                            "phone_number_id": "845643508632489"
                        },
                        "contacts": [{
                            "profile": {"name": "Test User"},
                            "wa_id": "919999999999"
                        }],
                        "messages": [{
                            "from": "919999999999",
                            "id": "test_message_id",
                            "timestamp": "1761586803",
                            "text": {"body": "Hello"},
                            "type": "text"
                        }]
                    },
                    "field": "messages"
                }]
            }]
        }
        
        parsed = whatsapp_service.parse_webhook_message(message_webhook)
        if parsed and parsed.get('text') == 'Hello':
            print("✅ WhatsApp webhook parsing test passed")
            return True
        else:
            print("❌ WhatsApp webhook parsing failed")
            return False
            
    except Exception as e:
        print(f"❌ Webhook parsing test error: {e}")
        return False

def test_status_update_handling():
    """Test status update handling (should not cause warnings)"""
    try:
        from app.whatsapp_service import WhatsAppService
        
        whatsapp_service = WhatsAppService()
        
        # Test status update webhook
        status_webhook = {
            "object": "whatsapp_business_account",
            "entry": [{
                "id": "1133168128944313",
                "changes": [{
                    "value": {
                        "messaging_product": "whatsapp",
                        "metadata": {
                            "display_phone_number": "15556370308",
                            "phone_number_id": "845643508632489"
                        },
                        "statuses": [{
                            "id": "test_status_id",
                            "status": "delivered",
                            "timestamp": "1761586803",
                            "recipient_id": "919999999999"
                        }]
                    },
                    "field": "messages"
                }]
            }]
        }
        
        parsed = whatsapp_service.parse_webhook_message(status_webhook)
        if parsed is None:  # Should return None for status updates
            print("✅ Status update handling test passed")
            return True
        else:
            print("❌ Status update handling failed")
            return False
            
    except Exception as e:
        print(f"❌ Status update test error: {e}")
        return False

def run_comprehensive_tests():
    """Run all tests"""
    print("🚀 Starting Comprehensive WhatsApp Testing")
    print("=" * 60)
    
    # Setup
    setup_test_environment()
    
    # Test 1: Imports
    if not test_imports():
        print("❌ Import tests failed - stopping")
        return False
    
    # Test 2: App creation
    app = test_app_creation()
    if not app:
        print("❌ App creation failed - stopping")
        return False
    
    # Test 3: Database connection
    if not test_database_connection(app):
        print("❌ Database connection failed - stopping")
        return False
    
    # Test 4: Services
    if not test_whatsapp_services(app):
        print("❌ Service initialization failed - stopping")
        return False
    
    # Test 5: Product model attributes
    if not test_product_model_attributes(app):
        print("❌ Product model test failed - stopping")
        return False
    
    # Test 6: Webhook parsing
    if not test_whatsapp_webhook_parsing():
        print("❌ Webhook parsing test failed")
        return False
    
    # Test 7: Status update handling
    if not test_status_update_handling():
        print("❌ Status update test failed")
        return False
    
    # Test 8: Onboarding flow
    if not test_whatsapp_onboarding_flow(app):
        print("❌ Onboarding flow test failed")
        return False
    
    # Test 9: Order flow
    if not test_whatsapp_order_flow(app):
        print("❌ Order flow test failed")
        return False
    
    print("=" * 60)
    print("🎉 ALL TESTS PASSED! WhatsApp chatbot is ready for deployment.")
    print("=" * 60)
    return True

if __name__ == "__main__":
    success = run_comprehensive_tests()
    sys.exit(0 if success else 1)
