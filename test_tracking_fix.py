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
os.environ['GROQ_API_KEY'] = 'gsk_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx'
os.environ['WHATSAPP_ACCESS_TOKEN'] = 'EAAxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx'
os.environ['WHATSAPP_PHONE_NUMBER_ID'] = '845643508632489'
os.environ['WHATSAPP_VERIFY_TOKEN'] = 'quantum_blue_verify_token'
os.environ['WHATSAPP_WEBHOOK_URL'] = 'https://your-domain.com/webhook/whatsapp'
os.environ['TAVILY_API_KEY'] = 'tvly-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx'
os.environ['EMAIL_USERNAME'] = 'rarerabbit.m986@gmail.com'
os.environ['EMAIL_PASSWORD'] = 'asep mids dntr jrdw'
os.environ['EMAIL_SERVER'] = 'smtp.gmail.com'
os.environ['EMAIL_PORT'] = '587'

from app import create_app, db
from app.models import User, Product, Warehouse, Order, OrderItem, Conversation, ChatSession
from app.whatsapp_webhook import handle_whatsapp_tracking_flow, whatsapp_sessions, get_whatsapp_session, save_whatsapp_session
from app.database_service import DatabaseService

def test_tracking_fix():
    app = create_app()
    app.config['TESTING'] = True
    app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL')
    app.config['WTF_CSRF_ENABLED'] = False
    
    with app.app_context():
        db.create_all()
        
        # Initialize services
        db_service = DatabaseService()
        
        # Use existing user or create a unique test user
        import time
        unique_email = f"tracking_test_{int(time.time())}@example.com"
        test_user_phone = f"919999{int(time.time()) % 100000}"
        test_user = User(
            name="Tracking Test User",
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

        # Save user to database to get an ID
        db.session.add(test_user)
        db.session.commit()
        print(f"✅ Test user created with ID: {test_user.id}, Email: {unique_email}, Phone: {test_user_phone}")
        
        # Add test warehouse if it doesn't exist
        warehouse1 = Warehouse.query.filter_by(location_name="Mumbai Central").first()
        if not warehouse1:
            warehouse1 = Warehouse(location_name="Mumbai Central", location_code="WH001")
            db.session.add(warehouse1)
            db.session.commit()

        # Add test products if they don't exist
        if not Product.query.filter_by(product_code="QB001").first():
            db.session.add(Product(product_code="QB001", product_name="Quantum Processor", product_description="High-performance quantum processor for AI applications", price_of_product=2500.0, discount=150.0, scheme="Buy 2 Get 1 Free", warehouse_id=warehouse1.id, product_quantity=100, available_for_sale=100))
        if not Product.query.filter_by(product_code="QB003").first():
            db.session.add(Product(product_code="QB003", product_name="AI Memory Card", product_description="High-speed memory card for AI operations", price_of_product=800.0, discount=50.0, scheme="Buy 3 Get 2 Free", warehouse_id=warehouse1.id, product_quantity=200, available_for_sale=200))
        db.session.commit()
        
        print("✅ Database setup complete")

        # Reset whatsapp_sessions for this test run
        whatsapp_sessions.clear()
        whatsapp_session_data = get_whatsapp_session(test_user.phone)
        tracking_session = whatsapp_session_data['tracking_session']

        print("\n🧪 Testing WhatsApp Order Tracking Fix")
        print("==================================================")

        # Test 1: Track orders when user has no orders
        print("\n📱 Test 1: Track orders with no orders")
        print("-" * 40)
        response1 = handle_whatsapp_tracking_flow(test_user, {}, "track my order", tracking_session, db_service)
        print(f"Response 1: {response1[:200]}...")
        if "No Orders Found" in response1:
            print("✅ Test 1 PASSED: Correctly shows no orders message")
        else:
            print("❌ Test 1 FAILED: Should show no orders message")
            return False

        # Test 2: Create a test order
        print("\n📱 Test 2: Create test order")
        print("-" * 40)
        
        # Create a test order
        test_order = Order(
            user_id=test_user.id,
            warehouse_id=warehouse1.id,
            warehouse_location="Mumbai Central",
            user_email=unique_email,
            total_amount=2500.0,
            status="confirmed"
        )
        test_order.generate_order_id()
        db.session.add(test_order)
        db.session.commit()
        
        # Add order items
        product1 = Product.query.filter_by(product_code="QB001").first()
        order_item1 = OrderItem(
            order_id=test_order.id,
            product_id=product1.id,
            product_code="QB001",
            product_quantity_ordered=1,
            unit_price=2500.0,
            total_price=2500.0
        )
        db.session.add(order_item1)
        db.session.commit()
        
        print(f"✅ Test order created: {test_order.order_id}")

        # Test 3: Track orders when user has orders
        print("\n📱 Test 3: Track orders with existing orders")
        print("-" * 40)
        response2 = handle_whatsapp_tracking_flow(test_user, {}, "track my order", tracking_session, db_service)
        print(f"Response 2: {response2[:300]}...")
        if "Your Orders" in response2 and test_order.order_id in response2:
            print("✅ Test 3 PASSED: Correctly shows user's orders")
        else:
            print("❌ Test 3 FAILED: Should show user's orders")
            return False

        # Test 4: Track specific order
        print("\n📱 Test 4: Track specific order")
        print("-" * 40)
        response3 = handle_whatsapp_tracking_flow(test_user, {}, f"track {test_order.order_id}", tracking_session, db_service)
        print(f"Response 3: {response3[:300]}...")
        if "Order Details" in response3 and test_order.order_id in response3 and "Quantum Processor" in response3:
            print("✅ Test 4 PASSED: Correctly shows specific order details")
        else:
            print("❌ Test 4 FAILED: Should show specific order details")
            return False

        # Test 5: Track non-existent order
        print("\n📱 Test 5: Track non-existent order")
        print("-" * 40)
        response4 = handle_whatsapp_tracking_flow(test_user, {}, "track QB999999", tracking_session, db_service)
        print(f"Response 4: {response4[:200]}...")
        if "Order Not Found" in response4:
            print("✅ Test 5 PASSED: Correctly shows order not found")
        else:
            print("❌ Test 5 FAILED: Should show order not found")
            return False

    print("\n============================================================")
    print("🎉 ALL TRACKING TESTS PASSED!")
    print("============================================================")
    print("✅ WhatsApp order tracking is now working correctly:")
    print("   • Shows 'No Orders Found' when user has no orders")
    print("   • Lists all orders when user types 'track my order'")
    print("   • Shows specific order details when tracking by order ID")
    print("   • Shows 'Order Not Found' for non-existent orders")
    return True

if __name__ == '__main__':
    if test_tracking_fix():
        print("\n🎉 ALL TESTS PASSED! WhatsApp order tracking is fixed!")
    else:
        print("\n❌ Some tests failed. Please check the implementation.")
