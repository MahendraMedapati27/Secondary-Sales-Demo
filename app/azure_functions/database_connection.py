"""
Database Connection Module for Azure Function
Handles database connectivity using environment variables
"""

import os
import logging
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from urllib.parse import quote_plus

logger = logging.getLogger(__name__)


def get_database_connection_string():
    """
    Get database connection string from environment variables
    
    Returns:
        Connection string for SQL Server
    """
    sql_server = os.getenv('SQL_SERVER')
    sql_database = os.getenv('SQL_DATABASE')
    sql_username = os.getenv('SQL_USERNAME')
    sql_password = os.getenv('SQL_PASSWORD')
    
    if not all([sql_server, sql_database, sql_username, sql_password]):
        raise ValueError("Database environment variables not properly configured")
    
    # URL encode the password to handle special characters
    encoded_password = quote_plus(sql_password)
    
    # Build connection string for SQL Server using pymssql driver
    connection_string = (
        f"mssql+pymssql://{sql_username}:{encoded_password}@{sql_server}/{sql_database}"
        f"?charset=utf8&tds_version=7.4&timeout=30&login_timeout=15"
    )
    
    return connection_string


def get_db_connection():
    """
    Get database engine
    
    Returns:
        SQLAlchemy engine
    """
    try:
        connection_string = get_database_connection_string()
        
        # Create engine with connection pooling
        engine = create_engine(
            connection_string,
            pool_pre_ping=True,  # Verify connections before using
            pool_size=5,
            max_overflow=10,
            pool_recycle=1800,  # Recycle connections after 30 minutes
            pool_timeout=30,
            echo=False,  # Set to True for SQL query logging
            connect_args={
                'login_timeout': 15,
                'timeout': 30,
                'tds_version': '7.4',
                'charset': 'utf8',
                'autocommit': False,
            }
        )
        
        logger.info("Database engine created successfully")
        return engine
        
    except Exception as e:
        logger.error(f"Error creating database engine: {str(e)}")
        raise


def init_db():
    """
    Initialize database session
    
    Returns:
        SQLAlchemy session
    """
    try:
        engine = get_db_connection()
        Session = sessionmaker(bind=engine)
        session = Session()
        
        # Test the connection
        session.execute(text("SELECT 1"))
        
        logger.info("Database session initialized successfully")
        return session
        
    except Exception as e:
        logger.error(f"Error initializing database session: {str(e)}")
        raise


def test_connection():
    """
    Test database connection
    
    Returns:
        True if connection successful, False otherwise
    """
    try:
        session = init_db()
        result = session.execute(text("SELECT 1 as test"))
        test_value = result.fetchone()[0]
        session.close()
        
        if test_value == 1:
            logger.info("Database connection test successful")
            return True
        else:
            logger.error("Database connection test failed: unexpected result")
            return False
            
    except Exception as e:
        logger.error(f"Database connection test failed: {str(e)}")
        return False


def ensure_processed_files_table(session):
    """
    Ensure the processed_files tracking table exists
    Creates table if it doesn't exist (idempotent operation)
    
    Args:
        session: SQLAlchemy session
    """
    try:
        # Create table if not exists (SQL Server syntax)
        create_table_sql = text("""
            IF NOT EXISTS (SELECT * FROM sys.objects WHERE object_id = OBJECT_ID(N'[dbo].[processed_csv_files]') AND type in (N'U'))
            BEGIN
                CREATE TABLE [dbo].[processed_csv_files] (
                    id INT IDENTITY(1,1) PRIMARY KEY,
                    blob_name NVARCHAR(500) NOT NULL,
                    file_name NVARCHAR(255) NOT NULL,
                    blob_size BIGINT NULL,
                    processed_at DATETIME2 NOT NULL DEFAULT GETUTCDATE(),
                    records_imported INT NULL,
                    records_skipped INT NULL,
                    records_errored INT NULL,
                    status NVARCHAR(50) NOT NULL DEFAULT 'success',
                    error_message NVARCHAR(MAX) NULL,
                    CONSTRAINT UQ_processed_csv_files_blob_name UNIQUE (blob_name)
                );
                
                CREATE INDEX IX_processed_csv_files_processed_at ON [dbo].[processed_csv_files] (processed_at DESC);
                CREATE INDEX IX_processed_csv_files_file_name ON [dbo].[processed_csv_files] (file_name);
            END
        """)
        
        session.execute(create_table_sql)
        session.commit()
        logger.info("Processed files tracking table ensured")
        
    except Exception as e:
        logger.error(f"Error ensuring processed_files table: {str(e)}")
        session.rollback()
        raise


def is_file_already_processed(session, blob_name: str) -> bool:
    """
    Check if a file has already been processed
    
    Args:
        session: SQLAlchemy session
        blob_name: Full blob path/name
        
    Returns:
        True if file was already processed, False otherwise
    """
    try:
        # Ensure table exists
        ensure_processed_files_table(session)
        
        query = text("""
            SELECT COUNT(*) FROM processed_csv_files 
            WHERE blob_name = :blob_name AND status = 'success'
        """)
        
        result = session.execute(query, {'blob_name': blob_name})
        count = result.fetchone()[0]
        
        return count > 0
        
    except Exception as e:
        logger.error(f"Error checking if file processed: {str(e)}")
        # If we can't check, assume not processed to be safe
        return False


def mark_file_as_processed(session, blob_name: str, file_name: str, blob_size: int, 
                           records_imported: int = 0, records_skipped: int = 0, 
                           records_errored: int = 0, status: str = 'success', 
                           error_message: str = None):
    """
    Mark a file as processed in the tracking table
    
    Args:
        session: SQLAlchemy session
        blob_name: Full blob path/name
        file_name: Just the filename
        blob_size: Size of blob in bytes
        records_imported: Number of records successfully imported
        records_skipped: Number of records skipped
        records_errored: Number of records with errors
        status: Processing status ('success', 'partial', 'failed')
        error_message: Error message if processing failed
    """
    try:
        # Ensure table exists
        ensure_processed_files_table(session)
        
        # Insert or update processing record
        insert_sql = text("""
            INSERT INTO processed_csv_files 
                (blob_name, file_name, blob_size, records_imported, records_skipped, 
                 records_errored, status, error_message, processed_at)
            VALUES 
                (:blob_name, :file_name, :blob_size, :records_imported, :records_skipped, 
                 :records_errored, :status, :error_message, GETUTCDATE())
        """)
        
        session.execute(insert_sql, {
            'blob_name': blob_name,
            'file_name': file_name,
            'blob_size': blob_size,
            'records_imported': records_imported,
            'records_skipped': records_skipped,
            'records_errored': records_errored,
            'status': status,
            'error_message': error_message
        })
        
        session.commit()
        logger.info(f"Marked file as processed: {file_name}")
        
    except Exception as e:
        logger.error(f"Error marking file as processed: {str(e)}")
        session.rollback()
        # Don't raise - this is non-critical


def get_processing_history(session, limit: int = 100):
    """
    Get recent file processing history
    
    Args:
        session: SQLAlchemy session
        limit: Maximum number of records to return
        
    Returns:
        List of processing records
    """
    try:
        query = text("""
            SELECT TOP (:limit)
                id, blob_name, file_name, blob_size, processed_at,
                records_imported, records_skipped, records_errored, status, error_message
            FROM processed_csv_files
            ORDER BY processed_at DESC
        """)
        
        result = session.execute(query, {'limit': limit})
        return result.fetchall()
        
    except Exception as e:
        logger.error(f"Error getting processing history: {str(e)}")
        return []
