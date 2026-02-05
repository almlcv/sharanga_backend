from pydantic import BaseModel, Field, ConfigDict, field_serializer
from typing import Optional, List
from datetime import datetime
from bson import ObjectId


class PartConfigBase(BaseModel):
    """Base fields shared across schemas"""
    part_description: str = Field(..., min_length=1, description="Name of the part.")
    part_number: str = Field(..., description="Item code.")
    machine: Optional[str] = Field(None, description="Machine assigned (e.g., 120T).")
    rm_mb: Optional[List[str]] = Field(None, description="Raw Material and Master Batch codes")
    cycle_time: Optional[float] = Field(None, description="Typical cycle time in seconds.")
    part_weight: Optional[float] = Field(None, description="Net part weight in grams.")
    runner_weight: Optional[float] = Field(None, description="Runner weight in grams.")
    cavity: Optional[int] = Field(None, ge=1, le=8, description="Cavity count.")
    
    bin_capacity: Optional[int] = Field(
        None, 
        ge=1, 
        description="Standard quantity of parts per bin. Used to automate bin transfers."
    )


class PartConfigCreate(PartConfigBase):
    """
    Schema for creating a new part.
    """
    crate_sides: bool = Field(
        False,
        description="If true, generates RH and LH variants automatically."
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "crate_sides": True,
                "machine": "120T",
                "part_description": "ALTROZ BRACKET-D",
                "part_number": "10077-7R05S",
                "rm_mb": ["PP TF 30% Black"],
                "cycle_time": 12.5,
                "part_weight": 45.3,
                "runner_weight": 2.5,
                "cavity": 4,
                "bin_capacity": 100
            }
        }
    )


class PartConfigUpdate(BaseModel):
    """
    Schema for partial updates.
    
    NOTE: 'part_description' is intentionally excluded. 
    Renaming parts breaks historical links in FG Stock.
    """
    part_number: Optional[str] = None
    machine: Optional[str] = None
    rm_mb: Optional[List[str]] = None
    is_active: Optional[bool] = None
    variations: Optional[List[str]] = None
    cycle_time: Optional[float] = None
    part_weight: Optional[float] = None
    runner_weight: Optional[float] = None
    cavity: Optional[int] = Field(None, ge=1, le=8)
    
    bin_capacity: Optional[int] = Field(None, ge=1)


class PartConfigResponse(PartConfigBase):
    """Schema for API Response"""
    id: str
    variations: List[str] = Field(default_factory=list)
    rm_mb: Optional[List[str]] = None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @field_serializer('id')
    def serialize_id(self, value: ObjectId, _info):
        return str(value)


class PartConfigStatusUpdate(BaseModel):
    """Schema for toggling active status"""
    is_active: bool