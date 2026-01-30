from datetime import datetime
from typing import Optional, List, Dict
from pydantic import BaseModel, Field, validator


class BinInventorySchema(BaseModel):
    rabs_bins: int = Field(ge=0)
    ijl_bins: int = Field(ge=0)


class FGStockResponse(BaseModel):
    date: str
    variant_name: str
    part_number: str
    part_description: str
    side: str
    
    opening_stock: int
    production_added: int
    manual_adjustment: int
    dispatched: int
    closing_stock: int
    
    bins_available: BinInventorySchema
    bin_size: Optional[int]
    
    monthly_schedule: Optional[int]
    daily_target: Optional[int]
    variance_vs_target: Optional[int] = None
    
    updated_at: datetime
    
    class Config:
        from_attributes = True


class ManualStockAdjustmentRequest(BaseModel):
    """Manual stock adjustment (add or subtract)"""
    date: str = Field(..., pattern=r"^\d{4}-\d{2}-\d{2}$")
    variant_name: str
    adjustment_qty: int = Field(..., description="Positive to add, negative to subtract")
    remarks: str = Field(..., min_length=5, description="Reason for adjustment")


class ManualBinUpdateRequest(BaseModel):
    """Manual bin inventory update"""
    date: str = Field(..., pattern=r"^\d{4}-\d{2}-\d{2}$")
    variant_name: str
    rabs_bins: Optional[int] = Field(None, ge=0)
    ijl_bins: Optional[int] = Field(None, ge=0)
    remarks: str


class DispatchRequest(BaseModel):
    """Record dispatch"""
    date: str = Field(..., pattern=r"^\d{4}-\d{2}-\d{2}$")
    variant_name: str
    dispatched_qty: int = Field(..., gt=0)
    auto_transfer_bins: bool = Field(
        default=True, 
        description="Automatically move bins from RABS to IJL"
    )
    
    @validator('dispatched_qty')
    def validate_positive(cls, v):
        if v <= 0:
            raise ValueError("Dispatched quantity must be positive")
        return v


class BinTransferRequest(BaseModel):
    """Transfer bins between RABS and IJL"""
    date: str = Field(..., pattern=r"^\d{4}-\d{2}-\d{2}$")
    variant_name: str
    bins_to_transfer: int = Field(..., gt=0, description="Number of bins to move from RABS to IJL")


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
    side: str
    
    opening_stock_month: int
    total_production: int
    total_dispatched: int
    total_adjustments: int
    closing_stock_month: int
    
    monthly_plan: Optional[int]
    plan_achievement_pct: Optional[float]
    
    average_daily_production: float
    average_daily_dispatch: float