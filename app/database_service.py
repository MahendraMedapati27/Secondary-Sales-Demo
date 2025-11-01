import logging
from datetime import datetime
from sqlalchemy import text, and_, or_
from app import db
from app.models import User, Warehouse, Product, Order, OrderItem, CartItem, ChatSession, Conversation, PendingOrderProducts

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DatabaseService:
    """Service for database operations"""
    
    def __init__(self):
        self.logger = logger
    
    # User Management
    def get_user_by_email(self, email):
        """Get user by email"""
        return User.query.filter_by(email=email).first()
    
    def create_user(self, name, email, phone, user_type='customer', role=None, 
                   delivery_pin_code=None, company_name=None, company_address=None, 
                   warehouse_location=None):
        """Create new user with enhanced fields"""
        user = User(
            name=name,
            email=email,
            phone=phone,
            user_type=user_type,
            role=role,
            delivery_pin_code=delivery_pin_code,
            company_name=company_name,
            company_address=company_address,
            warehouse_location=warehouse_location
        )
        user.generate_unique_id()
        db.session.add(user)
        db.session.commit()
        return user
    
    def get_user_by_unique_id(self, unique_id):
        """Get user by unique ID"""
        return User.query.filter_by(unique_id=unique_id).first()
    
    def get_user_by_phone(self, phone):
        """Get user by phone number"""
        return User.query.filter_by(phone=phone).first()
    
    def get_users_by_type(self, user_type):
        """Get users by type (customer, mr, distributor, pharmacy)"""
        return User.query.filter_by(user_type=user_type, is_active=True).all()
    
    def get_distributors(self):
        """Get all distributors"""
        return self.get_users_by_type('distributor')
    
    def get_medical_representatives(self):
        """Get all medical representatives"""
        return self.get_users_by_type('mr')
    
    def update_user_warehouse(self, user_id, warehouse_location):
        """Update user's warehouse location"""
        user = User.query.get(user_id)
        if user:
            user.warehouse_location = warehouse_location
            user.last_verification = datetime.utcnow()
            db.session.commit()
            return user
        return None
    
    # Warehouse Management
    def get_warehouses(self):
        """Get all active warehouses"""
        return Warehouse.query.filter_by(is_active=True).all()
    
    def get_warehouse_by_location(self, location_name):
        """Get warehouse by location name"""
        return Warehouse.query.filter_by(location_name=location_name, is_active=True).first()
    
    def create_warehouse(self, location_name, address=None, city=None, state=None, country=None):
        """Create new warehouse"""
        warehouse = Warehouse(
            location_name=location_name,
            address=address,
            city=city,
            state=state,
            country=country
        )
        db.session.add(warehouse)
        db.session.commit()
        return warehouse
    
    # Product Management
    def get_products_by_warehouse(self, warehouse_id):
        """Get products by warehouse"""
        return Product.query.filter_by(warehouse_id=warehouse_id).all()
    
    def get_products_by_warehouse_location(self, warehouse_location):
        """Get products by warehouse location name"""
        warehouse = self.get_warehouse_by_location(warehouse_location)
        if warehouse:
            return self.get_products_by_warehouse(warehouse.id)
        return []
    
    def get_product_by_code_and_warehouse(self, product_code, warehouse_id):
        """Get specific product by code and warehouse"""
        return Product.query.filter_by(
            product_code=product_code,
            warehouse_id=warehouse_id
        ).first()
    
    def update_product_quantities(self, product_id, quantity_ordered):
        """Update product quantities when order is placed"""
        product = Product.query.get(product_id)
        if product and product.available_for_sale >= quantity_ordered:
            product.blocked_quantity += quantity_ordered
            product.update_available_quantity()
            db.session.commit()
            return True
        return False
    
    def search_products(self, query, warehouse_id=None):
        """Search products by name or code"""
        search_filter = or_(
            Product.product_name.ilike(f'%{query}%'),
            Product.product_code.ilike(f'%{query}%'),
            Product.product_description.ilike(f'%{query}%')
        )
        
        if warehouse_id:
            return Product.query.filter(
                and_(search_filter, Product.warehouse_id == warehouse_id)
            ).all()
        else:
            return Product.query.filter(search_filter).all()
    
    # Order Management
    def create_order(self, user_id, warehouse_id, warehouse_location, user_email):
        """Create new order"""
        order = Order(
            user_id=user_id,
            warehouse_id=warehouse_id,
            warehouse_location=warehouse_location,
            user_email=user_email
        )
        order.generate_order_id()
        db.session.add(order)
        db.session.commit()
        return order
    
    def add_order_item(self, order_id, product_id, product_code, quantity, unit_price, total_price=None):
        """Add item to order"""
        if total_price is None:
            total_price = quantity * unit_price
        order_item = OrderItem(
            order_id=order_id,
            product_id=product_id,
            product_code=product_code,
            product_quantity_ordered=quantity,
            unit_price=unit_price,
            total_price=total_price
        )
        db.session.add(order_item)
        db.session.commit()
        return order_item
    
    def update_order_total(self, order_id):
        """Update order total amount"""
        order = Order.query.get(order_id)
        if order:
            total = sum(item.total_price for item in order.order_items)
            order.total_amount = total
            db.session.commit()
            return order
        return None
    
    def get_orders_by_user(self, user_id):
        """Get orders by user"""
        return Order.query.filter_by(user_id=user_id).order_by(Order.order_date.desc()).all()
    
    def get_orders_by_email(self, email):
        """Get orders by email"""
        return Order.query.filter_by(user_email=email).order_by(Order.order_date.desc()).all()
    
    def get_order_by_id(self, order_id):
        """Get order by order ID"""
        return Order.query.filter_by(order_id=order_id).first()
    
    def update_order_status(self, order_id, status):
        """Update order status"""
        order = Order.query.filter_by(order_id=order_id).first()
        if order:
            order.status = status
            db.session.commit()
            return order
        return None
    
    # Chat Session Management
    def create_chat_session(self, user_id):
        """Create new chat session"""
        session = ChatSession(user_id=user_id)
        session.generate_session_id()
        db.session.add(session)
        db.session.commit()
        return session
    
    def get_active_session(self, user_id):
        """Get active chat session for user"""
        return ChatSession.query.filter_by(
            user_id=user_id,
            is_active=True,
            is_deleted=False
        ).first()
    
    def deactivate_session(self, session_id):
        """Deactivate chat session"""
        try:
            session = ChatSession.query.filter_by(session_id=session_id).first()
            if session:
                session.is_active = False
                session.is_deleted = True
                session.deleted_at = datetime.utcnow()
                db.session.commit()
                self.logger.info(f"Successfully deactivated session {session_id}")
                return True
            else:
                self.logger.warning(f"No session found to deactivate: {session_id}")
                return False
        except Exception as e:
            self.logger.error(f"Error deactivating session {session_id}: {str(e)}")
            try:
                db.session.rollback()
            except:
                pass
            return False
    
    def delete_session_conversations(self, session_id):
        """Delete conversations for a session"""
        try:
            # First, find the chat session by session_id to get the integer ID
            chat_session = ChatSession.query.filter_by(session_id=session_id).first()
            if not chat_session:
                self.logger.warning(f"No chat session found for session_id: {session_id}")
                return True
            
            # Delete conversations using the chat_session.id (integer)
            conversations = Conversation.query.filter_by(session_id=chat_session.id).all()
            
            for conv in conversations:
                db.session.delete(conv)
            
            db.session.commit()
            self.logger.info(f"Deleted {len(conversations)} conversations for session {session_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error deleting conversations for session {session_id}: {str(e)}")
            try:
                db.session.rollback()
            except:
                pass
            return False
    
    # Conversation Management
    def save_conversation(self, user_id, session_id, user_message, bot_response, data_sources=None, response_time=None):
        """Save conversation"""
        try:
            # Find the chat session by session_id to get the integer ID
            chat_session = ChatSession.query.filter_by(session_id=session_id).first()
            if not chat_session:
                self.logger.error(f"No chat session found for session_id: {session_id}")
                return None
            
            conversation = Conversation(
                user_id=user_id,
                session_id=chat_session.id,  # Use the integer ID from chat_session
                user_message=user_message,
                bot_response=bot_response,
                data_sources=data_sources,
                response_time=response_time
            )
            db.session.add(conversation)
            db.session.commit()
            self.logger.info(f"Saved conversation for user {user_id} in session {session_id}")
            return conversation
            
        except Exception as e:
            self.logger.error(f"Error saving conversation: {str(e)}")
            try:
                db.session.rollback()
            except:
                pass
            return None
    
    def get_conversation_history(self, user_id, limit=50):
        """Get conversation history for user"""
        return Conversation.query.filter_by(user_id=user_id).order_by(
            Conversation.created_at.desc()
        ).limit(limit).all()
    
    def get_session_conversations(self, session_id):
        """Get conversations for a session"""
        try:
            # First, find the chat session by session_id to get the integer ID
            chat_session = ChatSession.query.filter_by(session_id=session_id).first()
            if not chat_session:
                self.logger.warning(f"No chat session found for session_id: {session_id}")
                return []
            
            # Query conversations using the chat_session.id (integer)
            conversations = Conversation.query.filter_by(session_id=chat_session.id).order_by(
                Conversation.created_at.asc()
            ).all()
            
            self.logger.info(f"Retrieved {len(conversations)} conversations for session {session_id}")
            return conversations
            
        except Exception as e:
            self.logger.error(f"Failed to get session conversations for {session_id}: {str(e)}")
            return []
    
    # Company Information
    def get_company_info(self):
        """Get company information (static data)"""
        return {
            'company_name': 'Quantum Blue',
            'description': 'Advanced AI-powered chatbot for warehouse management and order processing',
            'features': [
                'Smart order placement',
                'Real-time inventory tracking',
                'AI-powered customer support',
                'Multi-warehouse management'
            ],
            'contact_info': {
                'email': 'support@quantumblue.com',
                'phone': '+1-800-QUANTUM',
                'address': '123 AI Street, Tech City, TC 12345'
            }
        }
    
    # Database Initialization
    def initialize_warehouses(self):
        """Initialize default warehouses"""
        warehouses = [
            {'location_name': 'Mumbai Central', 'city': 'Mumbai', 'state': 'Maharashtra', 'country': 'India'},
            {'location_name': 'Delhi North', 'city': 'Delhi', 'state': 'Delhi', 'country': 'India'},
            {'location_name': 'Bangalore South', 'city': 'Bangalore', 'state': 'Karnataka', 'country': 'India'},
            {'location_name': 'Chennai East', 'city': 'Chennai', 'state': 'Tamil Nadu', 'country': 'India'}
        ]
        
        for warehouse_data in warehouses:
            existing = Warehouse.query.filter_by(location_name=warehouse_data['location_name']).first()
            if not existing:
                warehouse = Warehouse(**warehouse_data)
                db.session.add(warehouse)
        
        db.session.commit()
        self.logger.info("Warehouses initialized")
    
    def create_sample_products(self):
        """Create sample products for testing with enhanced discount and scheme system"""
        warehouses = self.get_warehouses()
        if not warehouses:
            return
        
        # Enhanced sample products with new discount and scheme system
        sample_products = [
            {
                'product_code': 'RB001',
                'product_name': 'Quantum Blue AI Processor',
                'product_description': 'High-performance quantum processor for AI applications with advanced neural processing',
                'price_of_product': 2500.00,
                'product_quantity': 100,
                'batch_number': 'RB2024001',
                'expiry_date': datetime(2025, 12, 31).date(),
                # New discount system
                'discount_type': 'percentage',
                'discount_value': 10.0,
                'discount_name': 'Early Bird Discount',
                # New scheme system
                'scheme_type': 'buy_x_get_y',
                'scheme_value': '{"buy": 2, "get": 1, "free": true}',
                'scheme_name': 'Buy 2 Get 1 Free',
                # Legacy fields for backward compatibility
                'discount': 250.00,
                'scheme': 'Buy 2 Get 1 Free'
            },
            {
                'product_code': 'RB002',
                'product_name': 'Neural Network Module Pro',
                'product_description': 'Advanced neural network processing module with enhanced learning capabilities',
                'price_of_product': 1200.00,
                'product_quantity': 50,
                'batch_number': 'RB2024002',
                'expiry_date': datetime(2025, 10, 15).date(),
                'discount_type': 'fixed',
                'discount_value': 100.0,
                'discount_name': 'Bulk Purchase Discount',
                'scheme_type': 'percentage_off',
                'scheme_value': '{"percentage": 20, "min_quantity": 1}',
                'scheme_name': 'Buy 1 Get 20% Off',
                'discount': 100.00,
                'scheme': 'Buy 1 Get 20% Off'
            },
            {
                'product_code': 'RB003',
                'product_name': 'AI Memory Card Ultra',
                'product_description': 'High-speed memory card for AI operations with quantum storage technology',
                'price_of_product': 800.00,
                'product_quantity': 200,
                'batch_number': 'RB2024003',
                'expiry_date': datetime(2025, 8, 30).date(),
                'discount_type': 'bulk',
                'discount_value': 50.0,
                'discount_name': 'Loyalty Discount',
                'scheme_type': 'buy_x_get_y',
                'scheme_value': '{"buy": 3, "get": 2, "free": true}',
                'scheme_name': 'Buy 3 Get 2 Free',
                'discount': 50.00,
                'scheme': 'Buy 3 Get 2 Free'
            },
            {
                'product_code': 'RB004',
                'product_name': 'Quantum Sensors Advanced',
                'product_description': 'Advanced quantum sensing technology with precision measurement capabilities',
                'price_of_product': 1800.00,
                'product_quantity': 75,
                'batch_number': 'RB2024004',
                'expiry_date': datetime(2025, 11, 20).date(),
                'discount_type': 'percentage',
                'discount_value': 15.0,
                'discount_name': 'Volume Discount',
                'scheme_type': 'percentage_off',
                'scheme_value': '{"percentage": 15, "min_quantity": 1}',
                'scheme_name': 'Buy 1 Get 15% Off',
                'discount': 270.00,
                'scheme': 'Buy 1 Get 15% Off'
            },
            {
                'product_code': 'RB005',
                'product_name': 'AI Controller Master',
                'product_description': 'Smart AI control unit for automation with machine learning integration',
                'price_of_product': 950.00,
                'product_quantity': 120,
                'batch_number': 'RB2024005',
                'expiry_date': datetime(2025, 9, 10).date(),
                'discount_type': 'fixed',
                'discount_value': 75.0,
                'discount_name': 'Starter Discount',
                'scheme_type': 'percentage_off',
                'scheme_value': '{"percentage": 25, "min_quantity": 2}',
                'scheme_name': 'Buy 2 Get 25% Off',
                'discount': 75.00,
                'scheme': 'Buy 2 Get 25% Off'
            },
            # Additional products for more variety
            {
                'product_code': 'RB006',
                'product_name': 'Quantum Blue Data Analyzer',
                'product_description': 'Advanced data analysis tool with quantum computing capabilities',
                'price_of_product': 3200.00,
                'product_quantity': 30,
                'batch_number': 'RB2024006',
                'expiry_date': datetime(2025, 12, 15).date(),
                'discount_type': 'percentage',
                'discount_value': 12.0,
                'discount_name': 'Premium Discount',
                'scheme_type': 'buy_x_get_y',
                'scheme_value': '{"buy": 1, "get": 1, "free": false, "discount_percent": 50}',
                'scheme_name': 'Buy 1 Get 1 at 50% Off',
                'discount': 384.00,
                'scheme': 'Buy 1 Get 1 at 50% Off'
            },
            {
                'product_code': 'RB007',
                'product_name': 'Neural Interface Hub',
                'product_description': 'Connect multiple AI systems with advanced neural interface technology',
                'price_of_product': 1500.00,
                'product_quantity': 60,
                'batch_number': 'RB2024007',
                'expiry_date': datetime(2025, 10, 30).date(),
                'discount_type': 'bulk',
                'discount_value': 150.0,
                'discount_name': 'Enterprise Discount',
                'scheme_type': 'buy_x_get_y',
                'scheme_value': '{"buy": 2, "get": 1, "free": true}',
                'scheme_name': 'Buy 2 Get 1 Free',
                'discount': 150.00,
                'scheme': 'Buy 2 Get 1 Free'
            },
            {
                'product_code': 'RB008',
                'product_name': 'Quantum Blue Security Module',
                'product_description': 'Advanced security module with quantum encryption for AI systems',
                'price_of_product': 2200.00,
                'product_quantity': 40,
                'batch_number': 'RB2024008',
                'expiry_date': datetime(2025, 11, 25).date(),
                'discount_type': 'percentage',
                'discount_value': 8.0,
                'discount_name': 'Security Discount',
                'scheme_type': 'percentage_off',
                'scheme_value': '{"percentage": 20, "min_quantity": 1}',
                'scheme_name': 'Buy 1 Get 20% Off',
                'discount': 176.00,
                'scheme': 'Buy 1 Get 20% Off'
            }
        ]
        
        for warehouse in warehouses:
            for product_data in sample_products:
                existing = Product.query.filter_by(
                    product_code=product_data['product_code'],
                    warehouse_id=warehouse.id
                ).first()
                
                if not existing:
                    product = Product(
                        warehouse_id=warehouse.id,
                        **product_data
                    )
                    # Ensure all quantity fields are properly initialized
                    if product.product_quantity is None:
                        product.product_quantity = 0
                    if product.blocked_quantity is None:
                        product.blocked_quantity = 0
                    if product.available_for_sale is None:
                        product.available_for_sale = 0
                    
                    product.update_available_quantity()
                    db.session.add(product)
        
        db.session.commit()
        self.logger.info("Sample products created")
    
    def create_sample_users(self):
        """Create sample users for testing"""
        sample_users = [
            # Customers
            {
                'name': 'John Smith',
                'email': 'john.smith@email.com',
                'phone': '+1234567890',
                'user_type': 'customer',
                'role': 'Individual Customer',
                'delivery_pin_code': '10001',
                'delivery_zone': 'North Zone',
                'nearest_warehouse': 'Mumbai Central',
                'nearest_distributor': 'Mumbai Distributor',
                'company_name': None,
                'company_address': None
            },
            {
                'name': 'Sarah Johnson',
                'email': 'sarah.johnson@email.com',
                'phone': '+1234567891',
                'user_type': 'customer',
                'role': 'Individual Customer',
                'delivery_pin_code': '10002',
                'delivery_zone': 'South Zone',
                'nearest_warehouse': 'Bangalore South',
                'nearest_distributor': 'Bangalore Distributor',
                'company_name': None,
                'company_address': None
            },
            # Medical Representatives
            {
                'name': 'Dr. Michael Brown',
                'email': 'michael.brown@rb.com',
                'phone': '+1234567892',
                'user_type': 'mr',
                'role': 'Medical Representative',
                'delivery_pin_code': '10003',
                'delivery_zone': 'East Zone',
                'nearest_warehouse': 'Chennai East',
                'nearest_distributor': 'Chennai Distributor',
                'company_name': 'RB Pharmaceuticals',
                'company_address': '123 Medical Street, Chennai'
            },
            {
                'name': 'Dr. Emily Davis',
                'email': 'emily.davis@rb.com',
                'phone': '+1234567893',
                'user_type': 'mr',
                'role': 'Senior Medical Representative',
                'delivery_pin_code': '10004',
                'delivery_zone': 'West Zone',
                'nearest_warehouse': 'Mumbai Central',
                'nearest_distributor': 'Mumbai Distributor',
                'company_name': 'RB Pharmaceuticals',
                'company_address': '456 Pharma Avenue, Mumbai'
            },
            # Distributors
            {
                'name': 'Rajesh Kumar',
                'email': 'rajesh.kumar@distributor.com',
                'phone': '+1234567894',
                'user_type': 'distributor',
                'role': 'Regional Distributor',
                'delivery_pin_code': '10005',
                'delivery_zone': 'North Zone',
                'nearest_warehouse': 'Delhi North',
                'nearest_distributor': 'Delhi Distributor',
                'company_name': 'Kumar Distributors Pvt Ltd',
                'company_address': '789 Distribution Center, Delhi'
            },
            {
                'name': 'Priya Sharma',
                'email': 'priya.sharma@distributor.com',
                'phone': '+1234567895',
                'user_type': 'distributor',
                'role': 'City Distributor',
                'delivery_pin_code': '10006',
                'delivery_zone': 'South Zone',
                'nearest_warehouse': 'Bangalore South',
                'nearest_distributor': 'Bangalore Distributor',
                'company_name': 'Sharma Medical Supplies',
                'company_address': '321 Supply Chain Road, Bangalore'
            },
            # Pharmacies
            {
                'name': 'City Pharmacy',
                'email': 'orders@citypharmacy.com',
                'phone': '+1234567896',
                'user_type': 'pharmacy',
                'role': 'Retail Pharmacy',
                'delivery_pin_code': '10007',
                'delivery_zone': 'Central Zone',
                'nearest_warehouse': 'Mumbai Central',
                'nearest_distributor': 'Mumbai Distributor',
                'company_name': 'City Pharmacy Chain',
                'company_address': '654 Pharmacy Street, Mumbai'
            },
            {
                'name': 'Health Plus Pharmacy',
                'email': 'orders@healthplus.com',
                'phone': '+1234567897',
                'user_type': 'pharmacy',
                'role': 'Chain Pharmacy',
                'delivery_pin_code': '10008',
                'delivery_zone': 'East Zone',
                'nearest_warehouse': 'Chennai East',
                'nearest_distributor': 'Chennai Distributor',
                'company_name': 'Health Plus Pharmacy Chain',
                'company_address': '987 Health Avenue, Chennai'
            }
        ]
        
        for user_data in sample_users:
            existing = User.query.filter_by(email=user_data['email']).first()
            if not existing:
                user = User(**user_data)
                user.generate_unique_id()
                user.is_verified = True
                user.email_verified = True
                db.session.add(user)
        
        db.session.commit()
        self.logger.info("Sample users created")
    
    def get_product_by_code(self, product_code):
        """Get product by product code"""
        return Product.query.filter_by(product_code=product_code).first()
    
    def get_product_pricing(self, product_id, quantity):
        """Get dynamic pricing for a product with discounts and schemes"""
        try:
            product = Product.query.get(product_id)
            if not product:
                return {
                    'final_price': 0,
                    'discount_percentage': 0,
                    'scheme_name': None,
                    'total_amount': 0,
                    'total_quantity': quantity,
                    'paid_quantity': quantity,
                    'free_quantity': 0,
                    'base_price': 0,
                    'discount_amount': 0
                }
            
            base_price = float(product.price_of_product)
            discount_amount = float(product.discount) if product.discount else 0
            scheme = product.scheme if product.scheme else None
            
            # Calculate discount percentage
            discount_percentage = 0
            if discount_amount > 0:
                discount_percentage = (discount_amount / base_price) * 100
            
            # Start with base price minus discount
            price_after_discount = base_price - discount_amount
            
            # Initialize scheme variables
            final_price = price_after_discount
            total_quantity = quantity
            paid_quantity = quantity
            free_quantity = 0
            
            # Apply scheme-based discounts
            if scheme:
                if 'Buy 3 Get 2 Free' in scheme and quantity >= 3:
                    # Buy 3 Get 2 Free: For every 5 items (3 paid + 2 free), user pays for 3
                    scheme_groups = quantity // 5
                    remaining_items = quantity % 5
                    
                    # Calculate free items from complete groups
                    free_quantity = scheme_groups * 2
                    paid_quantity = scheme_groups * 3
                    
                    # Handle remaining items
                    if remaining_items >= 3:
                        # If 3 or more remaining, apply another group
                        free_quantity += 2
                        paid_quantity += 3
                    else:
                        # If less than 3 remaining, user pays for all remaining
                        paid_quantity += remaining_items
                    
                    total_quantity = quantity  # User gets all items
                    # Price per paid item remains the same
                    final_price = price_after_discount
                elif 'Buy 2 Get 1 Free' in scheme and quantity >= 2:
                    # Buy 2 Get 1 Free: For every 2 items bought, get 1 free
                    # So for every 3 items total (2 paid + 1 free), user pays for 2
                    scheme_groups = quantity // 3  # Number of complete "Buy 2 Get 1 Free" groups
                    remaining_items = quantity % 3
                    
                    # Calculate free items: 1 free for every 3 items (2 paid + 1 free)
                    free_quantity = scheme_groups * 1
                    paid_quantity = scheme_groups * 2
                    
                    # Handle remaining items
                    if remaining_items >= 2:
                        # If 2 or more remaining, user pays for all remaining (no free item for incomplete group)
                        paid_quantity += remaining_items
                    elif remaining_items == 1:
                        # If 1 remaining, user pays for it (no free item for single item)
                        paid_quantity += 1
                    
                    total_quantity = quantity  # User gets all items they requested
                    # Price per paid item remains the same
                    final_price = price_after_discount
                elif 'Buy 1 Get 20% Off' in scheme and quantity >= 1:
                    # 20% off on all items
                    final_price = price_after_discount * 0.80
                    total_quantity = quantity
                    paid_quantity = quantity
                    free_quantity = 0
                elif 'Buy 1 Get 15% Off' in scheme and quantity >= 1:
                    # 15% off on all items
                    final_price = price_after_discount * 0.85
                    total_quantity = quantity
                    paid_quantity = quantity
                    free_quantity = 0
                elif 'Buy 2 Get 25% Off' in scheme and quantity >= 2:
                    # 25% off on all items
                    final_price = price_after_discount * 0.75
                    total_quantity = quantity
                    paid_quantity = quantity
                    free_quantity = 0
            
            # Calculate total amount based on paid quantity
            total_amount = final_price * paid_quantity
            
            result = {
                'final_price': round(final_price, 2),
                'discount_percentage': round(discount_percentage, 2),
                'scheme_name': scheme,
                'total_amount': round(total_amount, 2),
                'total_quantity': total_quantity,
                'paid_quantity': paid_quantity,
                'free_quantity': free_quantity,
                'base_price': round(base_price, 2),
                'discount_amount': round(discount_amount, 2)
            }
            
            self.logger.info(f"Pricing calculation for product {product_id} (qty {quantity}): final_price={final_price}, paid_quantity={paid_quantity}, total_amount={total_amount}")
            self.logger.info(f"Full result: {result}")
            return result
            
        except Exception as e:
            self.logger.error(f"Error calculating pricing for product {product_id}: {str(e)}")
            # Return base pricing as fallback
            product = Product.query.get(product_id)
            if product:
                base_price = float(product.price_of_product)
                return {
                    'final_price': base_price,
                    'discount_percentage': 0,
                    'scheme_name': None,
                    'total_amount': base_price * quantity,
                    'total_quantity': quantity,
                    'paid_quantity': quantity,
                    'free_quantity': 0,
                    'base_price': round(base_price, 2),
                    'discount_amount': 0
                }
            return {
                'final_price': 0,
                'discount_percentage': 0,
                'scheme_name': None,
                'total_amount': 0,
                'total_quantity': quantity,
                'paid_quantity': quantity,
                'free_quantity': 0,
                'base_price': 0,
                'discount_amount': 0
            }
    
    def update_product_quantities(self, product_quantities):
        """Update product quantities after order selection"""
        try:
            for product_code, quantity in product_quantities.items():
                product = Product.query.filter_by(product_code=product_code).first()
                if product:
                    # Reduce available quantity
                    if product.available_for_sale >= quantity:
                        product.available_for_sale -= quantity
                        product.update_available_quantity()
                    else:
                        self.logger.warning(f"Insufficient stock for {product_code}: requested {quantity}, available {product.available_for_sale}")
            
            db.session.commit()
            return True
        except Exception as e:
            self.logger.error(f"Error updating product quantities: {str(e)}")
            db.session.rollback()
            return False
    
    def allocate_quantity_fefo(self, product_code, warehouse_id, quantity_to_allocate):
        """
        Allocate quantity using FEFO (First Expiry, First Out) logic
        Returns list of allocations with batch numbers and quantities
        """
        from datetime import date
        from sqlalchemy import or_
        
        try:
            # Get all batches of this product in the warehouse
            # Filter out expired batches and sort by expiry date (earliest first)
            # Batches with NULL expiry_date go to the end (treated as never expiring)
            today = date.today()
            
            # Get all batches, filtering out expired ones
            all_batches = Product.query.filter_by(
                product_code=product_code,
                warehouse_id=warehouse_id,
                is_active=True
            ).filter(
                or_(
                    Product.expiry_date >= today,
                    Product.expiry_date.is_(None)
                )
            ).all()
            
            # Sort batches: those with expiry_date first (earliest first), then NULL expiry_date ones
            batches = sorted(
                all_batches,
                key=lambda b: (b.expiry_date is None, b.expiry_date or date.max)
            )
            
            # FEFO VERIFICATION LOGGING
            self.logger.info(f"=== FEFO ALLOCATION START ===")
            self.logger.info(f"Product: {product_code}, Warehouse: {warehouse_id}, Requested: {quantity_to_allocate}")
            self.logger.info(f"Total batches found: {len(batches)}")
            
            # Log all batches with their expiry dates for verification
            for idx, batch in enumerate(batches):
                expiry_str = batch.expiry_date.isoformat() if batch.expiry_date else "No expiry (NULL)"
                days_until_expiry = (batch.expiry_date - today).days if batch.expiry_date else "N/A"
                self.logger.info(f"  Batch #{idx+1}: {batch.batch_number} | Expiry: {expiry_str} | Days until expiry: {days_until_expiry} | Available: {batch.available_for_sale}")
            
            if not batches:
                self.logger.warning(f"No non-expired batches found for product {product_code} in warehouse {warehouse_id}")
                # Check if product exists in this warehouse but is expired
                expired_batches_raw = Product.query.filter_by(
                    product_code=product_code,
                    warehouse_id=warehouse_id,
                    is_active=True
                ).filter(
                    Product.expiry_date.isnot(None),
                    Product.expiry_date < today
                ).all()
                
                if expired_batches_raw:
                    # Use expired batches as fallback (still follow FEFO - earliest expired first)
                    expired_batches = sorted(
                        expired_batches_raw,
                        key=lambda b: (b.expiry_date is None, b.expiry_date or date.max)
                    )
                    earliest_expiry = min(batch.expiry_date for batch in expired_batches if batch.expiry_date)
                    days_expired = (today - earliest_expiry).days
                    total_expired_stock = sum(batch.available_for_sale for batch in expired_batches if batch.available_for_sale > 0)
                    self.logger.warning(f"⚠️ Using EXPIRED batches for {product_code} in warehouse {warehouse_id} (expired {days_expired} days ago). Available expired stock: {total_expired_stock}")
                    
                    if total_expired_stock < quantity_to_allocate:
                        return None, f"Insufficient expired stock for {product_code}. Available expired: {total_expired_stock}, Requested: {quantity_to_allocate}"
                    
                    # Allocate from expired batches using FEFO
                    allocations = []
                    remaining_quantity = quantity_to_allocate
                    
                    for batch_idx, batch in enumerate(expired_batches):
                        if remaining_quantity <= 0:
                            break
                        
                        available_in_batch = batch.available_for_sale
                        if available_in_batch <= 0:
                            continue
                        
                        allocate_from_batch = min(remaining_quantity, available_in_batch)
                        batch.blocked_quantity += allocate_from_batch
                        batch.update_available_quantity()
                        
                        expiry_str = batch.expiry_date.isoformat() if batch.expiry_date else "No expiry"
                        days_until = (batch.expiry_date - today).days if batch.expiry_date else None
                        self.logger.warning(f"⚠️ FEFO ALLOCATION FROM EXPIRED: Batch #{batch_idx+1} {batch.batch_number} | Allocated: {allocate_from_batch} | Expires: {expiry_str} | Days expired: {abs(days_until) if days_until else 'N/A'} | Remaining to allocate: {remaining_quantity}")
                        
                        allocations.append({
                            'batch_id': batch.id,
                            'batch_number': batch.batch_number,
                            'expiry_date': batch.expiry_date.isoformat() if batch.expiry_date else None,
                            'quantity': allocate_from_batch,
                            'product_code': batch.product_code,
                            'product_name': batch.product_name,
                            'days_until_expiry': days_until,
                            'is_expired': True
                        })
                        
                        remaining_quantity -= allocate_from_batch
                    
                    db.session.commit()
                    self.logger.warning(f"⚠️ FEFO: Successfully allocated all {quantity_to_allocate} units from EXPIRED batches")
                    
                    return allocations, "Allocation successful (using expired stock)"
                
                # Check if product exists in other warehouses
                product_in_other_warehouse = Product.query.filter_by(
                    product_code=product_code,
                    is_active=True
                ).filter(
                    Product.warehouse_id != warehouse_id
                ).first()
                
                if product_in_other_warehouse:
                    other_warehouse = Warehouse.query.get(product_in_other_warehouse.warehouse_id)
                    warehouse_name = other_warehouse.location_name if other_warehouse else f"warehouse {product_in_other_warehouse.warehouse_id}"
                    self.logger.warning(f"Product {product_code} exists in {warehouse_name}, but not in requested warehouse {warehouse_id}")
                    # Get the requested warehouse name for better error message
                    requested_warehouse = Warehouse.query.get(warehouse_id)
                    requested_name = requested_warehouse.location_name if requested_warehouse else f"warehouse {warehouse_id}"
                    return None, f"Product {product_code} is not available in your warehouse ({requested_name}). It is available in {warehouse_name}. Please contact support to transfer stock or place order from the correct warehouse."
                else:
                    return None, f"Product {product_code} not found in any warehouse"
            
            # Calculate total available across all batches
            total_available = sum(batch.available_for_sale for batch in batches if batch.available_for_sale > 0)
            self.logger.info(f"Total available stock: {total_available}")
            
            if total_available < quantity_to_allocate:
                self.logger.warning(f"FEFO: Insufficient stock. Available: {total_available}, Requested: {quantity_to_allocate}")
                return None, f"Insufficient stock for {product_code}. Available: {total_available}, Requested: {quantity_to_allocate}"
            
            allocations = []
            remaining_quantity = quantity_to_allocate
            self.logger.info(f"Starting allocation - remaining to allocate: {remaining_quantity}")
            
            # Allocate from earliest expiring batches first
            for batch_idx, batch in enumerate(batches):
                if remaining_quantity <= 0:
                    break
                
                available_in_batch = batch.available_for_sale
                if available_in_batch <= 0:
                    continue
                
                # Allocate as much as possible from this batch
                allocate_from_batch = min(remaining_quantity, available_in_batch)
                
                # Block the quantity
                batch.blocked_quantity += allocate_from_batch
                batch.update_available_quantity()
                
                expiry_str = batch.expiry_date.isoformat() if batch.expiry_date else "No expiry"
                days_until = (batch.expiry_date - today).days if batch.expiry_date else None
                self.logger.info(f"FEFO ALLOCATION: Batch #{batch_idx+1} {batch.batch_number} | Allocated: {allocate_from_batch} | Expires: {expiry_str} | Days until expiry: {days_until} | Remaining to allocate: {remaining_quantity}")
                
                allocations.append({
                    'batch_id': batch.id,
                    'batch_number': batch.batch_number,
                    'expiry_date': batch.expiry_date.isoformat() if batch.expiry_date else None,
                    'quantity': allocate_from_batch,
                    'product_code': batch.product_code,
                    'product_name': batch.product_name,
                    'days_until_expiry': days_until
                })
                
                remaining_quantity -= allocate_from_batch
            
            db.session.commit()
            
            if remaining_quantity > 0:
                self.logger.warning(f"FEFO: Could not allocate full quantity. Remaining: {remaining_quantity}")
            else:
                self.logger.info(f"FEFO: Successfully allocated all {quantity_to_allocate} units")
            
            # FEFO VERIFICATION SUMMARY
            self.logger.info(f"=== FEFO ALLOCATION COMPLETE ===")
            self.logger.info(f"Total batches used: {len(allocations)}")
            for alloc in allocations:
                self.logger.info(f"  - {alloc['quantity']} units from batch {alloc['batch_number']} (expires: {alloc['expiry_date']}, days until: {alloc.get('days_until_expiry', 'N/A')})")
            
            return allocations, "Allocation successful"
            
        except Exception as e:
            error_msg = str(e)
            self.logger.error(f"Error in FEFO allocation for {product_code}: {error_msg}")
            # Check if it's a database connection error
            if 'Connection' in error_msg or 'pymssql' in error_msg.lower() or 'InterfaceError' in error_msg:
                self.logger.error(f"Database connection error detected. Please check database connectivity.")
            db.session.rollback()
            return None, f"Error allocating products: {str(e)}"
    
    # Cart Management
    def add_to_cart(self, user_id, product_id, quantity, pricing_details=None):
        """Add item to user's cart"""
        try:
            # Check if item already exists in cart
            existing_item = CartItem.query.filter_by(
                user_id=user_id, 
                product_id=product_id
            ).first()
            
            if existing_item:
                # Update cumulative quantities
                existing_item.product_quantity += quantity
                if pricing_details:
                    existing_item.base_price = pricing_details.get('base_price', existing_item.base_price or 0)
                    existing_item.discount_amount = (existing_item.discount_amount or 0) + pricing_details.get('discount_amount', 0)
                    existing_item.scheme_discount_amount = (existing_item.scheme_discount_amount or 0) + pricing_details.get('scheme_discount_amount', 0)
                    existing_item.final_price = pricing_details.get('final_price', existing_item.final_price or 0)
                    existing_item.scheme_applied = pricing_details.get('scheme_name', existing_item.scheme_applied)
                    # Accumulate paid/free correctly
                    existing_item.free_quantity = (existing_item.free_quantity or 0) + pricing_details.get('free_quantity', 0)
                    existing_item.paid_quantity = (existing_item.paid_quantity or 0) + pricing_details.get('paid_quantity', quantity)
                else:
                    existing_item.paid_quantity = (existing_item.paid_quantity or 0) + quantity
                
                existing_item.total_price = (existing_item.final_price or 0) * (existing_item.paid_quantity or 0)
                existing_item.updated_at = datetime.utcnow()
            else:
                # Create new cart item
                product = Product.query.get(product_id)
                if not product:
                    return None, "Product not found"
                
                cart_item = CartItem(
                    user_id=user_id,
                    product_id=product_id,
                    product_code=product.product_code,
                    product_quantity=quantity,
                    unit_price=product.price_of_product,
                    base_price=pricing_details.get('base_price', product.price_of_product) if pricing_details else product.price_of_product,
                    discount_amount=pricing_details.get('discount_amount', 0) if pricing_details else 0,
                    scheme_discount_amount=pricing_details.get('scheme_discount_amount', 0) if pricing_details else 0,
                    final_price=pricing_details.get('final_price', product.price_of_product) if pricing_details else product.price_of_product,
                    scheme_applied=pricing_details.get('scheme_name') if pricing_details else None,
                    free_quantity=pricing_details.get('free_quantity', 0) if pricing_details else 0,
                    paid_quantity=pricing_details.get('paid_quantity', quantity) if pricing_details else quantity
                )
                cart_item.total_price = cart_item.final_price * cart_item.paid_quantity
                db.session.add(cart_item)
            
            db.session.commit()
            return existing_item if existing_item else cart_item, "Item added to cart"
            
        except Exception as e:
            self.logger.error(f"Error adding to cart: {str(e)}")
            db.session.rollback()
            return None, f"Error adding to cart: {str(e)}"
    
    def get_cart_items(self, user_id):
        """Get user's cart items"""
        return CartItem.query.filter_by(user_id=user_id).all()
    
    def update_cart_item_quantity(self, cart_item_id, quantity):
        """Update cart item quantity"""
        try:
            cart_item = CartItem.query.get(cart_item_id)
            if cart_item:
                cart_item.product_quantity = quantity
                cart_item.total_price = cart_item.final_price * cart_item.paid_quantity
                cart_item.updated_at = datetime.utcnow()
                db.session.commit()
                return cart_item, "Cart item updated"
            return None, "Cart item not found"
        except Exception as e:
            self.logger.error(f"Error updating cart item: {str(e)}")
            db.session.rollback()
            return None, f"Error updating cart item: {str(e)}"
    
    def remove_from_cart(self, cart_item_id):
        """Remove item from cart"""
        try:
            cart_item = CartItem.query.get(cart_item_id)
            if cart_item:
                db.session.delete(cart_item)
                db.session.commit()
                return True, "Item removed from cart"
            return False, "Cart item not found"
        except Exception as e:
            error_msg = str(e)
            self.logger.error(f"Error removing from cart: {error_msg}")
            # Check if it's a database connection error
            if 'Connection' in error_msg or 'pymssql' in error_msg.lower() or 'InterfaceError' in error_msg:
                self.logger.error(f"Database connection error detected. Attempting to reconnect...")
                try:
                    db.session.close()
                    db.session.rollback()
                except:
                    pass
            db.session.rollback()
            return False, f"Error removing from cart: {str(e)}"
    
    def remove_from_cart_by_product(self, user_id, product_id, quantity):
        """Remove specific quantity of a product from cart"""
        try:
            cart_item = CartItem.query.filter_by(
                user_id=user_id, 
                product_id=product_id
            ).first()
            
            if not cart_item:
                return False, "Product not found in cart"
            
            if cart_item.product_quantity <= quantity:
                # Remove entire item
                db.session.delete(cart_item)
                db.session.commit()
                return True, f"Removed all {cart_item.product.product_name} from cart"
            else:
                # Reduce quantity
                cart_item.product_quantity -= quantity
                cart_item.paid_quantity = max(0, cart_item.paid_quantity - quantity)
                cart_item.total_price = cart_item.final_price * cart_item.paid_quantity
                cart_item.updated_at = datetime.utcnow()
                db.session.commit()
                return True, f"Removed {quantity} {cart_item.product.product_name} from cart"
                
        except Exception as e:
            error_msg = str(e)
            self.logger.error(f"Error removing from cart by product: {error_msg}")
            # Check if it's a database connection error
            if 'Connection' in error_msg or 'pymssql' in error_msg.lower() or 'InterfaceError' in error_msg:
                self.logger.error(f"Database connection error detected. Attempting to reconnect...")
                try:
                    db.session.close()
                    db.session.rollback()
                except:
                    pass
            db.session.rollback()
            return False, f"Error removing from cart: {str(e)}"
    
    def clear_cart(self, user_id):
        """Clear user's cart"""
        try:
            CartItem.query.filter_by(user_id=user_id).delete()
            db.session.commit()
            return True, "Cart cleared"
        except Exception as e:
            self.logger.error(f"Error clearing cart: {str(e)}")
            db.session.rollback()
            return False, f"Error clearing cart: {str(e)}"

    def get_distributor_for_warehouse(self, warehouse_location):
        """Get distributor for a specific warehouse location"""
        return User.query.filter_by(user_type='distributor', nearest_warehouse=warehouse_location).first()

    def get_orders_for_distributor(self, distributor_user, status_filter=None):
        """Get orders for a distributor's warehouse
        
        Args:
            distributor_user: Distributor user object
            status_filter: Optional list of statuses to filter by. If None, returns all orders except 'completed'.
                           Examples: ['in_transit'], ['confirmed'], ['pending'], etc.
        """
        warehouse = distributor_user.nearest_warehouse
        
        # Build query
        query = Order.query.filter(Order.warehouse_location == warehouse)
        
        # Apply status filter
        if status_filter:
            if isinstance(status_filter, str):
                status_filter = [status_filter]
            # Filter by status or order_stage
            query = query.filter(
                or_(
                    Order.status.in_(status_filter),
                    Order.order_stage.in_(status_filter)
                )
            )
        else:
            # Default: exclude completed orders
            query = query.filter(Order.order_stage != 'completed')
        
        return query.order_by(Order.order_date.desc()).all()
    
    # Pending Order Products Management
    def create_pending_order_product(self, original_order_id, product_code, product_name, 
                                    requested_quantity, user_id, user_email, 
                                    warehouse_id, warehouse_location):
        """Create a pending order product entry for expired items"""
        try:
            pending_order = PendingOrderProducts(
                original_order_id=original_order_id,
                product_code=product_code,
                product_name=product_name,
                requested_quantity=requested_quantity,
                user_id=user_id,
                user_email=user_email,
                warehouse_id=warehouse_id,
                warehouse_location=warehouse_location,
                status='pending'
            )
            db.session.add(pending_order)
            db.session.commit()
            self.logger.info(f"Created pending order for product {product_code} in order {original_order_id}")
            return pending_order
        except Exception as e:
            self.logger.error(f"Error creating pending order product: {str(e)}")
            db.session.rollback()
            return None
    
    def get_pending_order_products(self, user_id=None, original_order_id=None, warehouse_location=None, status='pending'):
        """Get pending order products with optional filters"""
        query = PendingOrderProducts.query.filter_by(status=status)
        
        if user_id:
            query = query.filter_by(user_id=user_id)
        if original_order_id:
            query = query.filter_by(original_order_id=original_order_id)
        if warehouse_location:
            query = query.filter_by(warehouse_location=warehouse_location)
        
        return query.all()
    
    def get_all_pending_products(self):
        """Get all pending products across all users"""
        return PendingOrderProducts.query.filter_by(status='pending').all()
    
    def update_pending_order_status(self, pending_id, status, fulfilled_order_id=None):
        """Update pending order status"""
        try:
            pending_order = PendingOrderProducts.query.get(pending_id)
            if pending_order:
                pending_order.status = status
                if fulfilled_order_id:
                    pending_order.fulfilled_order_id = fulfilled_order_id
                    pending_order.fulfilled_at = datetime.utcnow()
                db.session.commit()
                return pending_order
            return None
        except Exception as e:
            self.logger.error(f"Error updating pending order status: {str(e)}")
            db.session.rollback()
            return None
    
    def mark_pending_order_notified(self, pending_id, notification_type='user'):
        """Mark that a notification has been sent"""
        try:
            pending_order = PendingOrderProducts.query.get(pending_id)
            if pending_order:
                if notification_type == 'user':
                    pending_order.user_notified = True
                elif notification_type == 'distributor':
                    pending_order.distributor_notified = True
                db.session.commit()
                return pending_order
            return None
        except Exception as e:
            self.logger.error(f"Error marking pending order as notified: {str(e)}")
            db.session.rollback()
            return None