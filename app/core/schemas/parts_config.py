from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List
from datetime import datetime


class PartConfigBase(BaseModel):
    """Base fields shared across schemas"""
    part_description: str = Field(..., min_length=1, description="Name of the part.")
    part_number: str = Field(..., description="Item code.")
    machine: Optional[str] = Field(None, description="Machine assigned (e.g., 120T).")
    rm_mb: Optional[List[str]] = Field(None, description="Raw Material and Master Batch codes")


class PartConfigCreate(PartConfigBase):
    """
    Schema for creating a new part.
    Matches the exact input structure requested.
    """
    # Logic Flag: If True, backend creates 'Name RH' and 'Name LH'
    create_sides: bool = Field(
        False,
        description="If true, generates RH and LH variants automatically."
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "create_sides": True,
                "machine": "120T",
                "part_description": "ALTROZ BRACKET-D",
                "part_number": "10077-7R05S",
                "rm_mb": ["PP TF 30% Black"]
            }
        }
    )


class PartConfigUpdate(BaseModel):
    """Schema for partial updates"""
    part_number: Optional[str] = None
    machine: Optional[str] = None
    rm_mb: Optional[List[str]] = None
    is_active: Optional[bool] = None
    
    # Allows manual override of generated variants if needed
    variations: Optional[List[str]] = None


class PartConfigResponse(PartConfigBase):
    """Schema for API Response"""
    id: str
    variations: List[str] = Field(default_factory=list)
    rm_mb: Optional[List[str]] = None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PartConfigStatusUpdate(BaseModel):
    """Schema for toggling active status"""
    is_active: bool