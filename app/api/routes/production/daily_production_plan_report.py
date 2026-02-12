"""
API endpoints for Daily Production Plan Reports (Excel format)
"""
from fastapi import APIRouter, Depends, Query, HTTPException, status

from app.core.auth.deps import get_current_user
from app.modules.daily_plan.daily_plan_report_service import DailyPlanReportService
from app.core.schemas.production.daily_production_plan_report import DailyProductionPlanReport


router = APIRouter(tags=["Production Plan Reports"], prefix="/production/plan-reports")


@router.get(
    "/monthly",
    response_model=DailyProductionPlanReport,
    summary="Get Monthly Production Plan Report (Excel Format)",
    description="""
    Generate monthly production plan report matching Excel "RABS INDUSTRIS GUJARAT - DAILYPRODUCTION PLAN" format.
    
    **This endpoint provides the exact same data structure as the Excel sheet:**
    
    **Columns Included:**
    - **CUSTOMER**: Customer name (from hourly production records)
    - **MC N0**: Machine number (from parts configuration)
    - **BIN QTY**: Bin capacity (from parts configuration)
    - **PART NAME**: Full part name with side (e.g., ALTROZ INNER LENS - (LH))
    - **MONTH PLAN**: Monthly target quantity
    - **OPN STOCK**: Opening stock at start of month
    - **BALANCE TO PRODUCE**: Remaining to produce (Month Plan - Opening Stock)
    - **PROD PLAN**: Total production plan (sum of daily targets)
    - **Daily Quantities**: Production quantity for each day (1-31)
    
    **Data Sources:**
    - Customer name: From `hourly_production` documents (most recent)
    - Machine number: From `part_configurations` collection
    - Bin capacity: From `part_configurations` collection
    - Opening stock: From `fg_stock_daily` collection (first day of month)
    - Monthly plan: From `daily_production_plan` collection
    - Daily targets: From `daily_production_plan` collection
    
    **Use Cases:**
    - Export to Excel matching existing format
    - Display production plan in UI
    - Integration with external systems
    - Monthly planning review
    
    **Example Response:**
    ```json
    {
      "month": "2026-02",
      "month_name": "FEBRUARY 2026",
      "rows": [
        {
          "customer": "IJL",
          "machine_number": "470",
          "bin_capacity": 8,
          "part_name": "ALTROZ INNER LENS - (LH)",
          "month_plan": 5000,
          "opening_stock": 0,
          "balance_to_produce": 5000,
          "prod_plan": 5000,
          "daily_quantities": {
            "3": 600,
            "4": 600,
            "5": 600,
            "10": 500,
            "11": 600,
            "12": 600,
            "13": 600
          },
          "part_description": "ALTROZ INNER LENS",
          "side": "LH",
          "part_number": "10077-7R05S"
        }
      ],
      "total_parts": 15,
      "total_month_plan": 75000,
      "total_prod_plan": 72000,
      "days_in_month": 28
    }
    ```
    """
)
async def get_monthly_production_plan_report(
    year: int = Query(..., ge=2000, le=2100, description="Year (e.g., 2026)"),
    month: int = Query(..., ge=1, le=12, description="Month (1-12)"),
    current_user: dict = Depends(get_current_user)
):
    """
    Get monthly production plan report in Excel format.
    
    Returns complete production plan with all fields matching the Excel sheet:
    Customer, Machine, Bin Qty, Part Name, Month Plan, Opening Stock, 
    Balance to Produce, Prod Plan, and daily quantities for each day.
    """
    try:
        report = await DailyPlanReportService.get_monthly_production_plan_report(year, month)
        return DailyProductionPlanReport(**report)
    except Exception as e:
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate production plan report: {str(e)}"
        )
