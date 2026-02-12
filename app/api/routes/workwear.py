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

@router.post(
    "/admin/configs",
    summary="Create Workwear Kit Template",
    description="""
    Create a new workwear kit configuration template.
    
    **Authorization:** Requires Admin or HR role.
    
    **Request Body:**
    - `config_name`: Unique identifier for the kit (e.g., "Safety Kit", "Winter Uniform")
    - `items`: List of workwear items, each with:
      - `item_name`: Name of the item (e.g., "Safety Shoes", "Hard Hat")
      - `quantity`: Number of items to issue
    
    **Business Rules:**
    - Config name must be unique across all kits
    - Items can include safety equipment, uniforms, PPE, tools, etc.
    - Once created, kits can be assigned to employees
    - Kits serve as templates for consistent workwear distribution
    
    **Use Case:**
    HR creates standardized workwear kits for different roles, departments, or safety requirements.
    
    **Example Request:**
    ```json
    {
      "config_name": "Safety Kit",
      "items": [
        {"item_name": "Safety Shoes", "quantity": 1},
        {"item_name": "Hard Hat", "quantity": 1},
        {"item_name": "Safety Goggles", "quantity": 2},
        {"item_name": "Gloves", "quantity": 3}
      ]
    }
    ```
    """,
    responses={
        201: {"description": "Workwear kit template created successfully"},
        400: {"description": "Kit name already exists or invalid data"},
        401: {"description": "Not authenticated"},
        403: {"description": "Insufficient permissions (requires Admin or HR role)"}
    }
)
async def create_workwear_config(
    schema: CreateWorkwearConfigSchema,
    current_user: CurrentUser = Depends(require_roles("Admin", "HR"))
):
    """Create a new Workwear Kit Template."""
    return await WorkwearConfigService.create_config(schema)

@router.get(
    "/admin/configs",
    summary="List All Workwear Kits",
    description="""
    Retrieve a list of all available workwear kit templates.
    
    **Authorization:** Requires Admin or HR role.
    
    **Returns:**
    List of all workwear kit configurations with their items and quantities.
    Each kit includes:
    - Kit name/identifier
    - List of items with names and quantities
    - Creation and update timestamps
    
    **Use Case:**
    HR views all available workwear kits to:
    - Review existing kit configurations
    - Select kits for employee assignment
    - Identify kits that need updates
    - Plan inventory requirements
    """,
    responses={
        200: {"description": "List of workwear kits retrieved successfully"},
        401: {"description": "Not authenticated"},
        403: {"description": "Insufficient permissions"}
    }
)
async def get_all_configs(
    current_user: CurrentUser = Depends(require_roles("Admin", "HR"))
):
    """List all available Workwear Kits."""
    return await WorkwearConfigService.get_all_configs()

@router.put(
    "/admin/configs/{config_name}",
    summary="Update Workwear Kit Template",
    description="""
    Update items in an existing workwear kit configuration.
    
    **Authorization:** Requires Admin or HR role.
    
    **Path Parameters:**
    - `config_name`: Name of the kit to update
    
    **Request Body:**
    - `items`: Updated list of workwear items with names and quantities
    
    **Business Rules:**
    - Only items can be updated; config name cannot be changed
    - Completely replaces the existing item list
    - Updates affect future assignments only
    - Existing employee workwear records remain unchanged
    
    **Use Case:**
    HR updates kit contents when:
    - Safety requirements change
    - New equipment is added to standard issue
    - Item quantities need adjustment
    - Obsolete items need removal
    
    **Example:**
    Update "Safety Kit" to add reflective vest and increase glove quantity.
    """,
    responses={
        200: {"description": "Kit updated successfully"},
        404: {"description": "Kit not found"},
        400: {"description": "Invalid data"},
        403: {"description": "Insufficient permissions"}
    }
)
async def update_config(
    config_name: str,
    schema: UpdateWorkwearConfigSchema,
    current_user: CurrentUser = Depends(require_roles("Admin", "HR"))
):
    """Update items in a specific Kit."""
    return await WorkwearConfigService.update_config(config_name, schema)

