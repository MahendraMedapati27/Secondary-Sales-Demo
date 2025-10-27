# WhatsApp Access Token Fix Guide

## 🚨 Current Issue
The WhatsApp chatbot is receiving messages but failing to send responses due to a 401 Unauthorized error:

```
ERROR:app.whatsapp_service:Failed to send WhatsApp message: 401 Client Error: Unauthorized
```

## 🔧 Solution: Update WhatsApp Access Token

### Step 1: Get New Access Token
1. Go to [Meta Developer Console](https://developers.facebook.com/)
2. Navigate to your WhatsApp Business App
3. Go to "WhatsApp" → "API Setup"
4. Click "Generate Token" or "Refresh Token"
5. Copy the new access token

### Step 2: Update Azure Environment Variable
1. Go to **Azure Portal** → **App Services** → `my-chatbot-app-73d666`
2. Click **"Configuration"** → **"Application settings"**
3. Find `WHATSAPP_ACCESS_TOKEN`
4. Update the value with your new token
5. Click **"Apply"**
6. **Restart the app** (Overview → Restart)

### Step 3: Verify Configuration
Make sure these environment variables are set correctly:

```
WHATSAPP_ACCESS_TOKEN = your-new-access-token
WHATSAPP_PHONE_NUMBER_ID = 845643508632489
WHATSAPP_VERIFY_TOKEN = quantum_blue_verify_token
WHATSAPP_WEBHOOK_URL = https://my-chatbot-app-73d666.azurewebsites.net/webhook/whatsapp
```

### Step 4: Test WhatsApp Integration
1. Send a message to your WhatsApp Business number: `+1 555 637 0308`
2. The bot should now respond successfully
3. Check Azure logs for successful message sending

## 📱 Expected Behavior After Fix
- ✅ Messages are received and parsed correctly
- ✅ Intent classification works
- ✅ Groq AI generates responses
- ✅ Responses are sent back to WhatsApp
- ✅ Messages are marked as read

## 🔍 Troubleshooting
If you still get 401 errors:
1. Verify the access token is not expired
2. Check that the token has the correct permissions
3. Ensure the phone number ID is correct
4. Restart the Azure App Service after making changes
