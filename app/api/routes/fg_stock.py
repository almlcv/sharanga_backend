from fastapi import APIRouter, Depends, Query, Path, status, HTTPException
from typing import List, Optional

from app.core.auth.deps import get_current_user, require_roles
from app.core.schemas.fg_stock import (
    FGStockResponse,
    ManualStockAdjustmentRequest,
    DispatchRequest,
    DailyFGStockSummary,
    MonthlyFGStockSummary,
)
from app.modules.fg_stock.fg_stock_service import FGStockService


router = APIRouter(tags=["FG Stock"], prefix="/fgstock")


# ==================== READ OPERATIONS ====================

@router.get(
    "/daily",
    response_model=DailyFGStockSummary,
    summary="Get Daily FG Stock for All Parts"
)
async def get_daily_fgstock(
    date: str = Query(..., pattern=r"^\d{4}-\d{2}-\d{2}$"),
    part_description: Optional[str] = Query(None),
    current_user: dict = Depends(get_current_user)
):
    """Get daily FG stock"""
    stocks = await FGStockService.get_daily_stocks(date, part_description)
    
    return DailyFGStockSummary(
        date=date,
        total_variants=len(stocks),
        stocks=[
            FGStockResponse(
                **s.model_dump(),
                variance_vs_target=(s.production_added - s.daily_target) if s.daily_target else None
            )
            for s in stocks
        ]
    )


@router.get(
    "/monthly",
    response_model=List[MonthlyFGStockSummary],
    summary="Get Monthly FG Stock Summary"
)
async def get_monthly_fgstock(
    year: int = Query(..., ge=2000, le=2100),
    month: int = Query(..., ge=1, le=12),
    part_description: Optional[str] = Query(None),
    current_user: dict = Depends(get_current_user)
):
    """Get monthly summary"""
    summaries = await FGStockService.get_monthly_summary(year, month, part_description)
    return [MonthlyFGStockSummary(**s) for s in summaries]


# ==================== DISPATCH OPERATIONS ====================

@router.post(
    "/dispatch",
    response_model=FGStockResponse,
    status_code=status.HTTP_200_OK,
    summary="Record Dispatch",
    description="""
    Records a dispatch transaction and reduces available stock.
    """
)
async def record_dispatch(
    payload: DispatchRequest,
    current_user: dict = Depends(require_roles("Production", "Dispatch", "Admin"))
):
    """Record dispatch - CLEAN (No bins)"""
    stock = await FGStockService.record_dispatch(payload, current_user)
    return FGStockResponse(**stock.model_dump())


# ==================== MANUAL OPERATIONS ====================

@router.post(
    "/adjust-stock",
    response_model=FGStockResponse,
    summary="200% Inspection Quantity Rej",
    description="""
    Subtracts the inspection_qty (Damaged/Found Stock).
    
    """
)
async def manual_stock_adjustment(
    payload: ManualStockAdjustmentRequest,
    current_user: dict = Depends(require_roles("Admin", "Production"))
):
    """ 200% Inspection Quantity Rej - CLEAN (No bins)"""
    stock = await FGStockService.manual_stock_adjustment(payload, current_user)
    return FGStockResponse(**stock.model_dump())