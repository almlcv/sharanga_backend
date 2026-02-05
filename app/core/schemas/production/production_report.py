from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import date


class PartProductionSummary(BaseModel):
    """Production summary for a single part (combines LH and RH)"""
    part_description: str
    
    # Monthly Plan
    schedule: Optional[int] = Field(None, description="Monthly target from plan")
    
    # Hourly Production Totals
    plan_qty: int = Field(0, description="Total planned quantity")
    actual_qty: int = Field(0, description="Total actual production")
    ok_qty: int = Field(0, description="Total OK/accepted quantity") 
    rejected_qty: int = Field(0, description="Total rejected quantity")
    
    # FG Stock Current State
    current_stock: int = Field(0, description="Closing stock (LH + RH)")
    dispatched: int = Field(0, description="Total dispatched")
    balance: int = Field(0, description="Current - Dispatched")
    
    # Targets & Projections
    daily_target: Optional[int] = Field(None, description="Target per working day")
    projected_days: Optional[float] = Field(None, description="Days of inventory remaining")
    
    # Last Month Reference
    last_month_production: Optional[int] = Field(None, description="Previous month total production")
    
    # Breakdown by Side
    lh_ok_qty: int = 0
    lh_rejected_qty: int = 0
    rh_ok_qty: int = 0
    rh_rejected_qty: int = 0


class DailyProductionReport(BaseModel):
    """Daily production report for all parts"""
    date: str = Field(..., description="Report date (YYYY-MM-DD)")
    parts: List[PartProductionSummary]
    
    # Overall Summary
    total_parts: int
    total_production: int
    total_rejected: int
    total_dispatch: int


class MonthlyProductionSummary(BaseModel):
    """Monthly production summary for a single part"""
    part_description: str
    month: str = Field(..., description="YYYY-MM")
    
    # Plan vs Actual
    monthly_schedule: Optional[int] = None
    total_production: int = 0
    plan_achievement_pct: Optional[float] = None
    
    # Quality
    total_ok_qty: int = 0
    total_rejected_qty: int = 0
    rejection_rate_pct: float = 0.0
    
    # Stock Movement
    opening_stock: int = 0
    closing_stock: int = 0
    total_dispatched: int = 0
    
    # Averages
    avg_daily_production: float = 0.0
    avg_daily_dispatch: float = 0.0
    
    # Working Days
    working_days_in_month: int = 0
    days_produced: int = 0  # Days with actual production


class MonthlyProductionReport(BaseModel):
    """Monthly production report for all parts"""
    year: int
    month: int
    parts: List[MonthlyProductionSummary]
    
    # Overall Summary
    total_parts: int
    total_production: int
    total_rejected: int
    overall_rejection_rate_pct: float