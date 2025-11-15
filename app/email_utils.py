import logging
import os
import base64
from flask import current_app, render_template_string
from flask_mail import Message
from app import mail, db
from app.models import EmailLog

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_logo_base64():
    """Get Quantum Blue logo as base64 for email embedding"""
    try:
        logo_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'static', 'Images', 'Q_logo_quantum_blue-removebg-preview.png')
        with open(logo_path, 'rb') as img_file:
            logo_data = base64.b64encode(img_file.read()).decode('utf-8')
            return f"data:image/png;base64,{logo_data}"
    except Exception as e:
        logger.warning(f"Could not load logo: {str(e)}")
        return ""

def create_email_template(title, content, footer_text="This is an automated email from Quantum Blue AI."):
    """Create standardized email template with logo"""
    logo_base64 = get_logo_base64()
    logo_html = f'<img src="{logo_base64}" alt="Quantum Blue" style="height: 60px; margin-bottom: 20px;" />' if logo_base64 else '<h1 style="color: #2563eb; margin: 0;">Quantum Blue</h1>'
    
    return f'''
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            body {{
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
                line-height: 1.6;
                color: #1f2937;
                margin: 0;
                padding: 0;
                background-color: #f3f4f6;
            }}
            .email-wrapper {{
                max-width: 600px;
                margin: 0 auto;
                background-color: #ffffff;
            }}
            .header {{
                background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%);
                padding: 30px 20px;
                text-align: center;
            }}
            .content {{
                padding: 30px 20px;
            }}
            .footer {{
                background-color: #f9fafb;
                padding: 20px;
                text-align: center;
                color: #6b7280;
                font-size: 14px;
                border-top: 1px solid #e5e7eb;
            }}
            .button {{
                display: inline-block;
                padding: 12px 24px;
                background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%);
                color: white;
                text-decoration: none;
                border-radius: 8px;
                font-weight: 600;
                margin: 10px 0;
            }}
            .info-box {{
                background-color: #eff6ff;
                border-left: 4px solid #3b82f6;
                padding: 15px;
                margin: 20px 0;
                border-radius: 4px;
            }}
            .success-box {{
                background-color: #d1fae5;
                border-left: 4px solid #10b981;
                padding: 15px;
                margin: 20px 0;
                border-radius: 4px;
            }}
            .warning-box {{
                background-color: #fef3c7;
                border-left: 4px solid #f59e0b;
                padding: 15px;
                margin: 20px 0;
                border-radius: 4px;
            }}
            h1, h2, h3 {{
                color: #1e40af;
            }}
            .title {{
                color: white;
                font-size: 24px;
                font-weight: 700;
                margin: 15px 0 5px 0;
            }}
            .subtitle {{
                color: rgba(255, 255, 255, 0.9);
                font-size: 14px;
                margin: 0;
            }}
        </style>
    </head>
    <body>
        <div class="email-wrapper">
            <div class="header">
                {logo_html}
                <div class="title">{title}</div>
                <div class="subtitle">Powered by Quantum Blue AI</div>
            </div>
            <div class="content">
                {content}
            </div>
            <div class="footer">
                <p>{footer_text}</p>
                <p style="margin: 5px 0;">&copy; 2025 Quantum Blue. All rights reserved.</p>
                <p style="margin: 5px 0; font-size: 12px;">RB (Powered by Quantum Blue AI)</p>
            </div>
        </div>
    </body>
    </html>
    '''

