from typing import List, Optional, Annotated
from enum import Enum
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict, BeforeValidator

# =============================================================================
# HELPERS & ENUMS
# =============================================================================

# Helper to handle MongoDB ObjectId
PyObjectId = Annotated[str, BeforeValidator(str)]

class ProjectStatus(str, Enum):
    ACTIVE = "Active"
    ARCHIVED = "Archived"

class TeamMemberRole(str, Enum):
    L1 = "L1"
    L2 = "L2"
    L3 = "L3"
    L4 = "L4"

class PointStatus(str, Enum):
    GREEN = "Green"
    YELLOW = "Yellow"
    ORANGE = "Orange"
    RED = "Red"

class PointPriority(str, Enum):
    LOW = "Low"
    MEDIUM = "Medium"
    HIGH = "High"
    EMERGENCY = "Emergency"
    P1 = "P1"
    P2 = "P2"
    P3 = "P3"
    P4 = "P4"

# =============================================================================
# REQUEST SCHEMAS
# =============================================================================

class TeamMember(BaseModel):
    user: PyObjectId
    role: TeamMemberRole
    department: Optional[str] = None
    added_at: Optional[datetime] = Field(default_factory=datetime.now)

class CreateProjectRequest(BaseModel):
    name: str = Field(..., min_length=1, description="Project name")
    description: Optional[str] = Field(None, description="Project description")
    ownerUsername: str = Field(..., description="Owner username")
    team_members: List[TeamMember] = Field(default_factory=list)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "Factory Safety Improvements Q4",
                "description": "Addressing safety gaps in the assembly line.",
                "ownerUsername": "john_doe", 
                "team_members": [
                    {"user": "507f1f77bcf86cd799439011", "role": "L2", "department": "Quality"}
                ]
            }
        }
    )

class AssignProjectsRequest(BaseModel):
    projectNames: List[str] = Field(..., description="List of project names to assign")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "projectNames": ["Factory Safety Improvements", "Q4 Maintenance"]
            }
        }
    )

class MemberData(BaseModel):
    username: str = Field(..., description="Username of the user to add")
    role: TeamMemberRole = Field(default=TeamMemberRole.L2, description="Role to assign in the project")

class AddMemberRequest(BaseModel):
    members: List[MemberData] = Field(..., min_items=1, description="List of users to add")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "members": [
                    {"username": "jane_smith", "role": "L3"},
                    {"username": "bob_jones", "role": "L2"}
                ]
            }
        }
    )

class RemoveMemberRequest(BaseModel):
    userIds: Optional[List[str]] = Field(None, description="List of User IDs to remove")

class PointEvidence(BaseModel):
    file_url: str
    uploaded_by: PyObjectId
    uploaded_at: datetime = Field(default_factory=datetime.now)

class CreatePointRequest(BaseModel):
    project_id: str
    title: str = Field(..., description="Title of the open point")
    description: Optional[str] = None
    responsibility: Optional[str] = None
    level: Optional[TeamMemberRole] = TeamMemberRole.L2
    gap_action: Optional[str] = None
    review_date: Optional[str] = None
    remarks: Optional[str] = None
    department: str = "General"
    priority: Optional[PointPriority] = PointPriority.LOW
    status: Optional[PointStatus] = PointStatus.RED
    target_date: Optional[datetime] = None
    responsible_person: Optional[str] = None
    reviewer: Optional[str] = None

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "project_id": "507f1f77bcf86cd799439011",
                "title": "Replace worn conveyor belt",
                "description": "Belt showing signs of fraying.",
                "department": "Maintenance",
                "priority": "High",
                "target_date": "2023-12-31T00:00:00Z",
                "status": "Red"
            }
        }
    )

class UpdatePointRequest(BaseModel):
    status: Optional[PointStatus] = Field(None, description="Update status (e.g., 'Green' to mark complete)")
    remarks: Optional[str] = Field(None, description="Remarks for history tracking")
    evidence: Optional[List[PointEvidence]] = Field(None, description="List of evidence file URLs")
    userId: Optional[str] = Field(None, description="User ID performing the action (Read from body)")
    title: Optional[str] = None
    description: Optional[str] = None
    responsibility: Optional[str] = None
    level: Optional[TeamMemberRole] = None
    gap_action: Optional[str] = None
    review_date: Optional[str] = None
    department: Optional[str] = None
    priority: Optional[PointPriority] = None
    target_date: Optional[datetime] = None
    responsible_person: Optional[str] = None
    reviewer: Optional[str] = None

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "status": "Green",
                "remarks": "Work completed successfully.",
                "userId": "507f1f77bcf86cd799439011",
                "evidence": [{"file_url": "http://example.com/photo.jpg", "uploaded_by": "507f1f77bcf86cd799439011"}]
            }
        }
    )