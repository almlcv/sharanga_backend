from typing import List, Optional, Annotated, Dict
from uuid import UUID, uuid4
from beanie import Document, Indexed
from pydantic import BaseModel, Field
from datetime import datetime
from enum import Enum

# =========================================================================
# ENUMS (Restricted Values)
# =========================================================================

class ContentType(str, Enum):
    """Defines the type of content"""
    CRT = "CRT"          
    OJT = "OJT"         
    GENERAL = "GENERAL"

class ItemStatus(str, Enum):
    """Defines the completion status of an item."""
    NOT_STARTED = "Not Started"
    WATCHED = "In Progress"
    COMPLETED = "Watched"

# New enum for Level result
class LevelResultStatus(str, Enum):
    """Defines the overall result of a level."""
    NOT_SET = "Not Set"
    PASSED = "Passed"
    FAILED = "Failed"

# Optional: keep module-level status only if you still need it
class ModuleResultStatus(str, Enum):
    """Defines the overall result of a module."""
    NOT_SET = "Not Set"
    PASSED = "Passed"
    FAILED = "Failed"

# =========================================================================
# A. SYSTEM CONFIGURATION (Master Copy)
# =========================================================================

class ConfigItem(BaseModel):
    """Unified Item Class for Master Config."""
    id: UUID = Field(default_factory=uuid4, description="Unique ID for tracking progress")
    type: ContentType = Field(..., description="Type of content: CRT, OJT, VIDEO, or GENERAL")
    title: str = Field(..., min_length=1, description="Title of the video or task")
    link: Optional[str] = Field(None, description="URL for videos (OJT tasks usually do not have links)")

class ConfigModule(BaseModel):
    """Module Container (Bucket)."""
    module_id: str = Field(..., description="Unique ID for this module")
    module_name: str = Field(..., description="Display name of the module")
    items: List[ConfigItem] = Field(default_factory=list, description="List of videos and tasks")

class SystemTrainingLevel(Document):
    """
    The Master Document for a Level. 
    Contains the entire tree structure (Modules -> Items).
    """
    level_id: Annotated[str, Indexed(unique=True)] = Field(..., description="Unique Level Key (e.g., 'induction')")
    display_name: str = Field(..., description="Display name (e.g., 'HR Induction')")
    description: Optional[str] = None
    modules: List[ConfigModule] = Field(default_factory=list)

    class Settings:
        name = "system_training_levels"

# =========================================================================
# B. EMPLOYEE PROGRESS (State Data)
# =========================================================================

class ItemProgress(BaseModel):
    """Tracks state for a specific item."""
    item_id: UUID
    type: ContentType
    status: ItemStatus = Field(default=ItemStatus.NOT_STARTED)
    completed_at: Optional[datetime] = None

class ModuleProgress(BaseModel):
    """Tracks state for a Module."""
    module_id: str
    items: List[ItemProgress] = Field(default_factory=list)
    result_status: Optional[bool] = Field(None, description="True=Passed, False=Failed, None=Not Set")
    retrain_count: int = 0

# NEW: per-level progress
class LevelProgress(BaseModel):
    """Tracks state for a Level (items grouped by modules, plus overall result)."""
    level_id: str
    modules: List[ModuleProgress] = Field(default_factory=list)
    result_status: LevelResultStatus = Field(default=LevelResultStatus.NOT_SET)
    retrain_count: int = 0

class TrainingProfile(Document):
    """
    Employee Profile: Tracks Assignments and Progress.
    """
    emp_id: Annotated[str, Indexed(unique=True)]
    assigned_levels: List[str] = Field(default_factory=list, description="List of Level IDs assigned to this employee")
    level_progress: Dict[str, LevelProgress] = Field(
        default_factory=dict,
        description="Map of Level ID -> LevelProgress (with modules and level result)"
    )

    class Settings:
        name = "training_profiles"