def send_email(to_email, subject, html_content, email_type='general', order_id=None, sender_email=None, sender_name=None, receiver_name=None):
    """Send email via SMTP with detailed logging"""
    try:
        sender_config = current_app.config.get('MAIL_DEFAULT_SENDER', 'noreply@quantumblue.ai')
        if isinstance(sender_config, tuple):
            sender_email_config = sender_config[1] if len(sender_config) > 1 else sender_config[0]
            sender_name_config = sender_config[0] if len(sender_config) > 1 else 'Quantum Blue AI'
        else:
            sender_email_config = sender_config
            sender_name_config = 'Quantum Blue AI'
        
        msg = Message(
            subject=subject,
            recipients=[to_email],
            html=html_content,
            sender=(sender_name or sender_name_config, sender_email or sender_email_config)
        )
        
        mail.send(msg)
        
        # Log successful email with detailed information
        try:
            # Create new session for logging to avoid transaction conflicts
            email_log = EmailLog(
                recipient=to_email,
                email_type=email_type,
                status='sent',
                order_id=order_id,
                sender_email=sender_email or sender_email_config,
                sender_name=sender_name or sender_name_config,
                receiver_email=to_email,
                receiver_name=receiver_name,
                subject=subject,
                body_preview=html_content[:200] if html_content else None  # First 200 chars as preview
            )
            db.session.add(email_log)
            db.session.flush()  # Flush to get any errors before commit
            db.session.commit()
            logger.debug(f'Email logged successfully: {email_type} to {to_email}, Order: {order_id}')
        except Exception as log_e:
            logger.warning(f'Failed to log email success: {str(log_e)}')
            # Don't fail the email send if logging fails
            try:
                db.session.rollback()
            except:
                pass
        
        logger.info(f'Email sent to {to_email} (Order: {order_id})')
        return True
        
    except Exception as e:
        logger.error(f'Email sending failed: {str(e)}')
        
        # Log failure with detailed information
        try:
            sender_config = current_app.config.get('MAIL_DEFAULT_SENDER', 'noreply@quantumblue.ai')
            if isinstance(sender_config, tuple):
                sender_email_config = sender_config[1] if len(sender_config) > 1 else sender_config[0]
                sender_name_config = sender_config[0] if len(sender_config) > 1 else 'Quantum Blue AI'
            else:
                sender_email_config = sender_config
                sender_name_config = 'Quantum Blue AI'
            
            email_log = EmailLog(
                recipient=to_email,
                email_type=email_type,
                status='failed',
                error_message=str(e),
                order_id=order_id,
                sender_email=sender_email or sender_email_config,
                sender_name=sender_name or sender_name_config,
                receiver_email=to_email,
                receiver_name=receiver_name,
                subject=subject,
                body_preview=html_content[:200] if html_content else None
            )
            db.session.add(email_log)
            db.session.flush()  # Flush to get any errors before commit
            db.session.commit()
            logger.debug(f'Email failure logged: {email_type} to {to_email}, Order: {order_id}')
        except Exception as log_e:
            logger.warning(f'Failed to log email failure: {str(log_e)}')
            # Don't fail if logging fails
            try:
                db.session.rollback()
            except:
                pass
        
        return False

def send_otp_email(user_email, user_name, otp):
    """Send OTP verification email"""
    subject = 'Email Verification - Your OTP Code'
    
    html_content = f'''
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{
                font-family: Arial, sans-serif;
                line-height: 1.6;
                color: #333;
                max-width: 600px;
                margin: 0 auto;
                padding: 20px;
            }}
            .container {{
                background-color: #f9f9f9;
                border-radius: 10px;
                padding: 30px;
                box-shadow: 0 2px 5px rgba(0,0,0,0.1);
            }}
            .header {{
                text-align: center;
                color: #007bff;
                margin-bottom: 30px;
            }}
            .otp-box {{
                background-color: #007bff;
                color: white;
                font-size: 32px;
                font-weight: bold;
                text-align: center;
                padding: 20px;
                border-radius: 8px;
                letter-spacing: 8px;
                margin: 30px 0;
            }}
            .info {{
                background-color: #fff3cd;
                border-left: 4px solid #ffc107;
                padding: 15px;
                margin: 20px 0;
            }}
            .footer {{
                text-align: center;
                color: #666;
                font-size: 14px;
                margin-top: 30px;
                padding-top: 20px;
                border-top: 1px solid #ddd;
            }}
            .button {{
                display: inline-block;
                background-color: #28a745;
                color: white;
                padding: 12px 30px;
                text-decoration: none;
                border-radius: 5px;
                margin: 20px 0;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🤖 Welcome to Quantum Blue!</h1>
            </div>
            
            <p>Hello <strong>{user_name}</strong>,</p>
            
            <p>Thank you for registering! To complete your registration, please use the following One-Time Password (OTP):</p>
            
            <div class="otp-box">
                {otp}
            </div>
            
            <div class="info">
                <strong>⏰ Important:</strong> This OTP is valid for <strong>10 minutes</strong> only.
            </div>
            
            <p>Enter this code on the verification page to activate your account.</p>
            
            <p><strong>Security Tips:</strong></p>
            <ul>
                <li>Never share this OTP with anyone</li>
                <li>Our team will never ask for your OTP</li>
                <li>If you didn't request this, please ignore this email</li>
            </ul>
            
            <div class="footer">
                <p>This is an automated email, please do not reply.</p>
                <p>&copy; 2025 Quantum Blue. All rights reserved.</p>
            </div>
        </div>
    </body>
    </html>
    '''
    
    return send_email(
        user_email, 
        subject, 
        html_content, 
        'otp_verification',
        receiver_name=user_name
    )

