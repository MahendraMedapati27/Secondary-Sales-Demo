#!/usr/bin/env python3
"""
Database migration script for RB (Powered by Quantum Blue AI)
Adds new columns to existing tables
"""

import os
import sys
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(project_root))

def main():
    """Main migration function"""
    try:
        print("=" * 60)
        print("🔄 RB (Powered by Quantum Blue AI) - Database Migration")
        print("=" * 60)
        
        # Import and create the Flask app
        from app import create_app
        app = create_app()
        
        with app.app_context():
            from app import db
            from sqlalchemy import text
            
            print("📊 Starting database migration...")
            
            # Get database engine
            engine = db.get_engine()
            
            with engine.connect() as conn:
                # Start transaction
                trans = conn.begin()
                
                try:
                    # Add new columns to users table
                    print("   Adding columns to users table...")
                    
                    # Add unique_id column
                    conn.execute(text("""
                        IF NOT EXISTS (SELECT 1 FROM sys.columns c
                           JOIN sys.objects o ON o.object_id = c.object_id
                           WHERE o.name = 'users' AND c.name = 'unique_id')
                        BEGIN
                            ALTER TABLE dbo.users ADD unique_id NVARCHAR(50) NULL;
                        END
                    """))
                    
                    # Update existing users with unique IDs
                    conn.execute(text("""
                        UPDATE dbo.users 
                        SET unique_id = 'CUST_' + FORMAT(GETDATE(), 'yyyyMMddHHmmss') + '_' + RIGHT('000000' + CAST(id AS VARCHAR), 6)
                        WHERE unique_id IS NULL;
                    """))
                    
                    # Create unique index after updating NULL values
                    conn.execute(text("""
                        IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_users_unique_id')
                        BEGIN
                            CREATE UNIQUE INDEX IX_users_unique_id ON dbo.users(unique_id);
                        END
                    """))
                    
                    # Add user_type column
                    conn.execute(text("""
                        IF NOT EXISTS (SELECT 1 FROM sys.columns c
                           JOIN sys.objects o ON o.object_id = c.object_id
                           WHERE o.name = 'users' AND c.name = 'user_type')
                        BEGIN
                            ALTER TABLE dbo.users ADD user_type NVARCHAR(20) NOT NULL DEFAULT 'customer';
                        END
                    """))
                    
                    # Add role column
                    conn.execute(text("""
                        IF NOT EXISTS (SELECT 1 FROM sys.columns c
                           JOIN sys.objects o ON o.object_id = c.object_id
                           WHERE o.name = 'users' AND c.name = 'role')
                        BEGIN
                            ALTER TABLE dbo.users ADD role NVARCHAR(50) NULL;
                        END
                    """))
                    
                    # Add delivery_pin_code column
                    conn.execute(text("""
                        IF NOT EXISTS (SELECT 1 FROM sys.columns c
                           JOIN sys.objects o ON o.object_id = c.object_id
                           WHERE o.name = 'users' AND c.name = 'delivery_pin_code')
                        BEGIN
                            ALTER TABLE dbo.users ADD delivery_pin_code NVARCHAR(10) NULL;
                        END
                    """))
                    
                    # Add delivery_zone column
                    conn.execute(text("""
                        IF NOT EXISTS (SELECT 1 FROM sys.columns c
                           JOIN sys.objects o ON o.object_id = c.object_id
                           WHERE o.name = 'users' AND c.name = 'delivery_zone')
                        BEGIN
                            ALTER TABLE dbo.users ADD delivery_zone NVARCHAR(100) NULL;
                        END
                    """))
                    
                    # Add nearest_warehouse column
                    conn.execute(text("""
                        IF NOT EXISTS (SELECT 1 FROM sys.columns c
                           JOIN sys.objects o ON o.object_id = c.object_id
                           WHERE o.name = 'users' AND c.name = 'nearest_warehouse')
                        BEGIN
                            ALTER TABLE dbo.users ADD nearest_warehouse NVARCHAR(100) NULL;
                        END
                    """))
                    
                    # Add nearest_distributor column
                    conn.execute(text("""
                        IF NOT EXISTS (SELECT 1 FROM sys.columns c
                           JOIN sys.objects o ON o.object_id = c.object_id
                           WHERE o.name = 'users' AND c.name = 'nearest_distributor')
                        BEGIN
                            ALTER TABLE dbo.users ADD nearest_distributor NVARCHAR(100) NULL;
                        END
                    """))
                    
                    # Add company_name column
                    conn.execute(text("""
                        IF NOT EXISTS (SELECT 1 FROM sys.columns c
                           JOIN sys.objects o ON o.object_id = c.object_id
                           WHERE o.name = 'users' AND c.name = 'company_name')
                        BEGIN
                            ALTER TABLE dbo.users ADD company_name NVARCHAR(200) NULL;
                        END
                    """))
                    
                    # Add company_address column
                    conn.execute(text("""
                        IF NOT EXISTS (SELECT 1 FROM sys.columns c
                           JOIN sys.objects o ON o.object_id = c.object_id
                           WHERE o.name = 'users' AND c.name = 'company_address')
                        BEGIN
                            ALTER TABLE dbo.users ADD company_address NVARCHAR(MAX) NULL;
                        END
                    """))
                    
                    # Add is_active column
                    conn.execute(text("""
                        IF NOT EXISTS (SELECT 1 FROM sys.columns c
                           JOIN sys.objects o ON o.object_id = c.object_id
                           WHERE o.name = 'users' AND c.name = 'is_active')
                        BEGIN
                            ALTER TABLE dbo.users ADD is_active BIT NOT NULL DEFAULT 1;
                        END
                    """))
                    
                    # Add is_verified column
                    conn.execute(text("""
                        IF NOT EXISTS (SELECT 1 FROM sys.columns c
                           JOIN sys.objects o ON o.object_id = c.object_id
                           WHERE o.name = 'users' AND c.name = 'is_verified')
                        BEGIN
                            ALTER TABLE dbo.users ADD is_verified BIT NOT NULL DEFAULT 0;
                        END
                    """))
                    
                    print("   Adding columns to products table...")
                    
                    # Add confirmed_quantity column
                    conn.execute(text("""
                        IF NOT EXISTS (SELECT 1 FROM sys.columns c
                           JOIN sys.objects o ON o.object_id = c.object_id
                           WHERE o.name = 'products' AND c.name = 'confirmed_quantity')
                        BEGIN
                            ALTER TABLE dbo.products ADD confirmed_quantity INT NOT NULL DEFAULT 0;
                        END
                    """))
                    
                    # Add discount_type column
                    conn.execute(text("""
                        IF NOT EXISTS (SELECT 1 FROM sys.columns c
                           JOIN sys.objects o ON o.object_id = c.object_id
                           WHERE o.name = 'products' AND c.name = 'discount_type')
                        BEGIN
                            ALTER TABLE dbo.products ADD discount_type NVARCHAR(50) NULL;
                        END
                    """))
                    
                    # Add discount_value column
                    conn.execute(text("""
                        IF NOT EXISTS (SELECT 1 FROM sys.columns c
                           JOIN sys.objects o ON o.object_id = c.object_id
                           WHERE o.name = 'products' AND c.name = 'discount_value')
                        BEGIN
                            ALTER TABLE dbo.products ADD discount_value FLOAT NOT NULL DEFAULT 0;
                        END
                    """))
                    
                    # Add discount_name column
                    conn.execute(text("""
                        IF NOT EXISTS (SELECT 1 FROM sys.columns c
                           JOIN sys.objects o ON o.object_id = c.object_id
                           WHERE o.name = 'products' AND c.name = 'discount_name')
                        BEGIN
                            ALTER TABLE dbo.products ADD discount_name NVARCHAR(100) NULL;
                        END
                    """))
                    
                    # Add scheme_type column
                    conn.execute(text("""
                        IF NOT EXISTS (SELECT 1 FROM sys.columns c
                           JOIN sys.objects o ON o.object_id = c.object_id
                           WHERE o.name = 'products' AND c.name = 'scheme_type')
                        BEGIN
                            ALTER TABLE dbo.products ADD scheme_type NVARCHAR(50) NULL;
                        END
                    """))
                    
                    # Add scheme_value column
                    conn.execute(text("""
                        IF NOT EXISTS (SELECT 1 FROM sys.columns c
                           JOIN sys.objects o ON o.object_id = c.object_id
                           WHERE o.name = 'products' AND c.name = 'scheme_value')
                        BEGIN
                            ALTER TABLE dbo.products ADD scheme_value NVARCHAR(200) NULL;
                        END
                    """))
                    
                    # Add scheme_name column
                    conn.execute(text("""
                        IF NOT EXISTS (SELECT 1 FROM sys.columns c
                           JOIN sys.objects o ON o.object_id = c.object_id
                           WHERE o.name = 'products' AND c.name = 'scheme_name')
                        BEGIN
                            ALTER TABLE dbo.products ADD scheme_name NVARCHAR(100) NULL;
                        END
                    """))
                    
                    # Add is_active column
                    conn.execute(text("""
                        IF NOT EXISTS (SELECT 1 FROM sys.columns c
                           JOIN sys.objects o ON o.object_id = c.object_id
                           WHERE o.name = 'products' AND c.name = 'is_active')
                        BEGIN
                            ALTER TABLE dbo.products ADD is_active BIT NOT NULL DEFAULT 1;
                        END
                    """))
                    
                    print("   Adding columns to orders table...")
                    
                    # Add subtotal_amount column
                    conn.execute(text("""
                        IF NOT EXISTS (SELECT 1 FROM sys.columns c
                           JOIN sys.objects o ON o.object_id = c.object_id
                           WHERE o.name = 'orders' AND c.name = 'subtotal_amount')
                        BEGIN
                            ALTER TABLE dbo.orders ADD subtotal_amount FLOAT NOT NULL DEFAULT 0;
                        END
                    """))
                    
                    # Add discount_amount column
                    conn.execute(text("""
                        IF NOT EXISTS (SELECT 1 FROM sys.columns c
                           JOIN sys.objects o ON o.object_id = c.object_id
                           WHERE o.name = 'orders' AND c.name = 'discount_amount')
                        BEGIN
                            ALTER TABLE dbo.orders ADD discount_amount FLOAT NOT NULL DEFAULT 0;
                        END
                    """))
                    
                    # Add scheme_discount_amount column
                    conn.execute(text("""
                        IF NOT EXISTS (SELECT 1 FROM sys.columns c
                           JOIN sys.objects o ON o.object_id = c.object_id
                           WHERE o.name = 'orders' AND c.name = 'scheme_discount_amount')
                        BEGIN
                            ALTER TABLE dbo.orders ADD scheme_discount_amount FLOAT NOT NULL DEFAULT 0;
                        END
                    """))
                    
                    # Add order_stage column
                    conn.execute(text("""
                        IF NOT EXISTS (SELECT 1 FROM sys.columns c
                           JOIN sys.objects o ON o.object_id = c.object_id
                           WHERE o.name = 'orders' AND c.name = 'order_stage')
                        BEGIN
                            ALTER TABLE dbo.orders ADD order_stage NVARCHAR(50) NOT NULL DEFAULT 'draft';
                        END
                    """))
                    
                    # Add placed_by column
                    conn.execute(text("""
                        IF NOT EXISTS (SELECT 1 FROM sys.columns c
                           JOIN sys.objects o ON o.object_id = c.object_id
                           WHERE o.name = 'orders' AND c.name = 'placed_by')
                        BEGIN
                            ALTER TABLE dbo.orders ADD placed_by NVARCHAR(20) NOT NULL DEFAULT 'customer';
                        END
                    """))
                    
                    # Add placed_by_user_id column
                    conn.execute(text("""
                        IF NOT EXISTS (SELECT 1 FROM sys.columns c
                           JOIN sys.objects o ON o.object_id = c.object_id
                           WHERE o.name = 'orders' AND c.name = 'placed_by_user_id')
                        BEGIN
                            ALTER TABLE dbo.orders ADD placed_by_user_id INT NULL;
                        END
                    """))
                    
                    # Add distributor confirmation columns
                    conn.execute(text("""
                        IF NOT EXISTS (SELECT 1 FROM sys.columns c
                           JOIN sys.objects o ON o.object_id = c.object_id
                           WHERE o.name = 'orders' AND c.name = 'distributor_confirmed')
                        BEGIN
                            ALTER TABLE dbo.orders ADD distributor_confirmed BIT NOT NULL DEFAULT 0;
                        END
                    """))
                    
                    conn.execute(text("""
                        IF NOT EXISTS (SELECT 1 FROM sys.columns c
                           JOIN sys.objects o ON o.object_id = c.object_id
                           WHERE o.name = 'orders' AND c.name = 'distributor_confirmed_at')
                        BEGIN
                            ALTER TABLE dbo.orders ADD distributor_confirmed_at DATETIME2 NULL;
                        END
                    """))
                    
                    conn.execute(text("""
                        IF NOT EXISTS (SELECT 1 FROM sys.columns c
                           JOIN sys.objects o ON o.object_id = c.object_id
                           WHERE o.name = 'orders' AND c.name = 'distributor_confirmed_by')
                        BEGIN
                            ALTER TABLE dbo.orders ADD distributor_confirmed_by INT NULL;
                        END
                    """))
                    
                    # Add invoice columns
                    conn.execute(text("""
                        IF NOT EXISTS (SELECT 1 FROM sys.columns c
                           JOIN sys.objects o ON o.object_id = c.object_id
                           WHERE o.name = 'orders' AND c.name = 'invoice_generated')
                        BEGIN
                            ALTER TABLE dbo.orders ADD invoice_generated BIT NOT NULL DEFAULT 0;
                        END
                    """))
                    
                    conn.execute(text("""
                        IF NOT EXISTS (SELECT 1 FROM sys.columns c
                           JOIN sys.objects o ON o.object_id = c.object_id
                           WHERE o.name = 'orders' AND c.name = 'invoice_generated_at')
                        BEGIN
                            ALTER TABLE dbo.orders ADD invoice_generated_at DATETIME2 NULL;
                        END
                    """))
                    
                    conn.execute(text("""
                        IF NOT EXISTS (SELECT 1 FROM sys.columns c
                           JOIN sys.objects o ON o.object_id = c.object_id
                           WHERE o.name = 'orders' AND c.name = 'invoice_number')
                        BEGIN
                            ALTER TABLE dbo.orders ADD invoice_number NVARCHAR(50) NULL;
                        END
                    """))
                    
                    # Create cart_items table
                    print("   Creating cart_items table...")
                    conn.execute(text("""
                        IF NOT EXISTS (SELECT 1 FROM sys.objects WHERE name = 'cart_items')
                        BEGIN
                            CREATE TABLE dbo.cart_items (
                                id INT IDENTITY(1,1) PRIMARY KEY,
                                product_code NVARCHAR(50) NOT NULL,
                                product_quantity INT NOT NULL,
                                unit_price FLOAT NOT NULL DEFAULT 0,
                                total_price FLOAT NOT NULL DEFAULT 0,
                                base_price FLOAT NOT NULL DEFAULT 0,
                                discount_amount FLOAT NOT NULL DEFAULT 0,
                                scheme_discount_amount FLOAT NOT NULL DEFAULT 0,
                                final_price FLOAT NOT NULL DEFAULT 0,
                                scheme_applied NVARCHAR(100) NULL,
                                free_quantity INT NOT NULL DEFAULT 0,
                                paid_quantity INT NOT NULL DEFAULT 0,
                                user_id INT NOT NULL,
                                product_id INT NOT NULL,
                                created_at DATETIME2 NOT NULL DEFAULT GETDATE(),
                                updated_at DATETIME2 NOT NULL DEFAULT GETDATE(),
                                FOREIGN KEY (user_id) REFERENCES dbo.users(id),
                                FOREIGN KEY (product_id) REFERENCES dbo.products(id)
                            );
                        END
                    """))
                    
                    # Add foreign key constraints for orders table
                    print("   Adding foreign key constraints...")
                    conn.execute(text("""
                        IF NOT EXISTS (SELECT 1 FROM sys.foreign_keys WHERE name = 'FK_orders_placed_by_user')
                        BEGIN
                            ALTER TABLE dbo.orders ADD CONSTRAINT FK_orders_placed_by_user 
                            FOREIGN KEY (placed_by_user_id) REFERENCES dbo.users(id);
                        END
                    """))
                    
                    conn.execute(text("""
                        IF NOT EXISTS (SELECT 1 FROM sys.foreign_keys WHERE name = 'FK_orders_distributor_confirmed_by')
                        BEGIN
                            ALTER TABLE dbo.orders ADD CONSTRAINT FK_orders_distributor_confirmed_by 
                            FOREIGN KEY (distributor_confirmed_by) REFERENCES dbo.users(id);
                        END
                    """))
                    
                    # Commit transaction
                    trans.commit()
                    print("✅ Database migration completed successfully!")
                    
                except Exception as e:
                    # Rollback transaction on error
                    trans.rollback()
                    print(f"❌ Migration failed: {str(e)}")
                    raise
                    
    except ImportError as e:
        print(f"❌ Import Error: {e}")
        print("💡 Make sure you're running from the correct directory and all dependencies are installed.")
        sys.exit(1)
        
    except Exception as e:
        print(f"❌ Migration Error: {e}")
        print("💡 Check your database connection and try again.")
        sys.exit(1)

if __name__ == '__main__':
    main()
