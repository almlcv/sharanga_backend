from typing import Optional
from fastapi import HTTPException, status
from passlib.context import CryptContext
import logging
import re

from app.core.models.hr import EmployeeProfile, LoginCredential
from app.shared.profile.profile_utils import ProfileUtils

logger = logging.getLogger(__name__)
pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")


class PasswordResetService:
    """Service for password reset operations"""
    
    @staticmethod
    def _validate_password_strength(password: str):
        """Validate password meets security requirements"""
        if len(password) < 8:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Password must be at least 8 characters long."
            )
        if not re.search(r"[A-Z]", password):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Password must contain at least one uppercase letter."
            )
        if not re.search(r"[a-z]", password):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Password must contain at least one lowercase letter."
            )
        if not re.search(r"\d", password):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Password must contain at least one number."
            )
    
    @staticmethod
    async def _get_login_by_identifier(identifier: str) -> LoginCredential:
        """Find login credential by email or phone"""
        login = await LoginCredential.find_one(
            {
                "$or": [
                    {"email": identifier},
                    {"username": identifier}
                ]
            }
        )
        
        if not login:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No account found with this email or phone number."
            )
        
        return login
    
    @staticmethod
    async def initiate_password_reset(identifier: str) -> dict:
        """
        Initiate password reset flow - find user and return info for OTP sending
        
        Args:
            identifier: Email or phone number
            
        Returns:
            dict with email, full_name, emp_id
        """
        # Verify user exists
        login = await PasswordResetService._get_login_by_identifier(identifier)
        
        # Get employee profile for full name
        profile = await EmployeeProfile.find_one(EmployeeProfile.emp_id == login.emp_id)
        
        if not login.email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No email address registered for this account. Please contact HR."
            )
        
        return {
            "email": login.email,
            "full_name": login.full_name or "User",
            "emp_id": login.emp_id
        }
    
    @staticmethod
    async def reset_password_with_otp(identifier: str, new_password: str) -> dict:
        """
        Reset password after OTP verification
        
        Args:
            identifier: Email or phone (already verified via OTP)
            new_password: New password to set
            
        Returns:
            Success message with user details
        """
        # Validate password strength
        PasswordResetService._validate_password_strength(new_password)
        
        # Get login credential
        login = await PasswordResetService._get_login_by_identifier(identifier)
        
        # Hash and update password
        login.password = pwd_context.hash(new_password)
        await login.save()
        
        logger.info(f"Password reset successfully for {login.emp_id} via OTP")
        
        return {
            "email": login.email,
            "full_name": login.full_name,
            "emp_id": login.emp_id,
            "changed_by": "Self (OTP Reset)"
        }
    
    @staticmethod
    async def change_password_authenticated(
        emp_id: str, 
        current_password: str, 
        new_password: str
    ) -> dict:
        """
        Change password for authenticated user (requires current password)
        
        Args:
            emp_id: Employee ID from JWT token
            current_password: Current password for verification
            new_password: New password to set
            
        Returns:
            Success message
        """
        # Validate new password strength
        PasswordResetService._validate_password_strength(new_password)
        
        # Get login credential
        login = await LoginCredential.find_one(LoginCredential.emp_id == emp_id)
        if not login:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Login credential not found."
            )
        
        # Verify current password
        if not pwd_context.verify(current_password, login.password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Current password is incorrect."
            )
        
        # Check if new password is same as current
        if pwd_context.verify(new_password, login.password):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="New password must be different from current password."
            )
        
        # Update password
        login.password = pwd_context.hash(new_password)
        await login.save()
        
        logger.info(f"Password changed successfully for {emp_id}")
        
        return {
            "email": login.email,
            "full_name": login.full_name,
            "emp_id": emp_id,
            "changed_by": "Self (Authenticated)"
        }
    
    @staticmethod
    async def reset_password_by_hr(emp_id: str, new_password: str, hr_emp_id: str) -> dict:
        """
        HR/Admin resets password for any employee
        
        Args:
            emp_id: Target employee ID
            new_password: New password to set
            hr_emp_id: HR/Admin employee ID (for audit)
            
        Returns:
            Success message
        """
        # Validate password strength
        PasswordResetService._validate_password_strength(new_password)
        
        # Get target employee's login credential
        login = await LoginCredential.find_one(LoginCredential.emp_id == emp_id)
        if not login:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Employee {emp_id} not found."
            )
        
        # Update password
        login.password = pwd_context.hash(new_password)
        await login.save()
        
        logger.info(f"Password reset by HR {hr_emp_id} for employee {emp_id}")
        
        return {
            "email": login.email,
            "full_name": login.full_name,
            "emp_id": emp_id,
            "changed_by": f"HR/Admin ({hr_emp_id})"
        }