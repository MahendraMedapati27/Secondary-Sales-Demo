from flask import Flask, redirect, url_for, request
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_cors import CORS
from flask_mail import Mail
from config import Config
from pathlib import Path
import logging
import threading
import time
import atexit

db = SQLAlchemy()
login_manager = LoginManager()
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
    
    # Fix MIME type for JavaScript modules
    @app.after_request
    def set_js_mime_type(response):
        """Ensure JavaScript files are served with correct MIME type"""
        if response.mimetype == 'text/plain' and request.path.endswith('.js'):
            response.mimetype = 'application/javascript'
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
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    mail.init_app(app)
    CORS(app)
    
    # Register blueprints
    from app.auth import auth_bp
    from app.chatbot import chatbot_bp
    from app.enhanced_chatbot import chatbot_bp as enhanced_chatbot_bp
    from app.whatsapp_webhook import whatsapp_bp
    
    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(chatbot_bp, url_prefix='/chat')
    app.register_blueprint(enhanced_chatbot_bp, url_prefix='/enhanced-chat')
    app.register_blueprint(whatsapp_bp, url_prefix='/webhook')
    
    # Root route
    @app.route('/')
    def index():
        return redirect(url_for('enhanced_chatbot.chat'))
    
    # Health check endpoint for Azure monitoring
    @app.route('/health')
    def health():
        return {'status': 'healthy', 'service': 'quantum-blue-chatbot'}, 200
    
    # Create database tables
    with app.app_context():
        def _mssql_maintenance():
            try:
                # Expand otp_secret and phone columns if too small (idempotent)
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
                    # Increase otp_secret column to NVARCHAR(255)
                    conn.execute(text("""
IF EXISTS (SELECT 1 FROM sys.columns c
           JOIN sys.objects o ON o.object_id = c.object_id
           WHERE o.name = 'users' AND c.name = 'otp_secret' AND c.max_length < 510)
BEGIN
    ALTER TABLE dbo.users ALTER COLUMN otp_secret NVARCHAR(255) NULL;
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
            
            # Create sample products
            db_service.create_sample_products()
            
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
        
        # Register cleanup on exit
        def cleanup_stock_checker():
            logging.info("🛑 Stopping stock checker background thread...")
        
        atexit.register(cleanup_stock_checker)
        
    except Exception as e:
        logging.warning(f"Failed to start stock checker background thread: {str(e)}")
        logging.warning("Pending orders will not be auto-fulfilled. Run 'python run_stock_checker.py' manually.")
    
    return app

@login_manager.user_loader
def load_user(user_id):
    from app.models import User
    return User.query.get(int(user_id))