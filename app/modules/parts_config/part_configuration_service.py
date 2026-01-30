from fastapi import HTTPException
from typing import List, Dict
from app.core.models.parts_config import PartConfiguration


class PartConfigurationService:
    """Service handling logic for Part Configurations."""

    @staticmethod
    async def create_or_update_part(part_data: dict) -> PartConfiguration:
        """
        Creates or updates a part configuration.
        """
        part_name = part_data["part_description"]
        has_sided_parts = part_data.get("create_sides", False)

        # --- Dynamic Generation of Variations ---
        if has_sided_parts:
            rh_name = f"{part_name} RH"
            lh_name = f"{part_name} LH"
            part_data["variations"] = [rh_name, lh_name]
        else:
            # Single Part Logic
            part_data["variations"] = []

        # --- Upsert Logic ---
        # Remove helper flags before DB save
        clean_data = {
            k: v for k, v in part_data.items()
            if k not in ["create_sides"]
        }

        existing = await PartConfiguration.find_one({
            "part_description": part_name
        })

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
    async def update_part_details(part_description: str, update_data: dict) -> PartConfiguration:
        """Allows manual override of details like RM/MB, Machine, etc."""
        part = await PartConfigurationService.get_part_by_description(part_description)
        
        for key, value in update_data.items():
            setattr(part, key, value)
            
        await part.save()
        return part