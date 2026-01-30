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
)
async def get_my_profile(current_user: CurrentUser = Depends(get_current_user)):
    """Get current logged-in employee's profile"""
    return await EmployeeService.get_my_profile(current_user.emp_id)