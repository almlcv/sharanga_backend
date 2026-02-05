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
    summary="Create or Update Part",
    description="""
    Creates a new part configuration or updates an existing one.
    
    **Behavior:**
    - If `part_description` already exists, it updates the record (Upsert).
    - If `crate_sides` is True, automatically generates 'LH' and 'RH' variations.
    - Enforces unique `part_description` and `part_number` constraints.
    
    **Role Required:** Admin or Production.
    """
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
    summary="Get All Parts",
    description="""
    Retrieves a list of all part configurations.
    
    **Filtering:**
    - `active_only=True` (default): Returns only parts currently in production.
    - `active_only=False`: Returns all parts including archived/deactivated ones.
    """
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
    summary="Get Part by Description",
    description="""
    Retrieves detailed specifications for a specific part.
    
    **Context:** Used by the Frontend to populate forms and by FG Stock to fetch automation settings (Bin Capacity).
    """
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
    summary="Update Part Details",
    description="""
    Updates technical specifications (Machine, Bin Capacity, RM, etc.).
    
    **Safety:**
    - `part_description` is **immutable**. Changing the name would break links to historical FG Stock data.
    - Only fields provided in the request body are updated (Partial Update).
    
    **Use Case:** Correcting `bin_capacity` or changing `machine` assignment.
    
    **Role Required:** Admin or Production.
    """
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
    summary="Toggle Part Status",
    description="""
    Activates or Deactivates a part.
    
    **Deactivation:** The part will not appear in daily production lists, but historical FG Stock data remains intact.
    
    **Role Required:** Admin.
    """
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