from datetime import datetime
from typing import List, Optional
from beanie import Document
from pydantic import Field
from app.shared.timezone import get_ist_now

class PartConfiguration(Document):
    """
    MongoDB Document representing a Part Configuration.
    Tracks Part Name, Part Number, Variations, and RM+MB.
    """
    part_description: str = Field(..., unique=True, description="Unique name of the part")
    part_number: str = Field(..., description="Item code / Part Number")
    
    # Requested Fields
    machine: Optional[str] = Field(None, description="Machine assigned (e.g., 120T)")
    rm_mb: Optional[List[str]] = Field(None, description="List of Raw Material (RM) and Master Batch (MB) codes")
    cycle_time: Optional[float] = Field(
        None,
        description="Typical cycle time in seconds for the part"
    )
    part_weight: Optional[float] = Field(
        None,
        description="Net part weight in grams"
    )
    runner_weight: Optional[float] = Field(
        None,
        description="Runner weight in grams"
    )
    cavity: Optional[int] = Field(
        None,
        description="Cavity count (1-8)."
    )
    bin_capacity: Optional[int] = Field(
        None, 
        ge=1, 
        description="Standard quantity of parts per bin."
    )
    # Dynamic Fields
    variations: List[str] = Field(default_factory=list, description="List of generated variants (e.g., RH/LH)")

    # Metadata
    is_active: bool = Field(default=True, description="Determines if the part is visible")
    created_at: datetime = Field(default_factory=get_ist_now)
    updated_at: datetime = Field(default_factory=get_ist_now)

    class Settings:
        name = "part_configurations"
        indexes = [
            "is_active",
            "part_description"
        ]

    class Config:
        json_schema_extra = {
            "example": {
                "part_description": "ALTROZ BRACKET-D",
                "part_number": "10077-7R05S",
                "machine": "120T",
                "rm_mb": ["PP TF 30% Black"],
                "variations": ["ALTROZ BRACKET-D RH", "ALTROZ BRACKET-D LH"],
                "is_active": True
            }
        }