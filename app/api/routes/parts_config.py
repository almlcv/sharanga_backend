from fastapi import APIRouter, Depends, Query, status
from typing import List

from app.core.schemas.auth import CurrentUser
from app.core.auth.deps import require_roles, get_current_user
from app.core.schemas.parts_config import (
    PartConfigCreate, 
    PartConfigUpdate, 
    PartConfigResponse, 
    PartConfigStatusUpdate
)
from app.modules.parts_config.part_configuration_service import PartConfigurationService

router = APIRouter(tags=["Part Configuration"], prefix="/parts/config")


# ==================== ENDPOINTS ====================

@router.post(
    "/", 
    response_model=PartConfigResponse, 
    status_code=status.HTTP_201_CREATED,
    summary="Create or Update Part Configuration",
    description="Input: Part Name, Part Number, Machine, RM/MB. Optional: create_sides flag."
)
async def create_or_update_part_config(
    part_data: PartConfigCreate,
    current_user: CurrentUser = Depends(require_roles("Admin"))
):
    """
    Create a new part or update an existing one.
    
    **Input Fields:**
    - `part_description`: The unique name of the part.
    - `part_number`: The item code.
    - `machine`: The machine assigned (e.g., 120T).
    - `rm_mb`: List of raw materials.
    - `create_sides`: (Optional) Set to true to auto-generate RH/LH variants.
    """
    result = await PartConfigurationService.create_or_update_part(part_data.model_dump())
    
    return PartConfigResponse(
        id=str(result.id),
        part_description=result.part_description,
        part_number=result.part_number,
        machine=result.machine,
        rm_mb=result.rm_mb,
        variations=result.variations,
        is_active=result.is_active,
        created_at=result.created_at,
        updated_at=result.updated_at
    )


@router.get(
    "/", 
    response_model=List[PartConfigResponse],
    summary="Get All Part Configurations",
)
async def get_all_parts(
    active_only: bool = Query(True, description="Filter to show only active parts."),
    current_user: CurrentUser = Depends(require_roles("Production", "Admin"))
):
    parts = await PartConfigurationService.get_all_parts(active_only)
    
    return [
        PartConfigResponse(
            id=str(p.id),
            part_description=p.part_description,
            part_number=p.part_number,
            machine=p.machine,
            rm_mb=p.rm_mb,
            variations=p.variations,
            is_active=p.is_active,
            created_at=p.created_at,
            updated_at=p.updated_at
        )
        for p in parts
    ]


@router.get(
    "/{part_description}", 
    response_model=PartConfigResponse,
    summary="Get Specific Part Configuration",
)
async def get_part_config(
    part_description: str,
    current_user: CurrentUser = Depends(get_current_user)
):
    part = await PartConfigurationService.get_part_by_description(part_description)
    return PartConfigResponse(
        id=str(part.id),
        part_description=part.part_description,
        part_number=part.part_number,
        machine=part.machine,
        rm_mb=part.rm_mb,
        variations=part.variations,
        is_active=part.is_active,
        created_at=part.created_at,
        updated_at=part.updated_at
    )


@router.patch(
    "/{part_description}/status", 
    response_model=dict,
    summary="Activate or Deactivate Part",
)
async def update_part_status(
    part_description: str,
    status_data: PartConfigStatusUpdate,
    current_user: CurrentUser = Depends(require_roles("Admin"))
):
    return await PartConfigurationService.update_part_status(
        part_description, 
        status_data.is_active
    )


@router.put(
    "/{part_description}", 
    response_model=PartConfigResponse,
    summary="Update Part Details",
)
async def update_part_details(
    part_description: str,
    update_data: PartConfigUpdate,
    current_user: CurrentUser = Depends(require_roles("Admin"))
):
    result = await PartConfigurationService.update_part_details(
        part_description, 
        update_data.model_dump(exclude_unset=True)
    )
    
    return PartConfigResponse(
        id=str(result.id),
        part_description=result.part_description,
        part_number=result.part_number,
        machine=result.machine,
        rm_mb=result.rm_mb,
        variations=result.variations,
        is_active=result.is_active,
        created_at=result.created_at,
        updated_at=result.updated_at
    )