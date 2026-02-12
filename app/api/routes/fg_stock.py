from fastapi import APIRouter, Depends, Query, Path, status, HTTPException
from typing import List, Optional, Union, Literal
from pydantic import BaseModel, Field

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


# ==================== UNIFIED REQUEST/RESPONSE SCHEMAS ====================

class UnifiedStockTransactionRequest(BaseModel):
    """Unified request for both dispatch and inspection adjustments"""
    
    transaction_type: Literal["dispatch", "inspection"] = Field(
        ..., 
        description="Type of transaction: 'dispatch' for outgoing stock, 'inspection' for quality rejections"
    )
    
    date: str = Field(..., pattern=r"^\d{4}-\d{2}-\d{2}$", description="Transaction date (YYYY-MM-DD)")
    variant_name: str = Field(..., description="Part variant name")
    
    # Quantity field - used differently based on transaction_type
    quantity: int = Field(..., gt=0, description="Quantity for dispatch OR absolute inspection quantity")
    
    remarks: str = Field(..., min_length=5, description="Reason/notes for the transaction")
    
    class Config:
        json_schema_extra = {
            "examples": [
                {
                    "transaction_type": "dispatch",
                    "date": "2026-02-11",
                    "variant_name": "ALTROZ BRACKET-D LH",
                    "quantity": 500,
                    "remarks": "Dispatch to Customer XYZ via Truck ABC-1234"
                },
                {
                    "transaction_type": "inspection",
                    "date": "2026-02-11",
                    "variant_name": "ALTROZ BRACKET-D LH",
                    "quantity": 50,
                    "remarks": "200% inspection rejection - surface defects found"
                }
            ]
        }


class BatchStockTransactionRequest(BaseModel):
    """Batch request for multiple transactions at once"""
    
    transactions: List[UnifiedStockTransactionRequest] = Field(
        ...,
        min_items=1,
        description="List of transactions to process"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "transactions": [
                    {
                        "transaction_type": "dispatch",
                        "date": "2026-02-11",
                        "variant_name": "ALTROZ BRACKET-D LH",
                        "quantity": 500,
                        "remarks": "Dispatch to Customer XYZ"
                    },
                    {
                        "transaction_type": "inspection",
                        "date": "2026-02-11",
                        "variant_name": "ALTROZ BRACKET-D LH",
                        "quantity": 50,
                        "remarks": "200% inspection rejection"
                    }
                ]
            }
        }


class BatchTransactionResponse(BaseModel):
    """Response for batch transactions"""
    
    total_transactions: int
    successful: int
    failed: int
    results: List[dict] = Field(description="Results for each transaction")
    
    class Config:
        json_schema_extra = {
            "example": {
                "total_transactions": 2,
                "successful": 2,
                "failed": 0,
                "results": [
                    {
                        "status": "success",
                        "transaction_type": "dispatch",
                        "variant_name": "ALTROZ BRACKET-D LH",
                        "message": "Dispatched 500 units successfully"
                    },
                    {
                        "status": "success",
                        "transaction_type": "inspection",
                        "variant_name": "ALTROZ BRACKET-D LH",
                        "message": "Inspection adjustment recorded successfully"
                    }
                ]
            }
        }


# ==================== UNIFIED GET ENDPOINT ====================

