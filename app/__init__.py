from flask import Flask, redirect, url_for, request, jsonify, g, current_app
from flask_sqlalchemy import SQLAlchemy
# LOGIN MANAGER DISABLED - Authentication not used
# from flask_login import LoginManager
from flask_cors import CORS
from flask_mail import Mail
from config import Config
from pathlib import Path
import logging
import threading
import time
import os
from datetime import datetime

db = SQLAlchemy()
# LOGIN MANAGER DISABLED - Authentication not used
# login_manager = LoginManager()
mail = Mail()

def create_app(config_class=Config):
    """Application factory"""
    # Ensure Flask knows where to find top-level templates and static assets
    base_dir = Path(__file__).resolve().parent
    app_root = base_dir.parent
    templates_path = app_root / 'templates'
    static_path = app_root / 'static'

    app = Flask(
        __name__,
        template_folder=str(templates_path),
        static_folder=str(static_path),
    )
    app.config.from_object(config_class)
    
    # Set request size limits (10MB)
    app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024  # 10MB
    
    # Session configuration
    app.config['PERMANENT_SESSION_LIFETIME'] = 3600  # 1 hour
    app.config['SESSION_COOKIE_HTTPONLY'] = True
    app.config['SESSION_COOKIE_SECURE'] = os.getenv('SESSION_COOKIE_SECURE', 'False').lower() == 'true'
    app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
    
    # Fix MIME type for JavaScript modules and add cache-busting headers
    @app.after_request
    def set_js_mime_type_and_cache(response):
        """Ensure JavaScript files are served with correct MIME type and disable caching"""
        if response.mimetype == 'text/plain' and request.path.endswith('.js'):
            response.mimetype = 'application/javascript'
        
        # Disable caching for all static files and API responses
        if request.path.startswith('/static/') or request.path.startswith('/enhanced-chat/'):
            response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate, max-age=0'
            response.headers['Pragma'] = 'no-cache'
            response.headers['Expires'] = '0'
        
        return response
    
    # Disable template caching in development and production - NUCLEAR OPTION
    app.config['TEMPLATES_AUTO_RELOAD'] = True
    app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0
    if hasattr(app, 'jinja_env'):
        app.jinja_env.auto_reload = True
        app.jinja_env.cache = None
        # Force clear any internal caches
        if hasattr(app.jinja_env, '_cache'):
            app.jinja_env._cache = None
    
    # Initialize extensions
    db.init_app(app)
    # LOGIN MANAGER DISABLED - Authentication not used
    # login_manager.init_app(app)
    # login_manager.login_view = 'auth.login'
    mail.init_app(app)
    CORS(app)
    
    # Initialize request ID and error handling
    from app.error_handling import generate_request_id, get_request_id
    
    @app.route('/favicon.ico')
    def favicon():
        """Handle favicon requests - return 204 No Content to avoid 404 errors"""
        return '', 204
    
    @app.before_request
    def before_request():
        """Set up request context"""
        from flask import g
        import time
        from app.session_manager import enforce_session_timeout, cleanup_session
        
        # Skip favicon requests to reduce log clutter
        if request.path == '/favicon.ico':
            return
        
        g.request_id = generate_request_id()
        g.request_start_time = time.time()
        
        # Session management
        if request.endpoint and request.endpoint != 'static':
            try:
                enforce_session_timeout()
                cleanup_session()
            except Exception as e:
                logger.warning(f"Session management error: {str(e)}")
        
        # Enforce request size limit
        if request.content_length and request.content_length > app.config['MAX_CONTENT_LENGTH']:
            from app.error_handling import ValidationError
            raise ValidationError(f"Request too large. Maximum size: {app.config['MAX_CONTENT_LENGTH'] / 1024 / 1024}MB")
        
        # Log request
        logger = logging.getLogger(__name__)
        logger.info(
            f"Request: {request.method} {request.path}",
            extra={
                'method': request.method,
                'path': request.path,
                'request_id': get_request_id(),
                'content_length': request.content_length
            }
        )
    
    @app.after_request
    def after_request(response):
        """Log response, add request ID header, and track metrics"""
        from app.error_handling import get_request_id
        from app.metrics import record_request
        import time
        
        response.headers['X-Request-ID'] = get_request_id()
        
        # Track metrics
        if hasattr(g, 'request_start_time'):
            response_time = time.time() - g.request_start_time
            record_request(request.path, response.status_code, response_time)
        
        return response
    
    # Global error handler
    @app.errorhandler(Exception)
    def handle_exception(e):
        """Global exception handler"""
        from app.error_handling import handle_error, AppError
        from app.metrics import record_error
        
        # Record error metrics
        error_type = type(e).__name__
        record_error(error_type, request.path)
        
        return handle_error(e, include_traceback=app.debug)
    
    # Metrics endpoint
    @app.route('/metrics')
    def metrics():
        """Get application metrics"""
        from app.metrics import get_metrics_summary
        return jsonify(get_metrics_summary()), 200
    
    # Register blueprints
    # AUTH BLUEPRINT DISABLED - Authentication not used
    # from app.auth import auth_bp
    from app.enhanced_chatbot import chatbot_bp as enhanced_chatbot_bp
    
    # app.register_blueprint(auth_bp, url_prefix='/auth')  # DISABLED
    app.register_blueprint(enhanced_chatbot_bp, url_prefix='/enhanced-chat')
    
    # Root route
    @app.route('/')
    def index():
        return redirect(url_for('enhanced_chatbot.chat'))
    
    # Health check endpoint for Azure monitoring
    @app.route('/health')
    def health():
        """Basic health check"""
        return {'status': 'healthy', 'service': 'quantum-blue-chatbot'}, 200
    
    # Database connection health check endpoint
    @app.route('/health/db')
    def health_db():
        """Database connection health check"""
        try:
            from sqlalchemy import text
            from app.timeout_utils import get_timeout, with_timeout
            engine = db.get_engine()
            
            @with_timeout(get_timeout('database'), 'Database health check')
            def _check_db():
                with engine.connect() as conn:
                    result = conn.execute(text("SELECT 1 as test"))
                    return result.fetchone()[0]
            
            test_value = _check_db()
            
            if test_value == 1:
                # Get pool status
                pool = engine.pool
                pool_status = {
                    'size': pool.size(),
                    'checked_in': pool.checkedin(),
                    'checked_out': pool.checkedout(),
                    'overflow': pool.overflow(),
                    'invalid': pool.invalid()
                }
                
                return {
                    'status': 'healthy',
                    'database': 'connected',
                    'pool_status': pool_status
                }, 200
            else:
                return {'status': 'unhealthy', 'database': 'query_failed'}, 503
                    
        except Exception as e:
            logger = logging.getLogger(__name__)
            logger.error(f"Database health check failed: {str(e)}")
            return {
                'status': 'unhealthy',
                'database': 'connection_failed',
                'error': str(e)
            }, 503
    
    # Deep health check endpoint
    @app.route('/health/deep')
    def health_deep():
        """Deep health check for all dependencies"""
        from app.circuit_breaker import _circuit_breakers
        from app.timeout_utils import get_timeout, with_timeout
        from sqlalchemy import text
        
        health_status = {
            'status': 'healthy',
            'timestamp': datetime.utcnow().isoformat(),
            'checks': {}
        }
        
        overall_healthy = True
        
        # Database check
        try:
            @with_timeout(get_timeout('database'), 'Database check')
            def _check_db():
                engine = db.get_engine()
                with engine.connect() as conn:
                    result = conn.execute(text("SELECT 1"))
                    return result.fetchone()[0] == 1
            
            db_healthy = _check_db()
            health_status['checks']['database'] = {
                'status': 'healthy' if db_healthy else 'unhealthy',
                'response_time': None  # Could track this
            }
            if not db_healthy:
                overall_healthy = False
        except Exception as e:
            health_status['checks']['database'] = {
                'status': 'unhealthy',
                'error': str(e)
            }
            overall_healthy = False
        
        # Circuit breaker status
        circuit_breaker_status = {}
        for name, breaker in _circuit_breakers.items():
            state = breaker.get_state()
            circuit_breaker_status[name] = {
                'state': state['state'],
                'failure_count': state['failure_count']
            }
            if state['state'] == 'open':
                overall_healthy = False
        
        health_status['checks']['circuit_breakers'] = circuit_breaker_status
        
        # External services check (lightweight)
        health_status['checks']['external_services'] = {}
        
        # Groq check (if configured)
        try:
            from app.groq_service import GroqService
            groq_service = GroqService()
            health_status['checks']['external_services']['groq'] = {
                'status': 'configured' if groq_service.client else 'not_configured'
            }
        except Exception as e:
            health_status['checks']['external_services']['groq'] = {
                'status': 'error',
                'error': str(e)
            }
        
        # Azure Translator check
        try:
            from app.translation_service import TranslationService
            translation_service = TranslationService()
            health_status['checks']['external_services']['azure_translator'] = {
                'status': 'available' if translation_service.is_available() else 'not_configured'
            }
        except Exception as e:
            health_status['checks']['external_services']['azure_translator'] = {
                'status': 'error',
                'error': str(e)
            }
        
        # Microsoft Graph check
        try:
            ms_graph_configured = all([
                current_app.config.get('MS_GRAPH_TENANT_ID'),
                current_app.config.get('MS_GRAPH_CLIENT_ID'),
                current_app.config.get('MS_GRAPH_CLIENT_SECRET')
            ])
            health_status['checks']['external_services']['microsoft_graph'] = {
                'status': 'configured' if ms_graph_configured else 'not_configured'
            }
        except Exception as e:
            health_status['checks']['external_services']['microsoft_graph'] = {
                'status': 'error',
                'error': str(e)
            }
        
        health_status['status'] = 'healthy' if overall_healthy else 'degraded'
        
        status_code = 200 if overall_healthy else 503
        return health_status, status_code
    
    # Create database tables
    with app.app_context():
        def _mssql_maintenance():
            try:
                # Expand phone column if too small (idempotent) - OTP removed
                from sqlalchemy import text
                engine = db.get_engine()
                with engine.connect() as conn:
                    # Increase phone column to NVARCHAR(50)
                    conn.execute(text("""
IF EXISTS (SELECT 1 FROM sys.columns c
           JOIN sys.objects o ON o.object_id = c.object_id
           WHERE o.name = 'users' AND c.name = 'phone' AND c.max_length < 100)
BEGIN
    ALTER TABLE dbo.users ALTER COLUMN phone NVARCHAR(50) NOT NULL;
END
"""))
                    # OTP columns removed - authentication not used
                    # Increase otp_secret column to NVARCHAR(255) - DISABLED
                    # conn.execute(text("""
