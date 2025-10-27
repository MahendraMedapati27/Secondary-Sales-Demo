from datetime import datetime, timedelta
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
import hashlib
from app import db
import pyotp
import secrets
import uuid

class User(UserMixin, db.Model):
    """User model"""
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    phone = db.Column(db.String(50), nullable=False)
    password_hash = db.Column(db.String(200))
    
    # Email verification with OTP
    email_verified = db.Column(db.Boolean, default=False)
    verified_at = db.Column(db.DateTime)
    # Stores a hashed OTP (scrypt via Werkzeug), requires larger capacity
    otp_secret = db.Column(db.String(255))
    otp_created_at = db.Column(db.DateTime)
    
    # Warehouse location
    warehouse_location = db.Column(db.String(100), nullable=True)
    last_verification = db.Column(db.DateTime, default=datetime.utcnow)
    
    # WhatsApp onboarding state
    onboarding_state = db.Column(db.String(50), default='ask_name')
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    conversations = db.relationship('Conversation', backref='user', lazy='dynamic', cascade='all, delete-orphan')
    orders = db.relationship('Order', backref='user', lazy='dynamic', cascade='all, delete-orphan')
    
    def set_password(self, password):
        """Hash and set password"""
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        """Verify password"""
        return check_password_hash(self.password_hash, password)
    
    def generate_otp(self):
        """Generate 6-digit OTP and store a truncated hash to fit legacy DB size"""
        otp = ''.join([str(secrets.randbelow(10)) for _ in range(6)])
        # Compute stable hash then truncate to 32 hex chars for compatibility
        digest = hashlib.sha256(f"{self.email}:{otp}".encode("utf-8")).hexdigest()
        self.otp_secret = digest[:32]
        self.otp_created_at = datetime.utcnow()
        return otp
    
    def verify_otp(self, otp, expiration=600):
        """Verify OTP (default 10 minutes expiration)"""
        if not self.otp_secret or not self.otp_created_at:
            return False
        if datetime.utcnow() > self.otp_created_at + timedelta(seconds=expiration):
            return False
        # Recompute short hash and compare
        expected = hashlib.sha256(f"{self.email}:{otp}".encode("utf-8")).hexdigest()[:32]
        return secrets.compare_digest(self.otp_secret, expected)
    
    def verify_email(self):
        """Mark email as verified"""
        self.email_verified = True
        self.verified_at = datetime.utcnow()
        self.otp_secret = None
        self.otp_created_at = None
    
    def __repr__(self):
        return f'<User {self.email}>'

class Conversation(db.Model):
    """Conversation history model"""
    __tablename__ = 'conversations'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    session_id = db.Column(db.Integer, db.ForeignKey('chat_sessions.id'), nullable=True)
    
    # Message details
    user_message = db.Column(db.Text, nullable=False)
    bot_response = db.Column(db.Text, nullable=False)
    
    # Metadata
    data_sources = db.Column(db.JSON)
    response_time = db.Column(db.Float)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    
    def __repr__(self):
        return f'<Conversation {self.id} - User {self.user_id}>'
    
    def to_dict(self):
        """Convert to dictionary"""
        return {
            'id': self.id,
            'user_message': self.user_message,
            'bot_response': self.bot_response,
            'data_sources': self.data_sources,
            'response_time': self.response_time,
            'created_at': self.created_at.isoformat()
        }

class EmailLog(db.Model):
    """Email sending log"""
    __tablename__ = 'email_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    recipient = db.Column(db.String(120), nullable=False)
    email_type = db.Column(db.String(50), nullable=False)
    status = db.Column(db.String(20), nullable=False)
    error_message = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<EmailLog {self.id} - {self.email_type}>'

