"""
Script to create company admin user in the database
"""
import sys
import logging
from app import create_app, db
from app.models import User

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def create_company_user():
    """Create company admin user with unique ID"""
    app = create_app()
    
    with app.app_context():
        try:
            # Check if company user already exists
            existing_company = User.query.filter_by(role='company').first()
            
            if existing_company:
                logger.info(f"✓ Company user already exists:")
                logger.info(f"  • Name: {existing_company.name}")
                logger.info(f"  • Unique ID: {existing_company.unique_id}")
                logger.info(f"  • Email: {existing_company.email}")
                return
            
            # Create new company user
            company_user = User(
                name="RB Company Admin",
                pharmacy_name="Quantum Blue Headquarters",
                area="Headquarters",
                email="company@quantumblue.com",  # Change this to actual company email
                phone="+95-9-123456789",
                role="company",
                is_active=True
            )
            
            # Generate unique ID
            company_user.generate_unique_id()
            
            db.session.add(company_user)
            db.session.commit()
            
            logger.info("=" * 60)
            logger.info("✅ COMPANY USER CREATED SUCCESSFULLY!")
            logger.info("=" * 60)
            logger.info("Company Admin Details:")
            logger.info(f"  • Name: {company_user.name}")
            logger.info(f"  • Unique ID: {company_user.unique_id}")
            logger.info(f"  • Email: {company_user.email}")
            logger.info(f"  • Role: {company_user.role}")
            logger.info("=" * 60)
            logger.info("📋 IMPORTANT: Save this Unique ID!")
            logger.info(f"   Unique ID: {company_user.unique_id}")
            logger.info("=" * 60)
            logger.info("🔐 Access Instructions:")
            logger.info("1. Go to the chatbot URL")
            logger.info("2. Enter the Unique ID above")
            logger.info("3. Start chatting to generate reports")
            logger.info("=" * 60)
            
        except Exception as e:
            logger.error(f"❌ Error creating company user: {str(e)}")
            db.session.rollback()
            raise

if __name__ == '__main__':
    try:
        create_company_user()
        sys.exit(0)
    except Exception as e:
        logger.error(f"Script failed: {str(e)}")
        sys.exit(1)

