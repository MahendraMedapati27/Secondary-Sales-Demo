#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Migration script to add delivery partner columns and create delivery partner users
This script:
1. Adds required columns to dealer_wise_stock_details and orders tables
2. Creates delivery partner users (2-3 per area) based on existing areas in the system
"""

import sys
import os
from pathlib import Path

# Force UTF-8 encoding and unbuffered output
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
os.environ['PYTHONUNBUFFERED'] = '1'

# Add project root to path
project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(project_root))

# Import after path is set
from app import create_app, db
from app.models import User
from sqlalchemy import text
from datetime import datetime

# Setup logging to file as well
log_file = project_root / 'delivery_partner_migration.log'

def log(message):
    """Log to both console and file"""
    print(message, flush=True)
    try:
        with open(log_file, 'a', encoding='utf-8') as f:
            f.write(message + '\n')
    except:
        pass

def add_database_columns():
    """Add required columns for delivery partner feature"""
    log("\n" + "="*60)
    log("📊 STEP 1: Adding Database Columns")
    log("="*60)
    
    try:
        engine = db.get_engine()
        with engine.connect() as conn:
            # Check if using MSSQL
            is_mssql = str(engine.url).startswith('mssql')
            
            if is_mssql:
                log("   Detected MSSQL database...")
                
                # Add out_for_delivery_quantity to dealer_wise_stock_details
                log("   → Adding 'out_for_delivery_quantity' column to dealer_wise_stock_details...")
                conn.execute(text("""
IF EXISTS (SELECT 1 FROM sys.objects WHERE object_id = OBJECT_ID(N'dbo.dealer_wise_stock_details') AND type in (N'U'))
AND NOT EXISTS (SELECT 1 FROM sys.columns WHERE object_id = OBJECT_ID(N'dbo.dealer_wise_stock_details') AND name = 'out_for_delivery_quantity')
BEGIN
    ALTER TABLE dbo.dealer_wise_stock_details ADD out_for_delivery_quantity INTEGER NOT NULL DEFAULT 0;
    PRINT 'Added out_for_delivery_quantity column to dealer_wise_stock_details';
END
ELSE IF NOT EXISTS (SELECT 1 FROM sys.objects WHERE object_id = OBJECT_ID(N'dbo.dealer_wise_stock_details') AND type in (N'U'))
BEGIN
    PRINT 'Table dealer_wise_stock_details does not exist. Skipping...';
END
ELSE
BEGIN
    PRINT 'Column out_for_delivery_quantity already exists in dealer_wise_stock_details';
END
"""))
                conn.commit()
                log("   ✅ Column added successfully!")
                
                # Add delivery partner columns to orders table
                log("   → Adding delivery partner columns to orders table...")
                
                # delivery_partner_id
                conn.execute(text("""
IF EXISTS (SELECT 1 FROM sys.objects WHERE object_id = OBJECT_ID(N'dbo.orders') AND type in (N'U'))
AND NOT EXISTS (SELECT 1 FROM sys.columns WHERE object_id = OBJECT_ID(N'dbo.orders') AND name = 'delivery_partner_id')
BEGIN
    ALTER TABLE dbo.orders ADD delivery_partner_id INTEGER NULL;
    PRINT 'Added delivery_partner_id column to orders';
END
"""))
                
                # delivery_partner_unique_id
                conn.execute(text("""
IF EXISTS (SELECT 1 FROM sys.objects WHERE object_id = OBJECT_ID(N'dbo.orders') AND type in (N'U'))
AND NOT EXISTS (SELECT 1 FROM sys.columns WHERE object_id = OBJECT_ID(N'dbo.orders') AND name = 'delivery_partner_unique_id')
BEGIN
    ALTER TABLE dbo.orders ADD delivery_partner_unique_id VARCHAR(50) NULL;
    PRINT 'Added delivery_partner_unique_id column to orders';
END
"""))
                
                # delivered_at
                conn.execute(text("""
IF EXISTS (SELECT 1 FROM sys.objects WHERE object_id = OBJECT_ID(N'dbo.orders') AND type in (N'U'))
AND NOT EXISTS (SELECT 1 FROM sys.columns WHERE object_id = OBJECT_ID(N'dbo.orders') AND name = 'delivered_at')
BEGIN
    ALTER TABLE dbo.orders ADD delivered_at DATETIME NULL;
    PRINT 'Added delivered_at column to orders';
