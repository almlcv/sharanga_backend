from fastapi import APIRouter, Depends, status
from typing import List
from app.core.schemas.parts_config import (
    PartConfigCreate,
    PartConfigUpdate,
    PartConfigResponse,
    PartConfigStatusUpdate
)
from app.modules.parts_config.part_configuration_service import PartConfigurationService
from app.core.auth.deps import get_current_user, require_roles

router = APIRouter(tags=["Parts Configuration"], prefix="/parts/config")


# ============================================================
# HELPER FUNCTION: SERIALIZATION FIX
# ============================================================
def _to_response_model(document) -> dict:
    """
    Converts a Beanie Document to a dictionary compatible with PartConfigResponse.
    
    Fixes the 'ObjectId' validation error by manually converting the MongoDB ID to a string.
    This ensures the API layer handles serialization cleanly without modifying the Service layer.
    """
    response_dict = document.model_dump()
    response_dict['id'] = str(document.id)
    return response_dict


# ============================================================
# PART CONFIGURATION ENDPOINTS
# ============================================================

@router.post(
    "/",
    response_model=PartConfigResponse,
    status_code=status.HTTP_200_OK,
    summary="Create or Update Part Configuration",
    description="""
    Create a new part configuration or update an existing one (Upsert operation).
    
    **Authorization:** Requires Admin or Production role.
    
    **Request Body:**
    - `part_description`: Unique part description/name
    - `part_number`: Unique part number/code
    - `machine`: Machine assigned to produce this part
    - `bin_capacity`: Bin capacity for FG stock automation
    - `crate_sides`: Boolean - if True, automatically generates LH and RH variations
    - `raw_material`: Raw material specification (optional)
    - `weight`: Part weight (optional)
    - `cycle_time`: Production cycle time (optional)
    - `is_active`: Active status (default: true)
    
    **Behavior:**
    - **If part_description exists**: Updates the existing record (Upsert)
    - **If crate_sides = true**: Automatically creates two variations:
      - Part with "-LH" suffix (Left Hand)
      - Part with "-RH" suffix (Right Hand)
    - **Validation**: Enforces unique part_description and part_number
    
    **Use Cases:**
    - Add new part to production system
    - Update existing part specifications
    - Configure sided parts (LH/RH) automatically
    
    **Example:**
    Create "Dashboard Panel" with LH/RH sides, bin capacity 100, machine "M1".
    """,
    responses={
        200: {"description": "Part created or updated successfully"},
        400: {"description": "Duplicate part_description/part_number or validation error"},
        401: {"description": "Not authenticated"},
        403: {"description": "Insufficient permissions (requires Admin or Production role)"}
    }
)
async def create_or_update_part_config(
    part_data: PartConfigCreate,
    current_user: dict = Depends(require_roles("Admin", "Production"))
):
    result = await PartConfigurationService.create_or_update_part(part_data)
    return _to_response_model(result)


@router.get(
    "/",
    response_model=List[PartConfigResponse],
    summary="Get All Part Configurations",
    description="""
    Retrieve a list of all part configurations with optional filtering.
    
    **Query Parameters:**
    - `active_only` (boolean, default: true): Filter by active status
      - `true`: Returns only active parts currently in production
      - `false`: Returns all parts including deactivated/archived ones
    
    **Returns:**
    List of part configurations, each containing:
    - Part description and number
    - Machine assignment
    - Bin capacity
    - Raw material specifications
    - Technical details (weight, cycle time)
    - Active status
    - Side information (LH/RH if applicable)
    
    **Use Cases:**
    - View all active parts for production planning
    - Review part specifications
    - Populate dropdown lists in UI
    - Export part master data
    
    **Example:**
    Get all active parts: `?active_only=true`
    Get all parts including inactive: `?active_only=false`
    """,
    responses={
        200: {"description": "List of part configurations retrieved successfully"},
        401: {"description": "Not authenticated"}
    }
)
async def get_all_parts(
    active_only: bool = True,
    current_user: dict = Depends(get_current_user)
):
    parts = await PartConfigurationService.get_all_parts(active_only)
    # Apply serialization fix to the list
    return [_to_response_model(p) for p in parts]


