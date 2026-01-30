from pydantic import BaseModel, Field
from uuid import UUID
from datetime import datetime
from typing import List, Optional

# IMPORT MODELS for Structure reuse
from app.core.models.training import (
    ConfigModule, 
    ConfigItem,
    ContentType,
    ItemStatus,
    ModuleResultStatus,
    LevelResultStatus
)

# --- INPUT SCHEMAS ---

class LevelCreate(BaseModel):
    """
    Request Schema to create a new Training Level.
    Accepts the full tree structure in one go.
    """
    level_id: str = Field(
        ...,
        min_length=1,
        examples=["level_1", "induction"],
        description="Unique identifier for the level"
    )
    display_name: str = Field(
        ...,
        examples=["Level 1 - Injection Molding", "HR Induction"],
        description="Human readable name for the level"
    )
    description: Optional[str] = Field(
        None,
        examples=["Technical training for the Injection Molding department"],
        description="Short description of the level purpose"
    )
    modules: List[ConfigModule] = Field(
        ...,
        description="List of modules containing videos and tasks"
    )

class AssignLevelRequest(BaseModel):
    """Request to assign a level to an employee."""
    emp_id: str = Field(..., examples=["EMP_001"])
    level_id: str = Field(..., examples=["induction"])

class MarkItemRequest(BaseModel):
    """Request to mark an item as Watched or Completed."""
    item_id: UUID = Field(..., description="The ID of the specific item to update")
    status: ItemStatus = Field(..., description="New status: 'Watched' for videos, 'Completed' for tasks")

class SetLevelResultRequest(BaseModel):
    """Request for HR/Manager to set Pass/Fail status for a level."""
    status: LevelResultStatus = Field(
        ...,
        description="Pass/Fail for the level (e.g. LevelResultStatus.PASSED)"
    )

# --- OUTPUT SCHEMAS ---

class DashboardVideoItem(BaseModel):
    """Response object for a Video in the dashboard."""
    id: UUID = Field(..., examples=["123e4567-e89b-12d3-a456-426614174000"])
    title: str = Field(..., examples=["Safety Basics"])
    link: str = Field(..., examples=["https://youtube.com/watch?v=xyz"])
    status: ItemStatus = Field(..., examples=[ItemStatus.WATCHED])
    watched_at: Optional[str] = Field(None, examples=["2023-10-27T10:00:00"])

class DashboardTaskItem(BaseModel):
    """Response object for an OJT Task in the dashboard."""
    id: UUID = Field(..., examples=["123e4567-e89b-12d3-a456-426614174001"])
    title: str = Field(..., examples=["Material Handling"])
    status: ItemStatus = Field(..., examples=[ItemStatus.COMPLETED])
    completed_at: Optional[str] = Field(None, examples=["2023-10-27T11:00:00"])

class DashboardModule(BaseModel):
    """Response object for a Module."""
    module_id: str = Field(..., examples=["mod_inject_01"])
    module_name: str = Field(..., examples=["Horizontal Injection Molding"])
    videos: List[DashboardVideoItem] = Field(default_factory=list, description="List of Videos and CRTs")
    ojt_tasks: List[DashboardTaskItem] = Field(default_factory=list, description="List of OJT Tasks")
    result_status: ModuleResultStatus = Field(default=ModuleResultStatus.NOT_SET, description="Overall Result of this module")
    retrain_count: int = Field(default=0, description="Number of times this module has been reset for retraining")

class DashboardLevel(BaseModel):
    """Response object for a full Level."""
    level_id: str = Field(..., examples=["level_1"])
    display_name: str = Field(..., examples=["Level 1 Training"])
    modules: List[DashboardModule] = Field(default_factory=list, description="List of modules in this level")
    result_status: LevelResultStatus = Field(
        default=LevelResultStatus.NOT_SET,
        description="Overall result of this level (Passed/Failed/Not Set)"
    )
    retrain_count: int = Field(default=0, description="Number of times this level has been reset for retraining")