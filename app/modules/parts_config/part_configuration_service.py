from fastapi import HTTPException
from typing import List, Dict
from pymongo.errors import DuplicateKeyError

from app.core.schemas.parts_config import PartConfigCreate, PartConfigUpdate
from app.core.models.parts_config import PartConfiguration


class PartConfigurationService:
    """Service handling logic for Part Configurations."""

    @staticmethod
    async def create_or_update_part(part_data: PartConfigCreate) -> PartConfiguration:
        part_name = part_data.part_description

        existing = await PartConfiguration.find_one({
            "part_description": part_name
        })

        # -----------------------------
        # VARIATION LOGIC (CREATE ONLY)
        # -----------------------------
        variations: List[str] = []

        if not existing and part_data.crate_sides:
            variations = [
                f"{part_name} RH",
                f"{part_name} LH"
            ]

        # -----------------------------
        # CLEAN PAYLOAD
        # -----------------------------
        clean_data = part_data.model_dump(exclude={"crate_sides"})

        if existing:
            # -----------------------------
            # UPDATE (variations untouched)
            # -----------------------------
            for key, value in clean_data.items():
                setattr(existing, key, value)

            existing.updated_at = existing.updated_at
            await existing.save()
            return existing

        # -----------------------------
        # CREATE
        # -----------------------------
        try:
            new_part = PartConfiguration(
                **clean_data,
                variations=variations
            )
            await new_part.insert()
            return new_part

        except DuplicateKeyError:
            raise HTTPException(
                status_code=400,
                detail=f"Part with description '{part_name}' already exists."
            )

    @staticmethod
    async def update_part_details(
        part_description: str,
        update_data: PartConfigUpdate
    ) -> PartConfiguration:
        part = await PartConfigurationService.get_part_by_description(part_description)

        update_dict = update_data.model_dump(exclude_unset=True)

        # SAFETY: prevent identity mutation
        update_dict.pop("part_description", None)

        # Explicit control of variations
        if "variations" in update_dict:
            part.variations = update_dict.pop("variations")

        for key, value in update_dict.items():
            setattr(part, key, value)

        await part.save()
        return part

    @staticmethod
    async def get_all_parts(active_only: bool = True) -> List[PartConfiguration]:
        query = {"is_active": True} if active_only else {}
        return await PartConfiguration.find(query).to_list()

    @staticmethod
    async def get_part_by_description(part_description: str) -> PartConfiguration:
        part = await PartConfiguration.find_one({"part_description": part_description})
        if not part:
            raise HTTPException(
                status_code=404,
                detail=f"Part '{part_description}' not found"
            )
        return part

    @staticmethod
    async def update_part_status(
        part_description: str,
        is_active: bool
    ) -> Dict:
        part = await PartConfigurationService.get_part_by_description(part_description)

        if part.is_active == is_active:
            raise HTTPException(
                status_code=400,
                detail=f"Part is already {'active' if is_active else 'inactive'}."
            )

        part.is_active = is_active
        await part.save()

        return {
            "message": f"Part status updated to {'active' if is_active else 'inactive'}."
        }
