from fastapi import HTTPException
from typing import List, Dict, Union

# Import the Schemas (Assuming they are in app.core.schemas.parts_config based on structure)
from app.core.schemas.parts_config import PartConfigCreate, PartConfigUpdate
from app.core.models.parts_config import PartConfiguration


class PartConfigurationService:
    """Service handling logic for Part Configurations."""

    @staticmethod
    async def create_or_update_part(part_data: Union[PartConfigCreate, dict]) -> PartConfiguration:
        """
        Creates or updates a part configuration.
        Accepts a Pydantic model for automatic validation (e.g., bin_capacity checks).
        """
        # Accept either a Pydantic model or a plain dict (routes often pass model_dump())
        if isinstance(part_data, dict):
            part_name = part_data.get("part_description")
            has_sided_parts = part_data.get("create_sides", False)
        else:
            part_name = part_data.part_description
            has_sided_parts = part_data.create_sides

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
            # If updating and flag is False, don't wipe existing variations
            if existing:
                variations = existing.variations
            else:
                # Creating a new part, no sides
                variations = []

        # --- Upsert Logic ---
        # Convert to clean dict, excluding helper fields
        if isinstance(part_data, dict):
            clean_data = {k: v for k, v in part_data.items() if k not in {"create_sides", "variations"}}
        else:
            clean_data = part_data.model_dump(exclude={"create_sides", "variations"})
        
        # Add back the calculated variations
        clean_data["variations"] = variations

        if existing:
            # Update existing
            for key, value in clean_data.items():
                setattr(existing, key, value)
            await existing.save()
            return existing
        else:
            # Create new
            new_part = PartConfiguration(**clean_data)
            await new_part.insert()
            return new_part

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
        Allows manual override of details like RM/MB, Machine, bin_capacity, etc.
        Accepts a Pydantic model for validation.
        """
        part = await PartConfigurationService.get_part_by_description(part_description)
        
        # Accept either a Pydantic model or a plain dict from route
        if isinstance(update_data, dict):
            update_dict = update_data
        else:
            # Convert Pydantic model to dict, excluding unset values (None)
            # This ensures we only update fields that were actually in the request
            update_dict = update_data.model_dump(exclude_unset=True)
        
        for key, value in update_dict.items():
            setattr(part, key, value)
            
        await part.save()
        return part