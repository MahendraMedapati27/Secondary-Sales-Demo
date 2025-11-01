from datetime import datetime, timedelta
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
import hashlib
from app import db
import pyotp
import secrets
import uuid

class User(UserMixin, db.Model):
    """Enhanced User model for RB (Powered by Quantum Blue AI)"""
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    unique_id = db.Column(db.String(50), unique=True, nullable=False, index=True)  # Unique identifier for users
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    phone = db.Column(db.String(50), nullable=False)
    password_hash = db.Column(db.String(200))
    
    # User type and role
    user_type = db.Column(db.String(20), nullable=False, default='customer')  # customer, mr, distributor, pharmacy
    role = db.Column(db.String(50), nullable=True)  # Medical Representative, Distributor, etc.
    
    # Location and delivery information
    delivery_pin_code = db.Column(db.String(10), nullable=True)
    delivery_zone = db.Column(db.String(100), nullable=True)
    nearest_warehouse = db.Column(db.String(100), nullable=True)
    nearest_distributor = db.Column(db.String(100), nullable=True)
    
    # Company information
    company_name = db.Column(db.String(200), nullable=True)
    company_address = db.Column(db.Text, nullable=True)
    
    # Email verification with OTP
    email_verified = db.Column(db.Boolean, default=False)
    verified_at = db.Column(db.DateTime)
    # Stores a hashed OTP (scrypt via Werkzeug), requires larger capacity
    otp_secret = db.Column(db.String(255))
    otp_created_at = db.Column(db.DateTime)
    
    # Warehouse location (legacy field for backward compatibility)
    warehouse_location = db.Column(db.String(100), nullable=True)
    last_verification = db.Column(db.DateTime, default=datetime.utcnow)
    
    # User status
    is_active = db.Column(db.Boolean, default=True)
    is_verified = db.Column(db.Boolean, default=False)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    conversations = db.relationship('Conversation', backref='user', lazy='dynamic', cascade='all, delete-orphan')
    orders = db.relationship('Order', foreign_keys='Order.user_id', backref='user', lazy='dynamic', cascade='all, delete-orphan')
    cart_items = db.relationship('CartItem', backref='user', lazy='dynamic', cascade='all, delete-orphan')
    
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
    
    def generate_unique_id(self):
        """Generate unique ID for user"""
        if not self.unique_id:
            # Generate based on user type and timestamp
            prefix = {
                'customer': 'CUST',
                'mr': 'MR',
                'distributor': 'DIST',
                'pharmacy': 'PHARM'
            }.get(self.user_type, 'USER')
            
            timestamp = datetime.utcnow().strftime('%Y%m%d%H%M%S')
            random_part = uuid.uuid4().hex[:6].upper()
            self.unique_id = f"{prefix}_{timestamp}_{random_part}"
        return self.unique_id
    
    def __repr__(self):
        return f'<User {self.unique_id} - {self.email}>'

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
    """Enhanced Product model for RB (Powered by Quantum Blue AI)"""
    __tablename__ = 'products'
    
    id = db.Column(db.Integer, primary_key=True)
    product_code = db.Column(db.String(50), nullable=False, index=True)
    product_name = db.Column(db.String(200), nullable=False)
    product_description = db.Column(db.Text)
    batch_number = db.Column(db.String(50))
    expiry_date = db.Column(db.Date)
    
    # Inventory management
    product_quantity = db.Column(db.Integer, default=0, nullable=False)
    blocked_quantity = db.Column(db.Integer, default=0, nullable=False)
    available_for_sale = db.Column(db.Integer, default=0, nullable=False)
    confirmed_quantity = db.Column(db.Integer, default=0, nullable=False)  # Quantity confirmed for orders
    
    # Pricing
    price_of_product = db.Column(db.Float, default=0.0)
    
    # Discount system (3 predefined discounts)
    discount_type = db.Column(db.String(50), nullable=True)  # 'percentage', 'fixed', 'bulk'
    discount_value = db.Column(db.Float, default=0.0)  # Percentage or fixed amount
    discount_name = db.Column(db.String(100), nullable=True)  # 'Early Bird', 'Bulk Purchase', 'Loyalty'
    
    # Scheme system (3 predefined schemes)
    scheme_type = db.Column(db.String(50), nullable=True)  # 'buy_x_get_y', 'percentage_off', 'free_shipping'
    scheme_value = db.Column(db.String(200), nullable=True)  # JSON string with scheme details
    scheme_name = db.Column(db.String(100), nullable=True)  # 'Buy 2 Get 1 Free', 'Buy 1 Get 20% Off', 'Buy 3 Get 2 Free'
    
    # Legacy fields for backward compatibility
    discount = db.Column(db.Float, default=0.0)
    scheme = db.Column(db.String(200))
    
    # Product status
    is_active = db.Column(db.Boolean, default=True)
    
    # Foreign keys
    warehouse_id = db.Column(db.Integer, db.ForeignKey('warehouses.id'), nullable=False)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    order_items = db.relationship('OrderItem', backref='product', lazy='dynamic', cascade='all, delete-orphan')
    cart_items = db.relationship('CartItem', backref='product', lazy='dynamic', cascade='all, delete-orphan')
    
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
    """Enhanced Order model for RB (Powered by Quantum Blue AI)"""
    __tablename__ = 'orders'
    
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.String(50), unique=True, nullable=False, index=True)
    user_email = db.Column(db.String(120), nullable=False, index=True)
    warehouse_location = db.Column(db.String(100), nullable=False)
    
    # Order amounts
    subtotal_amount = db.Column(db.Float, default=0.0)
    discount_amount = db.Column(db.Float, default=0.0)
    scheme_discount_amount = db.Column(db.Float, default=0.0)
    total_amount = db.Column(db.Float, default=0.0)
    
    # Order status workflow
    status = db.Column(db.String(50), default='pending')  # pending, in_transit, confirmed, shipped, delivered, cancelled
    order_stage = db.Column(db.String(50), default='draft')  # draft, placed, distributor_notified, distributor_confirmed, invoice_generated, completed
    
    # Order placement details
    placed_by = db.Column(db.String(20), nullable=False, default='customer')  # customer, mr, distributor
    placed_by_user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)  # Who placed the order
    
    # Distributor confirmation
    distributor_confirmed = db.Column(db.Boolean, default=False)
    distributor_confirmed_at = db.Column(db.DateTime, nullable=True)
    distributor_confirmed_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)  # Which distributor confirmed
    
    # Invoice details
    invoice_generated = db.Column(db.Boolean, default=False)
    invoice_generated_at = db.Column(db.DateTime, nullable=True)
    invoice_number = db.Column(db.String(50), nullable=True)
    
    # Foreign keys
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    warehouse_id = db.Column(db.Integer, db.ForeignKey('warehouses.id'), nullable=False)
    
    # Timestamps
    order_date = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    order_items = db.relationship('OrderItem', backref='order', lazy='dynamic', cascade='all, delete-orphan')
    placed_by_user = db.relationship('User', foreign_keys=[placed_by_user_id], backref='placed_orders')
    distributor_user = db.relationship('User', foreign_keys=[distributor_confirmed_by], backref='confirmed_orders')
    
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

