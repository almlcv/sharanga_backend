from fastapi import APIRouter, status, Depends, HTTPException
from app.core.schemas.password_reset import (
    ForgotPasswordRequest,
    ForgotPasswordResponse,
    VerifyOTPRequest,
    VerifyOTPResponse,
    ResetPasswordRequest,
    ResetPasswordResponse,
    ChangePasswordRequest,
    ChangePasswordResponse,
    HRResetPasswordRequest,
    HRResetPasswordResponse
)
from app.core.mail.password_reset_service import PasswordResetService
from app.core.mail.otp_service import OTPService
from app.core.mail.email_service import EmailService
from app.core.auth.deps import get_current_user, require_roles
from app.core.schemas.auth import CurrentUser


# ==================== AUTH ROUTER (PUBLIC ENDPOINTS) ====================

router = APIRouter(prefix="/auth", tags=["Authentication - Password Reset"])


@router.post(
    "/forgot-password",
    response_model=ForgotPasswordResponse,
    status_code=status.HTTP_200_OK,
    summary="Step 1: Request Password Reset",
    description="""
    Initiates password reset process by sending OTP to registered email.
    
    **Process:**
    1. User enters email or phone number
    2. System validates account exists
    3. Generates 6-digit OTP (valid 10 minutes)
    4. Sends OTP to registered email
    5. Returns masked email for confirmation
    
    **Rate Limiting:** Max 1 OTP request per 15 minutes per user
    """
)
async def forgot_password(request: ForgotPasswordRequest):
    """Initiate password reset - sends OTP to email"""
    
    # Get user info and validate
    user_info = await PasswordResetService.initiate_password_reset(request.identifier)
    
    # Generate and store OTP
    otp = await OTPService.generate_and_store_otp(request.identifier)
    
    # Send OTP via email
    await EmailService.send_otp_email(
        email=user_info["email"],
        otp=otp,
        full_name=user_info["full_name"]
    )
    
    # Mask email for privacy
    email = user_info["email"]
    email_parts = email.split("@")
    masked_local = email_parts[0][0] + "*" * (len(email_parts[0]) - 2) + email_parts[0][-1]
    email_hint = f"{masked_local}@{email_parts[1]}"
    
    return ForgotPasswordResponse(
        message="OTP sent successfully to your registered email",
        email_hint=email_hint
    )


@router.post(
    "/verify-reset-otp",
    response_model=VerifyOTPResponse,
    status_code=status.HTTP_200_OK,
    summary="Step 2: Verify OTP",
    description="""
    Verifies the OTP sent to user's email.
    
    **Validation:**
    - OTP must be 6 digits
    - OTP must not be expired (10 min validity)
    - Maximum 3 verification attempts
    - OTP can only be used once
    """
)
async def verify_otp(request: VerifyOTPRequest):
    """Verify OTP before password reset"""
    
    # Verify OTP
    await OTPService.verify_otp(request.identifier, request.otp)
    
    return VerifyOTPResponse(
        message="OTP verified successfully. You can now reset your password."
    )


@router.post(
    "/reset-password",
    response_model=ResetPasswordResponse,
    status_code=status.HTTP_200_OK,
    summary="Step 3: Reset Password with OTP",
    description="""
    Resets password after OTP verification.
    
    **Password Requirements:**
    - Minimum 8 characters
    - At least one uppercase letter
    - At least one lowercase letter
    - At least one number
    
    **Process:**
    1. Verifies OTP again
    2. Validates password strength
    3. Updates password
    4. Sends confirmation email
    5. Invalidates OTP
    """
)
async def reset_password(request: ResetPasswordRequest):
    """Reset password with verified OTP"""
    
    # Verify OTP again (security measure)
    await OTPService.verify_otp(request.identifier, request.otp)
    
    # Reset password
    result = await PasswordResetService.reset_password_with_otp(
        identifier=request.identifier,
        new_password=request.new_password
    )
    
    # Send confirmation email
    try:
        await EmailService.send_password_changed_notification(
            email=result["email"],
            full_name=result["full_name"],
            changed_by=result["changed_by"]
        )
    except Exception as e:
        # Log but don't fail if notification fails
        pass
    
    # Invalidate OTP
    await OTPService.invalidate_otp(request.identifier)
    
    return ResetPasswordResponse(
        message="Password reset successfully. You can now login with your new password.",
        emp_id=result["emp_id"]
    )


# ==================== EMPLOYEE ROUTER (AUTHENTICATED) ====================

employee_router = APIRouter(prefix="/employee", tags=["Employee - Password Management"])


@employee_router.put(
    "/change-password",
    response_model=ChangePasswordResponse,
    status_code=status.HTTP_200_OK,
    summary="Change Password (Authenticated)",
    description="""
    Change password for currently logged-in employee.
    
    **Requirements:**
    - Must be authenticated (valid JWT token)
    - Must provide current password
    - New password must meet strength requirements
    - New password must be different from current
    
    **Password Requirements:**
    - Minimum 8 characters
    - At least one uppercase letter
    - At least one lowercase letter
    - At least one number
    """
)
async def change_password(
    request: ChangePasswordRequest,
    current_user: CurrentUser = Depends(get_current_user)
):
    """Change password for authenticated user"""
    
    # Change password
    result = await PasswordResetService.change_password_authenticated(
        emp_id=current_user.emp_id,
        current_password=request.current_password,
        new_password=request.new_password
    )
    
    # Send confirmation email
    try:
        await EmailService.send_password_changed_notification(
            email=result["email"],
            full_name=result["full_name"],
            changed_by=result["changed_by"]
        )
    except Exception as e:
        # Log but don't fail if notification fails
        pass
    
    return ChangePasswordResponse(
        message="Password changed successfully"
    )


# ==================== HR ROUTER (ADMIN/HR ONLY) ====================

hr_router = APIRouter(prefix="/hr", tags=["HR - Password Management"])


@hr_router.put(
    "/employees/{emp_id}/reset-password",
    response_model=HRResetPasswordResponse,
    status_code=status.HTTP_200_OK,
    summary="Reset Employee Password (HR/Admin Only)",
    description="""
    HR/Admin can directly reset password for any employee.
    
    **Authorization:** Requires Admin or HR role
    
    **Process:**
    1. HR provides new password for target employee
    2. Password is validated and updated
    3. Notification email sent to employee
    4. Action is logged for audit trail
    
    **Password Requirements:**
    - Minimum 8 characters
    - At least one uppercase letter
    - At least one lowercase letter
    - At least one number
    """
)
async def reset_employee_password(
    emp_id: str,
    request: HRResetPasswordRequest,
    current_user: CurrentUser = Depends(require_roles("Admin", "HR"))
):
    """HR/Admin resets password for any employee"""
    
    # Reset password
    result = await PasswordResetService.reset_password_by_hr(
        emp_id=emp_id,
        new_password=request.new_password,
        hr_emp_id=current_user.emp_id
    )
    
    # Send notification email to employee
    try:
        await EmailService.send_password_changed_notification(
            email=result["email"],
            full_name=result["full_name"],
            changed_by=result["changed_by"]
        )
    except Exception as e:
        # Log but don't fail if notification fails
        pass
    
    return HRResetPasswordResponse(
        message=f"Password reset successfully for employee {emp_id}",
        emp_id=result["emp_id"],
        full_name=result["full_name"]
    )