#!/usr/bin/env python3
"""
WSGI entry point for Azure App Service
This file is required for Azure to detect and run the Flask application
"""

import os
import sys
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(project_root))

# Import the Flask app
from app import create_app

# Create the application instance
app = create_app()

# Initialize database on startup (only once)
with app.app_context():
    try:
        print("🔧 Initializing database...")
        from app.database_service import DatabaseService
        from app.models import User, Product
        
        # Check if initialization is needed
        try:
            user_count = User.query.count()
            product_count = Product.query.count()
            
            if user_count == 0 or product_count == 0:
                print("   Creating sample data...")
                db_service = DatabaseService()
                db_service.create_sample_products()
                db_service.create_sample_users()
                print("✅ Database initialized successfully!")
            else:
                print("✅ Database already initialized!")
        except Exception as init_error:
            print(f"⚠️ Database initialization skipped: {init_error}")
    except Exception as e:
        print(f"⚠️ Warning during initialization: {e}")

# This is what Azure/Gunicorn/Waitress will use
application = app

if __name__ == '__main__':
    # For local development
    app.run(
        host='0.0.0.0',
        port=int(os.getenv('PORT', 8000)),
        debug=False
    )

