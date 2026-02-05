from fastapi import HTTPException
from typing import List, Dict
from pymongo.errors import DuplicateKeyError

from app.core.schemas.parts_config import PartConfigCreate, PartConfigUpdate
from app.core.models.parts_config import PartConfiguration


class PartConfigurationService:
    """Service handling logic for Part Configurations."""

    @staticmethod
    async def create_or_update_part(part_data: PartConfigCreate) -> PartConfiguration:
        """
        Creates or updates a part configuration.
        Enforces strict validation and Unique constraints.
        """
        part_name = part_data.part_description
        has_sided_parts = part_data.crate_sides

        # --- Check for Existing Part ---
        existing = await PartConfiguration.find_one({
            "part_description": part_name
        })

        # --- Dynamic Generation of Variations ---       
        if has_sided_parts:
            rh_name = f"{part_name} RH"
            lh_name = f"{part_name} LH"
            variations = [rh_name, lh_name]
        else:
            # Preserve existing variations on update
            if existing:
                variations = existing.variations
            else:
                variations = []

        # --- Upsert Logic ---
        clean_data = part_data.model_dump(exclude={"crate_sides", "variations"})
        clean_data["variations"] = variations

        if existing:
            # Update existing
            for key, value in clean_data.items():
                setattr(existing, key, value)
            await existing.save()
            return existing
        else:
            # Create new
            try:
                new_part = PartConfiguration(**clean_data)
                await new_part.insert()
                return new_part
            except DuplicateKeyError:
                # Handles race condition or duplicate creation attempts
                raise HTTPException(
                    status_code=400, 
                    detail=f"Part with description '{part_name}' already exists."
                )

    @staticmethod
    async def get_all_parts(active_only: bool = True) -> List[PartConfiguration]:
        """Retrieves all part configurations."""
        query = {"is_active": True} if active_only else {}
        parts = await PartConfiguration.find(query).to_list()
        return parts

    @staticmethod
    async def get_part_by_description(part_description: str) -> PartConfiguration:
        """Retrieves a specific part."""
        part = await PartConfiguration.find_one({"part_description": part_description})
        if not part:
            raise HTTPException(status_code=404, detail=f"Part '{part_description}' not found")
        return part

    @staticmethod
    async def update_part_status(part_description: str, is_active: bool) -> Dict:
        """Toggles active status of a part."""
        part = await PartConfigurationService.get_part_by_description(part_description)
        
        if part.is_active == is_active:
            raise HTTPException(
                status_code=400, 
                detail=f"Part is already {'active' if is_active else 'inactive'}."
            )
            
        part.is_active = is_active
        await part.save()
        
        return {"message": f"Part status updated to {'active' if is_active else 'inactive'}."}

    @staticmethod
    async def update_part_details(part_description: str, update_data: PartConfigUpdate) -> PartConfiguration:
        """
        Updates part details.
        Safety: Prevents modification of critical identity fields.
        """
        part = await PartConfigurationService.get_part_by_description(part_description)
        
        update_dict = update_data.model_dump(exclude_unset=True)
        
        # SAFETY: Prevent updating identity fields
        update_dict.pop("part_description", None) 
        update_dict.pop("variations", None) 
        
        for key, value in update_dict.items():
            setattr(part, key, value)
            
        await part.save()
        return part