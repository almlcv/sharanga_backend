from typing import Optional
import logging
import calendar
from collections import defaultdict

from app.core.models.parts_config import PartConfiguration
from app.core.models.fg_stock import FGStockDocument
from app.core.models.production.hourly_production import HourlyProductionDocument
from app.core.models.production.production_plan import MonthlyProductionPlan
from app.shared.variant_utils import construct_variant_name


logger = logging.getLogger(__name__)


class DailyPlanReportService:
    """Service for generating production plan reports matching Excel format"""
    
    @staticmethod
    async def get_monthly_production_plan_report(year: int, month: int) -> dict:
        """
        Generate monthly production plan report matching Excel "RABS INDUSTRIS GUJARAT - DAILYPRODUCTION PLAN" format
        
        Uses ACTUAL production data from hourly_production, aggregated by day
        
        Args:
            year: Year (e.g., 2026)
            month: Month (1-12)
            
        Returns:
            Report dict matching DailyProductionPlanReport schema
        """
        month_str = f"{year}-{str(month).zfill(2)}"
        
        # Get month name for display
        month_name = f"{calendar.month_name[month].upper()} {year}"
        
        # Get days in month
        days_in_month = calendar.monthrange(year, month)[1]
        
        # Get all hourly production for this month
        start_date = f"{month_str}-01"
        next_month = month + 1 if month < 12 else 1
        next_year = year if month < 12 else year + 1
        end_date = f"{next_year}-{str(next_month).zfill(2)}-01"
        
        hourly_docs = await HourlyProductionDocument.find(
            HourlyProductionDocument.date >= start_date,
            HourlyProductionDocument.date < end_date
        ).to_list()
        
        if not hourly_docs:
            return {
                "month": month_str,
                "month_name": month_name,
                "rows": [],
                "total_parts": 0,
                "total_month_plan": 0,
                "total_prod_plan": 0,
                "days_in_month": days_in_month
            }
        
        # Get all part configurations for metadata
        part_configs = await PartConfiguration.find(
            PartConfiguration.is_active == True
        ).to_list()
        part_config_map = {pc.part_description: pc for pc in part_configs}
        
        # Get monthly plans for month plan targets
        monthly_plans = await MonthlyProductionPlan.find(
            MonthlyProductionPlan.month == month_str
        ).to_list()
        monthly_plan_map = {mp.item_description: mp.schedule for mp in monthly_plans}
        
        # Get opening stock for all variants (closing stock from last day of previous month)
        # Opening stock for current month = Closing stock from last day of previous month
        prev_month = month - 1 if month > 1 else 12
        prev_year = year if month > 1 else year - 1
        
        # Get last day of previous month
        last_day_prev_month = calendar.monthrange(prev_year, prev_month)[1]
        last_day_date = f"{prev_year}-{str(prev_month).zfill(2)}-{str(last_day_prev_month).zfill(2)}"
        
        fg_stocks_prev = await FGStockDocument.find(
            FGStockDocument.date == last_day_date
        ).to_list()
        
        opening_stock_map = {}
        for fg in fg_stocks_prev:
            variant_key = construct_variant_name(fg.part_description, fg.side)
            # Opening stock = Closing stock from previous month
            opening_stock_map[variant_key] = fg.closing_stock
        
        # Aggregate hourly production by part variant and date
        # Structure: {variant_name: {date: total_ok_qty}}
        production_by_variant = defaultdict(lambda: defaultdict(int))
        variant_metadata = {}  # Store part_description, side, customer for each variant
        
        for doc in hourly_docs:
            # Build variant name using utility function
            variant_name = construct_variant_name(doc.part_description, doc.side)
            
            # Extract date (YYYY-MM-DD)
            date_str = doc.date
            
            # Aggregate OK quantity for this date
            production_by_variant[variant_name][date_str] += doc.totals.total_ok_qty
            
            # Store metadata (use first occurrence)
            if variant_name not in variant_metadata:
                variant_metadata[variant_name] = {
                    "part_description": doc.part_description,
                    "side": doc.side,
                    "customer_name": doc.customer_name
                }
        
        # Build report rows
        rows = []
        total_month_plan = 0
        total_prod_plan = 0
        
        for variant_name, daily_production in production_by_variant.items():
            metadata = variant_metadata[variant_name]
            part_desc = metadata["part_description"]
            side = metadata["side"]
            customer_name = metadata["customer_name"]
            
            # Get part config for metadata
            part_config = part_config_map.get(part_desc)
            
            # Get monthly plan (if part has LH/RH, divide by 2)
            monthly_schedule = monthly_plan_map.get(part_desc, 0)
            if side and monthly_schedule > 0:
                # If there are multiple sides, split the monthly plan
                # Check if both LH and RH exist in production data
                has_lh = any("LH" in v for v in production_by_variant.keys() if part_desc in v)
                has_rh = any("RH" in v for v in production_by_variant.keys() if part_desc in v)
                if has_lh and has_rh:
                    monthly_schedule = monthly_schedule // 2
            
            # Get opening stock
            opening_stock = opening_stock_map.get(variant_name, 0)
            
            # Calculate prod plan (sum of daily production)
            prod_plan = sum(daily_production.values())
            
            # Calculate balance to produce
            balance_to_produce = monthly_schedule - prod_plan
            
            # Convert daily production to day numbers
            daily_quantities = {}
            for date_str, qty in daily_production.items():
                try:
                    # Extract day from date string (YYYY-MM-DD)
                    day = int(date_str.split('-')[2])
                    daily_quantities[day] = qty
                except (ValueError, IndexError):
                    logger.warning(f"Invalid date format in production data: {date_str}")
                    continue
            
            # Build row
            row = {
                "customer": customer_name,
                "machine_number": part_config.machine if part_config else None,
                "bin_capacity": part_config.bin_capacity if part_config else None,
                "part_name": variant_name,
                "month_plan": monthly_schedule,
                "opening_stock": opening_stock,
                "balance_to_produce": balance_to_produce,
                "prod_plan": prod_plan,
                "daily_quantities": daily_quantities,
                "part_description": part_desc,
                "side": side,
                "part_number": part_config.part_number if part_config else None
            }
            
            rows.append(row)
            total_month_plan += monthly_schedule
            total_prod_plan += prod_plan
        
        # Sort rows by customer, then part name
        rows.sort(key=lambda x: (x["customer"] or "", x["part_name"]))
        
        return {
            "month": month_str,
            "month_name": month_name,
            "rows": rows,
            "total_parts": len(rows),
            "total_month_plan": total_month_plan,
            "total_prod_plan": total_prod_plan,
            "days_in_month": days_in_month
        }
    
    @staticmethod
    def _extract_side(variant_name: str) -> Optional[str]:
        """Extract side (LH/RH) from variant name"""
        variant_upper = variant_name.upper()
        if " LH" in variant_upper or "(LH)" in variant_upper:
            return "LH"
        elif " RH" in variant_upper or "(RH)" in variant_upper:
            return "RH"
        return None
