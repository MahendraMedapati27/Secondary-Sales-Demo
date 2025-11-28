#!/usr/bin/env python3
"""
Script to:
1. Drop data from tables (except users, products, foc, customers)
2. Extract first 200 rows from CSV
3. Populate dealer_wise_stock_details with new column support
"""
import sys
import os
from pathlib import Path

project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(project_root))

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')
    os.environ['PYTHONUNBUFFERED'] = '1'

import pandas as pd
from datetime import datetime
from app import create_app, db
from app.models import (
    User, Product, FOC, Customer,
    Order, OrderItem, DealerWiseStockDetails, 
    PendingOrderProducts, CartItem, EmailLog, Conversation
)
from sqlalchemy import text

def log(message):
    """Print with flush"""
    print(message, flush=True)
    sys.stdout.flush()

def print_header(title):
    log("\n" + "="*80)
    log(f"  {title}")
    log("="*80)

def drop_table_data():
    """Drop data from tables except users, products, foc, customers"""
    print_header("DROPPING TABLE DATA")
    
    # CRITICAL: Delete in order that respects foreign key constraints
    # Foreign key dependency chain: pending_orders → order_items → orders
    # Must delete in reverse order: pending_orders first, then order_items, then orders
    try:
        cleared_count = 0
        total_tables = 7
        
        # Step 1: Delete pending_orders first (references order_items)
        try:
            count = db.session.execute(text("SELECT COUNT(*) FROM pending_orders")).scalar()
            if count > 0:
                db.session.execute(text("DELETE FROM pending_orders"))
                db.session.commit()
                log(f"✅ Cleared {count} records from pending_orders")
            else:
                log(f"✅ pending_orders is already empty")
            cleared_count += 1
        except Exception as e:
            log(f"⚠️  Error clearing pending_orders: {str(e)[:150]}")
            db.session.rollback()
        
        # Step 2: Delete order_items (references orders)
        try:
            count = db.session.execute(text("SELECT COUNT(*) FROM order_items")).scalar()
            if count > 0:
                db.session.execute(text("DELETE FROM order_items"))
                db.session.commit()
                log(f"✅ Cleared {count} records from order_items")
            else:
                log(f"✅ order_items is already empty")
            cleared_count += 1
        except Exception as e:
            log(f"⚠️  Error clearing order_items: {str(e)[:150]}")
            db.session.rollback()
        
        # Step 3: Delete orders (parent table, now safe to delete)
        try:
            count = db.session.execute(text("SELECT COUNT(*) FROM orders")).scalar()
            if count > 0:
                db.session.execute(text("DELETE FROM orders"))
                db.session.commit()
                log(f"✅ Cleared {count} records from orders")
            else:
                log(f"✅ orders is already empty")
            cleared_count += 1
        except Exception as e:
            log(f"⚠️  Error clearing orders: {str(e)[:150]}")
            db.session.rollback()
        
        # Step 4: Delete other tables (no FK dependencies)
        other_tables = [
            'dealer_wise_stock_details',
            'cart_items',
            'email_logs',
            'conversations'
        ]
        
        for table in other_tables:
            try:
                count = db.session.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar()
                if count > 0:
                    db.session.execute(text(f"DELETE FROM {table}"))
                    db.session.commit()
                    log(f"✅ Cleared {count} records from {table}")
                else:
                    log(f"✅ {table} is already empty")
                cleared_count += 1
            except Exception as e:
                log(f"⚠️  Error clearing {table}: {str(e)[:150]}")
                db.session.rollback()
        
        log(f"\n✅ Successfully cleared {cleared_count} out of {total_tables} tables")
        return True
    except Exception as e:
        log(f"\n❌ Error clearing tables: {str(e)}")
        db.session.rollback()
        return False

def extract_from_csv(limit=200):
    """Extract first N rows from CSV file"""
    print_header(f"EXTRACTING FIRST {limit} ROWS FROM CSV")
    
    csv_path = project_root / 'table_exports' / 'dealer_wise_stock_details.csv'
    
    if not csv_path.exists():
        log(f"❌ CSV file not found: {csv_path}")
        return []
    
    try:
        # Read CSV (pandas automatically handles header)
        df = pd.read_csv(csv_path, nrows=limit)
        
        log(f"✅ Read {len(df)} rows from CSV")
        
        # Convert to list of dictionaries
        stock_details = []
        for idx, row in df.iterrows():
            try:
                # Handle negative quantities (convert to positive)
                quantity = int(row.get('quantity', 0))
                if quantity < 0:
                    quantity = abs(quantity)
                
                # Parse dates
                dispatch_date = None
                if pd.notna(row.get('dispatch_date')):
                    try:
                        dispatch_date = pd.to_datetime(row['dispatch_date']).date()
                    except:
                        dispatch_date = datetime.strptime(str(row['dispatch_date']), '%Y-%m-%d').date()
                
                expiry_date = None
                if pd.notna(row.get('expiry_date')):
                    try:
                        expiry_date = pd.to_datetime(row['expiry_date']).date()
                    except:
                        try:
                            expiry_date = datetime.strptime(str(row['expiry_date']), '%Y-%m-%d').date()
                        except:
                            expiry_date = None
                
                # CRITICAL: For new stock, status should be 'blocked' and available_for_sale should be 0
                # received_quantity should be NULL until dealer confirms
                status = str(row.get('status', 'blocked')).strip()
                received_qty_val = row.get('received_quantity')
                
                # Set received_quantity to None for new stock (not confirmed yet)
                # Only set it if status is 'confirmed' and value exists in CSV
                received_quantity = None
                if status == 'confirmed' and pd.notna(received_qty_val):
                    received_quantity = int(received_qty_val)
                
                stock_detail = {
                    'dealer_unique_id': str(row.get('dealer_unique_id', '')).strip(),
                    'dealer_name': str(row.get('dealer_name', '')).strip(),
                    'product_code': str(row.get('product_code', '')).strip(),
                    'product_name': str(row.get('product_name', '')).strip(),
                    'lot_number': str(row.get('lot_number', '')).strip() if pd.notna(row.get('lot_number')) else None,
                    'expiry_date': expiry_date,
                    'quantity': quantity,
                    'sales_price': float(row.get('sales_price', 0.0)),
                    'blocked_quantity': int(row.get('blocked_quantity', 0)),
                    'out_for_delivery_quantity': 0,  # New column - default to 0 for new stock
                    'available_for_sale': 0,  # CRITICAL: Should be 0 for new stock until dealer confirms
                    'sold_quantity': int(row.get('sold_quantity', 0)),
                    'status': status,  # Should be 'blocked' for new stock
                    'invoice_id': str(row.get('invoice_id', '')).strip() if pd.notna(row.get('invoice_id')) else None,
                    'dispatch_date': dispatch_date,
                    'received_quantity': received_quantity  # NULL for new stock until dealer confirms
                }
                
                stock_details.append(stock_detail)
            except Exception as e:
                log(f"⚠️  Error processing row {idx + 2}: {str(e)}")
                continue
        
        log(f"✅ Extracted {len(stock_details)} stock details")
        return stock_details
        
    except Exception as e:
        log(f"❌ Error reading CSV: {str(e)}")
        import traceback
        log(traceback.format_exc())
        return []

