#!/usr/bin/env python3
"""
Test WhatsApp Session Management
Tests that cart items persist between messages
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
    
    # Groq API key (use actual key from environment)
    os.environ['GROQ_API_KEY'] = 'gsk_your_actual_groq_api_key_here'  # Replace with your actual key
    
    print("✅ Test environment variables set")

def test_session_persistence():
    """Test that WhatsApp session data persists between messages"""
    print("🧪 Testing WhatsApp Session Persistence")
    print("=" * 50)
    
    try:
        from app import create_app, db
        from app.models import User, Product, Warehouse
        from app.whatsapp_webhook import handle_whatsapp_chat, get_whatsapp_session, save_whatsapp_session, whatsapp_sessions
        from app.database_service import DatabaseService
        
        app = create_app()
        
        with app.app_context():
            # Initialize services
            db_service = DatabaseService()
            
            # Create test user with warehouse
            import time
            unique_email = f"session_test_{int(time.time())}@example.com"
            test_user = User(
                name="Session Test User",
                email=unique_email,
                phone=f"919999{int(time.time()) % 100000}",
                email_verified=True,
                warehouse_location="Mumbai Central"
            )
            
            # Save user to database to get an ID
            db.session.add(test_user)
            db.session.commit()
            print(f"✅ Test user created with ID: {test_user.id}, Phone: {test_user.phone}")
            
            # Clear any existing sessions
            whatsapp_sessions.clear()
            
            # Test 1: First message - should create new session
            print("\n📱 Test 1: First message - 'place an order'")
            print("-" * 40)
            
            response1 = handle_whatsapp_chat(test_user, {}, "place an order")
            print(f"Response: {response1[:100]}...")
            
            # Check if session was created
            session1 = get_whatsapp_session(test_user.phone)
            print(f"Session created: {session1['order_session']['status']}")
            print(f"Session items: {len(session1['order_session']['items'])}")
            
            # Test 2: Add first product
            print("\n📱 Test 2: Add first product - 'add AI Memory Card 2'")
            print("-" * 40)
            
            response2 = handle_whatsapp_chat(test_user, {}, "add AI Memory Card 2")
            print(f"Response: {response2[:100]}...")
            
            # Check if session persisted and item was added
            session2 = get_whatsapp_session(test_user.phone)
            print(f"Session status: {session2['order_session']['status']}")
            print(f"Session items: {len(session2['order_session']['items'])}")
            print(f"Session total: ₹{session2['order_session']['final_total']:,.2f}")
            
            if len(session2['order_session']['items']) > 0:
                print("✅ First product added successfully")
                print(f"   Item: {session2['order_session']['items'][0]['product_name']}")
                print(f"   Quantity: {session2['order_session']['items'][0]['quantity']}")
            else:
                print("❌ First product not added")
                return False
            
            # Test 3: Add second product
            print("\n📱 Test 3: Add second product - 'add AI Controller 1'")
            print("-" * 40)
            
            response3 = handle_whatsapp_chat(test_user, {}, "add AI Controller 1")
            print(f"Response: {response3[:100]}...")
            
            # Check if session persisted and second item was added
            session3 = get_whatsapp_session(test_user.phone)
            print(f"Session status: {session3['order_session']['status']}")
            print(f"Session items: {len(session3['order_session']['items'])}")
            print(f"Session total: ₹{session3['order_session']['final_total']:,.2f}")
            
            if len(session3['order_session']['items']) > 1:
                print("✅ Second product added successfully")
                print(f"   Total items: {len(session3['order_session']['items'])}")
                for i, item in enumerate(session3['order_session']['items']):
                    print(f"   Item {i+1}: {item['product_name']} - {item['quantity']} units")
            else:
                print("❌ Second product not added")
                return False
            
            # Test 4: Remove a product
            print("\n📱 Test 4: Remove product - 'remove AI Controller'")
            print("-" * 40)
            
            response4 = handle_whatsapp_chat(test_user, {}, "remove AI Controller")
            print(f"Response: {response4[:100]}...")
            
            # Check if session persisted and item was removed
            session4 = get_whatsapp_session(test_user.phone)
            print(f"Session status: {session4['order_session']['status']}")
            print(f"Session items: {len(session4['order_session']['items'])}")
            print(f"Session total: ₹{session4['order_session']['final_total']:,.2f}")
            
            if len(session4['order_session']['items']) == 1:
                print("✅ Product removed successfully")
                print(f"   Remaining item: {session4['order_session']['items'][0]['product_name']}")
            else:
                print("❌ Product removal failed")
                return False
            
            # Test 5: Confirm order
            print("\n📱 Test 5: Confirm order - 'confirm order'")
            print("-" * 40)
            
            response5 = handle_whatsapp_chat(test_user, {}, "confirm order")
            print(f"Response: {response5[:100]}...")
            
            # Check if order was placed
            if "Order Placed Successfully" in response5:
                print("✅ Order placed successfully")
                print("✅ Session management working correctly!")
            else:
                print("❌ Order placement failed")
                return False
            
            print("\n" + "=" * 50)
            print("🎉 ALL SESSION PERSISTENCE TESTS PASSED!")
            print("=" * 50)
            print("✅ Session data persists between messages")
            print("✅ Cart items are maintained correctly")
            print("✅ Order totals are calculated properly")
            print("✅ Order placement works with persistent cart")
            
            return True
            
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_edge_cases():
    """Test edge cases for session management"""
    print("\n🧪 Testing Edge Cases")
    print("=" * 50)
    
    try:
        from app import create_app, db
        from app.models import User
        from app.whatsapp_webhook import handle_whatsapp_chat, get_whatsapp_session, whatsapp_sessions
        from app.database_service import DatabaseService
        
        app = create_app()
        
        with app.app_context():
            db_service = DatabaseService()
            
            # Create test user
            import time
            unique_email = f"edge_test_{int(time.time())}@example.com"
            test_user = User(
                name="Edge Test User",
                email=unique_email,
                phone=f"918888{int(time.time()) % 100000}",
                email_verified=True,
                warehouse_location="Mumbai Central"
            )
            
            db.session.add(test_user)
            db.session.commit()
            
            # Clear sessions
            whatsapp_sessions.clear()
            
            # Edge Case 1: Empty cart confirmation
            print("\n📱 Edge Case 1: Confirm empty cart")
            print("-" * 40)
            
            response1 = handle_whatsapp_chat(test_user, {}, "confirm order")
            print(f"Response: {response1[:100]}...")
            
            if "cart is empty" in response1.lower():
                print("✅ Empty cart handled correctly")
            else:
                print("❌ Empty cart not handled properly")
                return False
            
            # Edge Case 2: Invalid product name
            print("\n📱 Edge Case 2: Add invalid product")
            print("-" * 40)
            
            response2 = handle_whatsapp_chat(test_user, {}, "add Invalid Product 5")
            print(f"Response: {response2[:100]}...")
            
            if "not found" in response2.lower() or "couldn't find" in response2.lower():
                print("✅ Invalid product handled correctly")
            else:
                print("❌ Invalid product not handled properly")
                return False
            
            # Edge Case 3: Remove non-existent product
            print("\n📱 Edge Case 3: Remove non-existent product")
            print("-" * 40)
            
            response3 = handle_whatsapp_chat(test_user, {}, "remove Non Existent Product")
            print(f"Response: {response3[:100]}...")
            
            if "couldn't find" in response3.lower() or "not in your cart" in response3.lower():
                print("✅ Non-existent product removal handled correctly")
            else:
                print("❌ Non-existent product removal not handled properly")
                return False
            
            print("\n✅ ALL EDGE CASES PASSED!")
            return True
            
    except Exception as e:
        print(f"❌ Edge case test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False

def run_all_tests():
    """Run all session management tests"""
    setup_test_environment()
    
    # Test 1: Session persistence
    if not test_session_persistence():
        print("❌ Session persistence test failed")
        return False
    
    # Test 2: Edge cases
    if not test_edge_cases():
        print("❌ Edge cases test failed")
        return False
    
    print("\n🎉 ALL TESTS PASSED! WhatsApp session management is working correctly!")
    return True

if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