@router.get(
    "/{part_description}",
    response_model=PartConfigResponse,
    summary="Get Part Configuration by Description",
    description="""
    Retrieve detailed specifications for a specific part by its description.
    
    **Path Parameters:**
    - `part_description`: Unique part description/name
    
    **Returns:**
    Complete part configuration including:
    - Part number and description
    - Machine assignment
    - Bin capacity (used by FG Stock automation)
    - Raw material specifications
    - Technical specifications (weight, cycle time)
    - Side information (LH/RH if applicable)
    - Active status
    
    **Use Cases:**
    - Frontend forms: Populate part details when user selects a part
    - FG Stock: Fetch bin capacity for automated stock calculations
    - Production planning: Get machine and cycle time information
    - Quality control: Verify part specifications
    
    **Example:**
    Get configuration for "Dashboard Panel-LH" to display in production form.
    """,
    responses={
        200: {"description": "Part configuration retrieved successfully"},
        404: {"description": "Part not found"},
        401: {"description": "Not authenticated"}
    }
)
async def get_part_by_description(
    part_description: str,
    current_user: dict = Depends(get_current_user)
):
    result = await PartConfigurationService.get_part_by_description(part_description)
    return _to_response_model(result)


@router.patch(
    "/{part_description}",
    response_model=PartConfigResponse,
    summary="Update Part Technical Specifications",
    description="""
    Update technical specifications for an existing part (Partial Update).
    
    **Authorization:** Requires Admin or Production role.
    
    **Path Parameters:**
    - `part_description`: Part description (immutable identifier)
    
    **Request Body (all fields optional):**
    - `machine`: Update machine assignment
    - `bin_capacity`: Update bin capacity for FG stock
    - `raw_material`: Update raw material specification
    - `weight`: Update part weight
    - `cycle_time`: Update production cycle time
    - `part_number`: Update part number (use with caution)
    
    **Safety Rules:**
    - `part_description` is **immutable** - cannot be changed via this endpoint
    - Changing part_description would break links to historical data (FG Stock, production records)
    - Only provided fields are updated (partial update)
    - Other fields remain unchanged
    
    **Use Cases:**
    - Correct bin_capacity when automation settings change
    - Update machine assignment when production line changes
    - Adjust cycle_time based on process improvements
    - Update raw material specifications
    
    **Example:**
    Update bin capacity from 100 to 120 for "Dashboard Panel-LH".
    
    **Warning:** To change part_description, create a new part and deactivate the old one.
    """,
    responses={
        200: {"description": "Part specifications updated successfully"},
        404: {"description": "Part not found"},
        400: {"description": "Invalid data or duplicate part_number"},
        401: {"description": "Not authenticated"},
        403: {"description": "Insufficient permissions"}
    }
)
async def update_part_details(
    part_description: str,
    update_data: PartConfigUpdate,
    current_user: dict = Depends(require_roles("Admin", "Production"))
):
    result = await PartConfigurationService.update_part_details(part_description, update_data)
    return _to_response_model(result)


@router.patch(
    "/{part_description}/status",
    summary="Activate or Deactivate Part",
    description="""
    Toggle the active status of a part configuration.
    
    **Authorization:** Requires Admin role.
    
    **Path Parameters:**
    - `part_description`: Part description to update
    
    **Request Body:**
    - `is_active`: Boolean (true = activate, false = deactivate)
    
    **Effects of Deactivation:**
    - Part will NOT appear in:
      - Daily production lists
      - Active part dropdowns
      - New production planning
    - Historical data remains intact:
      - FG Stock records preserved
      - Production history preserved
      - All past transactions remain accessible
    
    **Effects of Activation:**
    - Part becomes available for:
      - New production planning
      - Production entry forms
      - Stock management
    
    **Use Cases:**
    - **Deactivate**: Part discontinued, obsolete, or temporarily out of production
    - **Activate**: Reintroduce previously discontinued part
    
    **Example:**
    Deactivate "Old Model Dashboard" when replaced by new model.
    
    **Note:** This is a soft delete. Part data is never permanently removed.
    """,
    responses={
        200: {"description": "Part status updated successfully"},
        404: {"description": "Part not found"},
        400: {"description": "Invalid status value"},
        401: {"description": "Not authenticated"},
        403: {"description": "Insufficient permissions (requires Admin role)"}
    }
)
async def update_part_status(
    part_description: str,
    status_data: PartConfigStatusUpdate,
    current_user: dict = Depends(require_roles("Admin"))
):
    return await PartConfigurationService.update_part_status(
        part_description, 
        status_data.is_active
    )