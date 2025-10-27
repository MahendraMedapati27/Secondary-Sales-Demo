# Azure App Service Environment Variables Checklist

## Required Environment Variables for WhatsApp Chatbot

### Database Configuration
- `SQLALCHEMY_DATABASE_URI` - Azure SQL Database connection string
- `SQL_SERVER` - Azure SQL Server name
- `SQL_DATABASE` - Database name
- `SQL_USERNAME` - Database username
- `SQL_PASSWORD` - Database password

### WhatsApp Business API
- `WHATSAPP_ACCESS_TOKEN` - Meta WhatsApp Business API access token
- `WHATSAPP_PHONE_NUMBER_ID` - WhatsApp phone number ID
- `WHATSAPP_VERIFY_TOKEN` - Webhook verification token (default: quantum_blue_verify_token)
- `WHATSAPP_WEBHOOK_URL` - Your webhook URL (https://your-app.azurewebsites.net/webhook/whatsapp)

### Groq LLM Service
- `GROQ_API_KEY` - Groq API key for LLM responses
- `GROQ_MODEL` - Model name (default: mixtral-8x7b-32768)

### Email Configuration
- `MAIL_SERVER` - SMTP server (default: smtp.gmail.com)
- `MAIL_PORT` - SMTP port (default: 587)
- `MAIL_USERNAME` - Email username
- `MAIL_PASSWORD` - Email password
- `MAIL_USE_TLS` - Use TLS (default: True)

### Web Search
- `TAVILY_API_KEY` - Tavily search API key

### Flask Configuration
- `SECRET_KEY` - Flask secret key
- `FLASK_ENV` - Set to 'production' for Azure

## How to Set Environment Variables in Azure App Service

1. Go to Azure Portal
2. Navigate to your App Service
3. Go to Configuration > Application settings
4. Add each environment variable as a new application setting
5. Save the configuration
6. Restart the App Service

## Database Migration

After setting environment variables, run the migration script:

```bash
python azure_migrate_database.py
```

This will add the required columns for WhatsApp functionality.