@router.get(
    "",
    response_model=Union[DailyFGStockSummary, List[MonthlyFGStockSummary]],
    summary="Get FG Stock (Daily or Monthly)",
    description="""
    **Unified endpoint to retrieve FG stock data - automatically determines daily or monthly view.**
    
    ## Query Parameters:
    
    - `year` (required): Year (e.g., 2026)
    - `month` (required): Month (1-12)
    - `date` (optional): Day of month (1-31)
    - `part_description` (optional): Filter by specific part
    
    ## Automatic View Selection:
    
    The endpoint automatically determines which view to return based on parameters provided:
    
    ### Daily View (when `date` is provided):
    - **Parameters:** `year`, `month`, `date`
    - **Example:** `?year=2026&month=2&date=11` → Returns stock for 2026-02-11
    - **Returns:** Daily stock details for all parts on that specific date
    
    ### Monthly View (when only `year` and `month` provided):
    - **Parameters:** `year`, `month` (without `date`)
    - **Example:** `?year=2026&month=2` → Returns monthly summary for Feb 2026
    - **Returns:** Aggregated monthly summary for all parts
    
    ## Returns:
    
    ### Daily View:
    - Date of the stock report
    - Total number of part variants
    - Stock details for each part including:
      - Part information (description, number, side)
      - Opening stock, Production added, Dispatched, Closing stock
      - Daily target and variance vs target
    
    ### Monthly View:
    - Monthly summary for each part including:
      - Total production and dispatch for the month
      - Average daily stock levels
      - Month-end closing stock
      - Performance metrics and plan achievement
    
    ## Use Cases:
    
    **Daily View:**
    - Monitor daily production vs targets
    - Plan dispatch schedules
    - Identify stock shortages or excess
    - Track daily performance
    
    **Monthly View:**
    - Analyze production trends
    - Evaluate dispatch efficiency
    - Plan next month's targets
    - Generate monthly reports
    
    ## Examples:
    
    **Get daily stock for a specific date:**
    ```
    GET /fgstock?year=2026&month=2&date=11
    ```
    
    **Get daily stock for a specific part:**
    ```
    GET /fgstock?year=2026&month=2&date=11&part_description=ALTROZ BRACKET-D
    ```
    
    **Get monthly stock summary:**
    ```
    GET /fgstock?year=2026&month=2
    ```
    
    **Get monthly stock for a specific part:**
    ```
    GET /fgstock?year=2026&month=2&part_description=ALTROZ BRACKET-D
    ```
    """,
    responses={
        200: {"description": "Stock data retrieved successfully"},
        400: {"description": "Invalid parameters or missing required fields"},
        401: {"description": "Not authenticated"}
    }
)
async def get_fgstock(
    year: Optional[int] = Query(None, ge=2000, le=2100, description="Year (e.g., 2026)"),
    month: Optional[int] = Query(None, ge=1, le=12, description="Month (1-12)"),
    date: Optional[int] = Query(None, ge=1, le=31, description="Day of month (1-31) - if provided, returns daily view"),
    part_description: Optional[str] = Query(None, description="Filter by part description"),
    current_user: dict = Depends(get_current_user)
):
    """
    Unified GET endpoint for FG stock.
    
    Automatically determines whether to return daily or monthly data:
    - If `date` is provided (with year and month): Returns daily stock
    - If only `year` and `month` are provided: Returns monthly summary
    """
    
    # Validate that we have at least year and month
    if not year or not month:
        raise HTTPException(
            status_code=400,
            detail="Must provide at least 'year' and 'month' parameters."
        )
    
    # DAILY VIEW - when date is provided
    if date:
        # Construct date string in YYYY-MM-DD format
        try:
            date_str = f"{year}-{str(month).zfill(2)}-{str(date).zfill(2)}"
            # Validate the date is valid
            from datetime import datetime
            datetime.strptime(date_str, "%Y-%m-%d")
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid date: {year}-{month}-{date}. Please check the day is valid for the given month."
            )
        
        stocks = await FGStockService.get_daily_stocks(date_str, part_description)
        
        return DailyFGStockSummary(
            date=date_str,
            total_variants=len(stocks),
            stocks=[
                FGStockResponse(
                    **s.model_dump(),
                    variance_vs_target=(s.production_added - s.daily_target) if s.daily_target else None
                )
                for s in stocks
            ]
        )
    
    # MONTHLY VIEW - when only year and month are provided
    else:
        summaries = await FGStockService.get_monthly_summary(year, month, part_description)
        return [MonthlyFGStockSummary(**s) for s in summaries]


# ==================== UNIFIED POST ENDPOINT ====================

