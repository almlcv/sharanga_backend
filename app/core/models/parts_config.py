from datetime import datetime
from typing import List, Optional
from beanie import Document
from pydantic import Field
from app.shared.timezone import get_ist_now


class PartConfiguration(Document):
    """
    Master Configuration Document for Parts.
    
    This document acts as the "Single Source of Truth" for the manufacturing system.
    - Hourly Production references this for technical specs (Cycle Time, Cavity).
    - FG Stock references this for automation (Bin Capacity, Variations).
    
    Important:
    - 'part_description' is used as the foreign key in FGStockDocument. 
      Changing this name will break historical links to daily stock records.
    """
    
    # ==================== Identity ====================
    
    part_description: str = Field(
        ..., 
        unique=True, 
        description="Unique name of the part (e.g., 'ALTROZ BRACKET-D'). IMMUTABLE. Used to link FG Stock."
    )
    part_number: str = Field(
        ..., 
        description="Item code / Part Number (e.g., '10077-7R05S')."
    )
    
    # ==================== Technical Specifications ====================
    
    machine: Optional[str] = Field(
        None, 
        description="Machine assigned for production (e.g., '120T', '200T')."
    )
    rm_mb: Optional[List[str]] = Field(
        None, 
        description="List of Raw Material (RM) and Master Batch (MB) codes used for this part."
    )
    cycle_time: Optional[float] = Field(
        None, 
        description="Typical cycle time in seconds. Used for efficiency calculations."
    )
    part_weight: Optional[float] = Field(
        None, 
        description="Net part weight in grams."
    )
    runner_weight: Optional[float] = Field(
        None, 
        description="Runner weight in grams."
    )
    cavity: Optional[int] = Field(
        None, 
        ge=1, 
        le=8, 
        description="Number of cavities in the mold (1-8)."
    )
    
    # ==================== Automation Features ====================
    
    bin_capacity: Optional[int] = Field(
        None, 
        ge=1, 
        description=(
            "Standard quantity of parts per bin. "
            "Used by FG Stock to automatically calculate bin transfers during dispatch. "
            "Example: If 100, dispatching 100 parts moves 1 bin."
        )
    )
    
    # ==================== Dynamic Logic ====================
    
    variations: List[str] = Field(
        default_factory=list, 
        description=(
            "List of generated variants (e.g., ['ALTROZ BRACKET-D RH', 'ALTROZ BRACKET-D LH']). "
            "Populated automatically if 'crate_sides' is true during creation."
        )
    )

    # ==================== Metadata ====================
    
    is_active: bool = Field(
        default=True, 
        description="Determines if the part is currently active/visible in production lists."
    )
    created_at: datetime = Field(default_factory=get_ist_now)
    updated_at: datetime = Field(default_factory=get_ist_now)

    class Settings:
        name = "part_configurations"
        indexes = [
            # Performance Index: Used frequently to filter active parts
            "is_active",
            # Unique Index: Ensures no duplicate part descriptions
            "part_description"
        ]

    class Config:
        json_schema_extra = {
            "example": {
                "part_description": "ALTROZ BRACKET-D",
                "part_number": "10077-7R05S",
                "machine": "120T",
                "rm_mb": ["PP TF 30% Black"],
                "cycle_time": 12.5,
                "part_weight": 45.3,
                "runner_weight": 2.5,
                "cavity": 4,
                "bin_capacity": 100,
                "variations": ["ALTROZ BRACKET-D RH", "ALTROZ BRACKET-D LH"],
                "is_active": True
            }
        }