"""
Company Report Service - Generate and export database reports
Allows company users to extract data from any table with column filtering
"""
import logging
import csv
import io
from datetime import datetime
from flask import current_app
from app import db
from app.models import (
    User, Order, OrderItem, Product, Customer, CartItem, 
    FOC, DealerWiseStockDetails, PendingOrderProducts, EmailLog
)
from app.email_utils import send_email_with_attachment, create_email_template

logger = logging.getLogger(__name__)

class CompanyReportService:
    """Service for generating company reports from database"""
    
    # Available tables for export
    AVAILABLE_TABLES = {
        'users': {
            'model': User,
            'name': 'Users (MRs & Distributors)',
            'columns': ['id', 'unique_id', 'name', 'pharmacy_name', 'area', 'discount', 
                       'email', 'phone', 'role', 'is_active', 'created_at', 'updated_at']
        },
        'orders': {
            'model': Order,
            'name': 'Orders',
            'columns': ['id', 'order_id', 'mr_id', 'mr_unique_id', 'customer_id', 
                       'customer_unique_id', 'subtotal', 'tax_rate', 'tax_amount', 
                       'total_amount', 'order_stage', 'status', 'distributor_confirmed_by',
                       'distributor_confirmed_at', 'created_at', 'updated_at']
        },
        'order_items': {
            'model': OrderItem,
            'name': 'Order Items',
            'columns': ['id', 'order_id', 'product_id', 'product_code', 'product_name',
                       'quantity', 'free_quantity', 'unit_price', 'total_price', 'created_at']
        },
        'products': {
            'model': Product,
            'name': 'Products (Master)',
            'columns': ['id', 'product_code', 'product_name', 'category', 'sales_price',
                       'unit', 'is_active', 'created_at', 'updated_at']
        },
        'customers': {
            'model': Customer,
            'name': 'Customers',
            'columns': ['id', 'customer_id', 'name', 'phone', 'address', 'area',
                       'mr_id', 'mr_unique_id', 'is_active', 'created_at', 'updated_at']
        },
        'cart_items': {
            'model': CartItem,
            'name': 'Cart Items',
            'columns': ['id', 'user_id', 'product_id', 'product_code', 'quantity',
                       'free_quantity', 'created_at']
        },
        'foc_schemes': {
            'model': FOC,
            'name': 'FOC Schemes',
            'columns': ['id', 'product_code', 'scheme_1', 'scheme_2', 'scheme_3',
                       'is_active', 'created_at', 'updated_at']
        },
        'dealer_stock': {
            'model': DealerWiseStockDetails,
            'name': 'Dealer Stock Details',
            'columns': ['id', 'product_code', 'product_id', 'dealer_name', 'dispatch_date',
                       'received_quantity', 'blocked_quantity', 'sold_quantity',
                       'available_for_sale', 'expiration_date', 'lot_number', 'status',
                       'confirmed_at', 'created_at']
        },
        'pending_orders': {
            'model': PendingOrderProducts,
            'name': 'Pending Order Products',
            'columns': ['id', 'original_order_id', 'product_code', 'product_name',
                       'requested_quantity', 'user_id', 'user_email', 'status',
                       'fulfilled_at', 'created_at', 'updated_at']
        },
        'email_logs': {
            'model': EmailLog,
            'name': 'Email Logs',
            'columns': ['id', 'recipient', 'email_type', 'status', 'error_message',
                       'sent_at']
        }
    }
    
    def get_available_tables(self):
        """Get list of available tables for export"""
        return {
            table_key: {
                'name': table_info['name'],
                'columns': table_info['columns']
            }
            for table_key, table_info in self.AVAILABLE_TABLES.items()
        }
    
    def generate_report(self, table_key, selected_columns=None, filters=None):
        """
        Generate CSV report for specified table
        
        Args:
            table_key: Key of the table to export
            selected_columns: List of columns to include (None = all columns)
            filters: Dictionary of filters to apply (optional)
        
        Returns:
            Dictionary with csv_data, filename, row_count
        """
        try:
            if table_key not in self.AVAILABLE_TABLES:
                return {
                    'success': False,
                    'error': f"Invalid table: {table_key}"
                }
            
            table_info = self.AVAILABLE_TABLES[table_key]
            model = table_info['model']
            available_columns = table_info['columns']
            
            # Determine columns to export
            if selected_columns and len(selected_columns) > 0:
                # Validate selected columns
                columns_to_export = [col for col in selected_columns if col in available_columns]
                if not columns_to_export:
                    return {
                        'success': False,
                        'error': 'No valid columns selected'
                    }
            else:
                columns_to_export = available_columns
            
            # Query the data
            query = db.session.query(model)
            
            # Apply filters if provided
            if filters:
                query = self._apply_filters(query, model, filters)
            
            # Get all records
            records = query.all()
            
            if not records:
                return {
                    'success': False,
                    'error': f'No data found in {table_info["name"]}'
                }
            
            # Generate CSV
            csv_buffer = io.StringIO()
            csv_writer = csv.writer(csv_buffer)
            
            # Write header
            csv_writer.writerow(columns_to_export)
            
            # Write data rows
            for record in records:
                row = []
                for col in columns_to_export:
                    value = getattr(record, col, '')
                    
                    # Format datetime objects
                    if isinstance(value, datetime):
                        value = value.strftime('%Y-%m-%d %H:%M:%S')
                    
                    # Convert None to empty string
                    if value is None:
                        value = ''
                    
                    row.append(value)
                
                csv_writer.writerow(row)
            
            # Get CSV data
            csv_data = csv_buffer.getvalue()
            csv_buffer.close()
            
            # Generate filename
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"RB_Report_{table_info['name'].replace(' ', '_')}_{timestamp}.csv"
            
            logger.info(f"✓ Generated report: {filename} with {len(records)} rows")
            
            return {
                'success': True,
                'csv_data': csv_data,
                'filename': filename,
                'row_count': len(records),
                'column_count': len(columns_to_export),
                'table_name': table_info['name']
            }
            
        except Exception as e:
            logger.error(f"Error generating report: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def _apply_filters(self, query, model, filters):
        """Apply filters to query"""
        try:
            # Example filters:
            # - date_range: {'start': '2025-01-01', 'end': '2025-12-31'}
            # - area: 'Magwe'
            # - status: 'pending'
            
            if 'date_range' in filters:
                date_range = filters['date_range']
                if 'start' in date_range and hasattr(model, 'created_at'):
                    query = query.filter(model.created_at >= date_range['start'])
                if 'end' in date_range and hasattr(model, 'created_at'):
                    query = query.filter(model.created_at <= date_range['end'])
            
            if 'area' in filters and hasattr(model, 'area'):
                query = query.filter(model.area == filters['area'])
            
            if 'status' in filters and hasattr(model, 'status'):
                query = query.filter(model.status == filters['status'])
            
            if 'role' in filters and hasattr(model, 'role'):
                query = query.filter(model.role == filters['role'])
            
            return query
            
        except Exception as e:
            logger.warning(f"Error applying filters: {str(e)}")
            return query
    
    def send_report_email(self, recipient_email, table_key, report_data, selected_columns=None):
        """
        Send report via email with CSV attachment
        
        Args:
            recipient_email: Email address to send report
            table_key: Table key for report title
            report_data: Report data from generate_report()
            selected_columns: List of selected columns (for summary)
        """
        try:
            if not report_data.get('success'):
                return {
                    'success': False,
                    'error': report_data.get('error', 'Report generation failed')
                }
            
            table_name = report_data['table_name']
            
            # Create email content
            column_info = ""
            if selected_columns and len(selected_columns) > 0:
                column_info = f"<p><strong>Columns Included:</strong> {', '.join(selected_columns)}</p>"
            else:
                column_info = "<p><strong>Columns:</strong> All available columns</p>"
            
            content = f"""
                <h2 style='color:#1e40af; margin-top:0;'>📊 Database Report Ready</h2>
                
                <p>Dear Company Admin,</p>
                
                <p>Your requested database report has been generated and is attached to this email.</p>
                
                <div class='info-box'>
                    <h3 style='margin-top: 0;'>Report Details</h3>
                    <p style='margin: 5px 0;'><strong>Table:</strong> {table_name}</p>
                    <p style='margin: 5px 0;'><strong>Total Records:</strong> {report_data['row_count']:,}</p>
                    <p style='margin: 5px 0;'><strong>Columns Exported:</strong> {report_data['column_count']}</p>
                    <p style='margin: 5px 0;'><strong>File Name:</strong> {report_data['filename']}</p>
                    <p style='margin: 5px 0;'><strong>Generated:</strong> {datetime.now().strftime('%B %d, %Y at %I:%M %p')}</p>
                </div>
                
                {column_info}
                
                <div class='success-box'>
                    <h3 style='margin-top: 0;'>✅ How to Use This Report</h3>
                    <p style='margin: 5px 0;'>• Open the attached CSV file in Excel or Google Sheets</p>
                    <p style='margin: 5px 0;'>• Use filters and pivot tables for analysis</p>
                    <p style='margin: 5px 0;'>• Create charts and visualizations</p>
                    <p style='margin: 5px 0;'>• Share insights with your team</p>
                </div>
                
                <p style='margin-top: 20px;'>If you need any additional reports or have questions, please request them through the chatbot.</p>
            """
            
            html_content = create_email_template(
                title=f"Report: {table_name}",
                content=content,
                footer_text="This report was generated by RB (Powered by Quantum Blue AI)"
            )
            
            # Send email with attachment
            success = send_email_with_attachment(
                to_email=recipient_email,
                subject=f"📊 Database Report: {table_name}",
                html_content=html_content,
                csv_data=report_data['csv_data'],
                filename=report_data['filename'],
                email_type='company_report'
            )
            
            if success:
                logger.info(f"✓ Report email sent to {recipient_email}: {report_data['filename']}")
                return {
                    'success': True,
                    'message': f"Report sent successfully to {recipient_email}"
                }
            else:
                return {
                    'success': False,
                    'error': 'Failed to send email'
                }
            
        except Exception as e:
            logger.error(f"Error sending report email: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }

