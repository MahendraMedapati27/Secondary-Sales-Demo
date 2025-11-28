"""
Excel File Extractor
Extracts dealer-wise stock details from Excel files
"""

import logging
import pandas as pd
import io
from typing import List, Dict, Optional
from datetime import datetime

# Single logger initialization - logging.basicConfig should only be called once in __init__.py
logger = logging.getLogger(__name__)


class ExcelExtractor:
    """Service for extracting stock details from Excel files"""
    
    def __init__(self):
        """Initialize Excel Extractor"""
        self.logger = logger
    
    def extract_stock_details(self, file_content: bytes, filename: str) -> List[Dict]:
        """
        Extract dealer-wise stock details from Excel or CSV file
        
        Args:
            file_content: File content as bytes
            filename: Name of the file (Excel or CSV)
            
        Returns:
            List of stock detail dictionaries
        """
        try:
            file_lower = filename.lower()
            
            # Check if it's a CSV file
            if file_lower.endswith('.csv'):
                return self._extract_from_csv(file_content, filename)
            
            # Otherwise, treat as Excel file
            return self._extract_from_excel(file_content, filename)
            
        except Exception as e:
            self.logger.error(f"Error extracting stock details from {filename}: {str(e)}")
            import traceback
            self.logger.error(traceback.format_exc())
            return []
    
    def _extract_from_csv(self, file_content: bytes, filename: str) -> List[Dict]:
        """Extract stock details from CSV file"""
        try:
            # Read CSV file
            csv_file = io.BytesIO(file_content)
            
            # Try different encodings
            encodings = ['utf-8', 'utf-8-sig', 'latin-1', 'cp1252']
            df = None
            
            for encoding in encodings:
                try:
                    csv_file.seek(0)
                    df = pd.read_csv(csv_file, encoding=encoding)
                    self.logger.info(f"Successfully read CSV with encoding: {encoding}")
                    break
                except (UnicodeDecodeError, pd.errors.ParserError):
                    continue
            
            if df is None:
                self.logger.error("Failed to read CSV file with any encoding")
                return []
            
            # Process as single sheet
            return self._process_dataframe(df, filename, 'Sheet1')
            
        except Exception as e:
            self.logger.error(f"Error reading CSV file: {str(e)}")
            return []
    
    def _extract_from_excel(self, file_content: bytes, filename: str) -> List[Dict]:
        """Extract stock details from Excel file"""
        try:
            # Read Excel file
            excel_file = io.BytesIO(file_content)
            
            # Try to read the first sheet (or all sheets)
            try:
                # Read all sheets
                excel_data = pd.read_excel(excel_file, sheet_name=None, engine='openpyxl')
            except Exception as e:
                self.logger.warning(f"Error reading Excel with openpyxl: {str(e)}, trying xlrd")
                excel_file.seek(0)
                try:
                    excel_data = pd.read_excel(excel_file, sheet_name=None, engine='xlrd')
                except Exception as e2:
                    self.logger.error(f"Error reading Excel file: {str(e2)}")
                    return []
            
            stock_details = []
            
            # Process each sheet
            for sheet_name, df in excel_data.items():
                self.logger.info(f"Processing sheet: {sheet_name}")
                sheet_details = self._process_dataframe(df, filename, sheet_name)
                stock_details.extend(sheet_details)
            
            self.logger.info(f"Extracted {len(stock_details)} stock detail records from {filename}")
            return stock_details
            
        except Exception as e:
            self.logger.error(f"Error reading Excel file: {str(e)}")
            return []
    
    def _process_dataframe(self, df: pd.DataFrame, filename: str, sheet_name: str) -> List[Dict]:
        """Process a pandas DataFrame and extract stock details"""
        try:
            stock_details = []
            
            # Try to detect column names (case-insensitive)
            df.columns = df.columns.str.strip().str.lower()
            
            # Common column name variations
            column_mapping = {
                'dealer': ['dealer', 'dealer name', 'dealer_name', 'distributor', 'distributor name'],
                'dealer_id': ['dealer id', 'dealer_id', 'dealer unique id', 'dealer_unique_id', 'unique id'],
                'product_code': ['product code', 'product_code', 'code', 'product id', 'product_id'],
                'product_name': ['product name', 'product_name', 'product', 'item name', 'item_name'],
                'quantity': ['quantity', 'qty', 'qty dispatched', 'qty_dispatched', 'dispatched quantity'],
                'dispatch_date': ['dispatch date', 'dispatch_date', 'date', 'dispatch', 'dispatched date'],
                'lot_number': ['lot number', 'lot_number', 'lot', 'batch', 'batch number', 'batch_number'],
                'expiry_date': ['expiry date', 'expiry_date', 'expiration date', 'expiration_date', 'expiration', 'expiry', 'exp'],
                'sales_price': ['sales price', 'sales_price', 'price', 'unit price', 'unit_price', 'rate'],
                'invoice_id': ['invoice id', 'invoice_id', 'invoice', 'invoice number', 'invoice_number', 'invoice no', 'invoice_no']
            }
            
            # Find actual column names
            actual_columns = {}
            for standard_name, variations in column_mapping.items():
                for col in df.columns:
                    if col in variations:
                        actual_columns[standard_name] = col
                        break
            
            self.logger.info(f"Detected columns: {actual_columns}")
            
            # If no dealer column found, try to infer from data
            if not actual_columns:
                self.logger.warning("No standard columns found, trying to infer structure")
                # Try to use first few rows as headers or use positional columns
                if len(df.columns) >= 3:
                    # Assume: Dealer, Product, Quantity, etc.
                    actual_columns = {
                        'dealer': df.columns[0] if 'dealer' in str(df.columns[0]).lower() else None,
                        'product_code': df.columns[1] if 'product' in str(df.columns[1]).lower() or 'code' in str(df.columns[1]).lower() else None,
                        'product_name': df.columns[2] if 'product' in str(df.columns[2]).lower() or 'name' in str(df.columns[2]).lower() else None,
                        'quantity': df.columns[3] if len(df.columns) > 3 and ('qty' in str(df.columns[3]).lower() or 'quantity' in str(df.columns[3]).lower()) else None
                    }
            
            # Process each row
            for idx, row in df.iterrows():
                try:
                    # Skip empty rows
                    if row.isna().all():
                        continue
                    
                    stock_detail = {
                        'source_file': filename,
                        'sheet_name': sheet_name,
                        'row_number': idx + 2  # Excel row number (1-indexed, +1 for header)
                    }
                    
                    # Extract dealer information
                    dealer_col = actual_columns.get('dealer')
                    if dealer_col and dealer_col in df.columns:
                        dealer_value = row.get(dealer_col)
                        if pd.notna(dealer_value):
                            dealer_name = str(dealer_value).strip()
                            # Clean dealer name:
                            # 1. Remove everything in brackets like (DLR)(Pyay) or (TGYI)
                            # 2. If name contains " - ", take only the part before " - "
                            import re
                            # Remove brackets and their content
                            dealer_name = re.sub(r'\s*\([^)]*\)', '', dealer_name).strip()
                            # If contains " - ", take only the part before it
                            if ' - ' in dealer_name:
                                dealer_name = dealer_name.split(' - ')[0].strip()
                            stock_detail['dealer_name'] = dealer_name
                    
                    dealer_id_col = actual_columns.get('dealer_id')
                    if dealer_id_col and dealer_id_col in df.columns:
                        dealer_id_value = row.get(dealer_id_col)
                        if pd.notna(dealer_id_value):
                            stock_detail['dealer_unique_id'] = str(dealer_id_value).strip()
                    
                    # Extract product information
                    product_code_col = actual_columns.get('product_code')
                    if product_code_col and product_code_col in df.columns:
                        product_code_value = row.get(product_code_col)
                        if pd.notna(product_code_value):
                            stock_detail['product_code'] = str(product_code_value).strip()
                    
                    product_name_col = actual_columns.get('product_name')
                    if product_name_col and product_name_col in df.columns:
                        product_name_value = row.get(product_name_col)
                        if pd.notna(product_name_value):
                            stock_detail['product_name'] = str(product_name_value).strip()
                    
                    # Extract quantity
                    quantity_col = actual_columns.get('quantity')
                    if quantity_col and quantity_col in df.columns:
                        quantity_value = row.get(quantity_col)
                        if pd.notna(quantity_value):
                            try:
                                stock_detail['quantity'] = int(float(quantity_value))
                            except (ValueError, TypeError):
                                self.logger.warning(f"Invalid quantity value: {quantity_value}")
                    
                    # Extract dispatch date
                    dispatch_date_col = actual_columns.get('dispatch_date')
                    if dispatch_date_col and dispatch_date_col in df.columns:
                        dispatch_date_value = row.get(dispatch_date_col)
                        if pd.notna(dispatch_date_value):
                            try:
                                if isinstance(dispatch_date_value, datetime):
                                    stock_detail['dispatch_date'] = dispatch_date_value.date()
                                elif isinstance(dispatch_date_value, pd.Timestamp):
                                    stock_detail['dispatch_date'] = dispatch_date_value.date()
                                else:
                                    # Try to parse string date
                                    stock_detail['dispatch_date'] = pd.to_datetime(dispatch_date_value).date()
                            except Exception as e:
                                self.logger.warning(f"Error parsing dispatch date: {str(e)}")
                    
                    # Extract lot number
                    lot_number_col = actual_columns.get('lot_number')
                    if lot_number_col and lot_number_col in df.columns:
                        lot_number_value = row.get(lot_number_col)
                        if pd.notna(lot_number_value):
                            stock_detail['lot_number'] = str(lot_number_value).strip()
                    
                    # Extract expiry date
                    expiry_date_col = actual_columns.get('expiry_date')
                    if expiry_date_col and expiry_date_col in df.columns:
                        expiry_date_value = row.get(expiry_date_col)
                        if pd.notna(expiry_date_value):
                            try:
                                if isinstance(expiry_date_value, datetime):
                                    stock_detail['expiry_date'] = expiry_date_value.date()
                                elif isinstance(expiry_date_value, pd.Timestamp):
                                    stock_detail['expiry_date'] = expiry_date_value.date()
                                else:
                                    stock_detail['expiry_date'] = pd.to_datetime(expiry_date_value).date()
                            except Exception as e:
                                self.logger.warning(f"Error parsing expiry date: {str(e)}")
                    
                    # Extract sales price
                    sales_price_col = actual_columns.get('sales_price')
                    if sales_price_col and sales_price_col in df.columns:
                        sales_price_value = row.get(sales_price_col)
                        if pd.notna(sales_price_value):
                            try:
                                stock_detail['sales_price'] = float(sales_price_value)
                            except (ValueError, TypeError):
                                self.logger.warning(f"Invalid sales price value: {sales_price_value}")
                    
                    # Extract invoice ID
                    invoice_id_col = actual_columns.get('invoice_id')
                    if invoice_id_col and invoice_id_col in df.columns:
                        invoice_id_value = row.get(invoice_id_col)
                        if pd.notna(invoice_id_value):
                            stock_detail['invoice_id'] = str(invoice_id_value).strip()
                    
                    # Only add if we have minimum required fields
                    if 'dealer_name' in stock_detail and 'product_code' in stock_detail:
                        # Set defaults for missing fields
                        stock_detail.setdefault('quantity', 0)
                        stock_detail.setdefault('sales_price', 0.0)
                        stock_detail.setdefault('dispatch_date', datetime.now().date())
                        stock_detail.setdefault('status', 'blocked')
                        stock_detail.setdefault('blocked_quantity', 0)
                        stock_detail.setdefault('available_for_sale', 0)
                        stock_detail.setdefault('sold_quantity', 0)
                        
                        stock_details.append(stock_detail)
                    else:
                        self.logger.debug(f"Skipping row {idx + 2}: missing required fields")
                
                except Exception as e:
                    self.logger.error(f"Error processing row {idx + 2}: {str(e)}")
                    continue
            
            return stock_details
            
        except Exception as e:
            self.logger.error(f"Error processing dataframe: {str(e)}")
            import traceback
            self.logger.error(traceback.format_exc())
            return []

