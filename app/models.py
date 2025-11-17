from datetime import datetime
from flask_login import UserMixin
from app import db
import uuid

class User(UserMixin, db.Model):
    """User model for HV - Dealers and MRs"""
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    unique_id = db.Column(db.String(50), unique=True, nullable=False, index=True)
    name = db.Column(db.String(100), nullable=False)
    pharmacy_name = db.Column(db.String(200), nullable=True)
    area = db.Column(db.String(100), nullable=True)
    discount = db.Column(db.Float, nullable=False, default=0.0)
    email = db.Column(db.String(120), nullable=True, index=True)
    phone = db.Column(db.String(50), nullable=False)
    role = db.Column(db.String(50), nullable=True)  # 'distributor' or 'mr'
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    conversations = db.relationship('Conversation', backref='user', lazy='dynamic', cascade='all, delete-orphan')
    cart_items = db.relationship('CartItem', backref='user', lazy='dynamic', cascade='all, delete-orphan')
    customers = db.relationship('Customer', foreign_keys='Customer.mr_id', backref='mr_user', lazy='dynamic')
    dealer_stock_details = db.relationship('DealerWiseStockDetails', foreign_keys='DealerWiseStockDetails.dealer_id', backref='dealer', lazy='dynamic')
    pending_orders = db.relationship('PendingOrderProducts', backref='user', lazy='dynamic')
    
    # Orders as MR
    mr_orders = db.relationship('Order', foreign_keys='Order.mr_id', backref='mr', lazy='dynamic')
    
    def generate_unique_id(self):
        """Generate unique ID for user"""
        if not self.unique_id:
            prefix = 'MR' if self.role == 'mr' else 'DIST'
            timestamp = datetime.utcnow().strftime('%Y%m%d%H%M%S')
            random_part = uuid.uuid4().hex[:6].upper()
            self.unique_id = f"{prefix}_{timestamp}_{random_part}"
        return self.unique_id
    
    def __repr__(self):
        return f'<User {self.unique_id} - {self.name}>'

class Customer(db.Model):
    """Customer model - customers assigned to MRs"""
    __tablename__ = 'customers'
    
    id = db.Column(db.Integer, primary_key=True)
    unique_id = db.Column(db.String(50), unique=True, nullable=False, index=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), nullable=True)
    phone = db.Column(db.String(50), nullable=True)
    address = db.Column(db.Text, nullable=True)
    mr_unique_id = db.Column(db.String(50), nullable=False, index=True)
    mr_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    orders = db.relationship('Order', backref='customer', lazy='dynamic', cascade='all, delete-orphan')
    
    def generate_unique_id(self):
        """Generate unique ID for customer"""
        if not self.unique_id:
            timestamp = datetime.utcnow().strftime('%Y%m%d%H%M%S')
            random_part = uuid.uuid4().hex[:6].upper()
            self.unique_id = f"CUST_{timestamp}_{random_part}"
        return self.unique_id
    
    def __repr__(self):
        return f'<Customer {self.unique_id} - {self.name}>'

class Product(db.Model):
    """Simplified Product model"""
    __tablename__ = 'products'
    
    id = db.Column(db.Integer, primary_key=True)
    product_name = db.Column(db.String(200), nullable=False)
    price = db.Column(db.Float, default=0.0)
    team = db.Column(db.String(100), nullable=True)
    
    # Relationships
    foc_schemes = db.relationship('FOC', backref='product', lazy='dynamic')
    dealer_stock_details = db.relationship('DealerWiseStockDetails', backref='product', lazy='dynamic')
    order_items = db.relationship('OrderItem', backref='product', lazy='dynamic')
    cart_items = db.relationship('CartItem', backref='product', lazy='dynamic')
    
    def __repr__(self):
        return f'<Product {self.id} - {self.product_name}>'

