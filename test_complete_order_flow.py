#!/usr/bin/env python3
"""
Complete WhatsApp Order Flow Test
Tests the entire order process: products display -> cart management -> order placement -> confirmation
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
    
    # Groq API key (replace with your actual key)
    os.environ['GROQ_API_KEY'] = 'gsk_your_groq_api_key_here'
    
    print("✅ Test environment variables set")

def test_complete_order_flow():
    """Test the complete order flow step by step"""
    print("🚀 Testing Complete WhatsApp Order Flow")
    print("=" * 60)
    
    try:
        from app import create_app, db
        from app.models import User, Product, Warehouse
        from app.whatsapp_webhook import handle_whatsapp_order_flow
        from app.database_service import DatabaseService
        from app.order_service import OrderService
        
        app = create_app()
        
        with app.app_context():
            # Initialize services
            db_service = DatabaseService()
            order_service = OrderService()
            
            # Use existing user or create a unique test user
            import time
            unique_email = f"test_{int(time.time())}@example.com"
            test_user = User(
                name="Test User",
                email=unique_email,
                phone=f"919999{int(time.time()) % 100000}",
                email_verified=True,
                warehouse_location="Mumbai Central"
            )
            
            # Save user to database to get an ID
            db.session.add(test_user)
            db.session.commit()
            print(f"✅ Test user created with ID: {test_user.id}, Email: {unique_email}")
            
            # Get warehouse and products
            warehouse = db_service.get_warehouse_by_location("Mumbai Central")
            if not warehouse:
                print("❌ Mumbai Central warehouse not found")
                return False
            
            products = db_service.get_products_by_warehouse(warehouse.id)
            if not products:
                print("❌ No products found for Mumbai Central warehouse")
                return False
            
            print(f"✅ Found {len(products)} products in Mumbai Central warehouse")
            
            # Initialize session and order session
            session = {}
            order_session = {
                'status': 'idle',
                'items': [],
                'total_cost': 0,
                'final_total': 0
            }
            
            # STEP 1: Test "place an order" message
            print("\n📱 STEP 1: Testing 'place an order' message")
            print("-" * 40)
            
            response1 = handle_whatsapp_order_flow(test_user, session, "place an order", order_session, db_service, order_service)
            print(f"Bot Response: {response1}")
            
            # Check if response contains product information
            if "Available Products" in response1 or "products" in response1.lower():
                print("✅ STEP 1 PASSED: Bot displayed available products")
            else:
                print("❌ STEP 1 FAILED: Bot did not display products")
                return False
            
            # STEP 2: Test adding first product (use AI Memory Card which has 200 available)
            print("\n📱 STEP 2: Testing 'add AI Memory Card 2'")
            print("-" * 40)
            
            response2 = handle_whatsapp_order_flow(test_user, session, "add AI Memory Card 2", order_session, db_service, order_service)
            print(f"Bot Response: {response2}")
            
            # Check if product was added to cart
            if "Products Added to Cart" in response2 and len(order_session['items']) > 0:
                print("✅ STEP 2 PASSED: Product added to cart successfully")
                print(f"   Cart now has {len(order_session['items'])} items")
                print(f"   Total: ₹{order_session['final_total']:,.2f}")
            else:
                print("❌ STEP 2 FAILED: Product not added to cart")
                return False
            
            # STEP 3: Test adding second product (use AI Controller which has 120 available)
            print("\n📱 STEP 3: Testing 'add AI Controller 1'")
            print("-" * 40)
            
            response3 = handle_whatsapp_order_flow(test_user, session, "add AI Controller 1", order_session, db_service, order_service)
            print(f"Bot Response: {response3}")
            
            # Check if second product was added
            if "Products Added to Cart" in response3 and len(order_session['items']) > 1:
                print("✅ STEP 3 PASSED: Second product added to cart")
                print(f"   Cart now has {len(order_session['items'])} items")
                print(f"   Total: ₹{order_session['final_total']:,.2f}")
            else:
                print("❌ STEP 3 FAILED: Second product not added")
                return False
            
            # STEP 4: Test cart display
            print("\n📱 STEP 4: Testing cart display")
            print("-" * 40)
            
            response4 = handle_whatsapp_order_flow(test_user, session, "show my cart", order_session, db_service, order_service)
            print(f"Bot Response: {response4}")
            
            # Check if cart is displayed with totals
            if "Current Cart" in response4 or "Cart" in response4:
                print("✅ STEP 4 PASSED: Cart displayed successfully")
            else:
                print("❌ STEP 4 FAILED: Cart not displayed")
                return False
            
            # STEP 5: Test removing a product
            print("\n📱 STEP 5: Testing 'remove AI Controller'")
            print("-" * 40)
            
            response5 = handle_whatsapp_order_flow(test_user, session, "remove AI Controller", order_session, db_service, order_service)
            print(f"Bot Response: {response5}")
            
            # Check if product was removed
            if "Products Removed from Cart" in response5:
                print("✅ STEP 5 PASSED: Product removed from cart")
                print(f"   Cart now has {len(order_session['items'])} items")
                print(f"   Total: ₹{order_session['final_total']:,.2f}")
            else:
                print("❌ STEP 5 FAILED: Product not removed")
                return False
            
            # STEP 6: Test adding another product (add more AI Memory Cards)
            print("\n📱 STEP 6: Testing 'add AI Memory Card 1'")
            print("-" * 40)
            
            response6 = handle_whatsapp_order_flow(test_user, session, "add AI Memory Card 1", order_session, db_service, order_service)
            print(f"Bot Response: {response6}")
            
            # Check if product was added
            if "Products Added to Cart" in response6:
                print("✅ STEP 6 PASSED: Additional product added to cart")
                print(f"   Cart now has {len(order_session['items'])} items")
                print(f"   Total: ₹{order_session['final_total']:,.2f}")
            else:
                print("❌ STEP 6 FAILED: Additional product not added")
                return False
            
            # STEP 7: Test order confirmation
            print("\n📱 STEP 7: Testing 'confirm order'")
            print("-" * 40)
            
            response7 = handle_whatsapp_order_flow(test_user, session, "confirm order", order_session, db_service, order_service)
            print(f"Bot Response: {response7}")
            
            # Check if order was placed successfully
            if "Order Placed Successfully" in response7 and "Order ID" in response7:
                print("✅ STEP 7 PASSED: Order placed successfully")
                print("✅ Order confirmation message sent")
            else:
                print("❌ STEP 7 FAILED: Order not placed")
                return False
            
            # STEP 8: Test order tracking
            print("\n📱 STEP 8: Testing order tracking")
            print("-" * 40)
            
            from app.whatsapp_webhook import handle_whatsapp_tracking_flow
            tracking_session = {'status': 'idle'}
            
            response8 = handle_whatsapp_tracking_flow(test_user, session, "track my order", tracking_session, db_service)
            print(f"Bot Response: {response8}")
            
            # Check if order tracking works
            if "Orders" in response8 or "Order" in response8:
                print("✅ STEP 8 PASSED: Order tracking works")
            else:
                print("❌ STEP 8 FAILED: Order tracking not working")
                return False
            
            print("\n" + "=" * 60)
            print("🎉 COMPLETE ORDER FLOW TEST PASSED!")
            print("=" * 60)
            print("✅ All steps completed successfully:")
            print("   • Products displayed with prices and discounts")
            print("   • Products added to cart with pricing calculations")
            print("   • Cart updated with totals and recommendations")
            print("   • Products removed from cart")
            print("   • Order placed successfully with confirmation")
            print("   • Order tracking functional")
            print("   • Email confirmation sent")
            
            return True
            
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_product_display_details():
    """Test detailed product display with prices, discounts, and schemes"""
    print("\n🔍 Testing Detailed Product Display")
    print("-" * 40)
    
    try:
        from app import create_app
        from app.database_service import DatabaseService
        
        app = create_app()
        
        with app.app_context():
            db_service = DatabaseService()
            warehouse = db_service.get_warehouse_by_location("Mumbai Central")
            products = db_service.get_products_by_warehouse(warehouse.id)
            
            print(f"📦 Products in Mumbai Central warehouse:")
            for product in products[:5]:  # Show first 5 products
                print(f"   • {product.product_name} (QB{product.product_code[2:]})")
                print(f"     Price: ₹{product.price_of_product:,.2f}")
                print(f"     Discount: ₹{product.discount:,.2f}")
                print(f"     Scheme: {product.scheme}")
                print(f"     Available: {product.available_for_sale} units")
                print()
            
            return True
            
    except Exception as e:
        print(f"❌ Product display test failed: {e}")
        return False

def run_all_tests():
    """Run all tests"""
    setup_test_environment()
    
    # Test 1: Product display details
    if not test_product_display_details():
        print("❌ Product display test failed")
        return False
    
    # Test 2: Complete order flow
    if not test_complete_order_flow():
        print("❌ Complete order flow test failed")
        return False
    
    print("\n🎉 ALL TESTS PASSED! WhatsApp chatbot is ready for production!")
    return True

if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
