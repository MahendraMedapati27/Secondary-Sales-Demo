"""
Migration script to add adjusted_lot_number column to order_items table
"""
from app import create_app, db
from app.models import OrderItem
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def migrate_order_items_lot_number():
    """Add adjusted_lot_number column to order_items table"""
    app = create_app()
    
    with app.app_context():
        try:
            # Add new column using ALTER TABLE
            logger.info("Adding adjusted_lot_number column to order_items table...")
            
            # Check if column already exists
            inspector = db.inspect(db.engine)
            columns = [col['name'] for col in inspector.get_columns('order_items')]
            
            with db.engine.connect() as conn:
                # SQL Server syntax: ALTER TABLE table_name ADD column_name datatype (no COLUMN keyword)
                if 'adjusted_lot_number' not in columns:
                    conn.execute(db.text("ALTER TABLE order_items ADD adjusted_lot_number VARCHAR(100) NULL"))
                    conn.commit()
                    logger.info("✓ Added adjusted_lot_number column")
                else:
                    logger.info("✓ adjusted_lot_number column already exists")
                
                logger.info("✅ Migration completed successfully!")
                
        except Exception as e:
            logger.error(f"❌ Migration failed: {str(e)}")
            db.session.rollback()
            raise

if __name__ == '__main__':
    migrate_order_items_lot_number()