@router.delete(
    "/admin/configs/{config_name}",
    summary="Delete Workwear Kit Template",
    description="""
    Permanently delete a workwear kit template.
    
    **Authorization:** Requires Admin or HR role.
    
    **Path Parameters:**
    - `config_name`: Name of the kit to delete
    
    **Warning:**
    - This action is permanent and cannot be undone
    - Does not affect existing employee workwear records
    - Kit cannot be assigned to new employees after deletion
    - Consider updating instead of deleting if kit is still in use
    
    **Use Case:**
    HR removes obsolete or incorrectly created kit templates.
    
    **Example:**
    Delete "Old Safety Kit" template that has been replaced by "New Safety Kit 2026".
    """,
    responses={
        200: {"description": "Kit deleted successfully"},
        404: {"description": "Kit not found"},
        403: {"description": "Insufficient permissions"}
    }
)
async def delete_config(
    config_name: str,
    current_user: CurrentUser = Depends(require_roles("Admin", "HR"))
):
    """Delete a Kit Template."""
    return await WorkwearConfigService.delete_config(config_name)

# =============================================================================
# HR/EMPLOYEE ROUTES (Assign and Track)
# =============================================================================

@router.post(
    "/assign",
    summary="Assign Workwear Kits to Employee",
    description="""
    Assign one or more workwear kits to an employee in a single request.
    
    **Authorization:** Requires Admin or HR role.
    
    **Request Body:**
    - `emp_id`: Employee ID to assign kits to
    - `config_names`: Array of kit names to assign
    
    **Business Rules:**
    - Employee must exist in the system
    - All kit names must be valid (exist in configurations)
    - Creates tracking records for each item in each kit
    - All items start with "pending" or "not issued" status
    - Multiple kits can be assigned simultaneously
    
    **Use Case:**
    During onboarding, HR assigns multiple kits to a new employee:
    - Safety Kit (PPE and safety equipment)
    - Uniform Kit (work uniforms)
    - Tool Kit (if applicable to role)
    
    **Example Request:**
    ```json
    {
      "emp_id": "EMP001",
      "config_names": ["Safety Kit", "Winter Uniform", "PPE Kit"]
    }
    ```
    
    **Workflow:**
    1. HR assigns kits during onboarding
    2. System creates tracking records for all items
    3. Stores department marks items as issued when distributed
    4. HR can track completion status
    """,
    responses={
        201: {"description": "Kits assigned successfully"},
        400: {"description": "Invalid employee ID or kit names"},
        404: {"description": "Employee or kit not found"},
        403: {"description": "Insufficient permissions"}
    }
)
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

@router.put(
    "/update_item",
    summary="Update Workwear Item Status",
    description="""
    Mark a specific workwear item as completed/issued for an employee.
    
    **Authorization:** Requires Admin or HR role.
    
    **Query Parameters:**
    - `emp_id`: Employee ID
    - `config_name`: Kit name containing the item
    
    **Request Body:**
    - `item_name`: Name of the item to update (e.g., "Safety Shoes")
    - `status`: New status (e.g., "issued", "completed", "returned")
    - `issued_date`: Date when item was issued (optional)
    - `remarks`: Additional notes (optional)
    
    **Business Rules:**
    - Item must exist in the specified kit for this employee
    - Status updates are tracked with timestamp
    - Can be used to track item lifecycle: pending → issued → returned/replaced
    - Multiple status updates allowed for tracking history
    
    **Use Case:**
    Stores department marks "Safety Shoes" as issued when employee receives them from inventory.
    
    **Example:**
    ```
    PUT /workwear/update_item?emp_id=EMP001&config_name=Safety Kit
    {
      "item_name": "Safety Shoes",
      "status": "issued",
      "issued_date": "2026-02-10",
      "remarks": "Size 9, Brand XYZ"
    }
    ```
    
    **Workflow:**
    1. Employee assigned kit (items pending)
    2. Employee visits stores
    3. Stores issues item and updates status
    4. HR can track completion percentage
    """,
    responses={
        200: {"description": "Item status updated successfully"},
        404: {"description": "Employee, kit, or item not found"},
        400: {"description": "Invalid data"},
        403: {"description": "Insufficient permissions"}
    }
)
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