#!/usr/bin/env python3
"""Test Microsoft Graph API Mail.Send functionality"""
from msal import ConfidentialClientApplication
import requests
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

CLIENT_ID = os.getenv('MS_GRAPH_CLIENT_ID')
CLIENT_SECRET = os.getenv('MS_GRAPH_CLIENT_SECRET')
TENANT_ID = os.getenv('MS_GRAPH_TENANT_ID')
SENDER_EMAIL = os.getenv('MS_GRAPH_SENDER_EMAIL', 'mahendra@highvolt.tech')

if not all([CLIENT_ID, CLIENT_SECRET, TENANT_ID]):
    print("❌ Missing required environment variables")
    exit(1)

AUTHORITY = f"https://login.microsoftonline.com/{TENANT_ID}"
SCOPE = ["https://graph.microsoft.com/.default"]

print("=== Testing Microsoft Graph Mail.Send ===")
print(f"Client ID: {CLIENT_ID}")
print(f"Tenant ID: {TENANT_ID}")
print(f"Sender Email: {SENDER_EMAIL}")
print()

# Get access token
app = ConfidentialClientApplication(
    CLIENT_ID,
    authority=AUTHORITY,
    client_credential=CLIENT_SECRET
)

print("1. Acquiring access token...")
result = app.acquire_token_for_client(scopes=SCOPE)

if "access_token" not in result:
    print(f"❌ Could not acquire token: {result.get('error_description', 'Unknown error')}")
    exit(1)

access_token = result['access_token']
print("✅ Token acquired successfully")
print()

# Test sending email
headers = {
    "Authorization": f"Bearer {access_token}",
    "Content-Type": "application/json"
}

# Test email message
test_email = {
    "message": {
        "subject": "Test Email from Chatbot",
        "body": {
            "contentType": "HTML",
            "content": "<h1>Test Email</h1><p>This is a test email from the chatbot system.</p>"
        },
        "toRecipients": [
            {
                "emailAddress": {
                    "address": SENDER_EMAIL  # Send to self for testing
                }
            }
        ]
    },
    "saveToSentItems": "true"
}

print(f"2. Attempting to send test email to {SENDER_EMAIL}...")
send_mail_url = f"https://graph.microsoft.com/v1.0/users/{SENDER_EMAIL}/sendMail"

try:
    response = requests.post(send_mail_url, json=test_email, headers=headers, timeout=30)
    
    if response.status_code == 202:
        print("✅ Email sent successfully!")
        print("   Status: 202 Accepted (email queued for sending)")
    elif response.status_code == 403:
        print("❌ Permission Denied (403)")
        print("   Error: Mail.Send permission is missing or not consented")
        print()
        print("   To fix this:")
        print("   1. Go to Azure Portal > App registrations > Graph-Data-Extractor-Service")
        print("   2. Go to API permissions")
        print("   3. Add permission > Microsoft Graph > Application permissions")
        print("   4. Search for 'Mail.Send' and add it")
        print("   5. Click 'Grant admin consent'")
        error_data = response.json()
        print(f"   Details: {error_data}")
    else:
        print(f"❌ Unexpected response: {response.status_code}")
        print(f"   Response: {response.text[:500]}")
        
except Exception as e:
    print(f"❌ Error: {str(e)}")

