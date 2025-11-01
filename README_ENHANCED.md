# RB (Powered by Quantum Blue AI) - Enhanced Inventory and Order Management System

## Overview

This is a comprehensive inventory and order management system designed for RB (Powered by Quantum Blue AI) that integrates sales, distribution, and order tracking. The system resolves the visibility gap between the Company, Distributors, Medical Representatives (MRs), and Retailers/Pharmacies by automating order capture, stock tracking, and reporting through Azure-based architecture.

## Key Features

### 🎯 Core Functionality
- **Multi-User System**: Support for Customers, Medical Representatives, Distributors, and Pharmacies
- **LLM-Powered Product Extraction**: Intelligent extraction of products and quantities from natural language
- **Advanced Pricing System**: 3 predefined discounts and 3 schemes with automatic calculation
- **Cart Management**: Full shopping cart functionality with real-time pricing
- **Order Workflow**: Complete order lifecycle from placement to delivery
- **Distributor Confirmation**: Automated distributor notification and confirmation system
- **Invoice Generation**: Automatic invoice generation and email notifications

### 🏗️ System Architecture

#### 1. Data Entry and Synchronization Layer
- All sales from company to distributors recorded in Azure-hosted database
- Each transaction includes Product ID, Batch Number, Quantity, Unit Price, Expiry Date, Distributor details
- Automated daily refresh of sales and inventory data

#### 2. Authentication and Access Layer
- Unique ID-based user verification
- Email/mobile OTP authentication
- Location and delivery mapping based on pin codes

#### 3. Order Placement and Tracking Layer
- Intelligent chatbot interaction with LLM-powered responses
- Natural language product extraction (10-15 products at once)
- Real-time cart management with pricing calculations
- Order confirmation and editing capabilities

#### 4. Order Processing and Fulfillment Layer
- Automated distributor notifications
- Distributor order verification and confirmation
- Invoice generation and distribution
- Inventory adjustment and tracking

## Database Schema

### Enhanced User Model
```python
class User:
    unique_id: str          # Unique identifier for users
    user_type: str          # customer, mr, distributor, pharmacy
    role: str               # Medical Representative, Distributor, etc.
    delivery_pin_code: str  # Location-based delivery
    nearest_warehouse: str  # Assigned warehouse
    company_name: str       # Company information
    is_active: bool         # Account status
```

### Enhanced Product Model
```python
class Product:
    # Discount System (3 predefined)
    discount_type: str      # percentage, fixed, bulk
    discount_value: float   # Percentage or fixed amount
    discount_name: str      # Early Bird, Bulk Purchase, Loyalty
    
    # Scheme System (3 predefined)
    scheme_type: str        # buy_x_get_y, percentage_off, free_shipping
    scheme_value: str       # JSON with scheme details
    scheme_name: str        # Buy 2 Get 1 Free, etc.
    
    # Inventory Management
    confirmed_quantity: int # Quantity confirmed for orders
    blocked_quantity: int   # Quantity blocked during order process
```

### Enhanced Order Model
```python
class Order:
    # Order Workflow
    status: str             # pending, in_transit, confirmed, shipped, delivered
    order_stage: str        # draft, placed, distributor_notified, etc.
    
    # Order Placement
    placed_by: str          # customer, mr, distributor
    placed_by_user_id: int  # Who placed the order
    
    # Distributor Confirmation
    distributor_confirmed: bool
    distributor_confirmed_at: datetime
    distributor_confirmed_by: int
    
    # Invoice Details
    invoice_generated: bool
    invoice_number: str
```

## API Endpoints

### Enhanced Chatbot (`/enhanced-chat/`)
- `POST /message` - Process chat messages with LLM
- `POST /place_order` - Place order from cart
- `GET /cart` - Get user's cart items
- `DELETE /cart/<item_id>` - Remove item from cart
- `POST /distributor/confirm_order` - Distributor confirm order

### Legacy Chatbot (`/chat/`)
- `POST /message` - Original chatbot functionality
- `GET /` - Chat interface

## Installation and Setup

### 1. Prerequisites
```bash
pip install -r requirements.txt
```

### 2. Environment Variables
```bash
# Required
SECRET_KEY=your-secret-key
SQLALCHEMY_DATABASE_URI=your-database-uri

# Optional but recommended
GROQ_API_KEY=your-groq-api-key
MAIL_USERNAME=your-email
MAIL_PASSWORD=your-email-password
TAVILY_API_KEY=your-tavily-api-key
```

### 3. Initialize Database and Sample Data
```bash
python startup.py
```

### 4. Run the Application
```bash
python run.py
```

## Usage Guide

