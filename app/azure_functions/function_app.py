import azure.functions as func
import logging
import os
import io
from datetime import datetime
from typing import Optional
from azure.storage.blob import BlobServiceClient

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = func.FunctionApp()

# Import local modules (copied from main app)
from excel_extractor import ExcelExtractor
from stock_importer import StockImporter
from database_connection import (
    get_db_connection, 
    init_db, 
    is_file_already_processed, 
    mark_file_as_processed
)

@app.event_grid_trigger(arg_name="event")
def dealer_stock_csv_processor(event: func.EventGridEvent):
    """
    Azure Function triggered by Event Grid when a new CSV file is added to:
    Container: gold
    Path: Dealer Wise Stock Details/Dealer_Wise_Stock.csv/
    
    This function:
    1. Downloads the CSV file from blob storage
    2. Extracts dealer-wise stock details
    3. Imports the data to the database
    """
    try:
        # Get event data
        event_data = event.get_json()
        
        logger.info(f"🔔 Event Grid trigger activated!")
        logger.info(f"📧 Event Type: {event.event_type}")
        logger.info(f"📧 Event Subject: {event.subject}")
        
        # Extract blob information from event
        blob_url = event_data.get('url')
        blob_size = event_data.get('contentLength', 0)
        
        # Parse blob name from URL or subject
        # Subject format: /blobServices/default/containers/{container}/blobs/{path}
        subject = event.subject
        blob_name = subject.split('/blobs/')[-1] if '/blobs/' in subject else None
        
        if not blob_name:
            logger.error("❌ Could not extract blob name from event")
            return
        
        logger.info(f"📄 Processing blob: {blob_name}")
        logger.info(f"📊 Blob size: {blob_size} bytes ({blob_size / 1024:.2f} KB)")
        
        # Extract filename from blob path
        filename = os.path.basename(blob_name)
        logger.info(f"📝 Filename: {filename}")
        
        # Validate file type
        if not filename.lower().endswith('.csv'):
            logger.warning(f"⚠️ Skipping non-CSV file: {filename}")
            return
        
        # Only process files in the specific path (container name not included in blob_name from event)
        expected_path = "Dealer Wise Stock Details/Dealer_Wise_Stock.csv/"
        if not blob_name.startswith(expected_path):
            logger.warning(f"⚠️ Skipping blob outside target path: {blob_name}")
            logger.warning(f"   Expected path: {expected_path}")
            logger.warning(f"   Actual blob: {blob_name}")
            return
        
        # Check if file was already processed
        logger.info("🔍 Checking if file was already processed...")
        db_session = None
        try:
            db_session = init_db()
            
            if is_file_already_processed(db_session, blob_name):
                logger.info(f"⏭️ File already processed, skipping: {filename}")
                logger.info(f"   Blob path: {blob_name}")
                logger.info("   This prevents duplicate imports.")
                if db_session:
                    db_session.close()
                return
            else:
                logger.info(f"✅ File is new, will process: {filename}")
            
            if db_session:
                db_session.close()
                
        except Exception as check_error:
            logger.warning(f"⚠️ Error checking file status: {str(check_error)}")
            logger.info("Proceeding with processing as safety measure...")
            if db_session:
                db_session.close()
        
        # Download blob content using Azure Storage SDK
        logger.info("📥 Downloading blob content...")
        try:
            # Get connection string from environment
            connection_string = os.environ.get('AzureWebJobsStorage')
            if not connection_string:
                raise Exception("AzureWebJobsStorage connection string not found")
            
            # Create blob service client
            blob_service_client = BlobServiceClient.from_connection_string(connection_string)
            
            # Parse container and blob path
            # Note: blob_name from Event Grid doesn't include container name
            container_name = "gold"
            blob_path = blob_name  # Already doesn't include container name
            
            # Get blob client
            blob_client = blob_service_client.get_blob_client(container=container_name, blob=blob_path)
            
            # Download blob
            blob_content = blob_client.download_blob().readall()
            
        except Exception as download_error:
            logger.error(f"❌ Error downloading blob: {str(download_error)}")
            raise
        
        if not blob_content:
            logger.error("❌ Blob content is empty")
            return
        
        logger.info(f"✅ Successfully read {len(blob_content)} bytes from blob")
        
        # Initialize services
        logger.info("🔧 Initializing services...")
        excel_extractor = ExcelExtractor()
        
        # Initialize database connection
        db_session = None
        try:
            db_session = init_db()
            stock_importer = StockImporter(db=db_session)
            
            # Extract stock details from CSV
            logger.info("🔍 Extracting stock details from CSV...")
            stock_details = excel_extractor.extract_stock_details(
                file_content=blob_content,
                filename=filename
            )
            
            if not stock_details:
                logger.warning("⚠️ No stock details extracted from CSV")
                return
            
            logger.info(f"✅ Extracted {len(stock_details)} stock detail records")
            
            # Import stock details to database
            # 🚀 PRODUCTION MODE: Import ALL records
            # For testing specific rows, set test_row_start and test_row_end (e.g., test_row_start=201, test_row_end=209)
            logger.info("💾 Importing stock details to database...")
            logger.info("🚀 PRODUCTION MODE: Importing ALL records")
            import_result = stock_importer.import_stock_details(stock_details, test_row_start=None, test_row_end=None)
            
            if import_result.get('success'):
                imported_count = import_result.get('imported_count', 0)
                skipped_count = import_result.get('skipped_count', 0)
                error_count = import_result.get('error_count', 0)
                total_records = import_result.get('total_records', 0)
                test_mode = import_result.get('test_mode', False)
                test_row_index = import_result.get('test_row_index')
                
                logger.info(f"✅ Import completed successfully!")
                if test_mode:
                    test_row_start = import_result.get('test_row_start')
                    test_row_end = import_result.get('test_row_end')
                    if test_row_start is not None and test_row_end is not None:
                        logger.info(f"   📊 Total records in file: {total_records}")
                        logger.info(f"   🧪 TESTING MODE: Processed rows #{test_row_start + 1} to #{test_row_end + 1}")
                logger.info(f"   📈 Imported: {imported_count}")
                logger.info(f"   ⏭️ Skipped: {skipped_count}")
                logger.info(f"   ❌ Errors: {error_count}")
                
                # Log detailed skip reasons
                skip_reasons = import_result.get('skip_reasons', [])
                if skip_reasons:
                    logger.info(f"   📋 Detailed Skip Reasons ({len(skip_reasons)} total):")
                    for reason in skip_reasons[:10]:  # Log first 10 skip reasons
                        logger.info(f"      • {reason}")
                
                # Log errors if any
                if error_count > 0:
                    errors = import_result.get('errors', [])
                    logger.error(f"   ⚠️ Errors ({error_count} total):")
                    for error in errors[:5]:  # Log first 5 errors
                        logger.error(f"      • Row #{error.get('row_number', 'N/A')}: {error.get('error', 'Unknown error')}")
                
                # Mark file as processed
                status = 'success'
                if error_count > 0 and imported_count == 0:
                    status = 'failed'
                elif error_count > 0:
                    status = 'partial'
                
                logger.info(f"📝 Recording file as processed (status: {status})...")
                mark_file_as_processed(
                    session=db_session,
                    blob_name=blob_name,
                    file_name=filename,
                    blob_size=blob_size,
                    records_imported=imported_count,
                    records_skipped=skipped_count,
                    records_errored=error_count,
                    status=status,
                    error_message=None if status == 'success' else str(import_result.get('errors', [])[:3])
                )
                logger.info("✅ File marked as processed - will not be processed again")
                
            else:
                error_msg = import_result.get('error', 'Unknown error')
                logger.error(f"❌ Import failed: {error_msg}")
                
                # Mark file as failed (so we can retry manually if needed)
                logger.info("📝 Recording file as failed...")
                mark_file_as_processed(
                    session=db_session,
                    blob_name=blob_name,
                    file_name=filename,
                    blob_size=blob_size,
                    records_imported=0,
                    records_skipped=0,
                    records_errored=len(stock_details),
                    status='failed',
                    error_message=error_msg[:1000]  # Limit error message length
                )
            
            # Commit the transaction
            if db_session:
                db_session.commit()
                logger.info("✅ Database transaction committed")
                
        except Exception as db_error:
            logger.error(f"❌ Database error: {str(db_error)}")
            if db_session:
                db_session.rollback()
                logger.info("🔄 Database transaction rolled back")
            raise
        finally:
            if db_session:
                db_session.close()
                logger.info("🔒 Database connection closed")
        
        logger.info("🎉 Function execution completed successfully!")
        
    except Exception as e:
        logger.error(f"❌ Function execution failed: {str(e)}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise

@app.function_name("HealthCheck")
@app.route(route="health", methods=["GET"])
def health_check(req: func.HttpRequest) -> func.HttpResponse:
    """Health check endpoint for monitoring"""
    try:
        # Check database connection
        db_session = init_db()
        db_session.close()
        
        return func.HttpResponse(
            body='{"status": "healthy", "service": "dealer-stock-csv-processor"}',
            status_code=200,
            mimetype="application/json"
        )
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        return func.HttpResponse(
            body=f'{{"status": "unhealthy", "error": "{str(e)}"}}',
            status_code=503,
            mimetype="application/json"
        )

@app.function_name("ProcessingHistory")
@app.route(route="processing-history", methods=["GET"])
def processing_history(req: func.HttpRequest) -> func.HttpResponse:
    """
    Get recent file processing history
    Query params:
        - limit: Number of records to return (default: 50, max: 500)
        - status: Filter by status (success, partial, failed)
    """
    try:
        # Get query parameters
        limit = int(req.params.get('limit', '50'))
        limit = min(limit, 500)  # Cap at 500
        status_filter = req.params.get('status', None)
        
        db_session = init_db()
        
        # Import the function
        from database_connection import get_processing_history
        
        history = get_processing_history(db_session, limit=limit)
        db_session.close()
        
        # Format results
        results = []
        for row in history:
            record = {
                'id': row[0],
                'blob_name': row[1],
                'file_name': row[2],
                'blob_size': row[3],
                'processed_at': row[4].isoformat() if row[4] else None,
                'records_imported': row[5],
                'records_skipped': row[6],
                'records_errored': row[7],
                'status': row[8],
                'error_message': row[9]
            }
            
            # Apply status filter if provided
            if status_filter is None or record['status'] == status_filter:
                results.append(record)
        
        import json
        return func.HttpResponse(
            body=json.dumps({
                'count': len(results),
                'limit': limit,
                'status_filter': status_filter,
                'records': results
            }, indent=2),
            status_code=200,
            mimetype="application/json"
        )
        
    except Exception as e:
        logger.error(f"Error getting processing history: {str(e)}")
        import json
        return func.HttpResponse(
            body=json.dumps({
                'error': str(e),
                'message': 'Failed to retrieve processing history'
            }),
            status_code=500,
            mimetype="application/json"
        )

@app.function_name("ProcessedFileCheck")
@app.route(route="check-file", methods=["GET"])
def check_file_processed(req: func.HttpRequest) -> func.HttpResponse:
    """
    Check if a specific file has been processed
    Query params:
        - blob_name: Full blob path to check (required)
        - file_name: Just filename to search (optional)
    """
    try:
        blob_name = req.params.get('blob_name')
        file_name = req.params.get('file_name')
        
        if not blob_name and not file_name:
            import json
            return func.HttpResponse(
                body=json.dumps({
                    'error': 'blob_name or file_name parameter required'
                }),
                status_code=400,
                mimetype="application/json"
            )
        
        db_session = init_db()
        
        if blob_name:
            is_processed = is_file_already_processed(db_session, blob_name)
            search_key = blob_name
            search_type = 'blob_name'
        else:
            # Search by filename
            from sqlalchemy import text
            query = text("""
                SELECT COUNT(*) FROM processed_csv_files 
                WHERE file_name = :file_name AND status = 'success'
            """)
            result = db_session.execute(query, {'file_name': file_name})
            count = result.fetchone()[0]
            is_processed = count > 0
            search_key = file_name
            search_type = 'file_name'
        
        db_session.close()
        
        import json
        return func.HttpResponse(
            body=json.dumps({
                'search_type': search_type,
                'search_value': search_key,
                'is_processed': is_processed,
                'message': 'File has been processed' if is_processed else 'File is new/not processed'
            }, indent=2),
            status_code=200,
            mimetype="application/json"
        )
        
    except Exception as e:
        logger.error(f"Error checking file: {str(e)}")
        import json
        return func.HttpResponse(
            body=json.dumps({
                'error': str(e),
                'message': 'Failed to check file status'
            }),
            status_code=500,
            mimetype="application/json"
        )
