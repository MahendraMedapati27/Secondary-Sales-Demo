#!/usr/bin/env python3
"""
Database migration script to add new columns for WhatsApp functionality
"""

import os
import sys
import pymssql
from sqlalchemy import create_engine, text

def get_database_connection():
    """Get database connection string from environment"""
    # Get database connection details from environment variables
    db_server = os.getenv('DB_SERVER', 'localhost')
    db_name = os.getenv('DB_NAME', 'quantum_blue')
    db_user = os.getenv('DB_USER', 'sa')
    db_password = os.getenv('DB_PASSWORD', '')
    
    # Create connection string
    connection_string = f"mssql+pymssql://{db_user}:{db_password}@{db_server}/{db_name}"
    return create_engine(connection_string)

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
            return result.scalar() > 0
    except Exception as e:
        print(f"Error checking column {column_name} in {table_name}: {e}")
        return False

def add_column(engine, table_name, column_name, column_definition):
    """Add a column to a table"""
    try:
        with engine.connect() as conn:
            conn.execute(text(f"ALTER TABLE {table_name} ADD {column_name} {column_definition}"))
            conn.commit()
            print(f"✅ Added column {column_name} to {table_name}")
            return True
    except Exception as e:
        print(f"❌ Error adding column {column_name} to {table_name}: {e}")
        return False

def migrate_database():
    """Run the database migration"""
    print("🚀 Starting database migration for WhatsApp functionality...")
    
    try:
        engine = get_database_connection()
        
        # Test connection
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        print("✅ Database connection successful")
        
        # Check and add onboarding_state column
        if not check_column_exists(engine, 'users', 'onboarding_state'):
            print("📝 Adding onboarding_state column...")
            add_column(engine, 'users', 'onboarding_state', 'VARCHAR(50) DEFAULT \'ask_name\'')
        else:
            print("✅ onboarding_state column already exists")
        
        # Check and add whatsapp_session_data column
        if not check_column_exists(engine, 'users', 'whatsapp_session_data'):
            print("📝 Adding whatsapp_session_data column...")
            add_column(engine, 'users', 'whatsapp_session_data', 'NVARCHAR(MAX)')
        else:
            print("✅ whatsapp_session_data column already exists")
        
        print("🎉 Database migration completed successfully!")
        return True
        
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        return False

if __name__ == "__main__":
    success = migrate_database()
    sys.exit(0 if success else 1)
