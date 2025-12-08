"""
Stock Importer Service for Azure Function
Imports extracted stock details to the database
"""

import logging
from typing import List, Dict, Optional
from datetime import datetime, date
from sqlalchemy import text

logger = logging.getLogger(__name__)


class StockImporter:
    """Service for importing stock details to database"""
    
    def __init__(self, db=None):
        """
        Initialize Stock Importer
        
        Args:
            db: SQLAlchemy session
        """
        self.db = db
        self.logger = logger
    
    def get_dealer_by_name_or_id(self, dealer_name: Optional[str] = None, dealer_unique_id: Optional[str] = None) -> Optional[Dict]:
        """Get dealer user from database by name or unique ID"""
        try:
            query = "SELECT id, unique_id, name FROM users WHERE role = 'distributor'"
            params = {}
            
            if dealer_unique_id:
                query += " AND unique_id = :dealer_unique_id"
                params['dealer_unique_id'] = dealer_unique_id
            elif dealer_name:
                query += " AND (name = :dealer_name OR pharmacy_name = :dealer_name)"
                params['dealer_name'] = dealer_name
            
            result = self.db.execute(text(query), params)
            row = result.fetchone()
            
            if row:
                return {
                    'id': row[0],
                    'unique_id': row[1],
                    'name': row[2]
                }
            return None
            
        except Exception as e:
            self.logger.error(f"Error getting dealer: {str(e)}")
            return None
    
    def get_product_by_code_or_name(self, product_code: Optional[str] = None, product_name: Optional[str] = None) -> Optional[Dict]:
        """Get product from database by code or name"""
        try:
            search_name = product_name if product_name else product_code
            
            if not search_name:
                return None
            
            search_name_clean = search_name.strip()
            
            # Exact match (case-insensitive)
            try:
                query = "SELECT id, product_name FROM products WHERE LOWER(TRIM(product_name)) = LOWER(:search_name)"
                result = self.db.execute(text(query), {'search_name': search_name_clean})
                row = result.fetchone()
                if row:
                    return {
                        'id': row[0],
                        'product_name': row[1]
                    }
            except Exception as e:
                self.logger.debug(f"Error in exact match: {str(e)}")
            
            # Partial match
            try:
                query = "SELECT id, product_name FROM products WHERE LOWER(product_name) LIKE LOWER(:search_pattern)"
                result = self.db.execute(text(query), {'search_pattern': f'%{search_name_clean}%'})
                row = result.fetchone()
                if row:
                    return {
                        'id': row[0],
                        'product_name': row[1]
                    }
            except Exception as e:
                self.logger.debug(f"Error in partial match: {str(e)}")
            
            self.logger.warning(f"Product not found for: code='{product_code}', name='{product_name}'")
            return None
            
        except Exception as e:
            self.logger.error(f"Error getting product: {str(e)}")
            return None
    
    def import_stock_details(self, stock_details: List[Dict], test_row_start: int = None, test_row_end: int = None) -> Dict:
        """
        Import stock details to database
        
        Args:
            stock_details: List of stock detail dictionaries
            test_row_start: Start index for testing (inclusive, 0-based)
            test_row_end: End index for testing (inclusive, 0-based)
                         Set both to None to import all records
        
        Returns:
            Dictionary with import results
        """
        imported_count = 0
        skipped_count = 0
        error_count = 0
        errors = []
        skip_reasons = []  # Track skip reasons for detailed logging
        
        try:
            # Apply row range test mode
            total_records = len(stock_details)
            original_count = total_records
            
            if test_row_start is not None and test_row_end is not None:
                if test_row_start < len(stock_details) and test_row_end < len(stock_details):
                    stock_details = stock_details[test_row_start:test_row_end + 1]  # +1 because end is inclusive
                    self.logger.info(f"🧪 TESTING MODE: Importing rows #{test_row_start + 1} to #{test_row_end + 1} (indices {test_row_start}-{test_row_end}) from total {total_records} records")
                    self.logger.info(f"   Total rows to import: {len(stock_details)}")
                else:
                    self.logger.warning(f"⚠️ Test row range {test_row_start}-{test_row_end} is out of range (total: {total_records})")
                    return {
                        'success': False,
                        'error': f'Row range {test_row_start}-{test_row_end} out of range',
                        'imported_count': 0,
                        'skipped_count': 0,
                        'error_count': 0,
                        'errors': [],
                        'total_records': total_records,
                        'test_mode': True
                    }
            
            for idx, stock_detail in enumerate(stock_details):
                try:
                    # Calculate actual row number for logging
                    actual_row_num = test_row_start + idx + 1 if test_row_start is not None else idx + 1
                    
                    # Check for minimum required fields
                    if not stock_detail.get('dealer_name') and not stock_detail.get('dealer_unique_id'):
                        skip_reason = f"Row #{actual_row_num}: Missing dealer information (no dealer_name or dealer_unique_id)"
                        self.logger.warning(f"⏭️ {skip_reason}")
                        skip_reasons.append(skip_reason)
                        skipped_count += 1
                        continue
                    
                    if not stock_detail.get('product_code'):
                        skip_reason = f"Row #{actual_row_num}: Missing product_code"
                        self.logger.warning(f"⏭️ {skip_reason}")
                        self.logger.warning(f"   Dealer: {stock_detail.get('dealer_name', 'N/A')}")
                        skip_reasons.append(skip_reason)
                        skipped_count += 1
                        continue
                    
                    # Get dealer
                    dealer = None
                    if stock_detail.get('dealer_unique_id'):
                        dealer = self.get_dealer_by_name_or_id(dealer_unique_id=stock_detail['dealer_unique_id'])
                    elif stock_detail.get('dealer_name'):
                        dealer_name = stock_detail['dealer_name']
                        import re
                        cleaned_name = re.sub(r'\s*\([^)]*\)', '', dealer_name).strip()
                        if ' - ' in cleaned_name:
                            cleaned_name = cleaned_name.split(' - ')[0].strip()
                        dealer = self.get_dealer_by_name_or_id(dealer_name=cleaned_name)
                    
                    if not dealer:
                        dealer_name = stock_detail.get('dealer_name', 'N/A')
                        dealer_id = stock_detail.get('dealer_unique_id', 'N/A')
                        skip_reason = f"Row #{actual_row_num}: Dealer not found in database"
                        self.logger.warning(f"⏭️ {skip_reason}")
                        self.logger.warning(f"   Dealer Name: '{dealer_name}'")
                        self.logger.warning(f"   Dealer ID: '{dealer_id}'")
                        self.logger.warning(f"   Product: {stock_detail.get('product_code', 'N/A')} - {stock_detail.get('product_name', 'N/A')}")
                        skip_reasons.append(f"{skip_reason} - Dealer: '{dealer_name}' (ID: {dealer_id})")
                        skipped_count += 1
                        continue
                    
                    # Get product (optional - can import with NULL product_id)
                    product_id = None
                    if stock_detail.get('product_name'):
                        product = self.get_product_by_code_or_name(product_name=stock_detail['product_name'])
                        if product:
                            product_id = product['id']
                    
                    # Prepare dates
                    dispatch_date = stock_detail.get('dispatch_date')
                    if isinstance(dispatch_date, str):
                        dispatch_date = datetime.strptime(dispatch_date, '%Y-%m-%d').date()
                    elif isinstance(dispatch_date, datetime):
                        dispatch_date = dispatch_date.date()
                    
                    expiry_date = stock_detail.get('expiry_date')
                    if expiry_date:
                        try:
                            if isinstance(expiry_date, str):
                                expiry_date = datetime.strptime(expiry_date, '%Y-%m-%d').date()
                            elif isinstance(expiry_date, datetime):
                                expiry_date = expiry_date.date()
                        except Exception:
                            expiry_date = None
                    
                    # Check for duplicate
                    check_query = """
                        SELECT id FROM dealer_wise_stock_details
                        WHERE dealer_unique_id = :dealer_unique_id
                        AND product_code = :product_code
                        AND dispatch_date = :dispatch_date
                        AND (invoice_id = :invoice_id OR (:invoice_id IS NULL AND invoice_id IS NULL))
                    """
                    check_params = {
                        'dealer_unique_id': dealer['unique_id'],
                        'product_code': stock_detail.get('product_code', ''),
                        'dispatch_date': dispatch_date,
                        'invoice_id': stock_detail.get('invoice_id')
                    }
                    
                    existing = self.db.execute(text(check_query), check_params).fetchone()
                    
                    if existing:
                        skip_reason = f"Row #{actual_row_num}: Duplicate record already exists in database"
                        self.logger.warning(f"⏭️ {skip_reason}")
                        self.logger.warning(f"   Dealer: {dealer['name']}")
                        self.logger.warning(f"   Product: {stock_detail.get('product_code')} - {stock_detail.get('product_name')}")
                        self.logger.warning(f"   Dispatch Date: {dispatch_date}")
                        self.logger.warning(f"   Invoice: {stock_detail.get('invoice_id', 'N/A')}")
                        skip_reasons.append(f"{skip_reason} - {dealer['name']} / {stock_detail.get('product_code')}")
                        skipped_count += 1
                        continue
                    
                    # Insert stock detail
                    insert_query = """
                        INSERT INTO dealer_wise_stock_details (
                            dispatch_date, dealer_id, dealer_unique_id, dealer_name,
                            product_code, product_name, product_id,
                            lot_number, expiry_date, quantity,
                            sales_price, blocked_quantity, out_for_delivery_quantity,
                            available_for_sale, sold_quantity, status, invoice_id,
                            received_quantity,
                            created_at, updated_at
                        ) VALUES (
                            :dispatch_date, :dealer_id, :dealer_unique_id, :dealer_name,
                            :product_code, :product_name, :product_id,
                            :lot_number, :expiry_date, :quantity,
                            :sales_price, :blocked_quantity, :out_for_delivery_quantity,
                            :available_for_sale, :sold_quantity, :status, :invoice_id,
                            :received_quantity,
                            :created_at, :updated_at
                        )
                    """
                    
                    quantity = stock_detail.get('quantity', 0)
                    status = stock_detail.get('status', 'blocked')
                    available_qty = 0 if status == 'blocked' else quantity
                    
                    insert_params = {
                        'dispatch_date': dispatch_date,
                        'dealer_id': dealer['id'],
                        'dealer_unique_id': dealer['unique_id'],
                        'dealer_name': dealer['name'],
                        'product_code': stock_detail.get('product_code', ''),
                        'product_name': stock_detail.get('product_name', ''),
                        'product_id': product_id,
                        'lot_number': stock_detail.get('lot_number'),
                        'expiry_date': expiry_date,
                        'quantity': quantity,
                        'sales_price': stock_detail.get('sales_price', 0.0),
                        'blocked_quantity': stock_detail.get('blocked_quantity', 0),
                        'out_for_delivery_quantity': stock_detail.get('out_for_delivery_quantity', 0),
                        'available_for_sale': available_qty,
                        'sold_quantity': stock_detail.get('sold_quantity', 0),
                        'status': status,
                        'invoice_id': stock_detail.get('invoice_id'),
                        'received_quantity': stock_detail.get('received_quantity'),
                        'created_at': datetime.utcnow(),
                        'updated_at': datetime.utcnow()
                    }
                    
                    self.db.execute(text(insert_query), insert_params)
                    imported_count += 1
                    self.logger.info(f"✅ Row #{actual_row_num} imported: {dealer['name']} / {stock_detail.get('product_code')} / Qty: {quantity}")
                    
                except Exception as e:
                    error_count += 1
                    error_msg = f"Row #{actual_row_num}: Error importing - {str(e)}"
                    self.logger.error(f"❌ {error_msg}")
                    self.logger.error(f"   Dealer: {stock_detail.get('dealer_name', 'N/A')}")
                    self.logger.error(f"   Product: {stock_detail.get('product_code', 'N/A')} - {stock_detail.get('product_name', 'N/A')}")
                    errors.append({
                        'row_number': actual_row_num,
                        'stock_detail': stock_detail,
                        'error': str(e)
                    })
                    continue
            
            # Commit all changes
            self.db.commit()
            
            if test_row_start is not None and test_row_end is not None:
                self.logger.info(f"✅ Import completed (TESTING MODE - ROWS #{test_row_start + 1} to #{test_row_end + 1})")
                self.logger.info(f"   📊 Total records in file: {original_count}")
                self.logger.info(f"   🎯 Tested rows: #{test_row_start + 1} to #{test_row_end + 1} ({test_row_end - test_row_start + 1} rows)")
                self.logger.info(f"   📈 Imported: {imported_count}")
                self.logger.info(f"   ⏭️ Skipped: {skipped_count}")
                self.logger.info(f"   ❌ Errors: {error_count}")
                
                # Log skip reasons summary
                if skip_reasons:
                    self.logger.info(f"   📋 Skip Reasons Summary:")
                    for reason in skip_reasons:
                        self.logger.info(f"      - {reason}")
            else:
                self.logger.info(f"🚀 PRODUCTION Import completed: {imported_count} imported, {skipped_count} skipped, {error_count} errors")
                
                # In production, log skip reasons summary (first 50)
                if skip_reasons:
                    self.logger.info(f"   📋 Skip Reasons Summary ({len(skip_reasons)} total, showing first 50):")
                    for reason in skip_reasons[:50]:
                        self.logger.info(f"      - {reason}")
                    if len(skip_reasons) > 50:
                        self.logger.info(f"      ... and {len(skip_reasons) - 50} more skipped records")
            
            return {
                'success': True,
                'imported_count': imported_count,
                'skipped_count': skipped_count,
                'error_count': error_count,
                'errors': errors,
                'skip_reasons': skip_reasons,
                'total_records': original_count,
                'test_mode': test_row_start is not None and test_row_end is not None,
                'test_row_start': test_row_start,
                'test_row_end': test_row_end
            }
            
        except Exception as e:
            self.logger.error(f"Error in import process: {str(e)}")
            try:
                if self.db:
                    self.db.rollback()
            except:
                pass
            return {
                'success': False,
                'error': str(e),
                'imported_count': imported_count,
                'skipped_count': skipped_count,
                'error_count': error_count,
                'errors': errors,
                'skip_reasons': skip_reasons
            }
