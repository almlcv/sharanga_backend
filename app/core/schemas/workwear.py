from pydantic import BaseModel, Field
from typing import List, Optional

# --- Config Schemas (Admin) ---
class ConfigItemSchema(BaseModel):
    title: str
    description: Optional[str] = None

class CreateWorkwearConfigSchema(BaseModel):
    config_name: str = Field(..., examples=["induction_kit"])
    display_name: str = Field(..., examples=["Induction Safety Kit"])
    items: List[ConfigItemSchema]

class UpdateWorkwearConfigSchema(BaseModel):
    display_name: Optional[str] = None
    items: Optional[List[ConfigItemSchema]] = None

# --- Profile Schemas (Employee/HR) ---
class UpdateWorkwearItemSchema(BaseModel):
    title: str
    completed: bool
    date: Optional[str] = Field(None, description="YYYY-MM-DD format")

# --- Batch Assign Schema ---
class BatchAssignSchema(BaseModel):
    emp_id: str = Field(..., description="Employee ID")
    config_names: List[str] = Field(..., description="List of config names to assign (e.g. ['safety_kit', 'office_kit'])")