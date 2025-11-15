"""
Migration script to add new columns to order_items table
Adds: adjusted_quantity, adjusted_expiry_date, adjustment_reason, pending_quantity, updated_at
"""
from app import create_app, db
from app.models import OrderItem
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def migrate_order_items():
    """Add new columns to order_items table"""
    app = create_app()
    
    with app.app_context():
        try:
            logger.info("Adding new columns to order_items table...")
            
            # Check if columns already exist
            inspector = db.inspect(db.engine)
            columns = [col['name'] for col in inspector.get_columns('order_items')]
            
            with db.engine.connect() as conn:
                # SQL Server syntax: ALTER TABLE table_name ADD column_name datatype
                if 'adjusted_quantity' not in columns:
                    conn.execute(db.text("ALTER TABLE order_items ADD adjusted_quantity INT NULL"))
                    conn.commit()
                    logger.info("✓ Added adjusted_quantity column")
                
                if 'adjusted_expiry_date' not in columns:
                    conn.execute(db.text("ALTER TABLE order_items ADD adjusted_expiry_date DATE NULL"))
                    conn.commit()
                    logger.info("✓ Added adjusted_expiry_date column")
                
                if 'adjustment_reason' not in columns:
                    conn.execute(db.text("ALTER TABLE order_items ADD adjustment_reason TEXT NULL"))
                    conn.commit()
                    logger.info("✓ Added adjustment_reason column")
                
                if 'pending_quantity' not in columns:
                    conn.execute(db.text("ALTER TABLE order_items ADD pending_quantity INT DEFAULT 0"))
                    conn.commit()
                    logger.info("✓ Added pending_quantity column")
                
                if 'updated_at' not in columns:
                    conn.execute(db.text("ALTER TABLE order_items ADD updated_at DATETIME NULL"))
                    conn.commit()
                    logger.info("✓ Added updated_at column")
                
                logger.info("✅ Migration completed successfully!")
                
        except Exception as e:
            logger.error(f"❌ Migration failed: {str(e)}")
            db.session.rollback()
            raise

if __name__ == '__main__':
    migrate_order_items()