END
"""))
                
                # delivered_by
                conn.execute(text("""
IF EXISTS (SELECT 1 FROM sys.objects WHERE object_id = OBJECT_ID(N'dbo.orders') AND type in (N'U'))
AND NOT EXISTS (SELECT 1 FROM sys.columns WHERE object_id = OBJECT_ID(N'dbo.orders') AND name = 'delivered_by')
BEGIN
    ALTER TABLE dbo.orders ADD delivered_by INTEGER NULL;
    PRINT 'Added delivered_by column to orders';
END
"""))
                
                # Add indexes for better performance
                log("   → Adding indexes...")
                
                # Index for delivery_partner_id
                conn.execute(text("""
IF EXISTS (SELECT 1 FROM sys.objects WHERE object_id = OBJECT_ID(N'dbo.orders') AND type in (N'U'))
AND NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID(N'dbo.orders') AND name = 'idx_orders_delivery_partner_id')
BEGIN
    CREATE INDEX idx_orders_delivery_partner_id ON dbo.orders(delivery_partner_id);
    PRINT 'Created index idx_orders_delivery_partner_id';
END
"""))
                
                # Index for delivery_partner_unique_id
                conn.execute(text("""
IF EXISTS (SELECT 1 FROM sys.objects WHERE object_id = OBJECT_ID(N'dbo.orders') AND type in (N'U'))
AND NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID(N'dbo.orders') AND name = 'idx_orders_delivery_partner_unique_id')
BEGIN
    CREATE INDEX idx_orders_delivery_partner_unique_id ON dbo.orders(delivery_partner_unique_id);
    PRINT 'Created index idx_orders_delivery_partner_unique_id';
END
"""))
                
                conn.commit()
                log("   ✅ All columns and indexes added successfully!")
                
            else:
                # SQLite or other database
                log("   Detected non-MSSQL database (SQLite/PostgreSQL)...")
                
                # Add out_for_delivery_quantity
                try:
                    conn.execute(text("""
ALTER TABLE dealer_wise_stock_details 
ADD COLUMN out_for_delivery_quantity INTEGER NOT NULL DEFAULT 0;
"""))
                except Exception:
                    log("   ⚠️  Column out_for_delivery_quantity may already exist or table doesn't exist")
                
                # Add delivery partner columns to orders
                for col_def in [
                    ("delivery_partner_id", "INTEGER"),
                    ("delivery_partner_unique_id", "VARCHAR(50)"),
                    ("delivered_at", "DATETIME"),
                    ("delivered_by", "INTEGER")
                ]:
                    try:
                        conn.execute(text(f"""
