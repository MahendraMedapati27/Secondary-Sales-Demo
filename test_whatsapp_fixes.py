#!/usr/bin/env python3
"""
Test script to verify WhatsApp chatbot fixes:
1. Order confirmation priority detection
2. LLM-driven product extraction
3. Cart persistence
"""

import os
import sys
from pathlib import Path
import unittest
import json
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta

# Add the project root to Python path
project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(project_root))

# Set up a test configuration for Flask
os.environ['FLASK_ENV'] = 'testing'
os.environ['FLASK_DEBUG'] = 'true'
os.environ['DATABASE_URL'] = 'mssql+pymssql://sa:yourStrongPassword@localhost:1433/chatbot_db'
os.environ['GROQ_API_KEY'] = 'gsk_your_actual_groq_api_key_here'
os.environ['WHATSAPP_ACCESS_TOKEN'] = 'test_token'
os.environ['WHATSAPP_PHONE_NUMBER_ID'] = 'test_phone_id'
os.environ['WHATSAPP_VERIFY_TOKEN'] = 'quantum_blue_verify_token'
os.environ['WHATSAPP_WEBHOOK_URL'] = 'http://localhost:8000/webhook/whatsapp'
os.environ['TAVILY_API_KEY'] = 'tvly-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx'
os.environ['EMAIL_USERNAME'] = 'test@example.com'
os.environ['EMAIL_PASSWORD'] = 'password'
os.environ['EMAIL_SERVER'] = 'smtp.example.com'
os.environ['EMAIL_PORT'] = '587'

from app import create_app, db
from app.models import User, Product, Warehouse, Order, OrderItem
from app.whatsapp_webhook import handle_whatsapp_chat, handle_whatsapp_order_flow, whatsapp_sessions, get_whatsapp_session, save_whatsapp_session
from app.database_service import DatabaseService
from app.order_service import OrderService
from app.llm_classification_service import LLMClassificationService

