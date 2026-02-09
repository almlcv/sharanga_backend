from pydantic import BaseModel, Field, field_validator
from typing import Optional, Dict, List

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


# ----------------------------- Daily Production Plan -----------------------------

class DailyPlanVariantResponse(BaseModel):
    """One variant's daily plan for a month (Excel row equivalent)."""
    variant_name: str
    part_description: str
    monthly_schedule: Optional[int] = None
    daily_targets: Dict[str, int] = Field(default_factory=dict)  # "YYYY-MM-DD" -> qty
    total_planned: int = 0  # sum of daily_targets

class DailyPlanMonthResponse(BaseModel):
    """Full daily plan for a month (all variants, like Excel sheet)."""
    month: str  # YYYY-MM
    variants: List[DailyPlanVariantResponse]


class SetDailyPlanRequest(BaseModel):
    """Set or update daily targets for one variant in a month."""
    year: str = Field(..., description="Year e.g. '2026'")
    month: str = Field(..., description="Month e.g. '01' or '1'")
    variant_name: str = Field(..., description="e.g. 'ALTROZ INNER LENS LH'")
    daily_targets: Dict[str, int] = Field(..., description="Map of date YYYY-MM-DD to planned qty")

    @field_validator('year')
    @classmethod
    def validate_year(cls, v):
        if len(v) != 4 or not v.isdigit():
            raise ValueError("Year must be 4-digit string")
        return v

    @field_validator('month')
    @classmethod
    def validate_month(cls, v):
        try:
            if 1 <= int(v) <= 12:
                return v
        except ValueError:
            pass
        raise ValueError("Month must be 1-12")


class GenerateDailyPlanRequest(BaseModel):
    """Generate daily plan from monthly plans (spread schedule over working days)."""
    year: str = Field(..., description="Year e.g. '2026'")
    month: str = Field(..., description="Month e.g. '01' or '1'")

    @field_validator('year')
    @classmethod
    def validate_year(cls, v):
        if len(v) != 4 or not v.isdigit():
            raise ValueError("Year must be 4-digit string")
        return v

    @field_validator('month')
    @classmethod
    def validate_month(cls, v):
        try:
            if 1 <= int(v) <= 12:
                return v
        except ValueError:
            pass
        raise ValueError("Month must be 1-12")