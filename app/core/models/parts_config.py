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