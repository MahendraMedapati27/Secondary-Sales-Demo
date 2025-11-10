"""
Migration script to add authentication columns to users table
Adds: password_hash, email_verified, otp_secret, otp_created_at
"""
import sys
import logging
from app import create_app, db
from app.models import User
from sqlalchemy import text

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def migrate_add_user_auth_columns():
    """Add authentication-related columns to users table"""
    app = create_app()
    
    with app.app_context():
        try:
            logger.info("Starting migration: Adding auth columns to users table...")
            
            # Check if columns already exist
            inspector = db.inspect(db.engine)
            existing_columns = [col['name'] for col in inspector.get_columns('users')]
            
            columns_to_add = []
            if 'password_hash' not in existing_columns:
                columns_to_add.append(('password_hash', 'NVARCHAR(256) NULL'))
            if 'email_verified' not in existing_columns:
                columns_to_add.append(('email_verified', 'BIT DEFAULT 0'))
            if 'otp_secret' not in existing_columns:
                columns_to_add.append(('otp_secret', 'NVARCHAR(10) NULL'))
            if 'otp_created_at' not in existing_columns:
                columns_to_add.append(('otp_created_at', 'DATETIME NULL'))
            
            if not columns_to_add:
                logger.info("✓ All auth columns already exist. No migration needed.")
                return
            
            # Add columns
            for col_name, col_type in columns_to_add:
                logger.info(f"Adding column: {col_name}")
                db.session.execute(text(f"ALTER TABLE users ADD {col_name} {col_type}"))
            
            db.session.commit()
            logger.info("✓ Successfully added auth columns")
            
            logger.info("=" * 60)
            logger.info("✅ MIGRATION COMPLETE!")
            logger.info("=" * 60)
            logger.info("Summary:")
            logger.info(f"  • Added columns: {', '.join([c[0] for c in columns_to_add])}")
            logger.info("  • All users can now use password authentication")
            logger.info("  • OTP system ready for email verification")
            logger.info("=" * 60)
            
        except Exception as e:
            logger.error(f"❌ Migration failed: {str(e)}")
            db.session.rollback()
            raise

if __name__ == '__main__':
    try:
        migrate_add_user_auth_columns()
        sys.exit(0)
    except Exception as e:
        logger.error(f"Migration failed: {str(e)}")
        sys.exit(1)

