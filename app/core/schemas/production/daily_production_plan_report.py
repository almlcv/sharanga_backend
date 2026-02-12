"""
Schema for Daily Production Plan Report - matches Excel "RABS INDUSTRIS GUJARAT - DAILYPRODUCTION PLAN" table
"""
from pydantic import BaseModel, Field
from typing import List, Optional, Dict


class DailyProductionPlanRow(BaseModel):
    """Single row in the daily production plan report - matches Excel row structure"""
    
    # Excel Column B: CUSTOMER
    customer: Optional[str] = Field(None, description="Customer name (e.g., IJL, SUNVACCUM)")
    
    # Excel Column C: MC N0
    machine_number: Optional[str] = Field(None, description="Machine number (e.g., 470, 250, 120T)")
    
    # Excel Column D: BIN QTY
    bin_capacity: Optional[int] = Field(None, description="Bin capacity/quantity")
    
    # Excel Column E: PART NAME
    part_name: str = Field(..., description="Full part name with side (e.g., ALTROZ INNER LENS - (LH))")
    
    # Excel Column F: MONTH PLAN
    month_plan: Optional[int] = Field(None, description="Monthly target quantity")
    
    # Excel Column G: OPN STOCK (Opening Stock)
    opening_stock: int = Field(0, description="Opening stock at start of month")
    
    # Excel Column H: BALANCE TO PRODUCE
    balance_to_produce: int = Field(0, description="Remaining quantity to produce (Month Plan - Opening Stock)")
    
    # Excel Column I: PROD PLAN
    prod_plan: int = Field(0, description="Total production plan for the month (sum of daily targets)")
    
    # Excel Columns J+: Daily production quantities (1-31)
    daily_quantities: Dict[int, int] = Field(
        default_factory=dict,
        description="Daily production quantities. Key=day number (1-31), Value=quantity"
    )
    
    # Additional metadata (not in Excel but useful)
    part_description: str = Field(..., description="Base part description without side")
    side: Optional[str] = Field(None, description="LH or RH")
    part_number: Optional[str] = Field(None, description="Part number/code")


class DailyProductionPlanReport(BaseModel):
    """
    Complete Daily Production Plan Report for a month
    Matches Excel "RABS INDUSTRIS GUJARAT - DAILYPRODUCTION PLAN" table structure
    """
    
    # Report metadata
    month: str = Field(..., description="Month in YYYY-MM format (e.g., 2026-02)")
    month_name: str = Field(..., description="Month name for display (e.g., FEBRUARY 2026)")
    
    # Report data
    rows: List[DailyProductionPlanRow] = Field(
        default_factory=list,
        description="List of production plan rows, one per part variant"
    )
    
    # Summary
    total_parts: int = Field(0, description="Total number of part variants")
    total_month_plan: int = Field(0, description="Sum of all monthly plans")
    total_prod_plan: int = Field(0, description="Sum of all production plans")
    
    # Days in month
    days_in_month: int = Field(..., description="Number of days in the month (28-31)")
