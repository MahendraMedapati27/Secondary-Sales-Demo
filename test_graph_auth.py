#!/usr/bin/env python3
"""Test Microsoft Graph API authentication"""
from msal import ConfidentialClientApplication
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

CLIENT_ID = os.getenv('MS_GRAPH_CLIENT_ID')
CLIENT_SECRET = os.getenv('MS_GRAPH_CLIENT_SECRET')
TENANT_ID = os.getenv('MS_GRAPH_TENANT_ID')

if not all([CLIENT_ID, CLIENT_SECRET, TENANT_ID]):
    print("❌ Missing required environment variables")
    print(f"CLIENT_ID: {'✅' if CLIENT_ID else '❌'}")
    print(f"CLIENT_SECRET: {'✅' if CLIENT_SECRET else '❌'}")
    print(f"TENANT_ID: {'✅' if TENANT_ID else '❌'}")
    exit(1)

AUTHORITY = f"https://login.microsoftonline.com/{TENANT_ID}"
SCOPE = ["https://graph.microsoft.com/.default"]

print("Attempting to acquire token...")
print(f"Client ID: {CLIENT_ID}")
print(f"Tenant ID: {TENANT_ID}")

app = ConfidentialClientApplication(
    CLIENT_ID,
    authority=AUTHORITY,
    client_credential=CLIENT_SECRET
)

result = app.acquire_token_for_client(scopes=SCOPE)

if "access_token" in result:
    print("✅ Token acquired successfully!")
    print(f"Token expires in: {result.get('expires_in', 'N/A')} seconds")
    
    # Test if we can access user info (basic test)
    import requests
    headers = {
        "Authorization": f"Bearer {result['access_token']}",
        "Content-Type": "application/json"
    }
    
    # Try to get user info (this will work if we have User.Read permission)
    test_url = "https://graph.microsoft.com/v1.0/users/mahendra@highvolt.tech"
    test_response = requests.get(test_url, headers=headers)
    
    if test_response.status_code == 200:
        print("✅ Successfully accessed Microsoft Graph API")
        user_data = test_response.json()
        print(f"User: {user_data.get('displayName', 'N/A')} ({user_data.get('mail', 'N/A')})")
    else:
        print(f"⚠️  Graph API test returned: {test_response.status_code}")
        print(f"Response: {test_response.text[:200]}")
    
else:
    print(f"❌ Could not acquire token: {result.get('error_description', 'Unknown error')}")
    print(f"Error: {result.get('error', 'N/A')}")
    exit(1)

