from pydantic import BaseModel, Field, field_validator
from typing import Optional

class MonthlyPlanRequest(BaseModel):
    """
    Schema matching the exact JSON structure provided.
    """
    year: str = Field(..., description="Year (e.g., '2026')")
    month: str = Field(..., description="Month (e.g., '01' or '1')")
    item_description: str = Field(..., description="Exact part name")
    schedule: float = Field(..., description="Total monthly target quantity")
    dispatch_quantity_per_day: Optional[float] = Field(None, description="Average daily dispatch quantity")
    day_stock_to_kept: Optional[int] = Field(None, description="Target days of stock to keep")
    resp_person: Optional[str] = Field(None, description="Person responsible for the plan")

    @field_validator('year')
    @classmethod
    def validate_year(cls, v):
        if len(v) != 4 or not v.isdigit():
            raise ValueError("Year must be a 4-digit string (e.g., '2026')")
        return v

    @field_validator('month')
    @classmethod
    def validate_month(cls, v):
        try:
            m_int = int(v)
            if m_int < 1 or m_int > 12:
                raise ValueError
        except ValueError:
            raise ValueError("Month must be a number between 1 and 12 (e.g., '01')")
        return v

class MonthlyPlanResponse(BaseModel):
    message: str
    month_str: str # The combined YYYY-MM used in DB
    item_description: str
    part_number: Optional[str] = None # Fetched from PartConfiguration
    upserted_id: Optional[str] = None