"""
Migration script to add new columns to email_logs table
Adds: order_id, sender_email, sender_name, receiver_email, receiver_name, subject, body_preview
"""
from app import create_app, db
from app.models import EmailLog
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def migrate_email_logs():
    """Add new columns to email_logs table"""
    app = create_app()
    
    with app.app_context():
        try:
            # Add new columns using ALTER TABLE
            logger.info("Adding new columns to email_logs table...")
            
            # Check if columns already exist
            inspector = db.inspect(db.engine)
            columns = [col['name'] for col in inspector.get_columns('email_logs')]
            
            with db.engine.connect() as conn:
                # SQL Server syntax: ALTER TABLE table_name ADD column_name datatype (no COLUMN keyword)
                # Add order_id column
                if 'order_id' not in columns:
                    conn.execute(db.text("ALTER TABLE email_logs ADD order_id VARCHAR(50) NULL"))
                    try:
                        conn.execute(db.text("CREATE INDEX idx_email_logs_order_id ON email_logs(order_id)"))
                    except:
                        pass  # Index might already exist
                    conn.commit()
                    logger.info("✓ Added order_id column")
                
                # Add sender columns
                if 'sender_email' not in columns:
                    conn.execute(db.text("ALTER TABLE email_logs ADD sender_email VARCHAR(120) NULL"))
                    conn.commit()
                    logger.info("✓ Added sender_email column")
                
                if 'sender_name' not in columns:
                    conn.execute(db.text("ALTER TABLE email_logs ADD sender_name VARCHAR(200) NULL"))
                    conn.commit()
                    logger.info("✓ Added sender_name column")
                
                # Add receiver columns (recipient already exists, but add receiver_name)
                if 'receiver_email' not in columns:
                    conn.execute(db.text("ALTER TABLE email_logs ADD receiver_email VARCHAR(120) NULL"))
                    conn.commit()
                    logger.info("✓ Added receiver_email column")
                
                if 'receiver_name' not in columns:
                    conn.execute(db.text("ALTER TABLE email_logs ADD receiver_name VARCHAR(200) NULL"))
                    conn.commit()
                    logger.info("✓ Added receiver_name column")
                
                # Add email content columns
                if 'subject' not in columns:
                    conn.execute(db.text("ALTER TABLE email_logs ADD subject VARCHAR(500) NULL"))
                    conn.commit()
                    logger.info("✓ Added subject column")
                
                if 'body_preview' not in columns:
                    conn.execute(db.text("ALTER TABLE email_logs ADD body_preview TEXT NULL"))
                    conn.commit()
                    logger.info("✓ Added body_preview column")
                
                # Update existing records: set receiver_email = recipient if receiver_email is NULL
                try:
                    conn.execute(db.text("""
                        UPDATE email_logs 
                        SET receiver_email = recipient 
                        WHERE receiver_email IS NULL AND recipient IS NOT NULL
                    """))
                    conn.commit()
                except Exception as e:
                    logger.warning(f"Could not update existing records: {str(e)}")
                    conn.rollback()
                logger.info("✅ Migration completed successfully!")
                
        except Exception as e:
            logger.error(f"❌ Migration failed: {str(e)}")
            db.session.rollback()
            raise

if __name__ == '__main__':
    migrate_email_logs()