def send_welcome_email(user_email, user_name):
    """Send welcome email after successful verification"""
    subject = 'Welcome to Quantum Blue - Account Verified!'
    
    html_content = f'''
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{
                font-family: Arial, sans-serif;
                line-height: 1.6;
                color: #333;
                max-width: 600px;
                margin: 0 auto;
                padding: 20px;
            }}
            .container {{
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                border-radius: 10px;
                padding: 30px;
                color: white;
            }}
            .content {{
                background-color: white;
                color: #333;
                border-radius: 8px;
                padding: 30px;
                margin-top: 20px;
            }}
            .success-icon {{
                text-align: center;
                font-size: 60px;
                margin: 20px 0;
            }}
            .feature {{
                background-color: #f8f9fa;
                padding: 15px;
                margin: 10px 0;
                border-radius: 5px;
                border-left: 4px solid #007bff;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1 style="text-align: center; margin: 0;">🎉 Welcome Aboard!</h1>
            
            <div class="content">
                <div class="success-icon">✅</div>
                
                <h2 style="color: #28a745; text-align: center;">Account Successfully Verified!</h2>
                
                <p>Hello <strong>{user_name}</strong>,</p>
                
                <p>Congratulations! Your email has been verified and your account is now active.</p>
                
                <h3>What You Can Do Now:</h3>
                
                <div class="feature">
                    <strong>💬 Smart Conversations</strong><br>
                    Chat with our AI assistant powered by Azure OpenAI
                </div>
                
                <div class="feature">
                    <strong>📊 Data Insights</strong><br>
                    Get intelligent responses based on real-time data
                </div>
                
                <div class="feature">
                    <strong>📧 Conversation History</strong><br>
                    Export and email your chat history anytime
                </div>
                
                <div class="feature">
                    <strong>🔒 Secure & Private</strong><br>
                    Your data is protected with enterprise-grade security
                </div>
                
                <p style="text-align: center; margin-top: 30px;">
                    <a href="#" style="display: inline-block; background-color: #007bff; color: white; padding: 15px 40px; text-decoration: none; border-radius: 5px; font-weight: bold;">
                        Start Chatting Now →
                    </a>
                </p>
                
                <p style="color: #666; font-size: 14px; margin-top: 30px; text-align: center;">
                    Need help? Contact us at <a href="mailto:{current_app.config['ADMIN_EMAIL']}">{current_app.config['ADMIN_EMAIL']}</a>
                </p>
            </div>
        </div>
    </body>
    </html>
    '''
    
    return send_email(
        user_email, 
        subject, 
        html_content, 
        'welcome',
        receiver_name=user_name
    )

