#!/usr/bin/env python3
"""
Flask Chatbot Application Entry Point
Quantum Blue AI Chatbot with WhatsApp Integration
"""

import os
import sys
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(project_root))

# Import and create the Flask app at module level for gunicorn
from app import create_app
app = create_app()

def main():
    """Main application entry point"""
    try:
        # App is already created at module level
        global app
        
        # Get configuration from environment
        debug_mode = os.getenv('FLASK_DEBUG', 'False').lower() == 'true'
        host = os.getenv('FLASK_HOST', '0.0.0.0')
        port = int(os.getenv('FLASK_PORT', 5000))
        
        print("=" * 60)
        print("🚀 QUANTUM BLUE AI CHATBOT STARTING UP")
        print("=" * 60)
        print(f"📡 Host: {host}")
        print(f"🔌 Port: {port}")
        print(f"🐛 Debug Mode: {'ON' if debug_mode else 'OFF'}")
        print(f"🌐 Environment: {os.getenv('FLASK_ENV', 'production')}")
        print("=" * 60)
        
        # Check for required environment variables
        required_vars = ['SECRET_KEY']
        missing_vars = [var for var in required_vars if not os.getenv(var)]
        
        if missing_vars:
            print("⚠️  WARNING: Missing required environment variables:")
            for var in missing_vars:
                print(f"   - {var}")
            print("\n💡 The app will use default values for development.")
            print("   For production, set these in your .env file or environment.")
            print()
        
        # Check for optional but important services
        optional_services = {
            'GROQ_API_KEY': 'Groq AI Service',
            'MAIL_USERNAME': 'Email Service (OTP)',
            'WHATSAPP_ACCESS_TOKEN': 'WhatsApp Integration',
            'TAVILY_API_KEY': 'Web Search Service'
        }
        
        print("🔧 Service Status:")
        for env_var, service_name in optional_services.items():
            status = "✅ Available" if os.getenv(env_var) else "❌ Not configured"
            print(f"   {service_name}: {status}")
        
        print("=" * 60)
        print("🌐 Starting Flask development server...")
        print(f"📱 Access the chatbot at: http://{host}:{port}")
        print("🛑 Press Ctrl+C to stop the server")
        print("=" * 60)
        
        # Run the Flask application
        # For Azure App Service, use waitress for production
        if os.getenv('FLASK_ENV') == 'production':
            from waitress import serve
            print("🚀 Starting production server with Waitress...")
            serve(app, host=host, port=port, threads=4)
        else:
            app.run(
                host=host,
                port=port,
                debug=debug_mode,
                threaded=True
            )
        
    except ImportError as e:
        print(f"❌ Import Error: {e}")
        print("💡 Make sure you're running from the correct directory and all dependencies are installed.")
        print("   Run: pip install -r requirements.txt")
        sys.exit(1)
        
    except Exception as e:
        print(f"❌ Application Error: {e}")
        print("💡 Check your configuration and try again.")
        sys.exit(1)

if __name__ == '__main__':
    main()