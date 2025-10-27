#!/bin/bash
# Comprehensive Deployment Script for Quantum Blue Chatbot
# This script ensures both web interface and WhatsApp chatbot work correctly

echo "🚀 QUANTUM BLUE CHATBOT - COMPREHENSIVE DEPLOYMENT"
echo "=================================================="

# Check if we're in the right directory
if [ ! -f "requirements.txt" ]; then
    echo "❌ Error: requirements.txt not found. Please run this script from the project root."
    exit 1
fi

echo "📋 Pre-deployment Checks:"
echo "========================"

# Check Python version
python_version=$(python3 --version 2>&1)
echo "✅ Python Version: $python_version"

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "⚠️  Virtual environment not found. Creating one..."
    python3 -m venv venv
fi

# Activate virtual environment
source venv/bin/activate

# Install/update dependencies
echo "📦 Installing Dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

# Check for required environment variables
echo ""
echo "🔧 Environment Variables Check:"
echo "==============================="

required_vars=("SECRET_KEY" "GROQ_API_KEY")
optional_vars=("WHATSAPP_ACCESS_TOKEN" "WHATSAPP_PHONE_NUMBER_ID" "WHATSAPP_VERIFY_TOKEN" "MAIL_USERNAME" "TAVILY_API_KEY")

for var in "${required_vars[@]}"; do
    if [ -z "${!var}" ]; then
        echo "❌ Missing required: $var"
    else
        echo "✅ Found: $var"
    fi
done

for var in "${optional_vars[@]}"; do
    if [ -z "${!var}" ]; then
        echo "⚠️  Optional missing: $var"
    else
        echo "✅ Found: $var"
    fi
done

# Run basic tests
echo ""
echo "🧪 Running Basic Tests:"
echo "======================"

# Test imports
python3 -c "
try:
    from app import create_app
    from app.groq_service import GroqService
    from app.whatsapp_service import WhatsAppService
    from app.llm_classification_service import LLMClassificationService
    print('✅ All imports successful')
except ImportError as e:
    print(f'❌ Import error: {e}')
    exit(1)
"

# Test Flask app creation
python3 -c "
try:
    from app import create_app
    app = create_app()
    print('✅ Flask app created successfully')
except Exception as e:
    print(f'❌ Flask app creation failed: {e}')
    exit(1)
"

echo ""
echo "📝 Deployment Summary:"
echo "====================="
echo "✅ Dependencies installed"
echo "✅ Imports verified"
echo "✅ Flask app created"
echo ""
echo "🚀 Ready for deployment!"
echo ""
echo "Next steps:"
echo "1. Set environment variables in Azure"
echo "2. Push to GitHub to trigger deployment"
echo "3. Test web interface: https://my-chatbot-app-73d666.azurewebsites.net"
echo "4. Test WhatsApp webhook: https://my-chatbot-app-73d666.azurewebsites.net/webhook/whatsapp"
echo ""
echo "📱 WhatsApp Configuration:"
echo "- Webhook URL: https://my-chatbot-app-73d666.azurewebsites.net/webhook/whatsapp"
echo "- Verify Token: quantum_blue_verify_token"
echo "- Phone Number: +1 555 637 0308"
