from datetime import datetime, timedelta
from typing import List, Optional, Dict
import logging
from collections import defaultdict

from app.core.models.production.production_plan import MonthlyProductionPlan
from app.core.models.production.hourly_production import HourlyProductionDocument
from app.core.models.fg_stock import FGStockDocument


logger = logging.getLogger(__name__)


class ProductionReportService:
    """Service for generating production reports combining multiple data sources"""
    
    @staticmethod
    async def get_daily_production_report(report_date: str) -> dict:
        """
        Generate daily production report combining:
        - Monthly plan (schedule, targets)
        - Hourly production (plan, actual, OK, rejected)
        - FG stock (current stock, dispatch, balance)
        
        Args:
            report_date: Date in YYYY-MM-DD format
            
        Returns:
            Daily report with all parts
        """
        # Parse date
        try:
            dt = datetime.strptime(report_date, "%Y-%m-%d")
            year, month = dt.year, dt.month
        except ValueError:
            raise ValueError(f"Invalid date format: {report_date}")
        
        # Get all hourly production documents for this date
        hourly_docs = await HourlyProductionDocument.find(
            HourlyProductionDocument.date == report_date
        ).to_list()
        
        # Get all FG stock for this date
        fg_stocks = await FGStockDocument.find(
            FGStockDocument.date == report_date
        ).to_list()
        
        # Get monthly plans for this month
        month_str = f"{year}-{str(month).zfill(2)}"
        monthly_plans = await MonthlyProductionPlan.find(
            MonthlyProductionPlan.month == month_str
        ).to_list()
        
        # Create plan map
        plan_map = {p.item_description: p for p in monthly_plans}
        
        # Aggregate by part description
        parts_data: Dict[str, Dict] = defaultdict(lambda: {
            "plan_qty": 0,
            "actual_qty": 0,
            "ok_qty": 0,
            "rejected_qty": 0,
            "lh_ok_qty": 0,
            "lh_rejected_qty": 0,
            "rh_ok_qty": 0,
            "rh_rejected_qty": 0,
            "current_stock": 0,
            "dispatched": 0,
        })
        
        # Aggregate hourly production
        for doc in hourly_docs:
            part_desc = doc.part_description
            side = doc.side
            
            parts_data[part_desc]["plan_qty"] += doc.totals.total_plan_qty
            parts_data[part_desc]["actual_qty"] += doc.totals.total_actual_qty
            parts_data[part_desc]["ok_qty"] += doc.totals.total_ok_qty
            parts_data[part_desc]["rejected_qty"] += doc.totals.total_rejected_qty
            
            # Side-specific tracking
            if side == "LH":
                parts_data[part_desc]["lh_ok_qty"] += doc.totals.total_ok_qty
                parts_data[part_desc]["lh_rejected_qty"] += doc.totals.total_rejected_qty
            elif side == "RH":
                parts_data[part_desc]["rh_ok_qty"] += doc.totals.total_ok_qty
                parts_data[part_desc]["rh_rejected_qty"] += doc.totals.total_rejected_qty
        
        # Aggregate FG stock
        for stock in fg_stocks:
            part_desc = stock.part_description
            parts_data[part_desc]["current_stock"] += stock.closing_stock
            parts_data[part_desc]["dispatched"] += stock.dispatched
        
        # Get last month production for comparison
        prev_month = dt.replace(day=1) - timedelta(days=1)
        prev_month_str = prev_month.strftime("%Y-%m")
        
        # Build final report
        parts_summary = []
        for part_desc, data in parts_data.items():
            # Get monthly plan
            plan = plan_map.get(part_desc)
            schedule = plan.schedule if plan else None
            daily_target = None
            
            if schedule:
                # Calculate working days (exclude Sundays)
                working_days = sum(
                    1 for d in range(1, 32)
                    if datetime(year, month, d).weekday() != 6
                    if d <= 31  # Handle month boundaries
                ) if month in [1,3,5,7,8,10,12] else 30
                daily_target = int(schedule / working_days) if working_days > 0 else None
            
            # Calculate balance
            balance = data["current_stock"] - data["dispatched"]
            
            # Calculate projected days
            projected_days = None
            if daily_target and daily_target > 0:
                projected_days = round(data["current_stock"] / daily_target, 2)
            
            # Get last month production
            last_month_prod = await ProductionReportService._get_last_month_production(
                part_desc, prev_month_str
            )
            
            parts_summary.append({
                "part_description": part_desc,
                "schedule": schedule,
                "plan_qty": data["plan_qty"],
                "actual_qty": data["actual_qty"],
                "ok_qty": data["ok_qty"],
                "rejected_qty": data["rejected_qty"],
                "current_stock": data["current_stock"],
                "dispatched": data["dispatched"],
                "balance": balance,
                "daily_target": daily_target,
                "projected_days": projected_days,
                "last_month_production": last_month_prod,
                "lh_ok_qty": data["lh_ok_qty"],
                "lh_rejected_qty": data["lh_rejected_qty"],
                "rh_ok_qty": data["rh_ok_qty"],
                "rh_rejected_qty": data["rh_rejected_qty"],
            })
        
        # Calculate totals
        total_production = sum(p["ok_qty"] for p in parts_summary)
        total_rejected = sum(p["rejected_qty"] for p in parts_summary)
        total_dispatch = sum(p["dispatched"] for p in parts_summary)
        
        return {
            "date": report_date,
            "parts": parts_summary,
            "total_parts": len(parts_summary),
            "total_production": total_production,
            "total_rejected": total_rejected,
            "total_dispatch": total_dispatch,
        }
    
    @staticmethod
    async def get_monthly_production_report(year: int, month: int) -> dict:
        """
        Generate monthly production report with aggregated data.
        
        Args:
            year: Year (e.g., 2026)
            month: Month (1-12)
            
        Returns:
            Monthly report with all parts
        """
        month_str = f"{year}-{str(month).zfill(2)}"
        
        # Get all hourly production for the month
        hourly_docs = await HourlyProductionDocument.find(
            HourlyProductionDocument.date >= f"{year}-{str(month).zfill(2)}-01",
            HourlyProductionDocument.date < f"{year}-{str(month+1 if month < 12 else 1).zfill(2)}-01"
        ).to_list()
        
        # Get all FG stock for the month
        fg_stocks = await FGStockDocument.find(
            FGStockDocument.year == year,
            FGStockDocument.month == month
        ).to_list()
        
        # Get monthly plans
        monthly_plans = await MonthlyProductionPlan.find(
            MonthlyProductionPlan.month == month_str
        ).to_list()
        
        plan_map = {p.item_description: p for p in monthly_plans}
        
        # Aggregate by part
        parts_data: Dict[str, Dict] = defaultdict(lambda: {
            "total_ok_qty": 0,
            "total_rejected_qty": 0,
            "days_produced": set(),
            "opening_stock": None,
            "closing_stock": None,
            "total_dispatched": 0,
        })
        
        # Aggregate hourly production
        for doc in hourly_docs:
            part_desc = doc.part_description
            parts_data[part_desc]["total_ok_qty"] += doc.totals.total_ok_qty
            parts_data[part_desc]["total_rejected_qty"] += doc.totals.total_rejected_qty
            parts_data[part_desc]["days_produced"].add(doc.date)
        
        # Aggregate FG stock
        for stock in fg_stocks:
            part_desc = stock.part_description
            
            # Track opening (first day) and closing (last day)
            if parts_data[part_desc]["opening_stock"] is None:
                parts_data[part_desc]["opening_stock"] = stock.opening_stock
            
            parts_data[part_desc]["closing_stock"] = stock.closing_stock
            parts_data[part_desc]["total_dispatched"] += stock.dispatched
        
        # Calculate working days
        working_days = sum(
            1 for d in range(1, 32)
            if datetime(year, month, d).weekday() != 6
        ) if month in [1,3,5,7,8,10,12] else 30
        
        # Build final report
        parts_summary = []
        total_production = 0
        total_rejected = 0
        
        for part_desc, data in parts_data.items():
            plan = plan_map.get(part_desc)
            schedule = plan.schedule if plan else None
            
            # Calculate achievement
            plan_achievement_pct = None
            if schedule and schedule > 0:
                plan_achievement_pct = round((data["total_ok_qty"] / schedule) * 100, 2)
            
            # Calculate rejection rate
            total_produced = data["total_ok_qty"] + data["total_rejected_qty"]
            rejection_rate_pct = 0.0
            if total_produced > 0:
                rejection_rate_pct = round((data["total_rejected_qty"] / total_produced) * 100, 2)
            
            # Calculate averages
            days_produced = len(data["days_produced"])
            avg_daily_production = round(data["total_ok_qty"] / days_produced, 2) if days_produced > 0 else 0.0
            avg_daily_dispatch = round(data["total_dispatched"] / working_days, 2) if working_days > 0 else 0.0
            
            total_production += data["total_ok_qty"]
            total_rejected += data["total_rejected_qty"]
            
            parts_summary.append({
                "part_description": part_desc,
                "month": month_str,
                "monthly_schedule": schedule,
                "total_production": data["total_ok_qty"],
                "plan_achievement_pct": plan_achievement_pct,
                "total_ok_qty": data["total_ok_qty"],
                "total_rejected_qty": data["total_rejected_qty"],
                "rejection_rate_pct": rejection_rate_pct,
                "opening_stock": data["opening_stock"] or 0,
                "closing_stock": data["closing_stock"] or 0,
                "total_dispatched": data["total_dispatched"],
                "avg_daily_production": avg_daily_production,
                "avg_daily_dispatch": avg_daily_dispatch,
                "working_days_in_month": working_days,
                "days_produced": days_produced,
            })
        
        # Calculate overall rejection rate
        total_produced = total_production + total_rejected
        overall_rejection_rate = 0.0
        if total_produced > 0:
            overall_rejection_rate = round((total_rejected / total_produced) * 100, 2)
        
        return {
            "year": year,
            "month": month,
            "parts": parts_summary,
            "total_parts": len(parts_summary),
            "total_production": total_production,
            "total_rejected": total_rejected,
            "overall_rejection_rate_pct": overall_rejection_rate,
        }
    
    @staticmethod
    async def _get_last_month_production(part_desc: str, prev_month_str: str) -> Optional[int]:
        """Get total production for a part in previous month"""
        try:
            year, month = map(int, prev_month_str.split("-"))
            
            hourly_docs = await HourlyProductionDocument.find(
                HourlyProductionDocument.part_description == part_desc,
                HourlyProductionDocument.date >= f"{prev_month_str}-01",
                HourlyProductionDocument.date < f"{year}-{str(month+1 if month < 12 else 1).zfill(2)}-01"
            ).to_list()
            
            return sum(doc.totals.total_ok_qty for doc in hourly_docs)
        except Exception as e:
            logger.error(f"Error getting last month production: {e}")
            return None