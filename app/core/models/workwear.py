from typing import List, Optional, Annotated
from datetime import datetime
from beanie import Document, Indexed
from pydantic import BaseModel, Field

# =========================================================================
# MASTER CONFIGURATION MODELS (Templates)
# =========================================================================

class ConfigItem(BaseModel):
    """Definition of a workwear item in a Template."""
    title: str = Field(..., description="Name of the item")
    description: Optional[str] = Field(None, description="Optional details")

class WorkwearConfig(Document):
    """Master Template."""
    config_name: Annotated[str, Indexed(unique=True)] = Field(...)
    display_name: str = Field(...)
    items: List[ConfigItem] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.now)

    class Settings:
        name = "workwear_configs"

# =========================================================================
# EMPLOYEE PROGRESS MODELS
# =========================================================================

class ProfileItem(BaseModel):
    """An item assigned to a specific employee."""
    title: str
    completed: bool = False
    date: Optional[str] = None

# NEW: Container for a single assigned kit
class WorkwearAssignment(BaseModel):
    """
    Represents one specific kit (e.g., 'Safety Kit') assigned to an employee.
    """
    config_name: str
    display_name: str
    items: List[ProfileItem] = Field(default_factory=list)
    assigned_at: datetime = Field(default_factory=datetime.now)
    completed: bool = Field(default=False) # Is this specific kit fully done?

class WorkwearProfile(Document):
    """
    Tracks ALL workwear assignments for a specific employee.
    """
    emp_id: Annotated[str, Indexed(unique=True)]
    
    # NEW: This is now a list, so a user can have 'safety_kit' + 'office_kit'
    assignments: List[WorkwearAssignment] = Field(default_factory=list)
    
    overall_completed: bool = Field(default=False, description="True if ALL assigned kits are complete")

    class Settings:
        name = "workwear_profiles"