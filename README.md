# 🤖 Quantum Blue AI - Intelligent Order Management Chatbot

<div align="center">

![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)
![Flask](https://img.shields.io/badge/Flask-2.3+-green.svg)
![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-2.0+-red.svg)
![License](https://img.shields.io/badge/License-Proprietary-yellow.svg)

**An AI-powered chatbot for streamlined B2B order management, inventory tracking, and analytics**

[Features](#-key-features) • [Installation](#-installation) • [Usage](#-usage) • [Architecture](#-architecture) • [API Reference](#-api-reference)

</div>

---

## 📋 Table of Contents

- [Overview](#-overview)
- [Key Features](#-key-features)
- [System Architecture](#-system-architecture)
- [Technology Stack](#-technology-stack)
- [Installation](#-installation)
- [Configuration](#-configuration)
- [Usage Guide](#-usage-guide)
- [User Roles & Workflows](#-user-roles--workflows)
- [Database Schema](#-database-schema)
- [API Reference](#-api-reference)
- [Email System](#-email-system)
- [Security](#-security)
- [Troubleshooting](#-troubleshooting)
- [Contributing](#-contributing)
- [License](#-license)

---

## 🎯 Overview

**Quantum Blue AI Chatbot** is an enterprise-grade conversational AI platform designed specifically for B2B distribution and wholesale operations. It streamlines the entire order management lifecycle—from product discovery to order fulfillment—using natural language processing and intelligent automation.

### What Problem Does It Solve?

- **Manual Order Processing**: Eliminates time-consuming phone calls and emails for order placement
- **Stock Visibility**: Real-time inventory tracking across multiple dealers and warehouses
- **Complex Pricing**: Automated FOC (Free of Cost) calculations and discount management
- **Multi-Role Coordination**: Seamless communication between MRs (Medical Representatives), Distributors, and Company Admin
- **Analytics Gap**: Comprehensive reporting and data export for business intelligence

### Who Is It For?

- **Medical Representatives (MRs)**: Place orders on behalf of dealers/retailers
- **Distributors**: Review, approve/reject orders, manage stock
- **Company Admin**: Generate analytics reports, monitor operations
- **Dealers/Retailers**: Track order status and delivery

---

## ✨ Key Features

### 🛒 **Intelligent Order Management**
- Natural language order placement ("I want to order 50 units of Product X")
- Real-time inventory checking across dealer networks
- Automatic FOC calculation with multi-tier schemes (e.g., Buy 10 Get 1, Buy 50 Get 6)
- Cart management with quantity adjustments
- Order confirmation workflow with email notifications

### 📊 **Advanced Analytics & Reporting**
- **Company Dashboard**: CSV export of all database tables
- **Custom Column Selection**: Choose specific fields for reports
- **Email Delivery**: Automatic report distribution
- **Real-time Stock Monitoring**: Track inventory levels across locations

### 💰 **Pricing & Discounts**
- Automatic 5% tax calculation
- FOC scheme application based on order quantities
- Dealer-specific pricing tiers
- Discount management system

### 📧 **Comprehensive Email System**
- **OTP Authentication**: Secure login with email verification
- **Order Confirmations**: Detailed order summaries with line items
- **Stock Alerts**: Notifications when inventory arrives
- **Rejection Notices**: Clear communication for declined orders
- **Analytics Reports**: CSV attachments with formatted HTML emails
- **Quantum Blue Branding**: Professional email templates with logo

### 🎨 **Modern UI/UX**
- **3D Avatar Assistant**: Powered by THREE.js with VRM support
- **Interactive Forms**: Dynamic product selection with search
- **Real-time Feedback**: Success/error messages with visual indicators
- **Responsive Design**: Mobile-friendly interface
- **Accessibility**: Screen reader compatible

### 🔐 **Security Features**
- Unique ID-based authentication per role
- Email OTP verification (2FA)
- Session management
- SQL injection prevention (SQLAlchemy ORM)
- CSRF protection
- Secure password hashing (Werkzeug)

---

## 🏗️ System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         Frontend Layer                           │
├─────────────────────────────────────────────────────────────────┤
│  • HTML5/CSS3/JavaScript (ES6+)                                  │
│  • THREE.js (3D Avatar)                                          │
│  • Jinja2 Templates                                              │
│  • Responsive Bootstrap Components                               │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                      Flask Application Layer                      │
├─────────────────────────────────────────────────────────────────┤
│  • Route Handlers (app/enhanced_chatbot.py)                      │
│  • Business Logic Services:                                      │
│    - LLM Classification (Groq AI)                                │
│    - Order Service (Order lifecycle)                             │
│    - Stock Management (Inventory tracking)                       │
│    - Email Service (SMTP integration)                            │
│    - Company Reports (CSV generation)                            │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                     Data Access Layer (ORM)                       │
├─────────────────────────────────────────────────────────────────┤
│  • SQLAlchemy Models (app/models.py)                             │
│  • Database Service (app/database_service.py)                    │
│  • Query Optimization                                            │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                      Database Layer (Azure SQL)                   │
├─────────────────────────────────────────────────────────────────┤
│  • Products & Inventory                                          │
│  • Orders & Order Items                                          │
│  • Users & Authentication                                        │
│  • FOC Schemes                                                   │
│  • Dealer Stock Details                                          │
│  • Email Logs & Chat Sessions                                    │
└─────────────────────────────────────────────────────────────────┘
```

### 🔄 **Data Flow Example: Order Placement**

```
1. MR enters: "I want to place an order for Dealer X"
   ↓
2. LLM classifies intent as "SELECT_CUSTOMER"
   ↓
3. System fetches dealer list from database
   ↓
4. MR selects dealer → System loads dealer's available products
   ↓
5. MR adds products to cart (FOC auto-calculated)
   ↓
6. MR confirms order → System creates Order record (status: PENDING)
   ↓
7. Email sent to Distributor for approval
   ↓
8. Distributor approves → Stock blocked, Email to MR & Company
   ↓
9. Order status updated to CONFIRMED
```

---

## 🛠️ Technology Stack

### **Backend**
| Technology | Version | Purpose |
|------------|---------|---------|
| **Python** | 3.8+ | Core programming language |
| **Flask** | 2.3+ | Web framework |
| **SQLAlchemy** | 2.0+ | ORM for database operations |
| **PyMSSQL** | 2.2+ | Azure SQL Server driver |
| **Werkzeug** | 2.3+ | Security utilities (password hashing) |

### **AI & NLP**
| Technology | Purpose |
|------------|---------|
| **Groq AI** | Intent classification & natural language understanding |
| **LLM Service** | Product matching, quantity extraction |

### **Frontend**
| Technology | Purpose |
|------------|---------|
| **HTML5/CSS3** | Structure & styling |
| **JavaScript (ES6+)** | Interactive UI logic |
| **THREE.js** | 3D avatar rendering |
| **VRM** | Avatar model format |
| **Jinja2** | Server-side templating |

### **Database**
| Technology | Purpose |
|------------|---------|
| **Azure SQL Database** | Primary data storage |
| **SQL Server Management Studio** | Database administration |

### **Email & Communication**
| Technology | Purpose |
|------------|---------|
| **SMTP (Gmail)** | Email delivery |
| **HTML Email Templates** | Formatted notifications |

### **Development & Deployment**
| Technology | Purpose |
|------------|---------|
| **Git** | Version control |
| **pip** | Python package management |
| **venv** | Virtual environment isolation |

---

## 📦 Installation

### Prerequisites

- **Python 3.8 or higher**
- **pip** (Python package manager)
- **Azure SQL Database** (or compatible SQL Server)
- **SMTP Email Account** (e.g., Gmail)
- **Groq API Key** (for AI features)

### Step 1: Clone the Repository

```bash
git clone https://github.com/MahendraMedapati27/Data_Management_Chatbot.git
cd Data_Management_Chatbot
```

### Step 2: Create Virtual Environment

```bash
# Windows
python -m venv venv
venv\Scripts\activate

# Linux/Mac
python3 -m venv venv
source venv/bin/activate
```

### Step 3: Install Dependencies

```bash
pip install -r requirements.txt
```

### Step 4: Configure Environment

Create a `config.py` file in the root directory:

```python
# config.py

# Database Configuration
DB_CONFIG = {
    'server': 'your-server.database.windows.net',
    'database': 'your-database-name',
    'user': 'your-username',
    'password': 'your-password',
    'driver': 'ODBC Driver 17 for SQL Server'
}

# Email Configuration (Gmail)
EMAIL_CONFIG = {
    'smtp_server': 'smtp.gmail.com',
    'smtp_port': 587,
    'sender_email': 'your-email@gmail.com',
    'sender_password': 'your-app-specific-password',
    'company_email': 'company-email@example.com'
}

# Groq AI Configuration
GROQ_API_KEY = 'your-groq-api-key'
GROQ_MODEL = 'llama-3.1-70b-versatile'

# Flask Configuration
SECRET_KEY = 'your-secret-key-change-this-in-production'
DEBUG = False  # Set to True for development
```

**⚠️ Security Note**: Never commit `config.py` to version control. Add it to `.gitignore`.

### Step 5: Initialize Database

```bash
python -c "from app.database_service import init_db; init_db()"
```

### Step 6: Run the Application

```bash
# Development
python run.py

# Production (use Gunicorn)
gunicorn -w 4 -b 0.0.0.0:5000 app:app
```

The application will be available at:
- **Local**: http://127.0.0.1:5000
- **Network**: http://[your-ip]:5000

---

## ⚙️ Configuration

### Database Schema Initialization

The application auto-creates tables on first run. To manually initialize:

```python
from app.database_service import init_db
init_db()
```

### Sample Data Import

To import sample products and users:

```python
python import_data_from_excel.py  # If you have Excel files
# OR
from app.database_service import create_sample_data
create_sample_data()
```

### User Creation

#### Create MR User:
```python
from app.models import User
from app.database_service import db_session

mr = User(
    name='John Doe',
    email='john@example.com',
    phone='1234567890',
    role='mr',
    unique_id='MR001'
)
db_session.add(mr)
db_session.commit()
```

#### Create Distributor User:
```python
distributor = User(
    name='ABC Distributors',
    email='abc@distributor.com',
    phone='9876543210',
    role='distributor',
    unique_id='DIST001'
)
db_session.add(distributor)
db_session.commit()
```

#### Create Company Admin:
```python
admin = User(
    name='Admin User',
    email='admin@company.com',
    role='company',
    unique_id='RB_COMPANY_001',
    email_verified=True
)
admin.set_password('secure_password')
db_session.add(admin)
db_session.commit()
```

---

## 📖 Usage Guide

### For Medical Representatives (MRs)

#### 1. **Login**
- Navigate to the chatbot URL
- Enter your unique ID (e.g., `MR001`)
- Verify with OTP sent to your registered email

#### 2. **Place an Order**
```
You: "I want to place an order"
Bot: "Please select a customer..."
[Select dealer from dropdown]

Bot: "Great! Here are the available products for [Dealer Name]"
[Product selection form appears]

[Enter quantities for desired products]
[Click "Add to Cart"]

You: "View cart"
Bot: [Displays cart with subtotal, tax, and total]

You: "Confirm order"
Bot: "Order placed successfully! Confirmation sent to distributor."
```

#### 3. **Track Orders**
```
You: "Track my orders"
Bot: [Displays list of pending/confirmed orders with status]
```

### For Distributors

#### 1. **Login**
- Enter distributor unique ID
- Verify with OTP

#### 2. **Review Orders**
```
You: "Track orders"
Bot: [Displays pending orders requiring approval]
```

#### 3. **Approve/Reject Orders**
- Click "Approve" or "Reject" on order details
- System sends email notifications to all parties
- Stock automatically blocked for approved orders

### For Company Admin

#### 1. **Login**
- Enter company unique ID (`RB_COMPANY_001`)
- Authenticate with password + OTP

#### 2. **Generate Reports**
```
You: "Generate report"
Bot: [Displays list of database tables]
[Select table: Products, Orders, Users, etc.]

Bot: [Displays column selection for chosen table]
[Select columns you want to export]

Bot: "Report generated! Check your email for the CSV file."
```

---

## 👥 User Roles & Workflows

### 🏥 **Medical Representative (MR)**

**Responsibilities:**
- Place orders on behalf of dealers/retailers
- Track order status
- Communicate product availability

**Workflow:**
```
Login → Select Dealer → Browse Products → Add to Cart → Confirm Order → Track Status
```

**Key Features:**
- Customer management
- Product catalog browsing
- FOC calculation visibility
- Order history

### 🏢 **Distributor**

**Responsibilities:**
- Approve/reject incoming orders
- Manage inventory levels
- Communicate with MRs and company

**Workflow:**
```
Login → View Pending Orders → Review Details → Approve/Reject → Stock Updates
```

**Key Features:**
- Order approval dashboard
- Stock management
- Email notifications
- Rejection reason input

### 🏛️ **Company Admin**

**Responsibilities:**
- Generate analytics reports
- Monitor system operations
- Export data for business intelligence

**Workflow:**
```
Login → Request Report → Select Table → Choose Columns → Receive Email with CSV
```

**Key Features:**
- Custom report generation
- CSV export of all tables
- Column-level filtering
- Email delivery

---

## 🗄️ Database Schema

### Core Tables

#### **users**
| Column | Type | Description |
|--------|------|-------------|
| id | INT (PK) | Auto-increment ID |
| name | VARCHAR(100) | User's full name |
| email | VARCHAR(100) | Email address |
| phone | VARCHAR(20) | Contact number |
| role | ENUM | 'mr', 'distributor', 'company' |
| unique_id | VARCHAR(50) | Login identifier |
| password_hash | VARCHAR(255) | Hashed password (company only) |
| email_verified | BOOLEAN | Email verification status |
| otp_secret | VARCHAR(10) | Current OTP |
| otp_created_at | DATETIME | OTP generation time |

#### **products**
| Column | Type | Description |
|--------|------|-------------|
| id | INT (PK) | Product ID |
| name | VARCHAR(200) | Product name |
| mrp | DECIMAL(10,2) | Maximum retail price |
| ptr | DECIMAL(10,2) | Price to retailer |
| pts | DECIMAL(10,2) | Price to stockist |
| description | TEXT | Product details |

#### **orders**
| Column | Type | Description |
|--------|------|-------------|
| id | INT (PK) | Order ID |
| mr_id | INT (FK) | Medical representative |
| customer_id | INT (FK) | Dealer/customer |
| subtotal | DECIMAL(10,2) | Pre-tax amount |
| tax_rate | DECIMAL(5,2) | Tax percentage (5%) |
| tax_amount | DECIMAL(10,2) | Calculated tax |
| total_amount | DECIMAL(10,2) | Grand total |
| status | ENUM | 'PENDING', 'CONFIRMED', 'REJECTED' |
| order_date | DATETIME | Creation timestamp |
| distributor_id | INT (FK) | Assigned distributor |

#### **order_items**
| Column | Type | Description |
|--------|------|-------------|
| id | INT (PK) | Item ID |
| order_id | INT (FK) | Parent order |
| product_id | INT (FK) | Product reference |
| quantity | INT | Ordered quantity |
| price | DECIMAL(10,2) | Unit price |
| foc_quantity | INT | Free items |

#### **foc**
| Column | Type | Description |
|--------|------|-------------|
| id | INT (PK) | FOC scheme ID |
| product_id | INT (FK) | Product reference |
| scheme_1 | VARCHAR(50) | Tier 1 (e.g., "10+1") |
| scheme_2 | VARCHAR(50) | Tier 2 (e.g., "20+2") |
| scheme_3 | VARCHAR(50) | Tier 3 (e.g., "50+6") |

#### **dealer_wise_stock_details**
| Column | Type | Description |
|--------|------|-------------|
| id | INT (PK) | Record ID |
| dealer_name | VARCHAR(100) | Dealer identifier |
| product_id | INT (FK) | Product reference |
| available_stock | INT | Current inventory |
| blocked_stock | INT | Reserved for orders |

### Relationship Diagram

```
users (MR) ──────┐
                 ├───→ orders ───→ order_items ───→ products
users (Customer) ┘                                        ↓
                                                         foc
users (Distributor) ───→ orders (approval)
                                                          
dealer_wise_stock_details ───→ products
```

---

## 🔌 API Reference

### Authentication Endpoints

#### **POST /api/auth/login**
```json
Request:
{
  "unique_id": "MR001"
}

Response:
{
  "success": true,
  "message": "OTP sent to your email",
  "user_id": 123
}
```

#### **POST /api/auth/verify-otp**
```json
Request:
{
  "user_id": 123,
  "otp": "123456"
}

Response:
{
  "success": true,
  "token": "session_token_here",
  "role": "mr"
}
```

### Order Management Endpoints

#### **POST /api/orders/create**
```json
Request:
{
  "mr_id": 1,
  "customer_id": 5,
  "items": [
    {
      "product_id": 10,
      "quantity": 50,
      "price": 100.00
    }
  ]
}

Response:
{
  "success": true,
  "order_id": 789,
  "total_amount": 5250.00,
  "message": "Order placed successfully"
}
```

#### **GET /api/orders/track/:role**
```json
Response:
{
  "success": true,
  "orders": [
    {
      "order_id": 789,
      "customer_name": "ABC Pharmacy",
      "total_amount": 5250.00,
      "status": "PENDING",
      "order_date": "2025-11-10T10:30:00"
    }
  ]
}
```

#### **POST /api/orders/approve**
```json
Request:
{
  "order_id": 789,
  "distributor_id": 2
}

Response:
{
  "success": true,
  "message": "Order approved and stock blocked"
}
```

### Report Generation Endpoints

#### **GET /company/tables**
```json
Response:
{
  "success": true,
  "tables": ["products", "orders", "users", "order_items"]
}
```

#### **POST /company/generate_report**
```json
Request:
{
  "table_name": "orders",
  "columns": ["id", "total_amount", "status", "order_date"]
}

Response:
{
  "success": true,
  "message": "Report sent to your email",
  "row_count": 150
}
```

---

## 📧 Email System

### Email Types

#### 1. **OTP Authentication**
- **Trigger**: User login
- **Recipient**: User's registered email
- **Content**: 6-digit OTP valid for 10 minutes
- **Template**: Plain text with branding

#### 2. **Order Confirmation (to Distributor)**
- **Trigger**: MR confirms order
- **Recipient**: Assigned distributor
- **Content**: 
  - Order ID and date
  - Customer details
  - Line items with quantities and FOC
  - Subtotal, tax (5%), and grand total
  - Approve/Reject buttons
- **Template**: HTML with Quantum Blue logo

#### 3. **Order Approval (to MR & Company)**
- **Trigger**: Distributor approves order
- **Recipients**: Ordering MR + Company email
- **Content**:
  - Confirmation message
  - Order summary
  - Stock blocking notice
- **Template**: HTML with Quantum Blue logo

#### 4. **Order Rejection (to MR)**
- **Trigger**: Distributor rejects order
- **Recipient**: Ordering MR
- **Content**:
  - Rejection notice
  - Reason for rejection
  - Order details for reference
- **Template**: HTML with Quantum Blue logo

#### 5. **Analytics Report (to Company Admin)**
- **Trigger**: Company requests report
- **Recipient**: Company admin email
- **Content**:
  - Report summary
  - CSV attachment
  - Row count and table name
- **Template**: HTML with Quantum Blue logo

### Email Configuration

#### Gmail Setup (Recommended):
1. Enable 2-Factor Authentication on your Gmail account
2. Generate an App-Specific Password:
   - Go to Google Account Settings
   - Security → App Passwords
   - Select "Mail" and your device
   - Copy the generated password
3. Use this password in `config.py`:

```python
EMAIL_CONFIG = {
    'smtp_server': 'smtp.gmail.com',
    'smtp_port': 587,
    'sender_email': 'your-email@gmail.com',
    'sender_password': 'your-16-char-app-password'
}
```

---

## 🔒 Security

### Authentication & Authorization

#### **Multi-Factor Authentication (MFA)**
- Unique ID + Email OTP for MRs and Distributors
- Password + Email OTP for Company Admin
- OTP expires after 10 minutes
- Maximum 3 OTP generation attempts per hour

#### **Session Management**
- Flask session cookies with secure flags
- Session timeout after 30 minutes of inactivity
- Logout invalidates session immediately

#### **Password Security**
- Werkzeug password hashing (PBKDF2)
- Minimum 8 characters required
- Company admin accounts only

### Data Protection

#### **SQL Injection Prevention**
- SQLAlchemy ORM (parameterized queries)
- Input validation on all user inputs
- Whitelist-based column selection for reports

#### **Cross-Site Scripting (XSS) Prevention**
- Jinja2 auto-escaping enabled
- Content Security Policy headers
- Input sanitization

#### **Cross-Site Request Forgery (CSRF)**
- CSRF tokens on all forms
- Same-origin policy enforcement

### Infrastructure Security

#### **Database**
- Azure SQL Database with TLS 1.2+
- Firewall rules (whitelist IPs)
- Encrypted connections
- Regular backups (Azure managed)

#### **Email**
- TLS encryption for SMTP
- App-specific passwords (no plain credentials)
- Rate limiting on OTP sends

---

## 🐛 Troubleshooting

### Common Issues

#### **Database Connection Failed**

**Symptoms:** `pymssql.OperationalError` on startup

**Solutions:**
1. Verify Azure SQL firewall allows your IP:
   ```
   Azure Portal → SQL Database → Firewalls and virtual networks
   ```
2. Check connection string in `config.py`
3. Test connection manually:
   ```python
   import pymssql
   conn = pymssql.connect(server='...', user='...', password='...', database='...')
   ```

#### **Email Not Sending**

**Symptoms:** OTP or order emails not received

**Solutions:**
1. Verify Gmail app password is correct
2. Check spam/junk folders
3. Enable "Less Secure Apps" (if not using app password)
4. Test SMTP connection:
   ```python
   import smtplib
   server = smtplib.SMTP('smtp.gmail.com', 587)
   server.starttls()
   server.login('your-email@gmail.com', 'app-password')
   ```

#### **Groq API Errors**

**Symptoms:** `401 Unauthorized` or `Rate Limit Exceeded`

**Solutions:**
1. Verify API key in `config.py`
2. Check quota at https://console.groq.com
3. Implement fallback logic for rate limits
4. Use caching for repeated queries

#### **Avatar Not Loading (T-Pose Issue)**

**Symptoms:** 3D avatar arms stuck horizontally

**Solutions:**
1. Hard refresh browser: `Ctrl + F5`
2. Clear browser cache
3. Check console for JavaScript errors
4. Verify `static/avatars/avatar.glb` exists
5. VRM A-shape pose is auto-applied on load

#### **Session Expiration**

**Symptoms:** "Session expired, please log in again"

**Solutions:**
1. Extend session timeout in `config.py`:
   ```python
   PERMANENT_SESSION_LIFETIME = timedelta(hours=2)
   ```
2. Implement "Remember Me" functionality
3. Add session refresh on activity

---

## 🤝 Contributing

We welcome contributions! Please follow these guidelines:

### Development Setup

1. Fork the repository
2. Create a feature branch:
   ```bash
   git checkout -b feature/your-feature-name
   ```
3. Make changes and test thoroughly
4. Commit with descriptive messages:
   ```bash
   git commit -m "feat: Add multi-currency support"
   ```
5. Push to your fork:
   ```bash
   git push origin feature/your-feature-name
   ```
6. Open a Pull Request

### Coding Standards

- **Python**: Follow PEP 8 style guide
- **JavaScript**: Use ESLint with Airbnb config
- **HTML/CSS**: Use BEM naming convention
- **Commit Messages**: Follow Conventional Commits

### Testing

Before submitting a PR, ensure:
- All existing tests pass
- New features have test coverage
- No linting errors
- Documentation is updated

---

## 📄 License

**Proprietary License**

This software is proprietary and confidential. Unauthorized copying, modification, distribution, or use of this software, via any medium, is strictly prohibited.

© 2025 Quantum Blue AI. All rights reserved.

---

## 📞 Support

For technical support or inquiries:

- **Email**: mahendra@highvolt.tech
- **GitHub Issues**: [Report a Bug](https://github.com/MahendraMedapati27/Data_Management_Chatbot/issues)
- **Documentation**: This README + inline code comments

---

## 🎉 Acknowledgments

- **Groq AI** for lightning-fast LLM inference
- **Azure** for reliable cloud database hosting
- **THREE.js** community for 3D rendering support
- **Flask** team for the excellent web framework

---

## 🗺️ Roadmap

### Version 2.0 (Planned)
- [ ] Multi-language support (Hindi, Telugu, Tamil)
- [ ] Mobile app (React Native)
- [ ] Voice order placement
- [ ] WhatsApp integration
- [ ] Real-time push notifications
- [ ] Advanced analytics dashboard
- [ ] Payment gateway integration
- [ ] QR code-based quick ordering

### Version 3.0 (Future)
- [ ] AI-powered demand forecasting
- [ ] Blockchain-based order verification
- [ ] IoT integration for warehouse automation
- [ ] Augmented reality product visualization

---

<div align="center">

**Made with ❤️ by Quantum Blue AI Team**

[⬆ Back to Top](#-quantum-blue-ai---intelligent-order-management-chatbot)

</div>

