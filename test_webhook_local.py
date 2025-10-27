#!/usr/bin/env python3
"""
Local WhatsApp Webhook Testing Script
Simulates WhatsApp webhook calls locally for testing
"""

import os
import sys
import json
import requests
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(project_root))

def setup_local_environment():
    """Set up local environment"""
    os.environ['FLASK_ENV'] = 'development'
    os.environ['FLASK_DEBUG'] = 'true'
    os.environ['DATABASE_URL'] = 'mssql+pyodbc://sqladmin:QuantumBlue@2024@chatbotsql2121.database.windows.net:1433/chatbot_db?driver=ODBC+Driver+17+for+SQL+Server'
    
    # WhatsApp credentials
    os.environ['WHATSAPP_ACCESS_TOKEN'] = 'test_token'
    os.environ['WHATSAPP_PHONE_NUMBER_ID'] = 'test_phone_id'
    os.environ['WHATSAPP_VERIFY_TOKEN'] = 'quantum_blue_verify_token'
    os.environ['WHATSAPP_WEBHOOK_URL'] = 'http://localhost:8000/webhook/whatsapp'
    
    # Groq API key (replace with your actual key)
    os.environ['GROQ_API_KEY'] = 'gsk_your_groq_api_key_here'

def create_test_webhook_payload(message_text, from_number="919999999999"):
    """Create a test webhook payload"""
    return {
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
                        "wa_id": from_number
                    }],
                    "messages": [{
                        "from": from_number,
                        "id": f"test_message_{int(time.time())}",
                        "timestamp": str(int(time.time())),
                        "text": {"body": message_text},
                        "type": "text"
                    }]
                },
                "field": "messages"
            }]
        }]
    }

def test_webhook_endpoint(base_url="http://localhost:8000"):
    """Test the webhook endpoint"""
    webhook_url = f"{base_url}/webhook/whatsapp"
    
    # Test verification
    print("🔍 Testing webhook verification...")
    verify_response = requests.get(webhook_url, params={
        'hub.mode': 'subscribe',
        'hub.challenge': 'test_challenge',
        'hub.verify_token': 'quantum_blue_verify_token'
    })
    
    if verify_response.status_code == 200 and verify_response.text == 'test_challenge':
        print("✅ Webhook verification successful")
    else:
        print(f"❌ Webhook verification failed: {verify_response.status_code} - {verify_response.text}")
        return False
    
    # Test message processing
    test_messages = [
        "hi",
        "test@example.com",
        "123456",
        "Mumbai Central",
        "place an order",
        "show me all products",
        "add Quantum Processor 2",
        "confirm order"
    ]
    
    for i, message in enumerate(test_messages, 1):
        print(f"\n📱 Testing message {i}: '{message}'")
        
        payload = create_test_webhook_payload(message)
        
        try:
            response = requests.post(webhook_url, json=payload, headers={
                'Content-Type': 'application/json'
            })
            
            if response.status_code == 200:
                print(f"✅ Message {i} processed successfully")
                print(f"   Response: {response.json()}")
            else:
                print(f"❌ Message {i} failed: {response.status_code} - {response.text}")
                
        except Exception as e:
            print(f"❌ Message {i} error: {e}")
    
    return True

def start_local_server():
    """Start local Flask server for testing"""
    print("🚀 Starting local Flask server...")
    
    from app import create_app
    app = create_app()
    
    print("✅ Local server started at http://localhost:8000")
    print("📱 Webhook URL: http://localhost:8000/webhook/whatsapp")
    print("🔍 Verification URL: http://localhost:8000/webhook/whatsapp?hub.mode=subscribe&hub.challenge=test&hub.verify_token=quantum_blue_verify_token")
    print("\nPress Ctrl+C to stop the server")
    
    app.run(host='0.0.0.0', port=8000, debug=True)

if __name__ == "__main__":
    import time
    
    setup_local_environment()
    
    if len(sys.argv) > 1 and sys.argv[1] == "server":
        start_local_server()
    else:
        print("🧪 Running webhook tests...")
        test_webhook_endpoint()
