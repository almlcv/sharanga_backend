# app/core/schemas/fg_stock.py

from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field, field_validator


class FGStockResponse(BaseModel):
    """Response schema for FG Stock - CLEAN (No bins)"""
    
    date: str
    variant_name: str
    part_number: str
    part_description: str
    side: Optional[str]
    
    # Stock quantities
    opening_stock: int
    production_added: int
    inspection_qty: int
    dispatched: int
    closing_stock: int
    
    # Monthly plan reference
    monthly_schedule: Optional[int]
    daily_target: Optional[int]
    variance_vs_target: Optional[int] = None
    
    updated_at: datetime

    class Config:
        from_attributes = True


class ManualStockAdjustmentRequest(BaseModel):
    """Manual stock adjustment (Set Absolute Inspection Quantity)"""
    date: str = Field(..., pattern=r"^\d{4}-\d{2}-\d{2}$")
    variant_name: str
    inspection_qty: int = Field(..., ge=0, description="Set absolute inspection quantity")
    remarks: str = Field(..., min_length=5, description="Reason for adjustment")


class DispatchRequest(BaseModel):
    """Record dispatch - SIMPLIFIED (No bin transfers)"""
    date: str = Field(..., pattern=r"^\d{4}-\d{2}-\d{2}$")
    variant_name: str
    dispatched_qty: int = Field(..., gt=0, description="Quantity to dispatch")
    
    @field_validator('dispatched_qty')
    @classmethod
    def validate_positive(cls, v):
        if v <= 0:
            raise ValueError("Dispatched quantity must be positive")
        return v


class DailyFGStockSummary(BaseModel):
    """Summary for all variants on a date"""
    date: str
    total_variants: int
    stocks: List[FGStockResponse]


class MonthlyFGStockSummary(BaseModel):
    """Monthly summary per variant"""
    year: int
    month: int
    variant_name: str
    part_description: str
    side: Optional[str]
    
    opening_stock_month: int
    total_production: int
    total_dispatched: int
    inspection_qty: int
    closing_stock_month: int
    
    monthly_plan: Optional[int]
    plan_achievement_pct: Optional[float]
    
    average_daily_production: float
    average_daily_dispatch: float