### 1. Access the System
- **Enhanced Chatbot**: http://localhost:5000/enhanced-chat
- **Legacy Chatbot**: http://localhost:5000/chat
- **Main Application**: http://localhost:5000

### 2. User Onboarding
1. Enter your unique ID (e.g., `CUST_20241201123456_ABC123`)
2. System will identify your user type and permissions
3. Access appropriate features based on your role

### 3. Sample User IDs for Testing
```
CUST_20241201123456_ABC123 - John Smith (Customer)
MR_20241201123457_DEF456 - Dr. Michael Brown (Medical Representative)
DIST_20241201123458_GHI789 - Rajesh Kumar (Distributor)
PHARM_20241201123459_JKL012 - City Pharmacy (Pharmacy)
```

### 4. Order Placement Workflow
1. **Start Order**: "I want to place an order"
2. **Add Products**: "Add 5 Quantum Blue AI Processors and 3 Neural Network Modules"
3. **Review Cart**: System shows pricing with discounts and schemes
4. **Confirm Order**: Order sent to distributor for confirmation
5. **Track Status**: Monitor order through completion

### 5. Distributor Workflow
1. **Receive Notification**: Email notification for new orders
2. **Review Order**: Check products, quantities, and customer details
3. **Confirm Order**: Accept or modify order details
4. **Invoice Generation**: Automatic invoice creation and distribution

## Discount and Scheme System

### Predefined Discounts
1. **Early Bird Discount** (10% off)
2. **Bulk Purchase Discount** ($100 off for orders >$1000)
3. **Loyalty Discount** (5% off for returning customers)

### Predefined Schemes
1. **Buy 2 Get 1 Free** - For every 2 items bought, get 1 free
2. **Buy 1 Get 20% Off** - 20% discount on all items
3. **Buy 3 Get 2 Free** - For every 3 items bought, get 2 free

## LLM Integration

### Product Extraction
- Natural language processing for product identification
- Quantity extraction from user messages
- Support for 10-15 products in single message
- Intelligent product name matching and synonyms

### Dynamic Responses
- Context-aware conversation management
- Personalized responses based on user type
- Intelligent order summaries with pricing details
- Professional business communication

## File Structure

```
chatbot-project/
├── app/
│   ├── models.py                 # Enhanced database models
│   ├── database_service.py       # Database operations
│   ├── pricing_service.py        # Discount and scheme calculations
│   ├── llm_order_service.py      # LLM-powered order processing
│   ├── enhanced_order_service.py # Complete order workflow
│   ├── enhanced_chatbot.py       # Enhanced chatbot interface
│   ├── chatbot.py               # Legacy chatbot
│   └── __init__.py              # App initialization
├── templates/
│   ├── enhanced_chat.html       # Enhanced chat interface
│   └── chat.html                # Legacy chat interface
├── static/js/
│   ├── enhanced_chat.js         # Enhanced chat JavaScript
│   └── chat.js                  # Legacy chat JavaScript
├── startup.py                   # Database initialization
├── run.py                       # Application entry point
└── README_ENHANCED.md           # This file
```

## Testing the System

### 1. Basic Order Flow
1. Access http://localhost:5000/enhanced-chat
2. Enter unique ID: `CUST_20241201123456_ABC123`
3. Say: "I want to place an order"
4. Add products: "Add 2 Quantum Blue AI Processors and 1 Neural Network Module Pro"
5. Review cart and place order

### 2. Distributor Confirmation
1. Use distributor ID: `DIST_20241201123458_GHI789`
2. Check for pending orders
3. Confirm orders as needed

### 3. Order Tracking
1. Use any user ID
2. Say: "Track my orders"
3. View order status and details

## Troubleshooting

### Common Issues
1. **Database Connection**: Ensure SQLALCHEMY_DATABASE_URI is correct
2. **LLM Services**: Check GROQ_API_KEY configuration
3. **Email Services**: Verify MAIL_USERNAME and MAIL_PASSWORD
4. **Sample Data**: Run `python startup.py` to initialize

### Logs
- Check console output for detailed error messages
- Database operations are logged with INFO level
- LLM requests are logged for debugging

## Future Enhancements

1. **WhatsApp Integration**: Extend to WhatsApp messaging
2. **Mobile App**: Native mobile application
3. **Advanced Analytics**: Business intelligence dashboard
4. **API Integration**: RESTful API for third-party integrations
5. **Real-time Notifications**: WebSocket-based live updates

## Support

For technical support or questions about the RB (Powered by Quantum Blue AI) system, please contact the development team or refer to the system documentation.

---

**RB (Powered by Quantum Blue AI)** - Intelligent Inventory and Order Management System
