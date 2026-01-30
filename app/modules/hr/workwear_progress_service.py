from fastapi import HTTPException
from datetime import datetime
from app.shared.timezone import get_ist_now
from typing import List
from app.core.models.workwear import (
    WorkwearConfig, 
    WorkwearProfile, 
    WorkwearAssignment, 
    ProfileItem,
)
from app.core.schemas.workwear import UpdateWorkwearItemSchema

class WorkwearProgressService:

    @staticmethod
    async def assign_multiple_configs_to_employee(emp_id: str, config_names: List[str]):
        """
        Assigns multiple kits to a single employee in one go.
        """
        # 1. Get or Create Profile
        profile = await WorkwearProfile.find_one(WorkwearProfile.emp_id == emp_id)
        if not profile:
            profile = WorkwearProfile(emp_id=emp_id)
            await profile.insert()

        added_count = 0
        
        # 2. Loop through the requested configs
        for name in config_names:
            # A. Check if this specific kit is already assigned to the user
            #    We skip duplicates to prevent errors in a batch request.
            existing_assignment = next((a for a in profile.assignments if a.config_name == name), None)
            if existing_assignment:
                continue 

            # B. Fetch Master Config
            config = await WorkwearConfig.find_one(WorkwearConfig.config_name == name)
            if not config:
                # Config doesn't exist in DB, skip it (or you could log a warning)
                continue

            # C. Create the new Assignment
            assignment_items = [ProfileItem(title=item.title) for item in config.items]
            
            new_assignment = WorkwearAssignment(
                config_name=config.config_name,
                display_name=config.display_name,
                items=assignment_items
            )

            # D. Append to profile
            profile.assignments.append(new_assignment)
            added_count += 1

        # 3. Save and Recalculate Status only if we actually added something
        if added_count > 0:
            profile.overall_completed = all(a.completed for a in profile.assignments)
            await profile.save()

        return {
            "message": f"Processed {len(config_names)} requests. Added {added_count} new kits.",
            "profile": profile
        }

    @staticmethod
    async def update_item_status(emp_id: str, config_name: str, schema: UpdateWorkwearItemSchema):
        """
        Note: We added 'config_name' here so we know WHICH kit to update.
        """
        profile = await WorkwearProfile.find_one(WorkwearProfile.emp_id == emp_id)
        if not profile:
            raise HTTPException(status_code=404, detail="Workwear profile not found")

        # 1. Find the specific assignment (e.g., 'safety_kit')
        assignment = next((a for a in profile.assignments if a.config_name == config_name), None)
        if not assignment:
            raise HTTPException(status_code=404, detail=f"Assignment '{config_name}' not found for this employee")

        # 2. Find the specific item within that assignment
        found = False
        for item in assignment.items:
            if item.title == schema.title:
                item.completed = schema.completed
                
                if schema.completed:
                    item.date = schema.date if schema.date else get_ist_now().strftime("%Y-%m-%d")
                else:
                    item.date = None
                
                found = True
                break

        if not found:
            raise HTTPException(status_code=404, detail="Item not found")

        # 3. Update Kit Completion Status
        assignment.completed = all(item.completed for item in assignment.items)

        # 4. Update Overall Profile Status
        profile.overall_completed = all(a.completed for a in profile.assignments)

        await profile.save()
        return {"message": "Status updated"}