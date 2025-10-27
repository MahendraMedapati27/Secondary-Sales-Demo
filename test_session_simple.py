#!/usr/bin/env python3
"""
Simple WhatsApp Session Management Test
Tests session persistence without external API calls
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
    
    # WhatsApp test credentials
    os.environ['WHATSAPP_ACCESS_TOKEN'] = 'test_token'
    os.environ['WHATSAPP_PHONE_NUMBER_ID'] = 'test_phone_id'
    os.environ['WHATSAPP_VERIFY_TOKEN'] = 'quantum_blue_verify_token'
    os.environ['WHATSAPP_WEBHOOK_URL'] = 'http://localhost:8000/webhook/whatsapp'
    
    # Groq API key (use dummy key for testing)
    os.environ['GROQ_API_KEY'] = 'gsk_dummy_key_for_testing'
    
    print("✅ Test environment variables set")

def test_session_functions():
    """Test the session management functions directly"""
    print("🧪 Testing Session Management Functions")
    print("=" * 50)
    
    try:
        from app.whatsapp_webhook import get_whatsapp_session, save_whatsapp_session, whatsapp_sessions
        
        # Clear any existing sessions
        whatsapp_sessions.clear()
        
        # Test 1: Get session for new user
        print("\n📱 Test 1: Get session for new user")
        print("-" * 40)
        
        test_phone = "919999999999"
        session1 = get_whatsapp_session(test_phone)
        
        print(f"Session created: {session1['order_session']['status']}")
        print(f"Session items: {len(session1['order_session']['items'])}")
        print(f"Session total: ₹{session1['order_session']['final_total']:,.2f}")
        
        if session1['order_session']['status'] == 'idle' and len(session1['order_session']['items']) == 0:
            print("✅ New session created correctly")
        else:
            print("❌ New session not created correctly")
            return False
        
        # Test 2: Modify session data
        print("\n📱 Test 2: Modify session data")
        print("-" * 40)
        
        # Add an item to the session
        session1['order_session']['items'].append({
            'product_name': 'Test Product',
            'product_code': 'TEST001',
            'quantity': 2,
            'unit_price': 100.0,
            'final_price': 90.0,
            'discount_percentage': 10.0,
            'scheme_name': 'Test Scheme',
            'item_total': 180.0
        })
        session1['order_session']['final_total'] = 180.0
        session1['order_session']['status'] = 'calculating'
        
        # Save the modified session
        save_whatsapp_session(test_phone, session1)
        
        print(f"Modified session items: {len(session1['order_session']['items'])}")
        print(f"Modified session total: ₹{session1['order_session']['final_total']:,.2f}")
        print(f"Modified session status: {session1['order_session']['status']}")
        
        # Test 3: Retrieve session data
        print("\n📱 Test 3: Retrieve session data")
        print("-" * 40)
        
        session2 = get_whatsapp_session(test_phone)
        
        print(f"Retrieved session items: {len(session2['order_session']['items'])}")
        print(f"Retrieved session total: ₹{session2['order_session']['final_total']:,.2f}")
        print(f"Retrieved session status: {session2['order_session']['status']}")
        
        if (len(session2['order_session']['items']) == 1 and 
            session2['order_session']['final_total'] == 180.0 and
            session2['order_session']['status'] == 'calculating'):
            print("✅ Session data persisted correctly")
        else:
            print("❌ Session data not persisted correctly")
            return False
        
        # Test 4: Multiple users
        print("\n📱 Test 4: Multiple users")
        print("-" * 40)
        
        test_phone2 = "918888888888"
        session3 = get_whatsapp_session(test_phone2)
        
        print(f"User 1 session items: {len(get_whatsapp_session(test_phone)['order_session']['items'])}")
        print(f"User 2 session items: {len(session3['order_session']['items'])}")
        
        if (len(get_whatsapp_session(test_phone)['order_session']['items']) == 1 and
            len(session3['order_session']['items']) == 0):
            print("✅ Multiple users handled correctly")
        else:
            print("❌ Multiple users not handled correctly")
            return False
        
        print("\n✅ ALL SESSION FUNCTION TESTS PASSED!")
        return True
        
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_order_flow_functions():
    """Test the order flow functions with session management"""
    print("\n🧪 Testing Order Flow Functions")
    print("=" * 50)
    
    try:
        from app import create_app, db
        from app.models import User, Product, Warehouse
        from app.whatsapp_webhook import handle_whatsapp_order_flow, get_whatsapp_session, save_whatsapp_session
        from app.database_service import DatabaseService
        from app.order_service import OrderService
        
        app = create_app()
        
        with app.app_context():
            # Initialize services
            db_service = DatabaseService()
            order_service = OrderService()
            
            # Create test user
            import time
            unique_email = f"order_test_{int(time.time())}@example.com"
            test_user = User(
                name="Order Test User",
                email=unique_email,
                phone=f"917777{int(time.time()) % 100000}",
                email_verified=True,
                warehouse_location="Mumbai Central"
            )
            
            db.session.add(test_user)
            db.session.commit()
            print(f"✅ Test user created with ID: {test_user.id}, Phone: {test_user.phone}")
            
            # Test 1: Add product to cart
            print("\n📱 Test 1: Add product to cart")
            print("-" * 40)
            
            # Get initial session
            session_data = get_whatsapp_session(test_user.phone)
            order_session = session_data['order_session']
            
            print(f"Initial session items: {len(order_session['items'])}")
            
            # Add a product
            response1 = handle_whatsapp_order_flow(test_user, {}, "add AI Memory Card 2", order_session, db_service, order_service)
            print(f"Add response: {response1[:100]}...")
            
            # Save session and check
            save_whatsapp_session(test_user.phone, session_data)
            updated_session = get_whatsapp_session(test_user.phone)
            
            print(f"Updated session items: {len(updated_session['order_session']['items'])}")
            print(f"Updated session total: ₹{updated_session['order_session']['final_total']:,.2f}")
            
            if len(updated_session['order_session']['items']) > 0:
                print("✅ Product added to cart successfully")
            else:
                print("❌ Product not added to cart")
                return False
            
            # Test 2: Add another product
            print("\n📱 Test 2: Add another product")
            print("-" * 40)
            
            response2 = handle_whatsapp_order_flow(test_user, {}, "add AI Controller 1", updated_session['order_session'], db_service, order_service)
            print(f"Add response: {response2[:100]}...")
            
            # Save session and check
            save_whatsapp_session(test_user.phone, updated_session)
            final_session = get_whatsapp_session(test_user.phone)
            
            print(f"Final session items: {len(final_session['order_session']['items'])}")
            print(f"Final session total: ₹{final_session['order_session']['final_total']:,.2f}")
            
            if len(final_session['order_session']['items']) > 1:
                print("✅ Second product added successfully")
                print(f"   Total items: {len(final_session['order_session']['items'])}")
                for i, item in enumerate(final_session['order_session']['items']):
                    print(f"   Item {i+1}: {item['product_name']} - {item['quantity']} units")
            else:
                print("❌ Second product not added")
                return False
            
            print("\n✅ ALL ORDER FLOW TESTS PASSED!")
            return True
            
    except Exception as e:
        print(f"❌ Order flow test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False

def run_all_tests():
    """Run all session management tests"""
    setup_test_environment()
    
    # Test 1: Session functions
    if not test_session_functions():
        print("❌ Session functions test failed")
        return False
    
    # Test 2: Order flow functions
    if not test_order_flow_functions():
        print("❌ Order flow functions test failed")
        return False
    
    print("\n🎉 ALL TESTS PASSED! WhatsApp session management is working correctly!")
    return True

if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