def send_conversation_email(user_email, admin_email, conversation_data):
    """Send conversation summary to user and admin"""
    subject = f'Conversation Summary - {conversation_data["date"]}'
    
    # Create conversation HTML
    messages_html = ''
    for conv in conversation_data['conversations']:
        messages_html += f'''
        <div style="margin-bottom: 20px; padding: 15px; background-color: #f8f9fa; border-radius: 5px; border-left: 4px solid #007bff;">
            <p style="margin: 0; color: #007bff; font-weight: bold;">
                <span style="background-color: #007bff; color: white; padding: 4px 8px; border-radius: 3px; font-size: 12px;">YOU</span>
            </p>
            <p style="margin: 10px 0; padding: 10px; background-color: white; border-radius: 4px;">{conv['user_message']}</p>
            
            <p style="margin: 15px 0 0 0; color: #28a745; font-weight: bold;">
                <span style="background-color: #28a745; color: white; padding: 4px 8px; border-radius: 3px; font-size: 12px;">AI ASSISTANT</span>
            </p>
            <p style="margin: 10px 0 0 0; padding: 10px; background-color: white; border-radius: 4px;">{conv['bot_response']}</p>
            
            <p style="margin: 10px 0 0 0; font-size: 12px; color: #666;">
                <em>Response time: {conv.get('response_time', 0):.2f}s</em>
            </p>
        </div>
        '''
    
    html_content = f'''
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{
                font-family: Arial, sans-serif;
                line-height: 1.6;
                color: #333;
                max-width: 800px;
                margin: 0 auto;
                padding: 20px;
                background-color: #f5f5f5;
            }}
            .container {{
                background-color: white;
                border-radius: 10px;
                padding: 30px;
                box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            }}
            .header {{
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                padding: 25px;
                border-radius: 8px;
                text-align: center;
                margin-bottom: 30px;
            }}
            .stats {{
                display: grid;
                grid-template-columns: repeat(3, 1fr);
                gap: 15px;
                margin: 20px 0;
            }}
            .stat-box {{
                background-color: #f8f9fa;
                padding: 15px;
                border-radius: 8px;
                text-align: center;
                border: 2px solid #e9ecef;
            }}
            .stat-value {{
                font-size: 24px;
                font-weight: bold;
                color: #007bff;
            }}
            .stat-label {{
                font-size: 12px;
                color: #666;
                text-transform: uppercase;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1 style="margin: 0;">📊 Conversation Summary</h1>
                <p style="margin: 10px 0 0 0; opacity: 0.9;">Your AI Chat History</p>
            </div>
            
            <div class="stats">
                <div class="stat-box">
                    <div class="stat-value">{len(conversation_data['conversations'])}</div>
                    <div class="stat-label">Total Messages</div>
                </div>
                <div class="stat-box">
                    <div class="stat-value">{conversation_data['date']}</div>
                    <div class="stat-label">Date</div>
                </div>
                <div class="stat-box">
                    <div class="stat-value">{conversation_data['user_name']}</div>
                    <div class="stat-label">User</div>
                </div>
            </div>
            
            <p><strong>📧 Email:</strong> {user_email}</p>
            
            <hr style="margin: 30px 0; border: none; border-top: 2px solid #e9ecef;">
            
            <h2 style="color: #333; margin-bottom: 20px;">💬 Conversation History</h2>
            
            {messages_html}
            
            <hr style="margin: 30px 0; border: none; border-top: 2px solid #e9ecef;">
            
            <p style="text-align: center; color: #666; font-size: 14px;">
                This is an automated email from Quantum Blue. Please do not reply.<br>
                <em>Generated on {conversation_data['date']}</em>
            </p>
        </div>
    </body>
    </html>
    '''
    
    # Send to user
    send_email(
        user_email, 
        subject, 
        html_content, 
        'conversation',
        receiver_name=conversation_data.get('user_name')
    )
    
    # Send to admin with [Admin] prefix
    send_email(
        admin_email, 
        f'[Admin] {subject}', 
        html_content, 
        'conversation_admin'
    )

def send_stock_arrival_notification(dealer_email, dealer_name, product_code, product_name, quantity, dispatch_date, lot_number=None, expiration_date=None):
    """Send stock arrival notification to dealer"""
    subject = f'New Stock Arrival: {product_name} ({product_code})'
    
    expiration_str = f'<p><strong>Expiration Date:</strong> {expiration_date.strftime("%Y-%m-%d") if expiration_date else "N/A"}</p>' if expiration_date else ''
    lot_str = f'<p><strong>Lot Number:</strong> {lot_number}</p>' if lot_number else ''
    
    html_content = f'''
    <html>
    <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
        <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
            <h2 style="color: #007bff;">📦 New Stock Arrival Notification</h2>
            
            <p>Dear {dealer_name},</p>
            
            <p>New stock has arrived and is waiting for your confirmation:</p>
            
            <div style="background-color: #f8f9fa; padding: 15px; border-radius: 5px; margin: 20px 0;">
                <h3 style="margin-top: 0;">Stock Details:</h3>
                <p><strong>Product Code:</strong> {product_code}</p>
                <p><strong>Product Name:</strong> {product_name}</p>
                <p><strong>Quantity:</strong> {quantity} units</p>
                <p><strong>Dispatch Date:</strong> {dispatch_date.strftime("%Y-%m-%d") if dispatch_date else "N/A"}</p>
                {lot_str}
                {expiration_str}
            </div>
            
            <p><strong>⚠️ Important:</strong> Please confirm this stock arrival through the chatbot. The stock is currently in "blocked" status and will not be available for sale until you confirm it.</p>
            
            <p>If the received quantity differs from the dispatched quantity, you can adjust it during confirmation.</p>
            
            <p style="margin-top: 30px;">
                Best regards,<br>
                <strong>Quantum Blue AI</strong>
            </p>
        </div>
    </body>
    </html>
    '''
    
    send_email(
        dealer_email, 
        subject, 
        html_content, 
        'stock_arrival',
        receiver_name=dealer_name
    )

