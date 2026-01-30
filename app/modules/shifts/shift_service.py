from typing import List
from fastapi import HTTPException, status
from app.core.models.shift import GlobalShiftSetting, ShiftItem
from app.core.schemas.shift import GlobalSettingCreate

class ShiftService:
    
    @staticmethod
    def _check_overlap(new_start_time: str, new_duration: float, shifts_list: List, exclude_index: int = None):
        """
        Internal helper to check if a new shift time overlaps with existing ones.
        """
        def get_minutes(t_str):
            h, m = map(int, t_str.split(':'))
            return h * 60 + m

        new_start_mins = get_minutes(new_start_time)
        new_end_mins = new_start_mins + int(new_duration * 60)

        for idx, shift in enumerate(shifts_list):
            if exclude_index is not None and idx == exclude_index:
                continue

            exist_start_mins = get_minutes(shift.start_time)
            exist_duration = shift.regular_hours + shift.overtime_hours
            exist_end_mins = exist_start_mins + int(exist_duration * 60)

            # Overlap Logic: (StartA < EndB) and (EndA > StartB)
            if (new_start_mins < exist_end_mins) and (new_end_mins > exist_start_mins):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Time conflict: Shift '{shift.name}' ({shift.start_time}) overlaps with new time."
                )

    @staticmethod
    async def get_active_setting() -> GlobalShiftSetting:
        """Retrieves the most recently updated global setting."""
        setting = await GlobalShiftSetting.find_one(sort=[-GlobalShiftSetting.updated_at])
        if not setting:
            raise HTTPException(
                status_code=404, 
                detail="No global shift setting configured. Please create one."
            )
        return setting
    
    @staticmethod
    async def get_all_settings() -> List[GlobalShiftSetting]:
        """
        Retrieves all global shift settings.
        Returns them sorted by 'updated_at' descending, so the active one is first.
        """
        return await GlobalShiftSetting.find_all().sort(-GlobalShiftSetting.updated_at).to_list()

    @staticmethod
    async def create_setting(data: GlobalSettingCreate) -> GlobalShiftSetting:
        """Creates a new global setting after validating for time overlaps."""
        # Validate all incoming shifts against each other
        for i, shift in enumerate(data.shifts):
            duration = shift.regular_hours + shift.overtime_hours
            ShiftService._check_overlap(shift.start_time, duration, data.shifts, exclude_index=i)

        # Create document
        setting = GlobalShiftSetting(**data.model_dump())
        await setting.insert()
        return setting

    @staticmethod
    async def update_setting(setting_id: str, data: GlobalSettingCreate) -> GlobalShiftSetting:
        """Updates an existing global setting."""
        setting = await GlobalShiftSetting.get(setting_id)
        if not setting:
            raise HTTPException(status_code=404, detail="Setting not found")

        # Validate the new list of shifts
        for i, shift in enumerate(data.shifts):
            duration = shift.regular_hours + shift.overtime_hours
            ShiftService._check_overlap(shift.start_time, duration, data.shifts, exclude_index=i)

        # Update fields
        setting.setting_name = data.setting_name
        setting.shifts = [ShiftItem(**s.model_dump()) for s in data.shifts]
        
        # Update timestamp to IST
        from app.shared.timezone import get_ist_now
        setting.updated_at = get_ist_now()
        
        await setting.save()
        return setting