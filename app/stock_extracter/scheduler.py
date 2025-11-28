"""
Scheduler Service
Periodically checks OneDrive for new files and processes them
"""

import logging
import time
import threading
from datetime import datetime
from typing import Optional
from .graph_service import MicrosoftGraphService
from .excel_extractor import ExcelExtractor
from .stock_importer import StockImporter

# Single logger initialization - logging.basicConfig should only be called once in __init__.py
logger = logging.getLogger(__name__)


class StockExtractionScheduler:
    """Scheduler for periodic stock extraction from OneDrive"""
    
    def __init__(
        self,
        graph_service: MicrosoftGraphService,
        excel_extractor: ExcelExtractor,
        stock_importer: StockImporter,
        site_url: str,
        folder_path: str,
        check_interval_minutes: int = 60,
        app=None
    ):
        """
        Initialize scheduler
        
        Args:
            graph_service: Microsoft Graph service instance
            excel_extractor: Excel extractor instance
            stock_importer: Stock importer instance
            site_url: SharePoint site URL
            folder_path: Path to folder containing Excel files
            check_interval_minutes: Interval in minutes between checks (default: 60)
        """
        self.graph_service = graph_service
        self.excel_extractor = excel_extractor
        self.stock_importer = stock_importer
        self.site_url = site_url
        self.folder_path = folder_path
        self.check_interval_minutes = check_interval_minutes
        self.logger = logger
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._site_id: Optional[str] = None
        self._processed_files = set()  # Track processed file IDs
        self.app = app  # Flask app instance for context
    
    def start(self):
        """Start the scheduler"""
        if self._running:
            self.logger.warning("Scheduler is already running")
            return
        
        self._running = True
        
        # Get site ID once
        self.logger.info(f"Getting site ID for: {self.site_url}")
        self._site_id = self.graph_service.get_site_id(self.site_url)
        
        if not self._site_id:
            self.logger.error("Failed to get site ID. Scheduler cannot start.")
            self._running = False
            return
        
        self.logger.info(f"Site ID: {self._site_id}")
        
        # Start background thread
        self._thread = threading.Thread(target=self._run, daemon=True, name="StockExtractionScheduler")
        self._thread.start()
        self.logger.info(f"Scheduler started. Checking every {self.check_interval_minutes} minutes.")
    
    def stop(self):
        """Stop the scheduler"""
        self._running = False
        if self._thread:
            self._thread.join(timeout=10)
        self.logger.info("Scheduler stopped")
    
    def _run(self):
        """Main scheduler loop"""
        while self._running:
            try:
                self.logger.info("Starting scheduled stock extraction check...")
                # Use app context if available
                if self.app:
                    with self.app.app_context():
                        self.process_new_files()
                else:
                    self.process_new_files()
                self.logger.info(f"Next check in {self.check_interval_minutes} minutes")
            except Exception as e:
                self.logger.error(f"Error in scheduler loop: {str(e)}")
                import traceback
                self.logger.error(traceback.format_exc())
            
            # Sleep for check interval
            sleep_seconds = self.check_interval_minutes * 60
            for _ in range(sleep_seconds):
                if not self._running:
                    break
                time.sleep(1)
    
    def process_new_files(self):
        """Process new files from OneDrive"""
        try:
            if not self._site_id:
                self.logger.error("Site ID not available")
                return
            
            # List files in folder
            self.logger.info(f"Listing files in folder: {self.folder_path}")
            files = self.graph_service.list_files_in_folder(self._site_id, self.folder_path)
            
            if not files:
                self.logger.info("No Excel files found in folder")
                return
            
            self.logger.info(f"Found {len(files)} Excel file(s)")
            
            # Process each file
            for file_info in files:
                file_id = file_info.get('id')
                file_name = file_info.get('name')
                
                if not file_id:
                    continue
                
                # Check if already processed
                if file_id in self._processed_files:
                    self.logger.debug(f"File already processed: {file_name}")
                    continue
                
                # Check if file was already imported (by checking database)
                if self.stock_importer.check_file_processed(file_name):
                    self.logger.info(f"File already imported to database: {file_name}")
                    self._processed_files.add(file_id)
                    continue
                
                # Process new file
                self.logger.info(f"Processing new file: {file_name}")
                
                try:
                    # Download file
                    file_content = self.graph_service.download_file(self._site_id, file_id)
                    
                    if not file_content:
                        self.logger.error(f"Failed to download file: {file_name}")
                        continue
                    
                    # Extract stock details
                    stock_details = self.excel_extractor.extract_stock_details(file_content, file_name)
                    
                    if not stock_details:
                        self.logger.warning(f"No stock details extracted from: {file_name}")
                        self._processed_files.add(file_id)  # Mark as processed even if empty
                        continue
                    
                    # Import to database
                    result = self.stock_importer.import_stock_details(stock_details)
                    
                    if result.get('success'):
                        imported = result.get('imported_count', 0)
                        skipped = result.get('skipped_count', 0)
                        errors = result.get('error_count', 0)
                        
                        self.logger.info(
                            f"File processed successfully: {file_name} - "
                            f"{imported} imported, {skipped} skipped, {errors} errors"
                        )
                        
                        # Mark as processed
                        self._processed_files.add(file_id)
                    else:
                        error_msg = result.get('error', 'Unknown error')
                        self.logger.error(f"Failed to import stock details from {file_name}: {error_msg}")
                
                except Exception as e:
                    self.logger.error(f"Error processing file {file_name}: {str(e)}")
                    import traceback
                    self.logger.error(traceback.format_exc())
                    continue
            
        except Exception as e:
            self.logger.error(f"Error in process_new_files: {str(e)}")
            import traceback
            self.logger.error(traceback.format_exc())
    
    def run_once(self):
        """Run extraction once (for manual trigger)"""
        self.logger.info("Running one-time extraction...")
        if not self._site_id:
            self._site_id = self.graph_service.get_site_id(self.site_url)
            if not self._site_id:
                self.logger.error("Failed to get site ID")
                return False
        
        # Use app context if available
        if self.app:
            with self.app.app_context():
                self.process_new_files()
        else:
            self.process_new_files()
        return True