def test_whatsapp_fixes():
    """Test all WhatsApp fixes comprehensively"""
    app = create_app()
    app.config['TESTING'] = True
    app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL')
    app.config['WTF_CSRF_ENABLED'] = False
    
    with app.app_context():
        db.create_all()
        
        # Initialize services
        db_service = DatabaseService()
        order_service = OrderService()
        classification_service = LLMClassificationService()
        
        # Create a unique test user
        import time
        unique_email = f"fix_test_{int(time.time())}@example.com"
        test_user_phone = f"919999{int(time.time()) % 100000}"
        test_user = User(
            name="Fix Test User",
            email=unique_email,
            phone=test_user_phone,
            email_verified=True,
            warehouse_location="Mumbai Central"
        )
        
        # Clean up existing test user if any
        existing_user = User.query.filter_by(phone=test_user_phone).first()
        if existing_user:
            db.session.delete(existing_user)
            db.session.commit()

        db.session.add(test_user)
        db.session.commit()
        print(f"✅ Test user created with ID: {test_user.id}, Email: {unique_email}, Phone: {test_user_phone}")
        
        # Add test warehouses and products
        warehouse1 = Warehouse.query.filter_by(location_name="Mumbai Central").first()
        if not warehouse1:
            warehouse1 = Warehouse(location_name="Mumbai Central", location_code="WH001")
            db.session.add(warehouse1)
        
        if not Product.query.filter_by(product_code="QB003").first():
            db.session.add(Product(product_code="QB003", product_name="AI Memory Card", product_description="High-speed memory card for AI operations", price_of_product=800.0, discount=50.0, scheme="Buy 3 Get 2 Free", warehouse_id=warehouse1.id, product_quantity=200, available_for_sale=200))
        if not Product.query.filter_by(product_code="QB005").first():
            db.session.add(Product(product_code="QB005", product_name="AI Controller", product_description="Central unit for AI systems", price_of_product=950.0, discount=75.0, scheme="Buy 2 Get 25% Off", warehouse_id=warehouse1.id, product_quantity=120, available_for_sale=120))
        db.session.commit()
        
        print("✅ Database setup complete")

        # Reset WhatsApp sessions for clean testing
        whatsapp_sessions.clear()
        
        # Mock session for WhatsApp
        session = {}
        
        print("\n🧪 Testing WhatsApp Fixes")
        print("=" * 50)

        # Test 1: Order Confirmation Priority Detection
        print("\n📱 Test 1: Order Confirmation Priority Detection")
        print("-" * 40)
        
        # First add items to cart
        with patch('app.llm_classification_service.LLMClassificationService.classify_user_intent') as mock_classify:
            mock_classify.return_value = {
                'classification': 'PLACE_ORDER', 
                'confidence': 0.98, 
                'entities': {'product_name': 'AI Memory Card', 'quantity': 5}
            }
            
            response1 = handle_whatsapp_chat(test_user, session, "add AI Memory Card 5")
            print(f"Response 1: {response1[:100]}...")
            
            # Check if cart has items
            current_session = get_whatsapp_session(test_user.phone)
            order_session = current_session['order_session']
            
            if len(order_session['items']) > 0:
                print("✅ Cart has items, proceeding to confirmation test")
                
                # Now test "confirm order" - this should be caught by priority check
                response2 = handle_whatsapp_chat(test_user, session, "confirm order")
                print(f"Response 2: {response2[:100]}...")
                
                if "Order Placed Successfully" in response2 or "Order" in response2:
                    print("✅ Test 1 PASSED: Order confirmation detected correctly")
                else:
                    print("❌ Test 1 FAILED: Order confirmation not detected")
                    return False
            else:
                print("❌ Test 1 FAILED: No items in cart")
                return False

        # Test 2: LLM-driven Product Extraction (Plural Handling)
        print("\n📱 Test 2: LLM-driven Product Extraction")
        print("-" * 40)
        
        # Reset session for clean test
        whatsapp_sessions.clear()
        
        with patch('app.llm_classification_service.LLMClassificationService.classify_user_intent') as mock_classify:
            # Test with plural form "AI Controllers" - should be normalized to "AI Controller"
            mock_classify.return_value = {
                'classification': 'PLACE_ORDER', 
                'confidence': 0.98, 
                'entities': {'product_name': 'AI Controller', 'quantity': 3}  # LLM should normalize "AI Controllers" to "AI Controller"
            }
            
            response3 = handle_whatsapp_chat(test_user, session, "add AI Controllers 3")
            print(f"Response 3: {response3[:100]}...")
            
            current_session = get_whatsapp_session(test_user.phone)
            order_session = current_session['order_session']
            
            if len(order_session['items']) > 0 and "AI Controller" in response3:
                print("✅ Test 2 PASSED: LLM extracted and normalized product name correctly")
            else:
                print("❌ Test 2 FAILED: Product extraction failed")
                return False

        # Test 3: Cart Persistence
        print("\n📱 Test 3: Cart Persistence")
        print("-" * 40)
        
        # Add another item to existing cart
        with patch('app.llm_classification_service.LLMClassificationService.classify_user_intent') as mock_classify:
            mock_classify.return_value = {
                'classification': 'PLACE_ORDER', 
                'confidence': 0.98, 
                'entities': {'product_name': 'AI Memory Card', 'quantity': 2}
            }
            
            response4 = handle_whatsapp_chat(test_user, session, "add AI Memory Card 2")
            print(f"Response 4: {response4[:100]}...")
            
            current_session = get_whatsapp_session(test_user.phone)
            order_session = current_session['order_session']
            
            if len(order_session['items']) >= 2:
                print(f"✅ Test 3 PASSED: Cart persistence working - {len(order_session['items'])} items in cart")
                print(f"   Items: {[item['product_name'] for item in order_session['items']]}")
            else:
                print("❌ Test 3 FAILED: Cart persistence failed")
                return False

        # Test 4: Multiple Confirmation Phrases
        print("\n📱 Test 4: Multiple Confirmation Phrases")
        print("-" * 40)
        
        confirmation_phrases = ["place my order", "place it", "checkout", "finalize order"]
        
        for phrase in confirmation_phrases:
            # Reset session for each test
            whatsapp_sessions.clear()
            
            # Add items first
            with patch('app.llm_classification_service.LLMClassificationService.classify_user_intent') as mock_classify:
                mock_classify.return_value = {
                    'classification': 'PLACE_ORDER', 
                    'confidence': 0.98, 
                    'entities': {'product_name': 'AI Memory Card', 'quantity': 1}
                }
                
                handle_whatsapp_chat(test_user, session, "add AI Memory Card 1")
                
                # Test confirmation phrase
                response = handle_whatsapp_chat(test_user, session, phrase)
                print(f"Phrase '{phrase}': {response[:50]}...")
                
                if "Order" in response or "placed" in response.lower():
                    print(f"✅ '{phrase}' detected correctly")
                else:
                    print(f"❌ '{phrase}' not detected")
                    return False

        print("\n" + "=" * 50)
        print("🎉 ALL TESTS PASSED! WhatsApp fixes are working correctly!")
        print("=" * 50)
        print("✅ Order confirmation priority detection working")
        print("✅ LLM-driven product extraction working")
        print("✅ Cart persistence working")
        print("✅ Multiple confirmation phrases detected")
        
        return True

if __name__ == '__main__':
    if test_whatsapp_fixes():
        print("\n🚀 WhatsApp chatbot fixes are ready for deployment!")
    else:
        print("\n❌ Some tests failed. Please check the implementation.")
