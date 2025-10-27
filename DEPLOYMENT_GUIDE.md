# 🚀 WhatsApp Chatbot Deployment Guide

## Pre-Deployment Checklist ✅

### 1. Database Migration
Before deploying, run the database migration to add required columns:

```bash
# On Azure App Service, run:
python azure_migrate_database.py
```

This will add:
- `onboarding_state` column to `users` table
- `whatsapp_session_data` column to `users` table

### 2. Environment Variables
Ensure these are set in Azure App Service Configuration:

#### Required Variables:
- `SQLALCHEMY_DATABASE_URI` - Database connection string
- `WHATSAPP_ACCESS_TOKEN` - Meta WhatsApp Business API token
- `WHATSAPP_PHONE_NUMBER_ID` - WhatsApp phone number ID
- `GROQ_API_KEY` - Groq LLM API key
- `MAIL_USERNAME` - Email for OTP sending
- `MAIL_PASSWORD` - Email password
- `TAVILY_API_KEY` - Web search API key

#### Optional Variables:
- `WHATSAPP_VERIFY_TOKEN` - Webhook verification token (default: quantum_blue_verify_token)
- `WHATSAPP_WEBHOOK_URL` - Your webhook URL
- `FLASK_ENV` - Set to 'production'

### 3. WhatsApp Business API Setup
1. Go to Meta Developer Console
2. Create/configure WhatsApp Business API
3. Get access token and phone number ID
4. Set webhook URL: `https://your-app.azurewebsites.net/webhook/whatsapp`
5. Set verify token: `quantum_blue_verify_token`

### 4. Deployment Steps
1. Push code to GitHub main branch
2. GitHub Actions will automatically deploy to Azure
3. Run database migration script
4. Test WhatsApp webhook
5. Verify all environment variables are set

## Post-Deployment Testing

### Test WhatsApp Webhook:
1. Send "Hi" to your WhatsApp Business number
2. Should receive: "Hi! Welcome to Quantum Blue. What's your name?"
3. Follow the onboarding flow

### Test Web Interface:
1. Visit your Azure App Service URL
2. Test the web chatbot functionality
3. Verify all features work

## Troubleshooting

### Common Issues:
1. **401 Unauthorized**: Update WhatsApp access token
2. **Database errors**: Run migration script
3. **Import errors**: Check all environment variables
4. **Webhook not receiving**: Verify webhook URL and verify token

### Logs:
Check Azure App Service logs for detailed error information.

## Features Included:
- ✅ WhatsApp onboarding flow (name, email, OTP, warehouse)
- ✅ Full chat functionality (orders, tracking, company info, web search)
- ✅ Backward compatibility with existing database
- ✅ Error handling and logging
- ✅ Session management
- ✅ Email OTP verification
- ✅ Warehouse selection
- ✅ Order placement and tracking
- ✅ Web search integration
- ✅ Company information queries

## Support:
If you encounter any issues, check the logs and ensure all environment variables are properly set.
