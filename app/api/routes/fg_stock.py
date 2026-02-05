from fastapi import APIRouter, Depends, Query, Path, status, HTTPException
from typing import List, Optional

from app.core.auth.deps import get_current_user, require_roles
from app.core.schemas.fg_stock import (
    FGStockResponse,
    ManualStockAdjustmentRequest,
    ManualBinUpdateRequest,
    DispatchRequest,
    BinTransferRequest,
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
    date: str = Query(..., pattern=r"^\d{4}-\d{2}-\d{2}$", description="Date (YYYY-MM-DD)"),
    part_description: Optional[str] = Query(None, description="Filter by part"),
    current_user: dict = Depends(get_current_user)
):
    """
    Retrieve FG stock for all variants on a specific date.
    Automatically creates records with rollover if missing.
    """
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
    """
    Retrieve monthly aggregated FG stock summary.
    Compares production vs monthly plan.
    """
    summaries = await FGStockService.get_monthly_summary(year, month, part_description)
    return [MonthlyFGStockSummary(**s) for s in summaries]


# ==================== DISPATCH OPERATIONS ====================

@router.post(
    "/dispatch",
    response_model=FGStockResponse,
    status_code=status.HTTP_200_OK,
    summary="Record Dispatch"
)
async def record_dispatch(
    payload: DispatchRequest,
    current_user: dict = Depends(require_roles("Production", "Dispatch", "Admin"))
):
    """
    Record dispatch and optionally transfer bins from RABS to IJL.
    
    **Features:**
    - Validates sufficient stock before dispatch
    - Auto-transfers bins if `auto_transfer_bins=true`
    - Records transaction in audit trail
    """
    stock = await FGStockService.record_dispatch(payload, current_user)
    return FGStockResponse(**stock.model_dump())


# ==================== MANUAL OPERATIONS ====================

@router.post(
    "/adjust-stock",
    response_model=FGStockResponse,
    summary="Manual Stock Adjustment"
)
async def manual_stock_adjustment(
    payload: ManualStockAdjustmentRequest,
    current_user: dict = Depends(require_roles("Admin", "Production"))
):
    """
    Manually add or subtract stock (e.g., for damaged goods, found stock).
    
    **Use Cases:**
    - Damaged goods: Use negative adjustment
    - Found stock: Use positive adjustment
    - Reconciliation after physical count
    
    **Requires:** Admin or Production role
    """
    stock = await FGStockService.manual_stock_adjustment(payload, current_user)
    return FGStockResponse(**stock.model_dump())


@router.post(
    "/adjust-bins",
    response_model=FGStockResponse,
    summary="Manual Bin Inventory Update"
)
async def manual_bin_update(
    payload: ManualBinUpdateRequest,
    current_user: dict = Depends(require_roles("Admin", "Production"))
):
    """
    Manually update bin counts in RABS or IJL.
    
    **Use Cases:**
    - Physical bin count reconciliation
    - Correcting bin inventory errors
    - Setting initial bin counts
    """
    stock = await FGStockService.manual_bin_update(payload, current_user)
    return FGStockResponse(**stock.model_dump())


@router.post(
    "/transfer-bins",
    response_model=FGStockResponse,
    summary="Transfer Bins from RABS to IJL"
)
async def transfer_bins(
    payload: BinTransferRequest,
    current_user: dict = Depends(require_roles("Production", "Dispatch", "Admin"))
):
    """
    Manually transfer bins from RABS warehouse to IJL dispatch area.
    
    **Validation:** Ensures sufficient RABS bins before transfer.
    """
    stock = await FGStockService.transfer_bins(payload, current_user)
    return FGStockResponse(**stock.model_dump())


# ==================== UTILITY ====================

@router.post(
    "/sync-from-hourly/{doc_id}",
    response_model=dict,
    summary="Manual Sync from Hourly Production (by _id)"
)
async def sync_from_hourly_production(
    doc_id: str = Path(..., description="Hourly production document _id (MongoDB ObjectId string)"),
    current_user: dict = Depends(require_roles("Admin"))
):
    """
    Manually trigger FG stock sync from a specific hourly production document.
    Useful for fixing missed auto-sync.
    
    **Admin only.**
    """
    from app.core.models.production.hourly_production import HourlyProductionDocument
    
    # Try to fetch by ObjectId `_id` first
    try:
        doc = await HourlyProductionDocument.get(doc_id)
    except Exception:
        doc = None

    if not doc:
        raise HTTPException(404, f"Hourly production document with _id '{doc_id}' not found")
    
    await FGStockService.update_from_hourly_production(doc, current_user.emp_id)
    
    part_display = f"{doc.part_description} {doc.side}" if doc.side else doc.part_description

    return {
        "message": f"Successfully synced FG stock from document {doc_id}",
        "date": doc.date,
        "part": part_display,
        "production_qty": doc.totals.total_ok_qty
    }