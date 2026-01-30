from fastapi import HTTPException
from uuid import UUID
from app.core.models.training import (
    SystemTrainingLevel, TrainingProfile, ModuleProgress, ItemProgress, LevelProgress
)
from app.core.schemas.training import LevelCreate

class TrainingConfigService:

    @staticmethod
    async def create_level(level_data: LevelCreate) -> SystemTrainingLevel:
        existing = await SystemTrainingLevel.find_one(SystemTrainingLevel.level_id == level_data.level_id)
        if existing:
            raise HTTPException(status_code=400, detail="Level ID already exists")
        
        for mod in level_data.modules:
            for item in mod.items:
                if not item.id:
                    item.id = UUID()
                    
        new_level = SystemTrainingLevel(**level_data.model_dump())
        await new_level.insert()
        return new_level

    @staticmethod
    async def get_level_config(level_id: str) -> SystemTrainingLevel:
        level = await SystemTrainingLevel.find_one(SystemTrainingLevel.level_id == level_id)
        if not level:
            raise HTTPException(status_code=404, detail="Level not found")
        return level

    @staticmethod
    async def update_level_config(level_id: str, level_data: SystemTrainingLevel) -> SystemTrainingLevel:
        existing = await SystemTrainingLevel.find_one(SystemTrainingLevel.level_id == level_id)
        if not existing:
            raise HTTPException(status_code=404, detail="Level not found")

        for mod in level_data.modules:
            for item in mod.items:
                if not item.id:
                    item.id = UUID()

        await existing.set(level_data.model_dump(exclude_unset=True))
        return existing

    @staticmethod
    async def assign_level_to_employee(emp_id: str, level_id: str):
        master_level = await SystemTrainingLevel.find_one(SystemTrainingLevel.level_id == level_id)
        if not master_level:
            raise HTTPException(status_code=404, detail="Level config not found")

        profile = await TrainingProfile.find_one(TrainingProfile.emp_id == emp_id)
        if not profile:
            profile = TrainingProfile(emp_id=emp_id)
        
        if level_id in profile.assigned_levels:
            raise HTTPException(status_code=400, detail="Employee already assigned")

        module_progress_list = []
        for mod in master_level.modules:
            items_progress = []
            
            for item in mod.items:
                items_progress.append(ItemProgress(
                    item_id=item.id,
                    type=item.type,
                    status="Not Started"
                ))

            module_progress_list.append(ModuleProgress(
                module_id=mod.module_id,
                items=items_progress
            ))

        level_progress = LevelProgress(
            level_id=level_id,
            modules=module_progress_list,
            result_status="Not Set",
            retrain_count=0,
        )

        profile.assigned_levels.append(level_id)
        profile.level_progress[level_id] = level_progress
        await profile.save()
        return profile