class Warehouse(db.Model):
    """Warehouse model"""
    __tablename__ = 'warehouses'
    
    id = db.Column(db.Integer, primary_key=True)
    location_name = db.Column(db.String(100), nullable=False, unique=True)
    address = db.Column(db.Text)
    city = db.Column(db.String(100))
    state = db.Column(db.String(100))
    country = db.Column(db.String(100))
    is_active = db.Column(db.Boolean, default=True)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    products = db.relationship('Product', backref='warehouse', lazy='dynamic', cascade='all, delete-orphan')
    orders = db.relationship('Order', backref='warehouse', lazy='dynamic', cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<Warehouse {self.location_name}>'

class Product(db.Model):
    """Product model"""
    __tablename__ = 'products'
    
    id = db.Column(db.Integer, primary_key=True)
    product_code = db.Column(db.String(50), nullable=False, index=True)
    product_name = db.Column(db.String(200), nullable=False)
    product_description = db.Column(db.Text)
    batch_number = db.Column(db.String(50))
    expiry_date = db.Column(db.Date)
    product_quantity = db.Column(db.Integer, default=0, nullable=False)
    blocked_quantity = db.Column(db.Integer, default=0, nullable=False)
    available_for_sale = db.Column(db.Integer, default=0, nullable=False)
    price_of_product = db.Column(db.Float, default=0.0)
    discount = db.Column(db.Float, default=0.0)
    scheme = db.Column(db.String(200))
    
    # Foreign keys
    warehouse_id = db.Column(db.Integer, db.ForeignKey('warehouses.id'), nullable=False)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    order_items = db.relationship('OrderItem', backref='product', lazy='dynamic', cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<Product {self.product_code} - {self.product_name}>'
    
    def update_available_quantity(self):
        """Update available_for_sale quantity"""
        # Ensure all quantities are properly initialized
        if self.product_quantity is None:
            self.product_quantity = 0
        if self.blocked_quantity is None:
            self.blocked_quantity = 0
        if self.available_for_sale is None:
            self.available_for_sale = 0
            
        self.available_for_sale = self.product_quantity - self.blocked_quantity
        db.session.commit()

class Order(db.Model):
    """Order model"""
    __tablename__ = 'orders'
    
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.String(50), unique=True, nullable=False, index=True)
    user_email = db.Column(db.String(120), nullable=False, index=True)
    warehouse_location = db.Column(db.String(100), nullable=False)
    total_amount = db.Column(db.Float, default=0.0)
    status = db.Column(db.String(50), default='pending')  # pending, confirmed, shipped, delivered, cancelled
    
    # Foreign keys
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    warehouse_id = db.Column(db.Integer, db.ForeignKey('warehouses.id'), nullable=False)
    
    # Timestamps
    order_date = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    order_items = db.relationship('OrderItem', backref='order', lazy='dynamic', cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<Order {self.order_id}>'
    
    def generate_order_id(self):
        """Generate unique order ID"""
        if not self.order_id:
            self.order_id = f"QB{datetime.utcnow().strftime('%Y%m%d')}{uuid.uuid4().hex[:8].upper()}"
        return self.order_id
    
    def to_dict(self):
        """Convert to dictionary"""
        return {
            'id': self.id,
            'order_id': self.order_id,
            'user_email': self.user_email,
            'warehouse_location': self.warehouse_location,
            'total_amount': self.total_amount,
            'status': self.status,
            'order_date': self.order_date.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }

class OrderItem(db.Model):
    """Order item model"""
    __tablename__ = 'order_items'
    
    id = db.Column(db.Integer, primary_key=True)
    product_code = db.Column(db.String(50), nullable=False)
    product_quantity_ordered = db.Column(db.Integer, nullable=False)
    unit_price = db.Column(db.Float, default=0.0)
    total_price = db.Column(db.Float, default=0.0)
    
    # Foreign keys
    order_id = db.Column(db.Integer, db.ForeignKey('orders.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<OrderItem {self.product_code} - Qty: {self.product_quantity_ordered}>'

class ChatSession(db.Model):
    """Chat session model for conversation management"""
    __tablename__ = 'chat_sessions'
    
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.String(100), unique=True, nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    is_deleted = db.Column(db.Boolean, default=False)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    deleted_at = db.Column(db.DateTime)
    
    # Relationships
    conversations = db.relationship('Conversation', backref='session', lazy='dynamic', cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<ChatSession {self.session_id}>'
    
    def generate_session_id(self):
        """Generate unique session ID"""
        if not self.session_id:
            self.session_id = f"QB_SESSION_{uuid.uuid4().hex[:16].upper()}"
        return self.session_id