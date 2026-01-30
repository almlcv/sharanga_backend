from fastapi import APIRouter, status, Depends
from typing import List
from app.core.schemas.shift import GlobalSettingCreate, GlobalSettingResponse, MessageResponse
from app.modules.shifts.shift_service import ShiftService

from app.core.auth.deps import require_roles, get_current_user

router = APIRouter(prefix="/v1/shifts/global", tags=["Global Shift Settings"])

@router.get(
    "", 
    response_model=List[GlobalSettingResponse],
    # dependencies=[Depends(get_current_user)],
    summary="Get All Shift Settings",
    description="Retrieves a list of all stored global shift configurations, sorted by most recently updated.",
    responses={
        200: {"description": "List of settings retrieved successfully"}
    }
)
async def get_all_settings():
    return await ShiftService.get_all_settings()


@router.get(
    "/current", 
    response_model=GlobalSettingResponse,
    # dependencies=[Depends(get_current_user)],
    summary="Get Active Shift Setting",
    description="Retrieves the currently active global shift configuration based on the latest update timestamp.",
    responses={
        404: {"model": MessageResponse, "description": "No settings found in the database"}
    }
)
async def get_current_setting():
    return await ShiftService.get_active_setting()

@router.post(
    "", 
    response_model=GlobalSettingResponse,
    # dependencies=[Depends(require_roles("Admin"))], 
    status_code=status.HTTP_201_CREATED,
    summary="Create Global Shift Setting",
    description="Creates a new global shift setting and validates for time overlaps. This becomes the active configuration immediately.",
    responses={
        400: {"model": MessageResponse, "description": "Validation error (e.g., overlapping shifts)"}
    }
)
async def create_global_setting(data: GlobalSettingCreate):
    return await ShiftService.create_setting(data)

@router.put(
    "/{setting_id}", 
    response_model=GlobalSettingResponse,
    # dependencies=[Depends(require_roles("Admin"))],
    summary="Update Global Shift Setting",
    description="Updates an existing global setting ID. Changes apply globally immediately. Overlap validation is performed.",
    responses={
        404: {"model": MessageResponse, "description": "Setting ID not found"},
        400: {"model": MessageResponse, "description": "Validation error (e.g., overlapping shifts)"}
    }
)
async def update_global_setting(setting_id: str, data: GlobalSettingCreate):
    return await ShiftService.update_setting(setting_id, data)