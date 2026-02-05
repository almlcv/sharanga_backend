from fastapi import APIRouter, Depends, Query, HTTPException, status
from typing import Optional

from app.core.auth.deps import get_current_user
from app.modules.production_reports.production_report_service import ProductionReportService
from app.core.schemas.production.production_report import (
    DailyProductionReport,
    MonthlyProductionReport,
)


router = APIRouter(tags=["Production Reports"], prefix="/production/reports")


@router.get(
    "/daily",
    response_model=DailyProductionReport,
    summary="Get Daily Production Report"
)
async def get_daily_production_report(
    date: str = Query(..., pattern=r"^\d{4}-\d{2}-\d{2}$", description="Date (YYYY-MM-DD)"),
    current_user: dict = Depends(get_current_user)
):
    """
    Generate comprehensive daily production report combining:
    - Monthly production schedule and targets
    - Hourly production actuals (plan, actual, OK, rejected)
    - FG stock status (current, dispatch, balance)
    - Last month production for comparison
    - Projected days of inventory
    
    **Fields Explained:**
    - **Sch**: Monthly schedule target
    - **Plan**: Total planned quantity for the day
    - **Act**: Total actual production quantity
    - **Rej**: Total rejected quantity
    - **Production**: Total OK production (Act - Rej)
    - **Current**: Current closing stock (FG stock)
    - **Dispatch**: Total dispatched quantity
    - **Balance**: Current - Dispatch
    - **Last Mth**: Previous month's total production
    - **Tgt Day**: Daily target based on monthly schedule
    - **Proj Days**: Days of inventory remaining (Current / Daily Target)
    
    **Use Cases:**
    - Daily production monitoring
    - Stock level tracking
    - Performance vs target comparison
    """
    try:
        report = await ProductionReportService.get_daily_production_report(date)
        return DailyProductionReport(**report)
    except ValueError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate report: {str(e)}"
        )


@router.get(
    "/monthly",
    response_model=MonthlyProductionReport,
    summary="Get Monthly Production Report"
)
async def get_monthly_production_report(
    year: int = Query(..., ge=2000, le=2100, description="Year (e.g., 2026)"),
    month: int = Query(..., ge=1, le=12, description="Month (1-12)"),
    current_user: dict = Depends(get_current_user)
):
    """
    Generate comprehensive monthly production report with:
    - Monthly schedule vs actual achievement
    - Total production and rejection statistics
    - Stock movement (opening to closing)
    - Quality metrics (rejection rate)
    - Daily averages for production and dispatch
    
    **Metrics:**
    - **Plan Achievement %**: (Actual Production / Monthly Schedule) × 100
    - **Rejection Rate %**: (Rejected / Total Produced) × 100
    - **Avg Daily Production**: Total Production / Days Produced
    - **Avg Daily Dispatch**: Total Dispatch / Working Days
    
    **Use Cases:**
    - Monthly performance review
    - Quality analysis
    - Capacity utilization tracking
    - Trend analysis
    """
    try:
        report = await ProductionReportService.get_monthly_production_report(year, month)
        return MonthlyProductionReport(**report)
    except Exception as e:
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate report: {str(e)}"
        )