def import_stock_details(stock_details):
    """Import stock details to database"""
    print_header("IMPORTING STOCK DETAILS")
    
    from app.stock_extracter.stock_importer import StockImporter
    
    importer = StockImporter(db=db)
    
    try:
        result = importer.import_stock_details(stock_details)
        
        if result.get('success'):
            imported = result.get('imported_count', 0)
            skipped = result.get('skipped_count', 0)
            errors = result.get('error_count', 0)
            
            log(f"\n✅ Import completed!")
            log(f"   Imported: {imported}")
            log(f"   Skipped: {skipped}")
            log(f"   Errors: {errors}")
            
            if errors > 0 and result.get('errors'):
                log(f"\n⚠️  First few errors:")
                for error in result['errors'][:5]:
                    log(f"   - {error.get('error', 'Unknown error')}")
            
            return True
        else:
            log(f"\n❌ Import failed: {result.get('error', 'Unknown error')}")
            return False
            
    except Exception as e:
        log(f"\n❌ Error importing: {str(e)}")
        import traceback
        log(traceback.format_exc())
        return False

def verify_import():
    """Verify the imported data"""
    print_header("VERIFYING IMPORTED DATA")
    
    try:
        # Count records
        total = DealerWiseStockDetails.query.count()
        log(f"Total records in dealer_wise_stock_details: {total}")
        
        # Check for new column
        sample = DealerWiseStockDetails.query.first()
        if sample:
            log(f"\nSample record:")
            log(f"   Product: {sample.product_code}")
            log(f"   Dealer: {sample.dealer_name}")
            log(f"   Quantity: {sample.quantity}")
            log(f"   Blocked: {sample.blocked_quantity}")
            log(f"   Out for Delivery: {sample.out_for_delivery_quantity}")
            log(f"   Available: {sample.available_for_sale}")
            log(f"   Sold: {sample.sold_quantity}")
            
            # Verify calculation
            calculated_available = max(0, (sample.received_quantity or sample.quantity) - 
                                     sample.blocked_quantity - 
                                     sample.out_for_delivery_quantity - 
                                     sample.sold_quantity)
            log(f"   Calculated Available: {calculated_available}")
            
            if calculated_available != sample.available_for_sale:
                log(f"   ⚠️  Available quantity mismatch! Expected {calculated_available}, got {sample.available_for_sale}")
            else:
                log(f"   ✅ Available quantity correct!")
        
        # Check status distribution
        from sqlalchemy import func
        status_counts = db.session.query(
            DealerWiseStockDetails.status,
            func.count(DealerWiseStockDetails.id)
        ).group_by(DealerWiseStockDetails.status).all()
        
        log(f"\nStatus distribution:")
        for status, count in status_counts:
            log(f"   {status}: {count}")
        
        return True
        
    except Exception as e:
        log(f"❌ Error verifying: {str(e)}")
        import traceback
        log(traceback.format_exc())
        return False

def main():
    """Main execution"""
    app = create_app()
    with app.app_context():
        print_header("STOCK DATA RESET AND POPULATION")
        
        # Step 1: Drop table data
        if not drop_table_data():
            log("\n❌ Failed to clear tables. Aborting.")
            return
        
        # Step 2: Extract from CSV
        stock_details = extract_from_csv(limit=200)
        if not stock_details:
            log("\n❌ No stock details extracted. Aborting.")
            return
        
        # Step 3: Import stock details
        if not import_stock_details(stock_details):
            log("\n❌ Failed to import stock details.")
            return
        
        # Step 4: Verify import
        verify_import()
        
        print_header("PROCESS COMPLETE")
        log("\n✅ Stock data reset and population completed successfully!")

if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        print(f"\n❌ Fatal error: {str(e)}", flush=True)
        import traceback
        traceback.print_exc()
        sys.exit(1)