@router.post(
    "",
    response_model=FGStockResponse,
    status_code=status.HTTP_200_OK,
    summary="Record Stock Transaction (Dispatch or Inspection)",
    description="""
    **Unified endpoint to record stock transactions - supports both dispatch and inspection adjustments.**
    
    ## Transaction Types:
    
    ### 1. Dispatch (`transaction_type: "dispatch"`)
    Record outgoing shipments and reduce available stock.
    
    **Authorization:** Requires Production, Dispatch, or Admin role.
    
    **Request Body:**
    - `transaction_type`: "dispatch"
    - `date`: Dispatch date (YYYY-MM-DD)
    - `variant_name`: Part variant being dispatched
    - `quantity`: Quantity to dispatch
    - `remarks`: Destination, vehicle number, or other dispatch details
    
    **Business Rules:**
    - Reduces closing stock by dispatch quantity
    - Cannot dispatch more than available stock
    - Transaction is logged with timestamp and user
    - Updates stock ledger automatically
    
    **Use Case:**
    Dispatch team records outgoing shipments:
    1. Verify available stock
    2. Record dispatch details
    3. System updates stock levels
    4. Generate dispatch documentation
    
    **Example:**
    ```json
    {
      "transaction_type": "dispatch",
      "date": "2026-02-11",
      "variant_name": "ALTROZ BRACKET-D LH",
      "quantity": 500,
      "remarks": "Dispatch to Customer XYZ via Truck ABC-1234"
    }
    ```
    
    ---
    
    ### 2. Inspection Adjustment (`transaction_type: "inspection"`)
    Manually adjust stock for quality inspection rejections or damaged goods.
    
    **Authorization:** Requires Admin or Production role.
    
    **Request Body:**
    - `transaction_type`: "inspection"
    - `date`: Adjustment date (YYYY-MM-DD)
    - `variant_name`: Part variant being adjusted
    - `quantity`: Absolute inspection quantity (rejected/damaged)
    - `remarks`: Reason for adjustment (e.g., "200% inspection rejection", "Damaged in storage")
    
    **Business Rules:**
    - Sets inspection_qty to the specified value
    - Subtracts from available stock
    - Used for quality control rejections
    - Transaction is logged for audit trail
    - Cannot reduce stock below zero
    - Requires proper authorization
    
    **Use Case:**
    Quality team performs 200% inspection and finds defective parts:
    1. Inspect finished goods
    2. Identify rejected quantity
    3. Record adjustment with reason
    4. System reduces stock accordingly
    
    **Example:**
    ```json
    {
      "transaction_type": "inspection",
      "date": "2026-02-11",
      "variant_name": "ALTROZ BRACKET-D LH",
      "quantity": 50,
      "remarks": "200% inspection rejection - surface defects found by Inspector John"
    }
    ```
    
    ---
    
    ## Response:
    Returns updated FG stock record with:
    - Current stock levels (opening, production, inspection, dispatched, closing)
    - Transaction details
    - Variance vs target
    - Timestamp
    """,
    responses={
        200: {"description": "Transaction recorded successfully, stock updated"},
        400: {"description": "Insufficient stock, invalid data, or business rule violation"},
        401: {"description": "Not authenticated"},
        403: {"description": "Insufficient permissions for this transaction type"},
        404: {"description": "Part variant not found"}
    }
)
async def record_stock_transaction(
    payload: UnifiedStockTransactionRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Unified POST endpoint for stock transactions.
    
    Routes to appropriate service method based on transaction_type:
    - "dispatch" -> FGStockService.record_dispatch()
    - "inspection" -> FGStockService.manual_stock_adjustment()
    """
    
    # DISPATCH TRANSACTION
    if payload.transaction_type == "dispatch":
        # Check authorization for dispatch
        user_roles = [current_user.role, current_user.role2]
        allowed_roles = ["Production", "Dispatch", "Admin"]
        
        if not any(role in allowed_roles for role in user_roles if role):
            raise HTTPException(
                status_code=403,
                detail="Insufficient permissions. Dispatch requires Production, Dispatch, or Admin role."
            )
        
        # Convert to DispatchRequest
        dispatch_request = DispatchRequest(
            date=payload.date,
            variant_name=payload.variant_name,
            dispatched_qty=payload.quantity
        )
        
        stock = await FGStockService.record_dispatch(dispatch_request, current_user)
        return FGStockResponse(**stock.model_dump())
    
    # INSPECTION ADJUSTMENT
    elif payload.transaction_type == "inspection":
        # Check authorization for inspection adjustment
        user_roles = [current_user.role, current_user.role2]
        allowed_roles = ["Admin", "Production"]
        
        if not any(role in allowed_roles for role in user_roles if role):
            raise HTTPException(
                status_code=403,
                detail="Insufficient permissions. Inspection adjustment requires Admin or Production role."
            )
        
        # Convert to ManualStockAdjustmentRequest
        adjustment_request = ManualStockAdjustmentRequest(
            date=payload.date,
            variant_name=payload.variant_name,
            inspection_qty=payload.quantity,
            remarks=payload.remarks
        )
        
        stock = await FGStockService.manual_stock_adjustment(adjustment_request, current_user)
        return FGStockResponse(**stock.model_dump())
    
    else:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid transaction_type: {payload.transaction_type}. Must be 'dispatch' or 'inspection'."
        )



# ==================== BATCH TRANSACTIONS ENDPOINT ====================

@router.post(
    "/batch",
    response_model=BatchTransactionResponse,
    status_code=status.HTTP_200_OK,
    summary="Record Multiple Stock Transactions (Batch)",
    description="""
    **Batch endpoint to record multiple transactions at once.**
    
    Process multiple dispatch and inspection transactions in a single request.
    
    ## Use Cases:
    
    1. **Mixed Operations**: Dispatch some parts and record inspections for others
    2. **Bulk Processing**: Process multiple parts in one API call
    3. **Efficiency**: Reduce API calls and improve performance
    4. **Atomicity**: All transactions are processed independently
    
    ## Request Body:
    
    ```json
    {
      "transactions": [
        {
          "transaction_type": "dispatch",
          "date": "2026-02-11",
          "variant_name": "ALTROZ BRACKET-D LH",
          "quantity": 500,
          "remarks": "Dispatch to Customer XYZ"
        },
        {
          "transaction_type": "inspection",
          "date": "2026-02-11",
          "variant_name": "ALTROZ BRACKET-D RH",
          "quantity": 50,
          "remarks": "200% inspection rejection"
        }
      ]
    }
    ```
    
    ## Response:
    
    Returns summary of all transactions with individual results:
    
    ```json
    {
      "total_transactions": 2,
      "successful": 2,
      "failed": 0,
      "results": [
        {
          "status": "success",
          "transaction_type": "dispatch",
          "variant_name": "ALTROZ BRACKET-D LH",
          "message": "Dispatched 500 units successfully"
        },
        {
          "status": "success",
          "transaction_type": "inspection",
          "variant_name": "ALTROZ BRACKET-D RH",
          "message": "Inspection adjustment recorded successfully"
        }
      ]
    }
    ```
    
    ## Error Handling:
    
    - Each transaction is processed independently
    - If one fails, others continue processing
    - Failed transactions are reported in results with error details
    - Overall response shows success/failure counts
    
    ## Authorization:
    
    - Dispatch requires: Production, Dispatch, or Admin role
    - Inspection requires: Admin or Production role
    - User must have appropriate role for each transaction type
    
    ## Examples:
    
    ### Dispatch Multiple Parts
    ```json
    {
      "transactions": [
        {
          "transaction_type": "dispatch",
          "date": "2026-02-11",
          "variant_name": "ALTROZ BRACKET-D LH",
          "quantity": 500,
          "remarks": "Dispatch to Customer A"
        },
        {
          "transaction_type": "dispatch",
          "date": "2026-02-11",
          "variant_name": "ALTROZ BRACKET-D RH",
          "quantity": 300,
          "remarks": "Dispatch to Customer B"
        }
      ]
    }
    ```
    
    ### Mixed Operations
    ```json
    {
      "transactions": [
        {
          "transaction_type": "dispatch",
          "date": "2026-02-11",
          "variant_name": "PART A",
          "quantity": 1000,
          "remarks": "Dispatch"
        },
        {
          "transaction_type": "inspection",
          "date": "2026-02-11",
          "variant_name": "PART B",
          "quantity": 100,
          "remarks": "Inspection rejection"
        },
        {
          "transaction_type": "dispatch",
          "date": "2026-02-11",
          "variant_name": "PART C",
          "quantity": 500,
          "remarks": "Dispatch"
        }
      ]
    }
    ```
    """,
    responses={
        200: {"description": "Batch transactions processed"},
        400: {"description": "Invalid request data"},
        401: {"description": "Not authenticated"},
        403: {"description": "Insufficient permissions"}
    }
)
async def record_batch_transactions(
    payload: BatchStockTransactionRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Process multiple stock transactions in a single batch request.
    
    Each transaction is processed independently.
    Returns summary with individual results for each transaction.
    """
    
    results = []
    successful = 0
    failed = 0
    
    for idx, transaction in enumerate(payload.transactions):
        try:
            # DISPATCH TRANSACTION
            if transaction.transaction_type == "dispatch":
                # Check authorization
                user_roles = [current_user.role, current_user.role2]
                allowed_roles = ["Production", "Dispatch", "Admin"]
                
                if not any(role in allowed_roles for role in user_roles if role):
                    raise HTTPException(
                        status_code=403,
                        detail="Insufficient permissions for dispatch"
                    )
                
                # Convert and process
                dispatch_request = DispatchRequest(
                    date=transaction.date,
                    variant_name=transaction.variant_name,
                    dispatched_qty=transaction.quantity
                )
                
                stock = await FGStockService.record_dispatch(dispatch_request, current_user)
                
                results.append({
                    "index": idx,
                    "status": "success",
                    "transaction_type": "dispatch",
                    "variant_name": transaction.variant_name,
                    "quantity": transaction.quantity,
                    "message": f"Dispatched {transaction.quantity} units successfully",
                    "closing_stock": stock.closing_stock
                })
                successful += 1
            
            # INSPECTION TRANSACTION
            elif transaction.transaction_type == "inspection":
                # Check authorization
                user_roles = [current_user.role, current_user.role2]
                allowed_roles = ["Admin", "Production"]
                
                if not any(role in allowed_roles for role in user_roles if role):
                    raise HTTPException(
                        status_code=403,
                        detail="Insufficient permissions for inspection"
                    )
                
                # Convert and process
                adjustment_request = ManualStockAdjustmentRequest(
                    date=transaction.date,
                    variant_name=transaction.variant_name,
                    inspection_qty=transaction.quantity,
                    remarks=transaction.remarks
                )
                
                stock = await FGStockService.manual_stock_adjustment(adjustment_request, current_user)
                
                results.append({
                    "index": idx,
                    "status": "success",
                    "transaction_type": "inspection",
                    "variant_name": transaction.variant_name,
                    "quantity": transaction.quantity,
                    "message": f"Inspection adjustment recorded successfully",
                    "closing_stock": stock.closing_stock
                })
                successful += 1
            
            else:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid transaction_type: {transaction.transaction_type}"
                )
        
        except HTTPException as e:
            failed += 1
            results.append({
                "index": idx,
                "status": "failed",
                "transaction_type": transaction.transaction_type,
                "variant_name": transaction.variant_name,
                "error": e.detail
            })
        
        except Exception as e:
            failed += 1
            results.append({
                "index": idx,
                "status": "failed",
                "transaction_type": transaction.transaction_type,
                "variant_name": transaction.variant_name,
                "error": str(e)
            })
    
    return BatchTransactionResponse(
        total_transactions=len(payload.transactions),
        successful=successful,
        failed=failed,
        results=results
    )
