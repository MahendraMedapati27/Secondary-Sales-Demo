#!/usr/bin/env python3
"""
Azure Database Migration Script for WhatsApp functionality
Run this script on Azure to add the required columns
"""

import os
import sys
import pymssql
from sqlalchemy import create_engine, text

def get_azure_database_connection():
    """Get Azure database connection"""
    # Azure SQL Database connection string
    connection_string = os.getenv('SQLALCHEMY_DATABASE_URI')
    if not connection_string:
        print("❌ SQLALCHEMY_DATABASE_URI environment variable not found")
        return None
    
    try:
        engine = create_engine(connection_string)
        # Test connection
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        print("✅ Database connection successful")
        return engine
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        return None

def check_column_exists(engine, table_name, column_name):
    """Check if a column exists in a table"""
    try:
        with engine.connect() as conn:
            result = conn.execute(text(f"""
                SELECT COUNT(*) 
                FROM INFORMATION_SCHEMA.COLUMNS 
                WHERE TABLE_NAME = '{table_name}' 
                AND COLUMN_NAME = '{column_name}'
            """))
            exists = result.scalar() > 0
            print(f"Column {column_name} in {table_name}: {'✅ Exists' if exists else '❌ Missing'}")
            return exists
    except Exception as e:
        print(f"❌ Error checking column {column_name} in {table_name}: {e}")
        return False

def add_column_safely(engine, table_name, column_name, column_definition):
    """Add a column to a table safely"""
    try:
        with engine.connect() as conn:
            # Check if column already exists
            if check_column_exists(engine, table_name, column_name):
                print(f"✅ Column {column_name} already exists in {table_name}")
                return True
            
            # Add the column
            conn.execute(text(f"ALTER TABLE {table_name} ADD {column_name} {column_definition}"))
            conn.commit()
            print(f"✅ Successfully added column {column_name} to {table_name}")
            return True
    except Exception as e:
        print(f"❌ Error adding column {column_name} to {table_name}: {e}")
        return False

def migrate_azure_database():
    """Run the Azure database migration"""
    print("🚀 Starting Azure database migration for WhatsApp functionality...")
    
    engine = get_azure_database_connection()
    if not engine:
        return False
    
    success = True
    
    # Add onboarding_state column
    print("\n📝 Checking onboarding_state column...")
    if not add_column_safely(engine, 'users', 'onboarding_state', 'VARCHAR(50) DEFAULT \'ask_name\''):
        success = False
    
    # Add whatsapp_session_data column
    print("\n📝 Checking whatsapp_session_data column...")
    if not add_column_safely(engine, 'users', 'whatsapp_session_data', 'NVARCHAR(MAX)'):
        success = False
    
    if success:
        print("\n🎉 Database migration completed successfully!")
        print("✅ WhatsApp functionality is now ready to use!")
    else:
        print("\n❌ Some migrations failed. Please check the errors above.")
    
    return success

if __name__ == "__main__":
    success = migrate_azure_database()
    sys.exit(0 if success else 1)
