"""
Migration script to add tax-related columns to orders table
Adds: subtotal, tax_rate, tax_amount columns
"""
import sys
import logging
from app import create_app, db
from app.models import Order
from sqlalchemy import text

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def migrate_add_tax_columns():
    """Add tax-related columns to orders table"""
    app = create_app()
    
    with app.app_context():
        try:
            logger.info("Starting migration: Adding tax columns to orders table...")
            
            # Check if columns already exist
            inspector = db.inspect(db.engine)
            existing_columns = [col['name'] for col in inspector.get_columns('orders')]
            
            columns_to_add = []
            if 'subtotal' not in existing_columns:
                columns_to_add.append(('subtotal', 'FLOAT DEFAULT 0.0'))
            if 'tax_rate' not in existing_columns:
                columns_to_add.append(('tax_rate', 'FLOAT DEFAULT 0.05'))
            if 'tax_amount' not in existing_columns:
                columns_to_add.append(('tax_amount', 'FLOAT DEFAULT 0.0'))
            
            if not columns_to_add:
                logger.info("✓ All tax columns already exist. No migration needed.")
                return
            
            # Add columns
            for col_name, col_type in columns_to_add:
                logger.info(f"Adding column: {col_name}")
                db.session.execute(text(f"ALTER TABLE orders ADD {col_name} {col_type}"))
            
            db.session.commit()
            logger.info("✓ Successfully added tax columns")
            
            # Update existing orders to calculate tax
            logger.info("Updating existing orders with tax calculations...")
            orders = Order.query.filter(
                db.or_(
                    Order.subtotal == None,
                    Order.subtotal == 0
                )
            ).all()
            
            updated_count = 0
            for order in orders:
                if order.total_amount and order.total_amount > 0:
                    # Reverse calculate: if total_amount was already set,
                    # assume it's the subtotal and recalculate
                    # Old orders: total_amount = actual total (no tax)
                    # We'll treat old total as subtotal and add tax
                    order.subtotal = order.total_amount / 1.05  # Remove tax to get subtotal
                    order.tax_rate = 0.05
                    order.tax_amount = order.subtotal * 0.05
                    order.total_amount = order.subtotal + order.tax_amount
                    updated_count += 1
            
            if updated_count > 0:
                db.session.commit()
                logger.info(f"✓ Updated {updated_count} existing orders with tax information")
            else:
                logger.info("No existing orders to update")
            
            logger.info("=" * 60)
            logger.info("✅ MIGRATION COMPLETE!")
            logger.info("=" * 60)
            logger.info("Summary:")
            logger.info(f"  • Added columns: {', '.join([c[0] for c in columns_to_add])}")
            logger.info(f"  • Updated {updated_count} existing orders")
            logger.info("=" * 60)
            
        except Exception as e:
            logger.error(f"❌ Migration failed: {str(e)}")
            db.session.rollback()
            raise

if __name__ == '__main__':
    try:
        migrate_add_tax_columns()
        sys.exit(0)
    except Exception as e:
        logger.error(f"Migration failed: {str(e)}")
        sys.exit(1)

