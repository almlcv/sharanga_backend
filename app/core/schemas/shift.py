from typing import List, Optional
from datetime import datetime
from bson import ObjectId  # Required to handle MongoDB IDs
from pydantic import BaseModel, Field, field_validator

class ShiftItemBase(BaseModel):
    name: str = Field(..., description="Shift Name (e.g., 'A', 'B')")
    start_time: str = Field(..., pattern="^([0-1]?[0-9]|2[0-3]):[0-5][0-9]$", description="Start time in HH:MM format (24h)")
    regular_hours: float = Field(..., gt=0, description="Standard paid hours")
    overtime_hours: float = Field(default=0, ge=0, description="Overtime paid hours")

    class Config:
        json_schema_extra = {
            "example": {
                "name": "Shift A",
                "start_time": "08:00",
                "regular_hours": 8,
                "overtime_hours": 0
            }
        }

class GlobalSettingCreate(BaseModel):
    setting_name: str = Field(..., description="Unique name for this shift configuration")
    shifts: List[ShiftItemBase] = Field(..., min_length=1, description="List of shifts to configure")

    class Config:
        json_schema_extra = {
            "example": {
                "setting_name": "Standard 8-Hour Day",
                "shifts": [
                    {"name": "A", "start_time": "09:00", "regular_hours": 8, "overtime_hours": 0}
                ]
            }
        }

class GlobalSettingResponse(BaseModel):
    id: Optional[str] = None
    setting_name: str
    shifts: List[ShiftItemBase]
    # Changed type from str to datetime. FastAPI/Pydantic will auto-serialize this to an ISO string in the JSON response.
    updated_at: Optional[datetime] = None 
    
    class Config:
        from_attributes = True

    # Validator to convert MongoDB ObjectId to string automatically
    @field_validator('id', mode='before')
    @classmethod
    def convert_objectid_to_str(cls, v):
        if isinstance(v, ObjectId):
            return str(v)
        return v

class MessageResponse(BaseModel):
    detail: str