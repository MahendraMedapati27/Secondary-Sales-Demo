#!/usr/bin/env python3
"""
Startup script for RB (Powered by Quantum Blue AI) Chatbot
Initializes database and sample data, then starts the Flask server
This is used for Azure App Service deployment
"""

import os
import sys
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(project_root))

def main():
    """Main startup function"""
    try:
        print("=" * 60)
        print("🚀 RB (Powered by Quantum Blue AI) - Startup")
        print("=" * 60)
        
        # Import and create the Flask app
        from app import create_app
        app = create_app()
        
        with app.app_context():
            from app.database_service import DatabaseService
            from app.models import User, Product, Warehouse
            
            print("📊 Checking database status...")
            
            # Check if we have any users
            user_count = User.query.count()
            product_count = Product.query.count()
            warehouse_count = Warehouse.query.count()
            
            print(f"   Users: {user_count}")
            print(f"   Products: {product_count}")
            print(f"   Warehouses: {warehouse_count}")
            
            if user_count == 0 or product_count == 0:
                print("\n🔧 Initializing sample data...")
                
                db_service = DatabaseService()
                
                # Initialize warehouses
                print("   Creating warehouses...")
                db_service.initialize_warehouses()
                
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
            print("\n👥 Sample User IDs for Testing:")
            print("-" * 40)
            
            sample_users = User.query.limit(5).all()
            for user in sample_users:
                print(f"   {user.unique_id} - {user.name} ({user.user_type})")
            
            print("\n📦 Sample Products Available:")
            print("-" * 40)
            
            sample_products = Product.query.limit(5).all()
            for product in sample_products:
                print(f"   {product.product_code} - {product.product_name} - ${product.price_of_product}")
            
            print("\n🏢 Warehouses Available:")
            print("-" * 40)
            
            warehouses = Warehouse.query.all()
            for warehouse in warehouses:
                print(f"   {warehouse.location_name} - {warehouse.city}, {warehouse.state}")
            
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

if __name__ == '__main__':
    main()