#!/usr/bin/env python3
"""
Test script for WhatsApp functionality locally
"""

import os
import sys
import json
from datetime import datetime

# Add the app directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

from app import create_app, db
from app.models import User, ChatSession
from app.whatsapp_webhook import process_whatsapp_message, handle_whatsapp_onboarding, handle_whatsapp_chat

def test_whatsapp_flow():
    """Test the WhatsApp flow locally"""
    print("🧪 Testing WhatsApp functionality locally...")
    
    # Create Flask app
    app = create_app()
    
    with app.app_context():
        try:
            # Create a test user with a unique phone number
            test_phone = "919515724999"  # Use a different phone number
            user = User.query.filter_by(phone=test_phone).first()
            
            if not user:
                print("📝 Creating test user...")
                user = User(
                    name="Test User",
                    email="test999@example.com",  # Use a unique email
                    phone=test_phone,
                    email_verified=False,
                    warehouse_location=None
                )
                user.set_password("test_password")
                db.session.add(user)
                db.session.commit()
                print(f"✅ Created test user: {user.name}")
            else:
                print(f"✅ Found existing user: {user.name}")
                # Reset user for testing
                user.email_verified = False
                user.warehouse_location = None
                db.session.commit()
                print("🔄 Reset user for testing")
            
            # Create a test session with unique ID
            import time
            session_id = f"TEST_SESSION_{int(time.time())}"
            session = ChatSession(
                session_id=session_id,
                user_id=user.id,
                is_active=True
            )
            db.session.add(session)
            db.session.commit()
            
            print("\n🔍 Testing onboarding flow...")
            
            # Test 1: First message should start onboarding
            print("\n1. Testing first message (should start onboarding)...")
            response1 = process_whatsapp_message(user, session, "Hi")
            print(f"   Response: {response1}")
            
            # Test 2: Provide name
            print("\n2. Testing name input...")
            response2 = process_whatsapp_message(user, session, "John Doe")
            print(f"   Response: {response2}")
            
            # Test 3: Provide email
            print("\n3. Testing email input...")
            response3 = process_whatsapp_message(user, session, "john.doe@example.com")
            print(f"   Response: {response3}")
            
            # Test 4: Provide OTP (simulate)
            print("\n4. Testing OTP input...")
            # First, we need to generate an OTP
            otp = user.generate_otp()
            db.session.commit()
            print(f"   Generated OTP: {otp}")
            response4 = process_whatsapp_message(user, session, otp)
            print(f"   Response: {response4}")
            
            # Test 5: Provide warehouse
            print("\n5. Testing warehouse selection...")
            response5 = process_whatsapp_message(user, session, "Mumbai")
            print(f"   Response: {response5}")
            
            # Test 6: Test chat functionality
            print("\n6. Testing chat functionality...")
            response6 = process_whatsapp_message(user, session, "I want to place an order")
            print(f"   Response: {response6}")
            
            print("\n✅ All tests completed successfully!")
            
        except Exception as e:
            print(f"❌ Test failed: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    return True

if __name__ == "__main__":
    success = test_whatsapp_flow()
    sys.exit(0 if success else 1)
