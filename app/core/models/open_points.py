from typing import List, Optional, Annotated
from datetime import datetime
from beanie import Document, Indexed
from pydantic import BaseModel, Field, BeforeValidator

PyObjectId = Annotated[str, BeforeValidator(str)]

# Nested Models
class TeamMemberModel(BaseModel):
    user: PyObjectId
    role: str
    department: Optional[str] = None
    added_at: datetime = Field(default_factory=datetime.now)

class HistoryEntry(BaseModel):
    action: str
    changed_by: PyObjectId
    remarks: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.now)

class EvidenceModel(BaseModel):
    file_url: str
    uploaded_by: PyObjectId
    uploaded_at: datetime = Field(default_factory=datetime.now)

# Document: Open Point Project
class OpenPointProject(Document):
    name: str
    description: Optional[str] = None
    owner: PyObjectId
    team_members: List[TeamMemberModel] = []
    status: str = "Active"
    created_at: datetime = Field(default_factory=datetime.now)

    class Settings:
        name = "open_point_projects"

# Document: Open Point
class OpenPoint(Document):
    project_id: PyObjectId
    title: str
    description: Optional[str] = None
    responsibility: Optional[str] = None
    level: str
    gap_action: Optional[str] = None
    review_date: Optional[str] = None
    remarks: Optional[str] = None
    department: str
    priority: str
    status: str
    target_date: Optional[datetime] = None
    responsible_person: Optional[PyObjectId] = None
    reviewer: Optional[PyObjectId] = None
    history: List[HistoryEntry] = []
    evidence: List[EvidenceModel] = []
    completion_date: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.now)

    class Settings:
        name = "open_points"