def send_quantity_discrepancy_email(dealer_name, dealer_email, product_code, product_name, sent_quantity, received_quantity, dispatch_date, reason=None):
    """Send quantity discrepancy notification to company"""
    company_email = current_app.config.get('COMPANY_EMAIL', 'mahendra@highvolt.tech')
    
    subject = f'Stock Quantity Discrepancy: {product_name} ({product_code})'
    
    reason_str = f'<p><strong>Reason:</strong> {reason}</p>' if reason else ''
    
    html_content = f'''
    <html>
    <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
        <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
            <h2 style="color: #dc3545;">⚠️ Stock Quantity Discrepancy Report</h2>
            
            <p>A quantity discrepancy has been reported for the following stock:</p>
            
            <div style="background-color: #fff3cd; padding: 15px; border-radius: 5px; margin: 20px 0; border-left: 4px solid #ffc107;">
                <h3 style="margin-top: 0;">Stock Details:</h3>
                <p><strong>Product Code:</strong> {product_code}</p>
                <p><strong>Product Name:</strong> {product_name}</p>
                <p><strong>Dealer:</strong> {dealer_name}</p>
                <p><strong>Dealer Email:</strong> {dealer_email}</p>
                <p><strong>Dispatch Date:</strong> {dispatch_date.strftime("%Y-%m-%d") if dispatch_date else "N/A"}</p>
                
                <hr style="margin: 15px 0;">
                
                <p><strong style="color: #dc3545;">Quantity Sent:</strong> {sent_quantity} units</p>
                <p><strong style="color: #dc3545;">Quantity Received:</strong> {received_quantity} units</p>
                <p><strong style="color: #dc3545;">Difference:</strong> {sent_quantity - received_quantity} units</p>
                
                {reason_str}
            </div>
            
            <p>Please review this discrepancy and take appropriate action.</p>
            
            <p style="margin-top: 30px;">
                Best regards,<br>
                <strong>Quantum Blue AI System</strong>
            </p>
        </div>
    </body>
    </html>
    '''
    
    send_email(
        company_email, 
        subject, 
        html_content, 
        'quantity_discrepancy',
        receiver_name='Company Admin'
    )

def send_email_with_attachment(to_email, subject, html_content, csv_data=None, filename='report.csv', email_type='report'):
    """Send email with CSV attachment"""
    try:
        msg = Message(
            subject=subject,
            recipients=[to_email],
            html=html_content,
            sender=current_app.config['MAIL_DEFAULT_SENDER']
        )
        
        # Attach CSV if provided
        if csv_data:
            if isinstance(csv_data, str):
                csv_data = csv_data.encode('utf-8')
            msg.attach(
                filename,
                'text/csv',
                csv_data,
                'attachment'
            )
        
        mail.send(msg)
        
        # Log successful email with detailed information
        try:
            sender_config = current_app.config.get('MAIL_DEFAULT_SENDER', 'noreply@quantumblue.ai')
            if isinstance(sender_config, tuple):
                sender_email_config = sender_config[1] if len(sender_config) > 1 else sender_config[0]
                sender_name_config = sender_config[0] if len(sender_config) > 1 else 'Quantum Blue AI'
            else:
                sender_email_config = sender_config
                sender_name_config = 'Quantum Blue AI'
            
            email_log = EmailLog(
                recipient=to_email,
                email_type=email_type,
                status='sent',
                sender_email=sender_email_config,
                sender_name=sender_name_config,
                receiver_email=to_email,
                subject=subject,
                body_preview=html_content[:200] if html_content else None
            )
            db.session.add(email_log)
            db.session.flush()
            db.session.commit()
        except Exception as log_e:
            logger.warning(f'Failed to log email success: {str(log_e)}')
            try:
                db.session.rollback()
            except:
                pass
        
        logger.info(f'Email with attachment sent to {to_email}')
        return True
        
    except Exception as e:
        logger.error(f'Email sending failed: {str(e)}')
        
        # Log failure with detailed information
        try:
            sender_config = current_app.config.get('MAIL_DEFAULT_SENDER', 'noreply@quantumblue.ai')
            if isinstance(sender_config, tuple):
                sender_email_config = sender_config[1] if len(sender_config) > 1 else sender_config[0]
                sender_name_config = sender_config[0] if len(sender_config) > 1 else 'Quantum Blue AI'
            else:
                sender_email_config = sender_config
                sender_name_config = 'Quantum Blue AI'
            
            email_log = EmailLog(
                recipient=to_email,
                email_type=email_type,
                status='failed',
                error_message=str(e),
                sender_email=sender_email_config,
                sender_name=sender_name_config,
                receiver_email=to_email,
                subject=subject,
                body_preview=html_content[:200] if html_content else None
            )
            db.session.add(email_log)
            db.session.flush()
            db.session.commit()
        except Exception as log_e:
            logger.warning(f'Failed to log email failure: {str(log_e)}')
            try:
                db.session.rollback()
            except:
                pass
        
        return False