ALTER TABLE orders ADD COLUMN {col_def[0]} {col_def[1]};
"""))
                        log(f"   ✅ Added {col_def[0]} column")
                    except Exception:
                        log(f"   ⚠️  Column {col_def[0]} may already exist")
                
                conn.commit()
        
        log("   ✅ Database columns migration completed!")
        return True
        
    except Exception as e:
        log(f"   ❌ Error adding columns: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def get_existing_areas():
    """Get all unique areas from existing users (distributors and MRs)"""
    try:
        # Get areas from both distributors and MRs
        distributors = User.query.filter_by(role='distributor', is_active=True).all()
        mrs = User.query.filter_by(role='mr', is_active=True).all()
        
        areas = set()
        for user in distributors + mrs:
            if user.area:
                areas.add(user.area)
        
        return sorted(list(areas))
    except Exception as e:
        log(f"   ⚠️  Error getting areas: {str(e)}")
        return []

def create_delivery_partners():
    """Create delivery partner users (2-3 per area)"""
    log("\n" + "="*60)
    log("👥 STEP 2: Creating Delivery Partner Users")
    log("="*60)
    
    try:
        # Get existing areas
        areas = get_existing_areas()
        
        if not areas:
            log("   ⚠️  No areas found in the database!")
            log("   💡 Make sure you have distributors or MRs with areas assigned.")
            return False
        
        log(f"   📍 Found {len(areas)} unique area(s): {', '.join(areas)}")
        
        created_count = 0
        skipped_count = 0
        
        for area in areas:
            log(f"\n   📍 Processing Area: {area}")
            
            # Check how many delivery partners already exist for this area
            existing_dps = User.query.filter_by(role='delivery_partner', area=area, is_active=True).count()
            
            if existing_dps >= 3:
                log(f"      ✅ Already has {existing_dps} delivery partners. Skipping...")
                skipped_count += existing_dps
                continue
            
            # Create 2-3 delivery partners for this area
            partners_to_create = max(2, 3 - existing_dps)  # Create at least 2, up to 3 total
            
            for i in range(partners_to_create):
                partner_num = existing_dps + i + 1
                
                # Create delivery partner user
                delivery_partner = User(
                    name=f'Delivery Partner {partner_num} - {area}',
                    email=f'dp{partner_num}_{area.lower().replace(" ", "_")}@example.com',
                    phone=f'555{1000 + (created_count * 10) + partner_num}',
                    role='delivery_partner',
                    area=area,
                    is_active=True
                )
                
                # Generate unique ID (will create DP_ prefix)
                delivery_partner.generate_unique_id()
                
                # Check if unique_id already exists
                existing = User.query.filter_by(unique_id=delivery_partner.unique_id).first()
                if existing:
                    log(f"      ⚠️  Unique ID {delivery_partner.unique_id} already exists. Regenerating...")
                    # Force regeneration by clearing unique_id
                    delivery_partner.unique_id = None
                    delivery_partner.generate_unique_id()
                
                db.session.add(delivery_partner)
                log(f"      ✅ Created: {delivery_partner.name} ({delivery_partner.unique_id})")
                created_count += 1
        
        # Commit all delivery partners
        db.session.commit()
        
        log(f"\n   ✅ Successfully created {created_count} delivery partner(s)!")
        if skipped_count > 0:
            log(f"   ℹ️  Skipped {skipped_count} existing delivery partner(s)")
        
        return True
        
    except Exception as e:
        log(f"   ❌ Error creating delivery partners: {str(e)}")
        db.session.rollback()
        import traceback
        traceback.print_exc()
        return False

def display_summary():
    """Display summary of delivery partners"""
    log("\n" + "="*60)
    log("📋 SUMMARY: Delivery Partners by Area")
    log("="*60)
    
    try:
        areas = get_existing_areas()
        
        for area in areas:
            dps = User.query.filter_by(role='delivery_partner', area=area, is_active=True).all()
            log(f"\n   📍 {area}:")
            if dps:
                for dp in dps:
                    log(f"      • {dp.unique_id} - {dp.name} ({dp.email})")
            else:
                log(f"      ⚠️  No delivery partners found")
        
        total_dps = User.query.filter_by(role='delivery_partner', is_active=True).count()
        log(f"\n   📊 Total Delivery Partners: {total_dps}")
        
    except Exception as e:
        log(f"   ⚠️  Error displaying summary: {str(e)}")

def main():
    """Main migration function"""
    log("="*60)
    log("🚀 DELIVERY PARTNER MIGRATION SCRIPT")
    log("="*60)
    log("This script will:")
    log("  1. Add required database columns")
    log("  2. Create delivery partner users (2-3 per area)")
    log("="*60)
    
    # Create Flask app context
    app = create_app()
    
    with app.app_context():
        # Step 1: Add database columns
        if not add_database_columns():
            log("\n❌ Migration failed at Step 1. Please check errors above.")
            return False
        
        # Step 2: Create delivery partners
        if not create_delivery_partners():
            log("\n❌ Migration failed at Step 2. Please check errors above.")
            return False
        
        # Step 3: Display summary
        display_summary()
        
        log("\n" + "="*60)
        log("✅ MIGRATION COMPLETED SUCCESSFULLY!")
        log("="*60)
        log("\n💡 Next Steps:")
        log("  1. Update delivery partner email addresses in the database")
        log("  2. Set appropriate phone numbers for delivery partners")
        log("  3. Test the delivery partner login flow")
        log("  4. Test order assignment to delivery partners")
        log("="*60)
        
        return True

if __name__ == '__main__':
    try:
        success = main()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        log("\n\n⚠️  Migration cancelled by user")
        sys.exit(1)
    except Exception as e:
        log(f"\n\n❌ Fatal error: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

