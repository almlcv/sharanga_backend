from fastapi import HTTPException
from uuid import UUID
from datetime import datetime
from app.shared.timezone import get_ist_now
from typing import List, Dict

from app.core.models.training import (
    TrainingProfile, SystemTrainingLevel, ModuleProgress, ItemProgress, LevelProgress
)
from app.core.schemas.training import (
    DashboardLevel, DashboardModule, DashboardVideoItem, DashboardTaskItem,
    MarkItemRequest,
    SetLevelResultRequest,
)

class TrainingProgressService:

    @staticmethod
    async def get_employee_dashboard(emp_id: str) -> List[DashboardLevel]:
        profile = await TrainingProfile.find_one(TrainingProfile.emp_id == emp_id)
        if not profile or not profile.assigned_levels:
            return []

        levels = await SystemTrainingLevel.find(
            {"level_id": {"$in": profile.assigned_levels}}
        ).to_list()

        dashboard_data = []

        for level in levels:
            level_progress: LevelProgress = profile.level_progress.get(level.level_id)
            if not level_progress:
                # In case of mismatch, skip or create default
                continue

            progress_lookup: Dict[str, Dict[UUID, ItemProgress]] = {}
            for mod_prog in level_progress.modules:
                item_map = {item.item_id: item for item in mod_prog.items}
                progress_lookup[mod_prog.module_id] = item_map

            dashboard_modules = []

            for mod in level.modules:
                module_progress_map = progress_lookup.get(mod.module_id, {})
                
                dashboard_videos = []
                dashboard_tasks = []

                for item in mod.items:
                    prog = module_progress_map.get(item.id)
                    status = prog.status if prog else "Not Started"
                    completed_at = prog.completed_at.isoformat() if prog and prog.completed_at else None

                    if item.type == "OJT":
                        dashboard_tasks.append(DashboardTaskItem(
                            id=item.id, title=item.title, status=status, completed_at=completed_at
                        ))
                    else:
                        dashboard_videos.append(DashboardVideoItem(
                            id=item.id, title=item.title, link=item.link or "", status=status, watched_at=completed_at
                        ))

                mod_prog_obj = next(
                    (m for m in level_progress.modules if m.module_id == mod.module_id), None
                )
                res_status = "Not Set"
                if mod_prog_obj:
                    if mod_prog_obj.result_status is True:
                        res_status = "Passed"
                    elif mod_prog_obj.result_status is False:
                        res_status = "Failed"
                
                retrain = mod_prog_obj.retrain_count if mod_prog_obj else 0

                dashboard_modules.append(DashboardModule(
                    module_id=mod.module_id,
                    module_name=mod.module_name,
                    videos=dashboard_videos,
                    ojt_tasks=dashboard_tasks,
                    result_status=res_status,
                    retrain_count=retrain
                ))

            dashboard_data.append(DashboardLevel(
                level_id=level.level_id,
                display_name=level.display_name,
                modules=dashboard_modules,
                result_status=level_progress.result_status,  # new field
                retrain_count=level_progress.retrain_count,
            ))

        return dashboard_data

    @staticmethod
    async def mark_item_complete(emp_id: str, level_id: str, request: MarkItemRequest):
        profile = await TrainingProfile.find_one(TrainingProfile.emp_id == emp_id)
        if not profile:
            raise HTTPException(status_code=404, detail="Employee profile not found")

        level_progress = profile.level_progress.get(level_id)
        if not level_progress:
            raise HTTPException(status_code=403, detail="Level not assigned to user")

        for mod in level_progress.modules:
            for item in mod.items:
                if item.item_id == request.item_id:
                    item.status = request.status
                    item.completed_at = get_ist_now()
                    await profile.save()
                    return {"message": "Status updated"}
        
        raise HTTPException(status_code=404, detail="Item not found in user progress")

    @staticmethod
    async def set_level_result(emp_id: str, level_id: str, request: SetLevelResultRequest):
        profile = await TrainingProfile.find_one(TrainingProfile.emp_id == emp_id)
        if not profile:
            raise HTTPException(status_code=404, detail="Employee profile not found")

        level_progress = profile.level_progress.get(level_id)
        if not level_progress:
            raise HTTPException(status_code=404, detail="Level not assigned to user")

        level_progress.result_status = request.status
        await profile.save()
        return {"message": "Level result updated"}