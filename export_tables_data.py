"""
Export data from users, foc, products, and dealer_wise_stock_details tables
"""

import os
import sys
import csv
from pathlib import Path
from datetime import datetime

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from app import create_app, db
from app.models import User, FOC, Product, DealerWiseStockDetails
from config import Config
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def export_table_to_csv(model, filename):
    """Export a table to CSV file"""
    try:
        records = model.query.all()
        logger.info(f"Exporting {len(records)} records from {model.__tablename__}...")
        
        if not records:
            logger.warning(f"No records found in {model.__tablename__}")
            return
        
        # Get column names from the first record's to_dict() if available, otherwise use model columns
        if hasattr(records[0], 'to_dict'):
            columns = list(records[0].to_dict().keys())
        else:
            columns = [column.name for column in model.__table__.columns]
        
        # Write to CSV
        with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=columns)
            writer.writeheader()
            
            for record in records:
                if hasattr(record, 'to_dict'):
                    row = record.to_dict()
                else:
                    row = {col: getattr(record, col, None) for col in columns}
                
                # Convert datetime objects to strings
                for key, value in row.items():
                    if isinstance(value, datetime):
                        row[key] = value.isoformat()
                    elif value is None:
                        row[key] = ''
                
                writer.writerow(row)
        
        logger.info(f"✓ Exported {len(records)} records to {filename}")
        
    except Exception as e:
        logger.error(f"Error exporting {model.__tablename__}: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())

def main():
    """Main execution function"""
    logger.info("=" * 60)
    logger.info("Exporting Tables Data")
    logger.info("=" * 60)
    
    app = create_app(Config)
    
    with app.app_context():
        try:
            # Create exports directory
            exports_dir = Path("table_exports")
            exports_dir.mkdir(exist_ok=True)
            
            # Export each table
            export_table_to_csv(User, exports_dir / "users.csv")
            export_table_to_csv(FOC, exports_dir / "foc.csv")
            export_table_to_csv(Product, exports_dir / "products.csv")
            export_table_to_csv(DealerWiseStockDetails, exports_dir / "dealer_wise_stock_details.csv")
            
            logger.info("\n" + "=" * 60)
            logger.info("✓ All exports completed!")
            logger.info(f"Files saved in: {exports_dir.absolute()}")
            logger.info("=" * 60)
            
        except Exception as e:
            logger.error(f"\n❌ Error during export: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            sys.exit(1)

if __name__ == '__main__':
    main()

