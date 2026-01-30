from beanie import Document
from pydantic import Field
from typing import Optional
from pymongo import ASCENDING

class MonthlyProductionPlan(Document):
    """
    MongoDB Document representing a Monthly Production Plan.
    Stores the target schedule for a specific part in a specific month.
    """
    
    # -----------------------------
    # FIELDS
    # -----------------------------
    month: str = Field(..., description="Combined format YYYY-MM (e.g., '2026-01')")
    item_description: str = Field(..., description="Name of the part")
    part_number: Optional[str] = Field(None, description="Item Code linked to PartConfiguration")
    schedule: int = Field(..., description="Total monthly target quantity")
    dispatch_quantity_per_day: Optional[float] = Field(None, description="Average daily dispatch quantity")
    day_stock_to_kept: Optional[int] = Field(None, description="Target days of stock to keep")
    resp_person: Optional[str] = Field(None, description="Person responsible for the plan")

    # -----------------------------
    # SETTINGS (INDEXES)
    # -----------------------------
    class Settings:
        name = "monthly_production_plan"
        
        indexes = [
            [("month", ASCENDING), ("item_description", ASCENDING)],
        ]
    
    class Config:
        json_schema_extra = {
            "example": {
                "month": "2026-01",
                "item_description": "ALTROZ BRACKET-D",
                "part_number": "10077-7R05S",
                "schedule": 5000,
                "dispatch_quantity_per_day": 200.0,
                "day_stock_to_kept": 3,
                "resp_person": "Manager Name"
            }
        }