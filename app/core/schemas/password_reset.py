from pydantic import BaseModel, Field, EmailStr, field_validator
import re


# ==================== REQUEST SCHEMAS ====================

class ForgotPasswordRequest(BaseModel):
    """Request to initiate password reset"""
    identifier: str = Field(
        ..., 
        description="Email address or phone number",
        examples=["user@example.com", "9876543210"]
    )

# class VerifyOTPRequest(BaseModel):
#     """Request to verify OTP"""
#     identifier: str = Field(
#         ..., 
#         description="Email address or phone number used in forgot password request"
#     )
#     otp: str = Field(
#         ..., 
#         min_length=6, 
#         max_length=6,
#         pattern=r"^\d{6}$",
#         description="6-digit OTP received via email"
#     )

class ResetPasswordRequest(BaseModel):
    """Request to reset password with OTP"""
    identifier: str = Field(
        ..., 
        description="Email address or phone number"
    )
    otp: str = Field(
        ..., 
        min_length=6, 
        max_length=6,
        pattern=r"^\d{6}$",
        description="6-digit OTP"
    )
    new_password: str = Field(
        ..., 
        min_length=8,
        description="New password (min 8 chars, must contain uppercase, lowercase, and number)"
    )

class ChangePasswordRequest(BaseModel):
    """Request to change password when authenticated"""
    current_password: str = Field(
        ..., 
        min_length=8,
        description="Current password for verification"
    )
    new_password: str = Field(
        ..., 
        min_length=8,
        description="New password (min 8 chars, must contain uppercase, lowercase, and number)"
    )

class HRResetPasswordRequest(BaseModel):
    """Request for HR to reset employee password"""
    new_password: str = Field(
        ..., 
        min_length=8,
        description="New password for the employee"
    )


# ==================== RESPONSE SCHEMAS ====================

class ForgotPasswordResponse(BaseModel):
    """Response after initiating password reset"""
    message: str = Field(
        ..., 
        description="Success message",
        examples=["OTP sent successfully to your registered email"]
    )
    email_hint: str = Field(
        ..., 
        description="Masked email for user verification",
        examples=["u***r@example.com"]
    )

# class VerifyOTPResponse(BaseModel):
#     """Response after OTP verification"""
#     message: str = Field(
#         ..., 
#         description="Verification status",
#         examples=["OTP verified successfully. You can now reset your password."]
#     )

class ResetPasswordResponse(BaseModel):
    """Response after successful password reset"""
    message: str = Field(
        ..., 
        description="Success message",
        examples=["Password reset successfully. You can now login with your new password."]
    )
    emp_id: str = Field(..., description="Employee ID")

class ChangePasswordResponse(BaseModel):
    """Response after authenticated password change"""
    message: str = Field(
        ..., 
        description="Success message",
        examples=["Password changed successfully"]
    )

class HRResetPasswordResponse(BaseModel):
    """Response after HR password reset"""
    message: str = Field(
        ..., 
        description="Success message",
        examples=["Password reset successfully for employee"]
    )
    emp_id: str = Field(..., description="Target employee ID")
    full_name: str = Field(..., description="Employee full name")