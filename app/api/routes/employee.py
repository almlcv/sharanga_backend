from fastapi import APIRouter, UploadFile, File, Form, Depends
from typing import Optional, List

from app.core.schemas.employee import EmployeeProfileResponse
from app.modules.employee.employee_service import EmployeeService
from app.core.models.hr import MaritalStatusEnum
from app.core.auth.deps import get_current_user
from app.core.schemas.auth import CurrentUser

router = APIRouter(prefix="/employee", tags=["Employee Service"])


@router.get(
    "/me",
    response_model=EmployeeProfileResponse,
    summary="Get My Profile",
    description="""
    Retrieve the complete profile information for the currently authenticated employee.
    
    **Authorization:** Requires valid JWT token (any authenticated user can access their own profile).
    
    **Returns:**
    - Personal information: name, DOB, gender, phone, email, marital status
    - Professional information: designation, department, experience, qualification, role
    - Identification details: Aadhaar number, address, blood group, emergency contact
    - Document URLs: avatar, ID proofs, education certificates, experience letters
    
    **Use Case:**
    Employees can view their own profile information for verification, review, or to identify what needs updating.
    """,
    responses={
        200: {"description": "Profile retrieved successfully"},
        401: {"description": "Not authenticated or invalid/expired token"},
        404: {"description": "Employee profile not found"}
    }
)
async def get_my_profile(current_user: CurrentUser = Depends(get_current_user)):
    """Get current logged-in employee's profile"""
    return await EmployeeService.get_my_profile(current_user.emp_id)