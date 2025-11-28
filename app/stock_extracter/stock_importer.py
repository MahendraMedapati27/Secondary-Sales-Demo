"""
Stock Importer Service
Imports extracted stock details to the database
"""

import logging
from typing import List, Dict, Optional
from datetime import datetime, date
from sqlalchemy import text
from flask import current_app

# Single logger initialization - logging.basicConfig should only be called once in __init__.py
logger = logging.getLogger(__name__)


class StockImporter:
    """Service for importing stock details to database"""
    
    def __init__(self, db=None):
        """
        Initialize Stock Importer
        
        Args:
            db: Flask-SQLAlchemy database instance (from app)
        """
        self.db = db
        self.logger = logger
    
    def get_dealer_by_name_or_id(self, dealer_name: Optional[str] = None, dealer_unique_id: Optional[str] = None) -> Optional[Dict]:
        """
        Get dealer user from database by name or unique ID
        
        Args:
            dealer_name: Dealer name
            dealer_unique_id: Dealer unique ID
            
        Returns:
            Dealer dictionary with id and unique_id, or None if not found
        """
        try:
            if not self.db:
                from app import db
                self.db = db
            
            query = "SELECT id, unique_id, name FROM users WHERE role = 'distributor'"
            params = {}
            
            if dealer_unique_id:
                query += " AND unique_id = :dealer_unique_id"
                params['dealer_unique_id'] = dealer_unique_id
            elif dealer_name:
                query += " AND (name = :dealer_name OR pharmacy_name = :dealer_name)"
                params['dealer_name'] = dealer_name
            
            result = self.db.session.execute(text(query), params)
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
        """
        Get product from database by code or name
        Note: products table only has product_name column, not product_code
        
        Args:
            product_code: Product code (from CSV, not used for lookup since table has no product_code column)
            product_name: Product name (primary method for matching)
            
        Returns:
            Product dictionary with id and product_name, or None if not found
        """
        try:
            if not self.db:
                from app import db
                self.db = db
            
            # Products table only has product_name, so we match by product_name
            # Priority: Use product_name if provided, otherwise try to match product_code as name (unlikely to work)
            search_name = product_name if product_name else product_code
            
            if not search_name:
                return None
            
            # Normalize the search name (remove extra spaces, convert to lowercase for comparison)
            search_name_clean = search_name.strip()
            
            # Method 1: Exact match (case-insensitive)
            try:
                query = "SELECT id, product_name FROM products WHERE LOWER(TRIM(product_name)) = LOWER(:search_name)"
                result = self.db.session.execute(text(query), {'search_name': search_name_clean})
                row = result.fetchone()
                if row:
                    self.logger.debug(f"Found product by exact match: '{search_name_clean}' -> id={row[0]}, name='{row[1]}'")
                    return {
                        'id': row[0],
                        'product_name': row[1]
                    }
            except Exception as e:
                self.logger.debug(f"Error in exact match: {str(e)}")
            
            # Method 2: Normalized match (remove content in parentheses for comparison)
            # e.g., "Tenepan-20mg (3*10's)" should match "Tenepan-20mg (3*10's)" or similar
            try:
                import re
                # Extract base name (before parentheses)
                base_name = re.sub(r'\s*\([^)]*\)', '', search_name_clean).strip()
                if base_name:
                    query = """
                        SELECT id, product_name FROM products 
                        WHERE LOWER(TRIM(REPLACE(REPLACE(product_name, '(', ''), ')', ''))) LIKE LOWER(:base_name_pattern)
                        OR LOWER(TRIM(product_name)) LIKE LOWER(:base_name_pattern2)
                    """
                    result = self.db.session.execute(text(query), {
                        'base_name_pattern': f'%{base_name}%',
                        'base_name_pattern2': f'%{base_name}%'
                    })
                    rows = result.fetchall()
                    if rows:
                        # Prefer exact base name match
                        for row in rows:
                            db_base_name = re.sub(r'\s*\([^)]*\)', '', row[1]).strip()
                            if base_name.lower() == db_base_name.lower():
                                self.logger.debug(f"Found product by normalized base match: '{search_name_clean}' -> id={row[0]}, name='{row[1]}'")
                                return {
                                    'id': row[0],
                                    'product_name': row[1]
                                }
                        # If no exact base match, return first result
                        row = rows[0]
                        self.logger.debug(f"Found product by partial base match: '{search_name_clean}' -> id={row[0]}, name='{row[1]}'")
                        return {
                            'id': row[0],
                            'product_name': row[1]
                        }
            except Exception as e:
                self.logger.debug(f"Error in normalized match: {str(e)}")
            
            # Method 3: Partial match (contains)
            try:
                query = "SELECT id, product_name FROM products WHERE LOWER(product_name) LIKE LOWER(:search_pattern)"
                result = self.db.session.execute(text(query), {'search_pattern': f'%{search_name_clean}%'})
                row = result.fetchone()
                if row:
                    self.logger.debug(f"Found product by partial match: '{search_name_clean}' -> id={row[0]}, name='{row[1]}'")
                    return {
                        'id': row[0],
                        'product_name': row[1]
                    }
            except Exception as e:
                self.logger.debug(f"Error in partial match: {str(e)}")
            
            # Method 4: Match by first word (e.g., "Tenepan" should match "Tenepan-20mg")
            try:
                import re
                first_word = search_name_clean.split()[0] if search_name_clean.split() else None
                if first_word and len(first_word) > 2:
                    query = "SELECT id, product_name FROM products WHERE LOWER(product_name) LIKE LOWER(:first_word_pattern)"
                    result = self.db.session.execute(text(query), {'first_word_pattern': f'{first_word}%'})
                    rows = result.fetchall()
                    if rows:
                        # If multiple matches, try to find the best one by checking if numbers match
                        search_numbers = re.findall(r'\d+', search_name_clean)
                        best_match = None
                        best_score = 0
                        
                        for row in rows:
                            db_numbers = re.findall(r'\d+', row[1])
                            # Score based on number matches
                            score = len(set(search_numbers) & set(db_numbers))
                            if score > best_score:
                                best_score = score
                                best_match = row
                        
                        if best_match:
                            self.logger.debug(f"Found product by first word + numbers: '{search_name_clean}' -> id={best_match[0]}, name='{best_match[1]}'")
                            return {
                                'id': best_match[0],
                                'product_name': best_match[1]
                            }
                        # If no number match, return first result
                        row = rows[0]
                        self.logger.debug(f"Found product by first word: '{search_name_clean}' -> id={row[0]}, name='{row[1]}'")
                        return {
                            'id': row[0],
                            'product_name': row[1]
                        }
            except Exception as e:
                self.logger.debug(f"Error in first word match: {str(e)}")
            
            self.logger.warning(f"Product not found for: code='{product_code}', name='{product_name}'")
            return None
            
        except Exception as e:
            self.logger.error(f"Error getting product: {str(e)}")
            import traceback
            self.logger.error(traceback.format_exc())
            return None
    
    def check_file_processed(self, filename: str, file_modified_date: Optional[datetime] = None) -> bool:
        """
        Check if file has already been processed
        
        Args:
            filename: Excel file name
            file_modified_date: File last modified date
            
        Returns:
            True if file already processed, False otherwise
        """
        try:
            if not self.db:
                from app import db
                self.db = db
            
            # Check if we have records from this file
            # We'll use a simple approach: check if any stock detail has this source_file
            # In a production system, you might want a separate file_processing_log table
            query = """
                SELECT COUNT(*) FROM dealer_wise_stock_details 
                WHERE invoice_id LIKE :filename_pattern
            """
            result = self.db.session.execute(text(query), {'filename_pattern': f'%{filename}%'})
            count = result.fetchone()[0]
            
            return count > 0
            
        except Exception as e:
            self.logger.warning(f"Error checking if file processed: {str(e)}")
            return False
    
    def import_stock_details(self, stock_details: List[Dict]) -> Dict:
        """
        Import stock details to database
        
        Args:
            stock_details: List of stock detail dictionaries
            
        Returns:
            Dictionary with import results
        """
        imported_count = 0
        skipped_count = 0
        error_count = 0
        errors = []
        
        try:
            if not self.db:
                from app import db
                self.db = db
            
            for stock_detail in stock_details:
                try:
                    # Get dealer
                    dealer = None
                    if stock_detail.get('dealer_unique_id'):
                        dealer = self.get_dealer_by_name_or_id(dealer_unique_id=stock_detail['dealer_unique_id'])
                    elif stock_detail.get('dealer_name'):
                        dealer_name = stock_detail['dealer_name']
                        # Clean the dealer name (should already be cleaned by extractor, but do it again for safety)
                        import re
                        cleaned_name = dealer_name
                        # Remove brackets
                        cleaned_name = re.sub(r'\s*\([^)]*\)', '', cleaned_name).strip()
                        # If contains " - ", take only the part before it
                        if ' - ' in cleaned_name:
                            cleaned_name = cleaned_name.split(' - ')[0].strip()
                        
                        # Try exact match first with cleaned name
                        dealer = self.get_dealer_by_name_or_id(dealer_name=cleaned_name)
                        
                        # If not found, try partial match (dealer name might be part of a longer name in DB)
                        if not dealer:
                            try:
                                session = self.db.session if self.db else None
                                if session:
                                    query = """
                                        SELECT id, unique_id, name FROM users 
                                        WHERE role = 'distributor' 
                                        AND (
                                            LOWER(name) = LOWER(:dealer_name)
                                            OR LOWER(name) LIKE LOWER(:dealer_name_pattern)
                                            OR LOWER(:dealer_name) LIKE LOWER(CONCAT('%', name, '%'))
                                        )
                                    """
                                    result = session.execute(text(query), {
                                        'dealer_name': cleaned_name,
                                        'dealer_name_pattern': f'%{cleaned_name}%'
                                    })
                                    row = result.fetchone()
                                    if row:
                                        dealer = {
                                            'id': row[0],
                                            'unique_id': row[1],
                                            'name': row[2]
                                        }
                            except Exception as e:
                                self.logger.debug(f"Error in partial dealer match: {str(e)}")
                    
                    if not dealer:
                        self.logger.warning(f"Dealer not found: {stock_detail.get('dealer_name')} or {stock_detail.get('dealer_unique_id')}")
                        skipped_count += 1
                        continue
                    
                    # Get product
                    # Note: products table only has product_name column, so we prioritize product_name for matching
                    product = None
                    product_id = None
                    
                    # Try to find product by product_name first (most reliable)
                    if stock_detail.get('product_name'):
                        product = self.get_product_by_code_or_name(product_name=stock_detail['product_name'])
                        if product:
                            product_id = product['id']
                            self.logger.debug(f"Found product for name '{stock_detail['product_name']}': id={product_id}, db_name='{product.get('product_name')}'")
                    
                    # If not found by name, try by product_code (though products table has no product_code column, 
                    # this might match if product_code happens to match a product_name)
                    if not product and stock_detail.get('product_code'):
                        product = self.get_product_by_code_or_name(product_code=stock_detail['product_code'])
                        if product:
                            product_id = product['id']
                            self.logger.debug(f"Found product for code '{stock_detail['product_code']}': id={product_id}, name='{product.get('product_name')}'")
                    
                    # If product not found, we can still import with product_name
                    # The product_id will be NULL (which is acceptable)
                    if not product_id:
                        self.logger.warning(f"Product not found - importing with product_id=NULL for product_code='{stock_detail.get('product_code')}', product_name='{stock_detail.get('product_name')}'")
                    
                    # Prepare data for insert
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
                            elif isinstance(expiry_date, date):
                                expiry_date = expiry_date
                            else:
                                expiry_date = None
                        except Exception as e:
                            self.logger.warning(f"Error parsing expiry_date: {str(e)}")
                            expiry_date = None
                    else:
                        expiry_date = None  # Keep as NULL if not available in Excel
                    
                    # Check for duplicate (same dealer, product, dispatch_date, invoice_id)
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
                    
                    existing = self.db.session.execute(text(check_query), check_params).fetchone()
                    
                    if existing:
                        self.logger.debug(f"Duplicate record found, skipping: {stock_detail.get('product_code')} for {dealer['name']}")
                        skipped_count += 1
                        continue
                    
                    # Insert stock detail
                    # CRITICAL: Include out_for_delivery_quantity column (new column for delivery partner feature)
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
                    
                    # CRITICAL: For new stock imports, available_for_sale should be 0
                    # Stock starts with status='blocked' and available_for_sale=0
                    # Only after dealer confirms (status='confirmed') should available_for_sale be calculated
                    quantity = stock_detail.get('quantity', 0)
                    blocked_qty = stock_detail.get('blocked_quantity', 0)
                    out_for_delivery_qty = stock_detail.get('out_for_delivery_quantity', 0)
                    sold_qty = stock_detail.get('sold_quantity', 0)
                    status = stock_detail.get('status', 'blocked')
                    
                    # Get received_quantity (should be NULL for new stock)
                    received_qty = stock_detail.get('received_quantity')
                    
                    # Calculate available_for_sale based on status
                    # If status is 'confirmed', calculate from received_quantity
                    # If status is 'blocked', available_for_sale should be 0
                    available_qty = stock_detail.get('available_for_sale')
                    if available_qty is None:
                        if status == 'confirmed' and received_qty is not None:
                            # Stock is confirmed - calculate available based on received quantity
                            available_qty = max(0, received_qty - blocked_qty - out_for_delivery_qty - sold_qty)
                        else:
                            # New stock (blocked) - available_for_sale is 0 until dealer confirms
                            available_qty = 0
                    
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
                        'blocked_quantity': blocked_qty,
                        'out_for_delivery_quantity': out_for_delivery_qty,  # New column
                        'available_for_sale': available_qty,
                        'sold_quantity': sold_qty,
                        'status': status,
                        'invoice_id': stock_detail.get('invoice_id'),
                        'received_quantity': received_qty,  # NULL for new stock until dealer confirms
                        'created_at': datetime.utcnow(),
                        'updated_at': datetime.utcnow()
                    }
                    
                    self.db.session.execute(text(insert_query), insert_params)
                    imported_count += 1
                    
                except Exception as e:
                    error_count += 1
                    error_msg = f"Error importing stock detail: {str(e)}"
                    self.logger.error(error_msg)
                    errors.append({
                        'stock_detail': stock_detail,
                        'error': str(e)
                    })
                    continue
            
            # Commit all changes
            self.db.session.commit()
            
            self.logger.info(f"Import completed: {imported_count} imported, {skipped_count} skipped, {error_count} errors")
            
            return {
                'success': True,
                'imported_count': imported_count,
                'skipped_count': skipped_count,
                'error_count': error_count,
                'errors': errors
            }
            
        except Exception as e:
            self.logger.error(f"Error in import process: {str(e)}")
            try:
                if self.db:
                    self.db.session.rollback()
            except:
                pass
            return {
                'success': False,
                'error': str(e),
                'imported_count': imported_count,
                'skipped_count': skipped_count,
                'error_count': error_count,
                'errors': errors
            }

