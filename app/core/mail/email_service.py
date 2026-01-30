from fastapi_mail import FastMail, MessageSchema, ConnectionConfig, MessageType
from pydantic import EmailStr
from typing import List
import logging

from app.core.setting import config

logger = logging.getLogger(__name__)

# Email Configuration
conf = ConnectionConfig(
    MAIL_USERNAME=config.MAIL_USERNAME,
    MAIL_PASSWORD=config.MAIL_PASSWORD,
    MAIL_FROM=config.MAIL_FROM,
    MAIL_PORT=config.MAIL_PORT,
    MAIL_SERVER=config.MAIL_SERVER,
    MAIL_STARTTLS=config.MAIL_STARTTLS,
    MAIL_SSL_TLS=config.MAIL_SSL_TLS,
    MAIL_FROM_NAME=config.MAIL_FROM_NAME,
    USE_CREDENTIALS=True,
    VALIDATE_CERTS=True
)

fast_mail = FastMail(conf)


class EmailService:
    """Service for sending emails"""
    
    @staticmethod
    async def send_otp_email(email: EmailStr, otp: str, full_name: str):
        """Send OTP for password reset"""
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background-color: #4CAF50; color: white; padding: 20px; text-align: center; }}
                .content {{ background-color: #f9f9f9; padding: 30px; border-radius: 5px; }}
                .otp-box {{ background-color: #fff; border: 2px solid #4CAF50; padding: 20px; 
                           text-align: center; font-size: 32px; font-weight: bold; 
                           letter-spacing: 8px; margin: 20px 0; border-radius: 5px; }}
                .warning {{ color: #d32f2f; font-size: 14px; margin-top: 20px; }}
                .footer {{ text-align: center; margin-top: 20px; font-size: 12px; color: #666; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>Password Reset Request</h1>
                </div>
                <div class="content">
                    <p>Hello <strong>{full_name}</strong>,</p>
                    <p>You requested to reset your password. Please use the following One-Time Password (OTP) to proceed:</p>
                    
                    <div class="otp-box">{otp}</div>
                    
                    <p><strong>This OTP is valid for 10 minutes.</strong></p>
                    
                    <p>If you didn't request this password reset, please ignore this email or contact your HR department immediately.</p>
                    
                    <div class="warning">
                        ⚠️ Never share your OTP with anyone. Our staff will never ask for your OTP.
                    </div>
                </div>
                <div class="footer">
                    <p>This is an automated email. Please do not reply.</p>
                    <p>&copy; {config.MAIL_FROM_NAME}</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        message = MessageSchema(
            subject="Password Reset OTP",
            recipients=[email],
            body=html_content,
            subtype=MessageType.html
        )
        
        try:
            await fast_mail.send_message(message)
            logger.info(f"OTP email sent successfully to {email}")
        except Exception as e:
            logger.error(f"Failed to send OTP email to {email}: {str(e)}")
            raise
    
    @staticmethod
    async def send_password_changed_notification(email: EmailStr, full_name: str, changed_by: str):
        """Send notification when password is changed"""
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background-color: #2196F3; color: white; padding: 20px; text-align: center; }}
                .content {{ background-color: #f9f9f9; padding: 30px; border-radius: 5px; }}
                .info-box {{ background-color: #e3f2fd; border-left: 4px solid #2196F3; 
                            padding: 15px; margin: 20px 0; }}
                .warning {{ color: #d32f2f; font-size: 14px; margin-top: 20px; 
                           background-color: #ffebee; padding: 15px; border-radius: 5px; }}
                .footer {{ text-align: center; margin-top: 20px; font-size: 12px; color: #666; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>Password Changed Successfully</h1>
                </div>
                <div class="content">
                    <p>Hello <strong>{full_name}</strong>,</p>
                    <p>This is to confirm that your password has been changed successfully.</p>
                    
                    <div class="info-box">
                        <strong>Change Details:</strong><br>
                        Changed by: {changed_by}<br>
                        Date & Time: {config.PROJECT_NAME} will show your local time
                    </div>
                    
                    <p>You can now login with your new password.</p>
                    
                    <div class="warning">
                        ⚠️ <strong>Security Alert:</strong> If you did not authorize this password change, 
                        please contact your HR department immediately.
                    </div>
                </div>
                <div class="footer">
                    <p>This is an automated email. Please do not reply.</p>
                    <p>&copy; {config.MAIL_FROM_NAME}</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        message = MessageSchema(
            subject="Password Changed Successfully",
            recipients=[email],
            body=html_content,
            subtype=MessageType.html
        )
        
        try:
            await fast_mail.send_message(message)
            logger.info(f"Password change notification sent to {email}")
        except Exception as e:
            logger.error(f"Failed to send notification to {email}: {str(e)}")
            # Don't raise - notification failure shouldn't block password change