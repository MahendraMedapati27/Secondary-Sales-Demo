#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Startup script for RB (Powered by Quantum Blue AI) Chatbot
Initializes database and sample data, then starts the Flask server
This is used for Azure App Service deployment
"""

import os
import sys
from pathlib import Path

# Set UTF-8 encoding for Windows console compatibility
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

# Add the project root to Python path
project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(project_root))

if __name__ == '__main__':
    # Run initialization
    app = None
    try:
        print("=" * 60)
        print("🚀 RB (Powered by Quantum Blue AI) - Startup")
        print("=" * 60)
        
        # Import and create the Flask app
        from app import create_app
        app = create_app()
        
        with app.app_context():
            from app.database_service import DatabaseService
            from app.models import User, Product
            
            print("📊 Checking database status...")
            
            # Check if we have any users
            user_count = User.query.count()
            product_count = Product.query.count()
            
            print(f"   Users: {user_count}")
            print(f"   Products: {product_count}")
            
            if user_count == 0 or product_count == 0:
                print("\n🔧 Initializing sample data...")
                
                db_service = DatabaseService()
                
                # Create sample products
                print("   Creating sample products...")
                db_service.create_sample_products()
                
                # Create sample users
                print("   Creating sample users...")
                db_service.create_sample_users()
                
                print("✅ Sample data initialized successfully!")
            else:
                print("✅ Database already initialized!")
            
            # Display sample user IDs for testing
            try:
                print("\n👥 Sample User IDs for Testing:")
                print("-" * 40)
                
                sample_users = User.query.limit(5).all()
                if sample_users:
                    for user in sample_users:
                        role_display = user.role if user.role else 'N/A'
                        print(f"   {user.unique_id} - {user.name} ({role_display})")
                else:
                    print("   No users found")
            except Exception as e:
                print(f"   ⚠️ Could not display users: {e}")
            
            try:
                print("\n📦 Sample Products Available:")
                print("-" * 40)
                
                sample_products = Product.query.limit(5).all()
                if sample_products:
                    for product in sample_products:
                        price_display = f"${product.price:.2f}" if product.price else "$0.00"
                        print(f"   ID:{product.id} - {product.product_name} - {price_display}")
                else:
                    print("   No products found")
            except Exception as e:
                print(f"   ⚠️ Could not display products: {e}")
            
            print("\n" + "=" * 60)
            print("🎉 RB (Powered by Quantum Blue AI) is ready!")
            print("=" * 60)
            print("🌐 Access the chatbot at: http://localhost:5000")
            print("📱 Enhanced chatbot at: http://localhost:5000/enhanced-chat")
            print("=" * 60)
    except ImportError as e:
        print(f"❌ Import Error: {e}")
        print("💡 Make sure you're running from the correct directory and all dependencies are installed.")
        print("   Run: pip install -r requirements.txt")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Startup Error: {e}")
        print("💡 Check your configuration and try again.")
        sys.exit(1)
    
    # Now start the server using run.py logic
    if app:
        try:
            print("\n🚀 Starting Flask server...")
            # Get configuration from environment
            debug_mode = os.getenv('FLASK_DEBUG', 'False').lower() == 'true'
            host = os.getenv('FLASK_HOST', '0.0.0.0')
            port = int(os.getenv('FLASK_PORT', 8000))
            
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
        except Exception as e:
            print(f"❌ Server Error: {e}")
            print("💡 Check your configuration and try again.")
            sys.exit(1)