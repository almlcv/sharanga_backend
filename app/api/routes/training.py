from fastapi import APIRouter, Depends
from typing import List

from app.core.schemas.auth import CurrentUser
from app.core.auth.deps import require_roles
from app.core.schemas.training import (
    LevelCreate, 
    AssignLevelRequest, 
    DashboardLevel, 
    MarkItemRequest,
    SetLevelResultRequest
)
from app.core.models.training import SystemTrainingLevel
from app.modules.hr.training_config_service import TrainingConfigService
from app.modules.hr.training_progress_service import TrainingProgressService

# =============================================================================
# MAIN ROUTER
# =============================================================================

router = APIRouter(prefix="/training")

# =============================================================================
# ADMIN ROUTES
# =============================================================================

admin_router = APIRouter(prefix="/admin", tags=["Training Admin"])

@admin_router.post(
    "/levels", 
    status_code=201, 
    summary="Create a new Training Level",
    description="Creates a complete Level including Modules, Videos, and Tasks in one request."
)
async def create_level(
    level_data: LevelCreate,
    current_user: CurrentUser = Depends(require_roles("Admin", "HR"))
):
    return await TrainingConfigService.create_level(level_data)

@admin_router.get(
    "/levels/{level_id}", 
    response_model=SystemTrainingLevel,
    summary="Get Level Configuration",
    description="Fetches the full hierarchical structure of a level for HR editing."
)
async def get_level_config(
    level_id: str,
    current_user: CurrentUser = Depends(require_roles("Admin", "HR"))
):
    return await TrainingConfigService.get_level_config(level_id)

@admin_router.put(
    "/levels/{level_id}", 
    response_model=SystemTrainingLevel,
    summary="Update Level Configuration",
    description="Updates the entire structure of a level. Used to edit titles, links, or delete items."
)
async def update_level_config(
    level_id: str,
    level_data: SystemTrainingLevel,
    current_user: CurrentUser = Depends(require_roles("Admin", "HR"))
):
    return await TrainingConfigService.update_level_config(level_id, level_data)

@admin_router.post(
    "/assign",
    summary="Assign Level to Employee",
    description="Assigns a training level to a specific employee and initializes their progress tracking."
)
async def assign_level_to_employee(
    request: AssignLevelRequest,
    current_user: CurrentUser = Depends(require_roles("Admin", "HR"))
):
    return await TrainingConfigService.assign_level_to_employee(request.emp_id, request.level_id)

# =============================================================================
# EMPLOYEE ROUTES
# =============================================================================

employee_router = APIRouter(prefix="/employee", tags=["Training Employee"])

@employee_router.get(
    "/dashboard", 
    response_model=List[DashboardLevel],
    summary="Get Employee Training Dashboard",
    description="Returns all assigned levels, merged with the employee's progress (Watched/Unwatched, Passed/Failed)."
)
async def get_dashboard(
    emp_id: str
):
    return await TrainingProgressService.get_employee_dashboard(emp_id)

@employee_router.post(
    "/item/action",
    summary="Mark Item as Watched or Completed",
    description="Allows an employee to mark a video as 'Watched' or a task as 'Completed'."
)
async def mark_item_action(
    emp_id: str,
    level_id: str,
    request: MarkItemRequest,
):
    return await TrainingProgressService.mark_item_complete(emp_id, level_id, request)

@employee_router.post(
    "/level/result",
    summary="Set Level Result (Pass/Fail)",
    description="Allows HR/Manager to set the Pass/Fail status for a training level."
)
async def set_level_result(
    emp_id: str,
    level_id: str,
    request: SetLevelResultRequest,
):
    return await TrainingProgressService.set_level_result(emp_id, level_id, request)

# =============================================================================
# INTEGRATION
# =============================================================================

router.include_router(admin_router)
router.include_router(employee_router)