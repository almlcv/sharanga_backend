

import smtplib
import sys
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
import os
import random
import string
import logging




SENDER_EMAIL = os.getenv('SENDER_EMAIL')
RECEIVER_EMAIL = os.getenv('RECEIVER_EMAIL')
SMTP_LOGIN_EMAIL_PASS = os.getenv('SMTP_LOGIN_EMAIL_PASS')
CC_EMAIL = os.getenv('CC_EMAIL')
SMTP_PORT = os.getenv('SMTP_PORT', 587)
SMTP_MAIL_FROM_NAME = os.getenv('SMTP_MAIL_FROM_NAME', 'Alluvium IoT Solutions Pvt Ltd')
SMTP_MAIL_SERVER = os.getenv('SMTP_MAIL_SERVER', 'smtp-mail.outlook.com')



class EmailSender:
    def __init__(self, receiver_email=RECEIVER_EMAIL, cc_email=None):
        self.sender_email = SENDER_EMAIL
        self.sender_name = SMTP_MAIL_FROM_NAME
        self.receiver_email = receiver_email
        self.cc_email = cc_email

    def _send_email(self, to_email: str, subject: str, message: str, attachment_path=None) -> bool:
        try:
            msg = MIMEMultipart()
            msg['From'] = f"{self.sender_name} <{self.sender_email}>"
            msg['To'] = to_email
            if self.cc_email:
                msg['Cc'] = self.cc_email
            msg['Subject'] = subject

            msg.attach(MIMEText(message, 'plain'))

            if attachment_path:
                with open(attachment_path, "rb") as attachment:
                    part = MIMEBase('application', 'octet-stream')
                    part.set_payload(attachment.read())
                    encoders.encode_base64(part)
                    part.add_header('Content-Disposition', 
                                  f'attachment; filename={os.path.basename(attachment_path)}')
                    msg.attach(part)

            with smtplib.SMTP(SMTP_MAIL_SERVER, SMTP_PORT) as server:
                server.starttls()
                server.login(SENDER_EMAIL, SMTP_LOGIN_EMAIL_PASS)
                
                recipients = [to_email]
                if self.cc_email:
                    recipients.append(self.cc_email)
                
                server.sendmail(self.sender_email, recipients, msg.as_string())

           
            return True

        except Exception as e:
            
            return False

    def send_password_reset_email(self, user_email: str, temp_password: str) -> bool:
        subject = "Password Reset - RABs Project"
        message = f"""
Dear User,

A password reset has been requested for your RABs Project account.

Your temporary password is: {temp_password}

For security reasons, please:
1. Log in with this temporary password
2. Change your password immediately after logging in
3. Do not share this password with anyone

If you did not request this password reset, please contact support immediately.

Best Regards,
{self.sender_name}"""
        return self._send_email(user_email, subject, message)

    def send_password_change_confirmation(self, user_email: str) -> bool:
        subject = "Password Changed Successfully - RABs Project"
        message = f"""
Dear User,

Your password has been successfully changed for your RABs Project account.

If you did not make this change, please contact support immediately.

Best Regards,
{self.sender_name}"""
        return self._send_email(user_email, subject, message)

    def send_alert_email(self, attachment_path=None, video_url=None, camera_id=None, category=None):
        subject = "Security Alert - RABs Project"
        message = f"""Hi,
We have observed an incident on this camera_id: {camera_id}, here {category} is detected.

Here is the video link for the incident: {video_url if video_url else "Video not available"}

Best Regards,
{self.sender_name}"""
        
        if not self.receiver_email:
           
            return "Error: Receiver email not specified"
            
        success = self._send_email(self.receiver_email, subject, message, attachment_path)
        return ("Email sent successfully" if success else "Failed to send email")

    @staticmethod
    def generate_temp_password(length=12):
        """Generate a random temporary password"""
        characters = string.ascii_letters + string.digits + "!@#$%^&*"
        password = [
            random.choice(string.ascii_lowercase),
            random.choice(string.ascii_uppercase),
            random.choice(string.digits),
            random.choice("!@#$%^&*")
        ]
        password.extend(random.choice(characters) for _ in range(length - 4))
        random.shuffle(password)
        return ''.join(password)


