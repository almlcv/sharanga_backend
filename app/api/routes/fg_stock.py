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
    summary="Get Daily FG Stock for All Parts",
    description="""
    Retrieves FG stock for all active part variants on a specific date.
    
    **Automation Features:**
    - **Auto-Generation:** Automatically creates a new stock record for the date if one does not exist.
    - **Smart Rollover:** If the previous day's data is missing (e.g., weekend, holiday), 
      the system automatically finds the latest historical closing stock and uses it as the opening stock.
    - **Target Variance:** Automatically calculates the difference between actual production and daily target if a plan is set.
    """
)
async def get_daily_fgstock(
    date: str = Query(..., pattern=r"^\d{4}-\d{2}-\d{2}$", description="Production date in YYYY-MM-DD format"),
    part_description: Optional[str] = Query(None, description="Filter results by specific Part Description"),
    current_user: dict = Depends(get_current_user)
):
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
    summary="Get Monthly FG Stock Summary",
    description="""
    Aggregates FG stock data for all active parts within a specific month.
    
    **Calculated Metrics:**
    - **Total Production:** Sum of `production_added` across all days.
    - **Total Dispatch:** Sum of `dispatched` across all days.
    - **Plan Achievement:** Percentage of total production vs monthly schedule.
    - **Average Averages:** Calculates average daily production and dispatch rates.
    """
)
async def get_monthly_fgstock(
    year: int = Query(..., ge=2000, le=2100, description="Year (e.g., 2025)"),
    month: int = Query(..., ge=1, le=12, description="Month (1-12)"),
    part_description: Optional[str] = Query(None, description="Filter by specific Part Description"),
    current_user: dict = Depends(get_current_user)
):
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
    
    **Production-Grade Features:**
    - **Atomic Updates:** Uses database-level locking to prevent race conditions. 
      Ensures stock never goes negative, even if multiple users dispatch simultaneously.
    - **Bin Automation:** If `auto_transfer_bins` is true, automatically calculates 
      and moves bins from RABS (Warehouse) to IJL (Dispatch Area) based on the `bin_capacity` from Part Configuration.
    - **Audit Trail:** Records the dispatch user and quantity change in the transaction history.
    
    **Role Required:** Production, Dispatch, or Admin.
    """
)
async def record_dispatch(
    payload: DispatchRequest,
    current_user: dict = Depends(require_roles("Production", "Dispatch", "Admin"))
):
    stock = await FGStockService.record_dispatch(payload, current_user)
    return FGStockResponse(**stock.model_dump())


# ==================== MANUAL OPERATIONS ====================

@router.post(
    "/adjust-stock",
    response_model=FGStockResponse,
    summary="Manual Stock Adjustment",
    description="""
    Manually adjusts the `inspection_qty` (Damaged/Found Stock).
    
    **Logic:** Sets the absolute value for `inspection_qty`. 
    This will reduce the `closing_stock` (if > 0) or increase it (if < current value).
    - **Validation:** `inspection_qty` cannot be negative and cannot exceed `production_added`.
    - **Safety:** Checks to ensure `closing_stock` does not go negative after adjustment.
    
    **Use Cases:** 
    - Writing off damaged goods found in warehouse.
    - Adding found stock to the system.
    - Reconciling after a physical count.
    
    **Role Required:** Admin or Production.
    """
)
async def manual_stock_adjustment(
    payload: ManualStockAdjustmentRequest,
    current_user: dict = Depends(require_roles("Admin", "Production"))
):
    stock = await FGStockService.manual_stock_adjustment(payload, current_user)
    return FGStockResponse(**stock.model_dump())


@router.post(
    "/adjust-bins",
    response_model=FGStockResponse,
    summary="Manual Bin Inventory Update",
    description="""
    Manually sets the exact bin count for RABS or IJL.
    
    **Logic:** Overwrites the current system bin count with the provided values.
    - **Use Case:** Correcting digital count to match physical count (Reconciliation).
    - **Use Case:** Setting initial bin counts on Day 1.
    
    **Note:** This does not affect the quantity of parts (`closing_stock`), only the bin counts.
    
    **Role Required:** Admin or Production.
    """
)
async def manual_bin_update(
    payload: ManualBinUpdateRequest,
    current_user: dict = Depends(require_roles("Admin", "Production"))
):
    stock = await FGStockService.manual_bin_update(payload, current_user)
    return FGStockResponse(**stock.model_dump())


@router.post(
    "/transfer-bins",
    response_model=FGStockResponse,
    summary="Transfer Bins from RABS to IJL",
    description="""
    Manually moves a specific number of bins from RABS (Warehouse) to IJL (Dispatch Area).
    
    **Validation:** System checks to ensure sufficient bins exist in RABS before processing the transfer.
    
    **Role Required:** Production, Dispatch, or Admin.
    """
)
async def transfer_bins(
    payload: BinTransferRequest,
    current_user: dict = Depends(require_roles("Production", "Dispatch", "Admin"))
):
    stock = await FGStockService.transfer_bins(payload, current_user)
    return FGStockResponse(**stock.model_dump())


# ==================== UTILITY / ADMIN ====================

@router.post(
    "/sync-from-hourly/{doc_id}",
    response_model=dict,
    summary="Manual Sync from Hourly Production",
    description="""
    Manually triggers a sync of FG Stock from a specific Hourly Production document.
    
    **Context:** 
    Normally, the system automatically syncs stock when a shift is finalized. 
    Use this endpoint only if the automation failed or you need to fix a historical record.
    
    **Logic:**
    1. Finds the Hourly Production Document by ID.
    2. Sums up `total_ok_qty` for that date/part.
    3. Updates FG Stock `production_added` and recalculates `closing_stock`.
    
    **Role Required:** Admin Only.
    """
)
async def sync_from_hourly_production(
    doc_id: str = Path(..., description="MongoDB ObjectId of the Hourly Production document"),
    current_user: dict = Depends(require_roles("Admin"))
):
    from app.core.models.production.hourly_production import HourlyProductionDocument
    
    # Fetch document
    doc = await HourlyProductionDocument.get(doc_id)

    if not doc:
        raise HTTPException(status_code=404, detail=f"Hourly production document with ID '{doc_id}' not found")
    
    # Execute Sync
    await FGStockService.update_from_hourly_production(doc, current_user.emp_id)
    
    part_display = f"{doc.part_description} {doc.side}" if doc.side else doc.part_description

    return {
        "message": f"Successfully synced FG stock from document {doc_id}",
        "date": doc.date,
        "part": part_display,
        "production_qty": doc.totals.total_ok_qty
    }