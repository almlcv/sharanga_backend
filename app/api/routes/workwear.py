from fastapi import APIRouter, Depends
from app.core.schemas.auth import CurrentUser
from app.core.auth.deps import  require_roles
from app.core.schemas.workwear import (
    CreateWorkwearConfigSchema, 
    UpdateWorkwearConfigSchema, 
    UpdateWorkwearItemSchema,
    BatchAssignSchema
)
from app.modules.hr.workwear_config_service import WorkwearConfigService
from app.modules.hr.workwear_progress_service import WorkwearProgressService

router = APIRouter(prefix="/workwear", tags=["Workwear Management"])

# =============================================================================
# ADMIN ROUTES (Manage Templates)
# =============================================================================

@router.post("/admin/configs")
async def create_workwear_config(
    schema: CreateWorkwearConfigSchema,
    current_user: CurrentUser = Depends(require_roles("Admin", "HR"))
):
    """Create a new Workwear Kit Template."""
    return await WorkwearConfigService.create_config(schema)

@router.get("/admin/configs")
async def get_all_configs(
    current_user: CurrentUser = Depends(require_roles("Admin", "HR"))
):
    """List all available Workwear Kits."""
    return await WorkwearConfigService.get_all_configs()

@router.put("/admin/configs/{config_name}")
async def update_config(
    config_name: str,
    schema: UpdateWorkwearConfigSchema,
    current_user: CurrentUser = Depends(require_roles("Admin", "HR"))
):
    """Update items in a specific Kit."""
    return await WorkwearConfigService.update_config(config_name, schema)

@router.delete("/admin/configs/{config_name}")
async def delete_config(
    config_name: str,
    current_user: CurrentUser = Depends(require_roles("Admin", "HR"))
):
    """Delete a Kit Template."""
    return await WorkwearConfigService.delete_config(config_name)

# =============================================================================
# HR/EMPLOYEE ROUTES (Assign and Track)
# =============================================================================

@router.post("/assign")
async def batch_assign_workwear(
    schema: BatchAssignSchema,
    current_user: CurrentUser = Depends(require_roles("Admin", "HR"))
):
    """
    Assign multiple Workwear Kits to an employee in a single request.
    """
    return await WorkwearProgressService.assign_multiple_configs_to_employee(
        emp_id=schema.emp_id, 
        config_names=schema.config_names
    )

@router.put("/update_item")
async def update_item(
    emp_id: str,
    config_name: str,
    schema: UpdateWorkwearItemSchema,
    current_user: CurrentUser = Depends(require_roles("Admin", "HR"))
):
    """
    Mark a specific item (e.g., 'Safety Shoes') as completed for an employee.
    """
    return await WorkwearProgressService.update_item_status(emp_id, config_name, schema)