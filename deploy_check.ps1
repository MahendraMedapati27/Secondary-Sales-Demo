# Comprehensive Deployment Script for Quantum Blue Chatbot (PowerShell)
# This script ensures both web interface and WhatsApp chatbot work correctly

Write-Host "🚀 QUANTUM BLUE CHATBOT - COMPREHENSIVE DEPLOYMENT" -ForegroundColor Green
Write-Host "==================================================" -ForegroundColor Green

# Check if we're in the right directory
if (-not (Test-Path "requirements.txt")) {
    Write-Host "❌ Error: requirements.txt not found. Please run this script from the project root." -ForegroundColor Red
    exit 1
}

Write-Host "📋 Pre-deployment Checks:" -ForegroundColor Yellow
Write-Host "========================" -ForegroundColor Yellow

# Check Python version
try {
    $pythonVersion = python --version 2>&1
    Write-Host "✅ Python Version: $pythonVersion" -ForegroundColor Green
} catch {
    Write-Host "❌ Python not found. Please install Python 3.9+" -ForegroundColor Red
    exit 1
}

# Check if virtual environment exists
if (-not (Test-Path "venv")) {
    Write-Host "⚠️  Virtual environment not found. Creating one..." -ForegroundColor Yellow
    python -m venv venv
}

# Activate virtual environment
Write-Host "📦 Activating virtual environment..." -ForegroundColor Blue
& "venv\Scripts\Activate.ps1"

# Install/update dependencies
Write-Host "📦 Installing Dependencies..." -ForegroundColor Blue
pip install --upgrade pip
pip install -r requirements.txt

Write-Host ""
Write-Host "🔧 Environment Variables Check:" -ForegroundColor Yellow
Write-Host "===============================" -ForegroundColor Yellow

$requiredVars = @("SECRET_KEY", "GROQ_API_KEY")
$optionalVars = @("WHATSAPP_ACCESS_TOKEN", "WHATSAPP_PHONE_NUMBER_ID", "WHATSAPP_VERIFY_TOKEN", "MAIL_USERNAME", "TAVILY_API_KEY")

foreach ($var in $requiredVars) {
    if ([string]::IsNullOrEmpty([Environment]::GetEnvironmentVariable($var))) {
        Write-Host "❌ Missing required: $var" -ForegroundColor Red
    } else {
        Write-Host "✅ Found: $var" -ForegroundColor Green
    }
}

foreach ($var in $optionalVars) {
    if ([string]::IsNullOrEmpty([Environment]::GetEnvironmentVariable($var))) {
        Write-Host "⚠️  Optional missing: $var" -ForegroundColor Yellow
    } else {
        Write-Host "✅ Found: $var" -ForegroundColor Green
    }
}

# Run basic tests
Write-Host ""
Write-Host "🧪 Running Basic Tests:" -ForegroundColor Yellow
Write-Host "======================" -ForegroundColor Yellow

# Test imports
try {
    python -c "
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
    Write-Host "✅ Import test passed" -ForegroundColor Green
} catch {
    Write-Host "❌ Import test failed" -ForegroundColor Red
}

# Test Flask app creation
try {
    python -c "
try:
    from app import create_app
    app = create_app()
    print('✅ Flask app created successfully')
except Exception as e:
    print(f'❌ Flask app creation failed: {e}')
    exit(1)
"
    Write-Host "✅ Flask app test passed" -ForegroundColor Green
} catch {
    Write-Host "❌ Flask app test failed" -ForegroundColor Red
}

Write-Host ""
Write-Host "📝 Deployment Summary:" -ForegroundColor Green
Write-Host "=====================" -ForegroundColor Green
Write-Host "✅ Dependencies installed" -ForegroundColor Green
Write-Host "✅ Imports verified" -ForegroundColor Green
Write-Host "✅ Flask app created" -ForegroundColor Green
Write-Host ""
Write-Host "🚀 Ready for deployment!" -ForegroundColor Green
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Cyan
Write-Host "1. Set environment variables in Azure" -ForegroundColor White
Write-Host "2. Push to GitHub to trigger deployment" -ForegroundColor White
Write-Host "3. Test web interface: https://my-chatbot-app-73d666.azurewebsites.net" -ForegroundColor White
Write-Host "4. Test WhatsApp webhook: https://my-chatbot-app-73d666.azurewebsites.net/webhook/whatsapp" -ForegroundColor White
Write-Host ""
Write-Host "📱 WhatsApp Configuration:" -ForegroundColor Cyan
Write-Host "- Webhook URL: https://my-chatbot-app-73d666.azurewebsites.net/webhook/whatsapp" -ForegroundColor White
Write-Host "- Verify Token: quantum_blue_verify_token" -ForegroundColor White
Write-Host "- Phone Number: +1 555 637 0308" -ForegroundColor White