class FOC(db.Model):
    """Free of Cost (FOC) schemes model for products"""
    __tablename__ = 'foc'
    
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=True, index=True)
    product_name = db.Column(db.String(200), nullable=False, index=True)
    scheme_1 = db.Column(db.String(50), nullable=True)
    scheme_2 = db.Column(db.String(50), nullable=True)
    scheme_3 = db.Column(db.String(50), nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f'<FOC {self.product_name} - Scheme 1: {self.scheme_1}, Scheme 2: {self.scheme_2}, Scheme 3: {self.scheme_3}>'
    
    def get_foc_for_quantity(self, quantity):
        """
        Get FOC benefits for a given quantity
        Returns: dict with 'free_quantity', 'paid_quantity', 'total_quantity', 'scheme_applied'
        """
        schemes = []
        if self.scheme_1:
            schemes.append(('Scheme 1', self._parse_scheme(self.scheme_1)))
        if self.scheme_2:
            schemes.append(('Scheme 2', self._parse_scheme(self.scheme_2)))
        if self.scheme_3:
            schemes.append(('Scheme 3', self._parse_scheme(self.scheme_3)))
        
        # Find the best matching scheme (highest quantity threshold that quantity meets)
        best_scheme = None
        best_threshold = 0
        
        for scheme_name, (buy_qty, free_qty) in schemes:
            if quantity >= buy_qty and buy_qty > best_threshold:
                best_threshold = buy_qty
                best_scheme = (buy_qty, free_qty)
        
        if best_scheme:
            buy_qty, free_qty = best_scheme
            groups = quantity // buy_qty
            free_quantity = groups * free_qty
            paid_quantity = quantity
            total_quantity = paid_quantity + free_quantity
            
            return {
                'free_quantity': free_quantity,
                'paid_quantity': paid_quantity,
                'total_quantity': total_quantity,
                'scheme_applied': True,
                'buy_quantity': buy_qty,
                'free_per_group': free_qty,
                'scheme_name': f'Buy {buy_qty} Get {free_qty} Free'
            }
        else:
            return {
                'free_quantity': 0,
                'paid_quantity': quantity,
                'total_quantity': quantity,
                'scheme_applied': False
            }
    
    def _parse_scheme(self, scheme_str):
        """Parse scheme string like "10+1" into (buy_quantity, free_quantity)"""
        try:
            if '+' in scheme_str:
                parts = scheme_str.split('+')
                buy_qty = int(parts[0].strip())
                free_qty = int(parts[1].strip())
                return (buy_qty, free_qty)
            else:
                return (0, 0)
        except (ValueError, IndexError):
            return (0, 0)
    
    def to_dict(self):
        """Convert to dictionary"""
        return {
            'id': self.id,
            'product_name': self.product_name,
            'scheme_1': self.scheme_1,
            'scheme_2': self.scheme_2,
            'scheme_3': self.scheme_3,
            'is_active': self.is_active
        }

class DealerWiseStockDetails(db.Model):
    """Model to track stock dispatched from company to dealers"""
    __tablename__ = 'dealer_wise_stock_details'
    
    id = db.Column(db.Integer, primary_key=True)
    dispatch_date = db.Column(db.Date, nullable=False)
    dealer_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True, index=True)
    dealer_unique_id = db.Column(db.String(50), nullable=False, index=True)
    dealer_name = db.Column(db.String(200), nullable=False)
    product_code = db.Column(db.String(50), nullable=False, index=True)
    product_name = db.Column(db.String(200), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=True, index=True)
    lot_number = db.Column(db.String(100), nullable=True)
    expiry_date = db.Column(db.Date, nullable=True)
    quantity = db.Column(db.Integer, nullable=False, default=0)
    sales_price = db.Column(db.Float, nullable=False, default=0.0)
    blocked_quantity = db.Column(db.Integer, nullable=False, default=0)
    available_for_sale = db.Column(db.Integer, nullable=False, default=0)
    sold_quantity = db.Column(db.Integer, nullable=False, default=0)
    status = db.Column(db.String(50), nullable=False, default='blocked')
    received_quantity = db.Column(db.Integer, nullable=True)
    quantity_adjusted = db.Column(db.Boolean, default=False, nullable=False)
    adjustment_reason = db.Column(db.Text, nullable=True)
    invoice_id = db.Column(db.String(100), nullable=True, index=True)
    confirmed_at = db.Column(db.DateTime, nullable=True)
    confirmed_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    confirmed_by_user = db.relationship('User', foreign_keys=[confirmed_by], backref='confirmed_stock_arrivals')
    
    def __repr__(self):
        return f'<DealerWiseStockDetails {self.product_code} - {self.dealer_name} - Qty: {self.quantity}>'
    
    def to_dict(self):
        """Convert to dictionary"""
        expiry_date_iso = self.expiry_date.isoformat() if self.expiry_date else None
        return {
            'id': self.id,
            'dispatch_date': self.dispatch_date.isoformat() if self.dispatch_date else None,
            'dealer_unique_id': self.dealer_unique_id,
            'dealer_name': self.dealer_name,
            'invoice_id': self.invoice_id,
            'product_code': self.product_code,
            'product_name': self.product_name,
            'lot_number': self.lot_number,
            'expiry_date': expiry_date_iso,  # Primary field name
            'expiration_date': expiry_date_iso,  # Alias for frontend compatibility
            'quantity': self.quantity,
            'sales_price': self.sales_price,
            'blocked_quantity': self.blocked_quantity,
            'available_for_sale': self.available_for_sale,
            'sold_quantity': self.sold_quantity,
            'status': self.status,
            'received_quantity': self.received_quantity,
            'quantity_adjusted': self.quantity_adjusted,
            'adjustment_reason': self.adjustment_reason,
            'confirmed_at': self.confirmed_at.isoformat() if self.confirmed_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
    
    def update_available_quantity(self):
        """Update available_for_sale based on received_quantity, blocked_quantity, and sold_quantity"""
        if self.received_quantity is not None:
            self.available_for_sale = max(0, self.received_quantity - self.blocked_quantity - self.sold_quantity)
        else:
            self.available_for_sale = 0

class Order(db.Model):
    """Order model"""
    __tablename__ = 'orders'
    
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.String(50), unique=True, nullable=False, index=True)
    mr_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    mr_unique_id = db.Column(db.String(50), nullable=True, index=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id'), nullable=True)
    customer_unique_id = db.Column(db.String(50), nullable=True, index=True)
    subtotal = db.Column(db.Float, default=0.0)  # Subtotal before tax
    tax_rate = db.Column(db.Float, default=0.05)  # Tax rate (default 5%)
    tax_amount = db.Column(db.Float, default=0.0)  # Tax amount
    total_amount = db.Column(db.Float, default=0.0)  # Grand total (subtotal + tax)
    order_stage = db.Column(db.String(50), default='draft')
    status = db.Column(db.String(50), default='pending')
    distributor_confirmed_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    distributor_confirmed_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    order_items = db.relationship('OrderItem', backref='order', lazy='dynamic', cascade='all, delete-orphan')
    distributor_user = db.relationship('User', foreign_keys=[distributor_confirmed_by], backref='confirmed_orders')
    
    def generate_order_id(self):
        """Generate unique order ID"""
        if not self.order_id:
            self.order_id = f"QB{datetime.utcnow().strftime('%Y%m%d')}{uuid.uuid4().hex[:8].upper()}"
        return self.order_id
    
    def __repr__(self):
        return f'<Order {self.order_id}>'
    
    def to_dict(self):
        """Convert to dictionary"""
        return {
            'id': self.id,
            'order_id': self.order_id,
            'mr_unique_id': self.mr_unique_id,
            'customer_unique_id': self.customer_unique_id,
            'total_amount': self.total_amount,
            'status': self.status,
            'order_stage': self.order_stage,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }

class OrderItem(db.Model):
    """Order item model"""
    __tablename__ = 'order_items'
    
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('orders.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    product_code = db.Column(db.String(50), nullable=False)
    product_name = db.Column(db.String(200), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)  # Paid quantity
    free_quantity = db.Column(db.Integer, default=0)  # FOC quantity
    unit_price = db.Column(db.Float, default=0.0)
    total_price = db.Column(db.Float, default=0.0)
    
    # Editable fields for dealer confirmation
    adjusted_quantity = db.Column(db.Integer, nullable=True)  # Actual quantity dispatched (if different from ordered)
    adjusted_expiry_date = db.Column(db.Date, nullable=True)  # Adjusted expiry date
    adjusted_lot_number = db.Column(db.String(100), nullable=True)  # Adjusted lot number
    adjustment_reason = db.Column(db.Text, nullable=True)  # Reason for adjustment
    pending_quantity = db.Column(db.Integer, default=0)  # Quantity moved to pending orders
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        total_qty = self.quantity + (self.free_quantity or 0)
        return f'<OrderItem {self.product_code} - Qty: {total_qty} ({self.quantity} paid + {self.free_quantity or 0} free)>'

class PendingOrderProducts(db.Model):
    """Model to track expired product orders that are waiting for stock"""
    __tablename__ = 'pending_orders'
    
    id = db.Column(db.Integer, primary_key=True)
    original_order_id = db.Column(db.String(50), nullable=True, index=True)
    product_code = db.Column(db.String(50), nullable=False, index=True)
    product_name = db.Column(db.String(200), nullable=False)
    requested_quantity = db.Column(db.Integer, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    user_email = db.Column(db.String(120), nullable=False)
    status = db.Column(db.String(50), default='pending')
    fulfilled_order_id = db.Column(db.String(50), nullable=True)
    user_notified = db.Column(db.Boolean, default=False)
    distributor_notified = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    fulfilled_at = db.Column(db.DateTime, nullable=True)
    
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

class Conversation(db.Model):
    """Conversation history model"""
    __tablename__ = 'conversations'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    session_id = db.Column(db.String(100), nullable=True)
    user_message = db.Column(db.Text, nullable=False)
    bot_response = db.Column(db.Text, nullable=False)
    data_sources = db.Column(db.Text, nullable=True)
    response_time = db.Column(db.Float)
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

class CartItem(db.Model):
    """Cart item model for managing user shopping cart"""
    __tablename__ = 'cart_items'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    product_code = db.Column(db.String(50), nullable=False)
    product_name = db.Column(db.String(200), nullable=True)
    quantity = db.Column(db.Integer, nullable=False)
    unit_price = db.Column(db.Float, default=0.0)
    total_price = db.Column(db.Float, default=0.0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f'<CartItem {self.product_code} - Qty: {self.quantity}>'

class ChatSession(db.Model):
    """Chat session model for conversation management"""
    __tablename__ = 'chat_sessions'
    
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.String(100), unique=True, nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    is_deleted = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    deleted_at = db.Column(db.DateTime)
    
    def generate_session_id(self):
        """Generate unique session ID"""
        if not self.session_id:
            self.session_id = f"QB_SESSION_{uuid.uuid4().hex[:16].upper()}"
        return self.session_id
    
    def __repr__(self):
        return f'<ChatSession {self.session_id}>'

class EmailLog(db.Model):
    """Email sending log with detailed tracking"""
    __tablename__ = 'email_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    recipient = db.Column(db.String(120), nullable=False)  # Kept for backward compatibility
    email_type = db.Column(db.String(50), nullable=False)
    status = db.Column(db.String(20), nullable=False)
    error_message = db.Column(db.Text)
    
    # New detailed columns
    order_id = db.Column(db.String(50), nullable=True, index=True)
    sender_email = db.Column(db.String(120), nullable=True)
    sender_name = db.Column(db.String(200), nullable=True)
    receiver_email = db.Column(db.String(120), nullable=True)
    receiver_name = db.Column(db.String(200), nullable=True)
    subject = db.Column(db.String(500), nullable=True)
    body_preview = db.Column(db.Text, nullable=True)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<EmailLog {self.id} - {self.email_type} - Order: {self.order_id}>'
    
    def to_dict(self):
        """Convert to dictionary"""
        return {
            'id': self.id,
            'recipient': self.recipient,
            'email_type': self.email_type,
            'status': self.status,
            'error_message': self.error_message,
            'order_id': self.order_id,
            'sender_email': self.sender_email,
            'sender_name': self.sender_name,
            'receiver_email': self.receiver_email or self.recipient,
            'receiver_name': self.receiver_name,
            'subject': self.subject,
            'body_preview': self.body_preview[:200] if self.body_preview else None,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

class Notification(db.Model):
    """Notification model for real-time notifications"""
    __tablename__ = 'notifications'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    notification_type = db.Column(db.String(50), nullable=False, index=True)  # 'new_order', 'order_approved', 'order_rejected', 'stock_arrival', 'low_stock', 'payment_reminder', 'order_status_change'
    title = db.Column(db.String(200), nullable=False)
    message = db.Column(db.Text, nullable=False)
    data = db.Column(db.Text, nullable=True)  # JSON string for additional data (order_id, product_code, etc.)
    is_read = db.Column(db.Boolean, default=False, nullable=False, index=True)
    read_at = db.Column(db.DateTime, nullable=True)
    action_url = db.Column(db.String(500), nullable=True)  # URL to navigate when notification is clicked
    priority = db.Column(db.String(20), default='normal')  # 'low', 'normal', 'high', 'urgent'
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    
    # Relationships
    user = db.relationship('User', backref='notifications', lazy=True)
    
    def __repr__(self):
        return f'<Notification {self.id} - {self.notification_type} for User {self.user_id}>'
    
    def to_dict(self):
        """Convert to dictionary"""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'notification_type': self.notification_type,
            'title': self.title,
            'message': self.message,
            'data': self.data,
            'is_read': self.is_read,
            'read_at': self.read_at.isoformat() if self.read_at else None,
            'action_url': self.action_url,
            'priority': self.priority,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
    
    def mark_as_read(self):
        """Mark notification as read"""
        self.is_read = True
        self.read_at = datetime.utcnow()
        db.session.commit()

class NotificationPreference(db.Model):
    """User notification preferences"""
    __tablename__ = 'notification_preferences'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, unique=True, index=True)
    
    # Notification type preferences (True = enabled, False = disabled)
    new_order_enabled = db.Column(db.Boolean, default=True)
    order_approved_enabled = db.Column(db.Boolean, default=True)
    order_rejected_enabled = db.Column(db.Boolean, default=True)
    stock_arrival_enabled = db.Column(db.Boolean, default=True)
    low_stock_enabled = db.Column(db.Boolean, default=True)
    payment_reminder_enabled = db.Column(db.Boolean, default=True)
    order_status_change_enabled = db.Column(db.Boolean, default=True)
    
    # Delivery preferences
    in_app_enabled = db.Column(db.Boolean, default=True)
    push_enabled = db.Column(db.Boolean, default=True)
    email_enabled = db.Column(db.Boolean, default=False)  # Optional email notifications
    
    # Push notification subscription (stored as JSON)
    push_subscription = db.Column(db.Text, nullable=True)  # JSON string for browser push subscription
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = db.relationship('User', backref='notification_preference', uselist=False, lazy=True)
    
    def __repr__(self):
        return f'<NotificationPreference for User {self.user_id}>'
    
    def to_dict(self):
        """Convert to dictionary"""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'new_order_enabled': self.new_order_enabled,
            'order_approved_enabled': self.order_approved_enabled,
            'order_rejected_enabled': self.order_rejected_enabled,
            'stock_arrival_enabled': self.stock_arrival_enabled,
            'low_stock_enabled': self.low_stock_enabled,
            'payment_reminder_enabled': self.payment_reminder_enabled,
            'order_status_change_enabled': self.order_status_change_enabled,
            'in_app_enabled': self.in_app_enabled,
            'push_enabled': self.push_enabled,
            'email_enabled': self.email_enabled,
            'push_subscription': self.push_subscription,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
    
    def is_type_enabled(self, notification_type):
        """Check if a specific notification type is enabled"""
        type_map = {
            'new_order': self.new_order_enabled,
            'order_approved': self.order_approved_enabled,
            'order_rejected': self.order_rejected_enabled,
            'stock_arrival': self.stock_arrival_enabled,
            'low_stock': self.low_stock_enabled,
            'payment_reminder': self.payment_reminder_enabled,
            'order_status_change': self.order_status_change_enabled
        }
        return type_map.get(notification_type, True)  # Default to enabled if type not found