# IF EXISTS (SELECT 1 FROM sys.columns c
#            JOIN sys.objects o ON o.object_id = c.object_id
#            WHERE o.name = 'users' AND c.name = 'otp_secret' AND c.max_length < 510)
# BEGIN
#     ALTER TABLE dbo.users ALTER COLUMN otp_secret NVARCHAR(255) NULL;
# END
# """))
                    # Add sales_price column to products table if it doesn't exist
                    conn.execute(text("""
IF EXISTS (SELECT 1 FROM sys.objects WHERE object_id = OBJECT_ID(N'dbo.products') AND type in (N'U'))
AND NOT EXISTS (SELECT 1 FROM sys.columns WHERE object_id = OBJECT_ID(N'dbo.products') AND name = 'sales_price')
BEGIN
    ALTER TABLE dbo.products ADD sales_price FLOAT NOT NULL DEFAULT 0;
END
"""))
            except Exception:
                # Non-fatal: continue app startup even if migration fails
                pass

        # Attempt to init DB with optional retries if Azure is required
        require_azure = bool(app.config.get('REQUIRE_AZURE_DB')) and str(app.config.get('SQLALCHEMY_DATABASE_URI', '')).startswith('mssql')
        attempts = int(app.config.get('DB_CONNECT_RETRIES', 3)) if require_azure else 1
        last_err = None
        for _ in range(attempts):
            try:
                db.create_all()
                if str(app.config.get('SQLALCHEMY_DATABASE_URI', '')).startswith('mssql'):
                    _mssql_maintenance()
                last_err = None
                break
            except Exception as e:
                last_err = e
        if last_err is not None:
            if require_azure:
                # Do not fallback; surface error
                raise last_err
            logging.warning(f"Primary DB init failed ({type(last_err).__name__}): {last_err}. Falling back to SQLite.")
            try:
                app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///quantum_blue.db'
                db.session.remove()
                try:
                    db.engine.dispose()
                except Exception:
                    pass
                db.create_all()
            except Exception as e2:
                logging.error(f"SQLite fallback failed ({type(e2).__name__}): {e2}")
                raise
        
        # Initialize sample data
        try:
            from app.database_service import DatabaseService
            db_service = DatabaseService()
            
            # Initialize warehouses
            db_service.initialize_warehouses()
            
            # Create sample products - DISABLED: Use dealer_wise_stock_details instead
            # db_service.create_sample_products()
            
            # Create sample users
            db_service.create_sample_users()
            
            logging.info("Sample data initialized successfully")
        except Exception as e:
            logging.warning(f"Failed to initialize sample data: {str(e)}")
    
    # Start stock checker background thread
    try:
        from app.stock_check_service import StockCheckService
        
        def stock_checker_worker():
            """Background worker thread for checking stock availability"""
            service = StockCheckService()
            logger = logging.getLogger(__name__)
            
            while True:
                try:
                    # Run stock check every 30 minutes
                    with app.app_context():
                        result = service.check_and_fulfill_pending_orders()
                        if result['success']:
                            fulfilled = result.get('fulfilled_count', 0)
                            if fulfilled > 0:
                                logger.info(f"✅ Stock check: {fulfilled} pending order(s) fulfilled automatically")
                            else:
                                logger.debug("✅ Stock check: No orders to fulfill")
                        else:
                            logger.error(f"❌ Stock check error: {result.get('error', 'Unknown error')}")
                except Exception as e:
                    logger.error(f"❌ Stock checker thread error: {str(e)}")
                
                # Sleep for 30 minutes (1800 seconds)
                time.sleep(1800)
        
        # Start the background thread as daemon
        stock_checker_thread = threading.Thread(target=stock_checker_worker, daemon=True, name="StockChecker")
        stock_checker_thread.start()
        logging.info("🚀 Stock checker background thread started (runs every 30 minutes)")
        
    except Exception as e:
        logging.warning(f"Failed to start stock checker background thread: {str(e)}")
        logging.warning("Pending orders will not be auto-fulfilled.")
    
    # Start stock extracter background thread
    # PAUSED: Stock extracter is currently disabled
    # To re-enable, change the condition below to: if app.config.get('EXTRACTER_ENABLED', True):
    if False:  # Stock extracter paused
        try:
            from app.stock_extracter.graph_service import MicrosoftGraphService
            from app.stock_extracter.excel_extractor import ExcelExtractor
            from app.stock_extracter.stock_importer import StockImporter
            from app.stock_extracter.scheduler import StockExtractionScheduler
            
            def stock_extracter_worker():
                """Background worker thread for extracting stock from OneDrive"""
                logger = logging.getLogger(__name__)
                
                # Initialize services
                try:
                    graph_service = MicrosoftGraphService(
                        tenant_id=app.config.get('MS_GRAPH_TENANT_ID'),
                        client_id=app.config.get('MS_GRAPH_CLIENT_ID'),
                        client_secret=app.config.get('MS_GRAPH_CLIENT_SECRET')
                    )
                    
                    excel_extractor = ExcelExtractor()
                    
                    stock_importer = StockImporter(db=db)
                    
                    scheduler = StockExtractionScheduler(
                        graph_service=graph_service,
                        excel_extractor=excel_extractor,
                        stock_importer=stock_importer,
                        site_url=app.config.get('SHAREPOINT_SITE_URL'),
                        folder_path=app.config.get('SHAREPOINT_FOLDER_PATH'),
                        check_interval_minutes=app.config.get('EXTRACTER_CHECK_INTERVAL_MINUTES', 60),
                        app=app
                    )
                    
                    # Run initial extraction
                    with app.app_context():
                        logger.info("Running initial stock extraction...")
                        scheduler.run_once()
                    
                    # Start scheduler
                    scheduler.start()
                    logger.info(f"✅ Stock extracter started (checking every {app.config.get('EXTRACTER_CHECK_INTERVAL_MINUTES', 60)} minutes)")
                    
                    # Keep thread alive
                    while True:
                        import time
                        time.sleep(60)  # Check every minute if still running
                        
                except Exception as e:
                    logger.error(f"❌ Stock extracter initialization error: {str(e)}")
                    import traceback
                    logger.error(traceback.format_exc())
            
            # Start the background thread as daemon
            stock_extracter_thread = threading.Thread(target=stock_extracter_worker, daemon=True, name="StockExtracter")
            stock_extracter_thread.start()
            logging.info("🚀 Stock extracter background thread started")
            
        except Exception as e:
            logging.warning(f"Failed to start stock extracter background thread: {str(e)}")
            logging.warning("Stock extraction from OneDrive will not be available.")
            import traceback
            logging.warning(traceback.format_exc())
    else:
        logging.info("⏸️ Stock extracter is paused (disabled)")
    
    return app

# LOGIN MANAGER DISABLED - Authentication not used
# @login_manager.user_loader
# def load_user(user_id):
#     from app.models import User
#     return User.query.get(int(user_id))