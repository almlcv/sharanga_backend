from datetime import datetime, timedelta
from app.shared.timezone import get_ist_now

from typing import List, Optional, Dict, Any
from fastapi import HTTPException, status
import logging

from app.core.models.fg_stock import FGStockDocument, BinInventory
from app.core.models.parts_config import PartConfiguration
from app.core.models.production.production_plan import MonthlyProductionPlan
from app.core.models.production.hourly_production import HourlyProductionDocument
from app.core.schemas.fg_stock import (
    ManualStockAdjustmentRequest,
    ManualBinUpdateRequest,
    DispatchRequest,
    BinTransferRequest,
)

logger = logging.getLogger(__name__)


class FGStockService:
    """Service layer for FG Stock management"""
    
    # -------------------------
    # Core Stock Operations
    # -------------------------
    
    @staticmethod
    async def get_or_create_stock(
        date: str, 
        variant_name: str,
        auto_rollover: bool = True
    ) -> FGStockDocument:
        """Get existing stock or create with rollover from previous day"""
        
        # Parse date
        try:
            dt = datetime.strptime(date, "%Y-%m-%d")
            year, month, day = dt.year, dt.month, dt.day
        except ValueError:
            raise HTTPException(400, f"Invalid date format: {date}")
        
        # Check if exists
        stock = await FGStockDocument.find_one(
            FGStockDocument.date == date,
            FGStockDocument.variant_name == variant_name
        )
        
        if stock:
            return stock
        
        # Get part configuration
        part_desc = variant_name.rsplit(" ", 1)[0]  # Remove LH/RH
        side = variant_name.split()[-1]  # LH or RH
        
        part_config = await PartConfiguration.find_one(
            PartConfiguration.part_description == part_desc,
            PartConfiguration.is_active == True
        )
        
        if not part_config:
            raise HTTPException(
                404, 
                f"Part configuration not found for '{part_desc}'"
            )
        
        # Get bin size
        bin_size = part_config.bin_settings.get(variant_name) if part_config.bin_settings else None
        
        # Get monthly plan
        month_str = f"{year}-{str(month).zfill(2)}"
        monthly_plan = await MonthlyProductionPlan.find_one(
            MonthlyProductionPlan.month == month_str,
            MonthlyProductionPlan.item_description == part_desc
        )
        
        monthly_schedule = monthly_plan.schedule if monthly_plan else None
        daily_target = None
        if monthly_schedule:
            # Calculate working days (simplified - exclude Sundays)
            working_days = sum(
                1 for d in range(1, 32)
                if datetime(year, month, d).weekday() != 6
            ) if month in [1,3,5,7,8,10,12] else 30
            daily_target = int(monthly_schedule / working_days)
        
        # Rollover from previous day
        opening_stock = 0
        opening_bins = BinInventory()
        
        if auto_rollover:
            prev_date = (dt - timedelta(days=1)).strftime("%Y-%m-%d")
            prev_stock = await FGStockDocument.find_one(
                FGStockDocument.date == prev_date,
                FGStockDocument.variant_name == variant_name
            )
            
            if prev_stock:
                opening_stock = prev_stock.closing_stock
                opening_bins = prev_stock.bins_available
        
        # Create new stock record
        stock = FGStockDocument(
            date=date,
            variant_name=variant_name,
            part_number=part_config.part_number,
            part_description=part_desc,
            side=side,
            year=year,
            month=month,
            day=day,
            opening_stock=opening_stock,
            bins_available=opening_bins,
            bin_size=bin_size,
            monthly_schedule=monthly_schedule,
            daily_target=daily_target
        )
        
        await stock.insert()
        logger.info(f"Created FG stock for {variant_name} on {date}")
        
        return stock
    
    @staticmethod
    async def update_from_hourly_production(
        doc: HourlyProductionDocument,
        user_id: Optional[str] = None
    ):
        """Auto-update FG stock when hourly production is submitted"""
        
        variant_name = f"{doc.part_description} {doc.side}"
        
        # Get or create stock record
        stock = await FGStockService.get_or_create_stock(doc.date, variant_name)
        
        # Calculate production to add (only OK quantity)
        production_qty = doc.totals.total_ok_qty
        
        # Update stock
        old_production = stock.production_added
        stock.production_added = production_qty
        
        # Calculate bins
        if stock.bin_size and stock.bin_size > 0:
            bins_to_add = production_qty // stock.bin_size
            stock.bins_available.rabs_bins = bins_to_add
        
        # Recalculate closing
        stock.recalculate_closing_stock()
        stock.last_synced_at = get_ist_now()
        
        # Add transaction
        stock.add_transaction(
            transaction_type="PRODUCTION",
            quantity_change=production_qty - old_production,
            user_id=user_id,
            reference_doc_no=doc.doc_no,
            remarks=f"Auto-sync from hourly production document {doc.doc_no}"
        )
        
        await stock.save()
        
        logger.info(
            f"Updated FG stock for {variant_name} on {doc.date}: "
            f"Production={production_qty}, Closing={stock.closing_stock}"
        )
    
    # -------------------------
    # Manual Operations
    # -------------------------
    
    @staticmethod
    async def manual_stock_adjustment(
        payload: ManualStockAdjustmentRequest,
        current_user: Dict[str, Any]
    ) -> FGStockDocument:
        """Manual stock adjustment (add/subtract)"""
        
        stock = await FGStockService.get_or_create_stock(
            payload.date, 
            payload.variant_name
        )
        
        # Apply adjustment
        stock.manual_adjustment += payload.adjustment_qty
        stock.recalculate_closing_stock()
        
        # Validate non-negative stock
        if stock.closing_stock < 0:
            raise HTTPException(
                400,
                f"Adjustment would result in negative stock: {stock.closing_stock}"
            )
        
        # Add transaction
        stock.add_transaction(
            transaction_type="MANUAL_ADJUSTMENT",
            quantity_change=payload.adjustment_qty,
            user_id=current_user.get("emp_id"),
            remarks=payload.remarks
        )
        
        await stock.save()
        
        logger.info(
            f"Manual adjustment: {payload.variant_name} on {payload.date} "
            f"by {current_user.get('full_name')}: {payload.adjustment_qty:+d}"
        )
        
        return stock
    
    @staticmethod
    async def manual_bin_update(
        payload: ManualBinUpdateRequest,
        current_user: Dict[str, Any]
    ) -> FGStockDocument:
        """Manual bin inventory update"""
        
        stock = await FGStockService.get_or_create_stock(
            payload.date,
            payload.variant_name
        )
        
        bins_change = {}
        
        if payload.rabs_bins is not None:
            old_rabs = stock.bins_available.rabs_bins
            stock.bins_available.rabs_bins = payload.rabs_bins
            bins_change["rabs_bins"] = payload.rabs_bins - old_rabs
        
        if payload.ijl_bins is not None:
            old_ijl = stock.bins_available.ijl_bins
            stock.bins_available.ijl_bins = payload.ijl_bins
            bins_change["ijl_bins"] = payload.ijl_bins - old_ijl
        
        stock.updated_at = get_ist_now()
        
        # Add transaction
        stock.add_transaction(
            transaction_type="MANUAL_BIN_UPDATE",
            quantity_change=0,
            bins_change=bins_change,
            user_id=current_user.get("emp_id"),
            remarks=payload.remarks
        )
        
        await stock.save()
        
        logger.info(
            f"Manual bin update: {payload.variant_name} on {payload.date} "
            f"by {current_user.get('full_name')}: {bins_change}"
        )
        
        return stock
    
    @staticmethod
    async def record_dispatch(
        payload: DispatchRequest,
        current_user: Dict[str, Any]
    ) -> FGStockDocument:
        """Record dispatch and optionally transfer bins"""
        
        stock = await FGStockService.get_or_create_stock(
            payload.date,
            payload.variant_name
        )
        
        # Validate sufficient stock
        if stock.closing_stock < payload.dispatched_qty:
            raise HTTPException(
                400,
                f"Insufficient stock. Available: {stock.closing_stock}, "
                f"Requested: {payload.dispatched_qty}"
            )
        
        # Update dispatch
        stock.dispatched += payload.dispatched_qty
        stock.recalculate_closing_stock()
        
        # Transfer bins if requested
        bins_change = None
        if payload.auto_transfer_bins and stock.bin_size and stock.bin_size > 0:
            bins_to_transfer = payload.dispatched_qty // stock.bin_size
            
            if bins_to_transfer > stock.bins_available.rabs_bins:
                bins_to_transfer = stock.bins_available.rabs_bins
            
            if bins_to_transfer > 0:
                stock.bins_available.rabs_bins -= bins_to_transfer
                stock.bins_available.ijl_bins += bins_to_transfer
                bins_change = {
                    "rabs_bins": -bins_to_transfer,
                    "ijl_bins": bins_to_transfer
                }
        
        # Add transaction
        stock.add_transaction(
            transaction_type="DISPATCH",
            quantity_change=-payload.dispatched_qty,
            bins_change=bins_change,
            user_id=current_user.emp_id,
            remarks=f"Dispatched {payload.dispatched_qty} units"
        )
        
        await stock.save()
        
        logger.info(
            f"Dispatch recorded: {payload.variant_name} on {payload.date} "
            f"by {current_user.full_name}: {payload.dispatched_qty} units"
        )
        
        return stock
    
    @staticmethod
    async def transfer_bins(
        payload: BinTransferRequest,
        current_user: Dict[str, Any]
    ) -> FGStockDocument:
        """Transfer bins from RABS to IJL"""
        
        stock = await FGStockService.get_or_create_stock(
            payload.date,
            payload.variant_name
        )
        
        # Validate sufficient RABS bins
        if stock.bins_available.rabs_bins < payload.bins_to_transfer:
            raise HTTPException(
                400,
                f"Insufficient RABS bins. Available: {stock.bins_available.rabs_bins}, "
                f"Requested: {payload.bins_to_transfer}"
            )
        
        # Transfer
        stock.bins_available.rabs_bins -= payload.bins_to_transfer
        stock.bins_available.ijl_bins += payload.bins_to_transfer
        stock.updated_at = get_ist_now()
        
        # Add transaction
        stock.add_transaction(
            transaction_type="BIN_TRANSFER",
            quantity_change=0,
            bins_change={
                "rabs_bins": -payload.bins_to_transfer,
                "ijl_bins": payload.bins_to_transfer
            },
            user_id=current_user.get("emp_id"),
            remarks=f"Transferred {payload.bins_to_transfer} bins from RABS to IJL"
        )
        
        await stock.save()
        
        logger.info(
            f"Bin transfer: {payload.variant_name} on {payload.date} "
            f"by {current_user.get('full_name')}: {payload.bins_to_transfer} bins"
        )
        
        return stock
    
    # -------------------------
    # Queries
    # -------------------------
    @staticmethod
    async def get_daily_stocks(
        date: str,
        part_description: Optional[str] = None
    ) -> List[FGStockDocument]:
        """Get all FG stocks for a date"""
        
        query = {"date": date}
        if part_description:
            query["part_description"] = part_description
        
        stocks = await FGStockDocument.find(query).to_list()

        return stocks
    
    @staticmethod
    async def get_monthly_summary(
        year: int,
        month: int,
        part_description: Optional[str] = None
    ) -> List[Dict]:
        """Get monthly summary per variant"""
        
        month_str = f"{year}-{str(month).zfill(2)}"
        
        # Build query
        query = {"year": year, "month": month}
        if part_description:
            query["part_description"] = part_description
        
        # Get all stocks for the month
        stocks = await FGStockDocument.find(query).to_list()
        
        # Group by variant
        variant_map: Dict[str, List[FGStockDocument]] = {}
        for stock in stocks:
            if stock.variant_name not in variant_map:
                variant_map[stock.variant_name] = []
            variant_map[stock.variant_name].append(stock)
        
        # Calculate summaries
        summaries = []
        for variant_name, variant_stocks in variant_map.items():
            # Sort by date
            variant_stocks.sort(key=lambda x: x.date)
            
            opening = variant_stocks[0].opening_stock if variant_stocks else 0
            closing = variant_stocks[-1].closing_stock if variant_stocks else 0
            
            total_production = sum(s.production_added for s in variant_stocks)
            total_dispatched = sum(s.dispatched for s in variant_stocks)
            total_adjustments = sum(s.manual_adjustment for s in variant_stocks)
            
            # Get monthly plan
            part_desc = variant_stocks[0].part_description if variant_stocks else ""
            monthly_plan_doc = await MonthlyProductionPlan.find_one(
                MonthlyProductionPlan.month == month_str,
                MonthlyProductionPlan.item_description == part_desc
            )
            
            monthly_plan = monthly_plan_doc.schedule if monthly_plan_doc else None
            plan_achievement_pct = None
            if monthly_plan and monthly_plan > 0:
                plan_achievement_pct = round((total_production / monthly_plan) * 100, 2)
            
            summaries.append({
                "year": year,
                "month": month,
                "variant_name": variant_name,
                "part_description": part_desc,
                "side": variant_stocks[0].side if variant_stocks else "",
                "opening_stock_month": opening,
                "total_production": total_production,
                "total_dispatched": total_dispatched,
                "total_adjustments": total_adjustments,
                "closing_stock_month": closing,
                "monthly_plan": monthly_plan,
                "plan_achievement_pct": plan_achievement_pct,
                "average_daily_production": round(total_production / len(variant_stocks), 2) if variant_stocks else 0,
                "average_daily_dispatch": round(total_dispatched / len(variant_stocks), 2) if variant_stocks else 0,
            })
        
        return summaries