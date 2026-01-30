from datetime import datetime
from typing import List, Optional
from beanie import Document
from pydantic import BaseModel, Field
from app.shared.timezone import get_ist_now

class ShiftItem(BaseModel):
    """Represents a single shift configuration stored in DB."""
    name: str = Field(..., description="Name of the shift (e.g., 'A', 'Morning')")
    start_time: str = Field(..., pattern="^([0-1]?[0-9]|2[0-3]):[0-5][0-9]$", description="Start time HH:MM")
    regular_hours: float = Field(..., gt=0, description="Standard paid hours")
    overtime_hours: float = Field(default=0, ge=0, description="Overtime paid hours")

class GlobalShiftSetting(Document):
    """
    Stores the currently active global shift configuration.
    The system assumes the latest updated document is the active one.
    """
    setting_name: str = Field(..., description="Name for this configuration period")
    shifts: List[ShiftItem] = Field(default_factory=list)
    updated_at: Optional[datetime] = Field(default_factory=get_ist_now)

    class Settings:
        name = "global_shift_settings"