class CartItem(db.Model):
    """Cart item model for managing user shopping cart"""
    __tablename__ = 'cart_items'
    
    id = db.Column(db.Integer, primary_key=True)
    product_code = db.Column(db.String(50), nullable=False)
    product_quantity = db.Column(db.Integer, nullable=False)
    unit_price = db.Column(db.Float, default=0.0)
    total_price = db.Column(db.Float, default=0.0)
    
    # Pricing details
    base_price = db.Column(db.Float, default=0.0)
    discount_amount = db.Column(db.Float, default=0.0)
    scheme_discount_amount = db.Column(db.Float, default=0.0)
    final_price = db.Column(db.Float, default=0.0)
    
    # Scheme details
    scheme_applied = db.Column(db.String(100), nullable=True)
    free_quantity = db.Column(db.Integer, default=0)
    paid_quantity = db.Column(db.Integer, default=0)
    
    # Foreign keys
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f'<CartItem {self.product_code} - Qty: {self.product_quantity}>'

class OrderItem(db.Model):
    """Enhanced Order item model"""
    __tablename__ = 'order_items'
    
    id = db.Column(db.Integer, primary_key=True)
    product_code = db.Column(db.String(50), nullable=False)
    product_quantity_ordered = db.Column(db.Integer, nullable=False)
    unit_price = db.Column(db.Float, default=0.0)
    total_price = db.Column(db.Float, default=0.0)
    
    # Enhanced pricing details
    base_price = db.Column(db.Float, default=0.0)
    discount_amount = db.Column(db.Float, default=0.0)
    scheme_discount_amount = db.Column(db.Float, default=0.0)
    final_price = db.Column(db.Float, default=0.0)
    
    # Scheme details
    scheme_applied = db.Column(db.String(100), nullable=True)
    free_quantity = db.Column(db.Integer, default=0)
    paid_quantity = db.Column(db.Integer, default=0)
    
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

class PendingOrderProducts(db.Model):
    """Model to track expired product orders that are waiting for stock"""
    __tablename__ = 'pending_order_products'
    
    id = db.Column(db.Integer, primary_key=True)
    
    # Link to original order (nullable - can be None when no order exists yet)
    original_order_id = db.Column(db.String(50), db.ForeignKey('orders.order_id'), nullable=True, index=True)
    
    # Product information
    product_code = db.Column(db.String(50), nullable=False, index=True)
    product_name = db.Column(db.String(200), nullable=False)
    requested_quantity = db.Column(db.Integer, nullable=False)
    
    # User who requested
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    user_email = db.Column(db.String(120), nullable=False)
    
    # Warehouse information
    warehouse_id = db.Column(db.Integer, db.ForeignKey('warehouses.id'), nullable=False)
    warehouse_location = db.Column(db.String(100), nullable=False)
    
    # Status tracking
    status = db.Column(db.String(50), default='pending')  # pending, fulfilled, cancelled
    fulfilled_order_id = db.Column(db.String(50), nullable=True)  # Order ID when stock arrived
    
    # Notifications tracking
    user_notified = db.Column(db.Boolean, default=False)  # User notified when stock arrived
    distributor_notified = db.Column(db.Boolean, default=False)  # Distributor notified when stock arrived
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    fulfilled_at = db.Column(db.DateTime, nullable=True)
    
    # Relationships
    user = db.relationship('User', backref='pending_orders')
    order = db.relationship('Order', foreign_keys=[original_order_id], backref='pending_products')
    warehouse = db.relationship('Warehouse', backref='pending_products')
    
    def __repr__(self):
        return f'<PendingOrderProducts {self.product_code} - {self.status}>'
    
    def to_dict(self):
        """Convert to dictionary"""
        return {
            'id': self.id,
            'original_order_id': self.original_order_id,
            'product_code': self.product_code,
            'product_name': self.product_name,
            'requested_quantity': self.requested_quantity,
            'status': self.status,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }