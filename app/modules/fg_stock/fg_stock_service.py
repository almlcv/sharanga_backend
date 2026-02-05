from datetime import datetime, timedelta
from app.shared.timezone import get_ist_now
from typing import List, Optional, Dict, Any
from fastapi import HTTPException
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
    """Service layer for FG Stock management - Production Grade"""

    @staticmethod
    async def get_or_create_stock(
        date: str,
        variant_name: str,
        auto_rollover: bool = True
    ) -> FGStockDocument:
        """
        Retrieves or creates a stock document.
        Implements SMART ROLLOVER: finds last available stock even if days are missing.
        """

        try:
            dt = datetime.strptime(date, "%Y-%m-%d")
            year, month, day = dt.year, dt.month, dt.day
        except ValueError:
            raise HTTPException(400, f"Invalid date format: {date}")

        # 1. Check if record exists for this exact date
        stock = await FGStockDocument.find_one(
            FGStockDocument.date == date,
            FGStockDocument.variant_name == variant_name
        )

        if stock:
            return stock

        # 2. Parse Part Details (LH/RH Logic)
        parts = variant_name.rsplit(" ", 1)
        if len(parts) == 2 and parts[1] in ("LH", "RH"):
            part_desc = parts[0]
            side = parts[1]
        else:
            part_desc = variant_name
            side = None

        # 3. Fetch Part Configuration (Source of Truth)
        part_config = await PartConfiguration.find_one(
            PartConfiguration.part_description == part_desc,
            PartConfiguration.is_active == True
        )

        if not part_config:
            raise HTTPException(404, f"Part configuration not found for '{part_desc}'")

        # AUTOMATION: Use Bin Capacity from Config
        bin_size = part_config.bin_capacity

        # 4. Handle Monthly Plan (If available)
        month_str = f"{year}-{str(month).zfill(2)}"
        monthly_plan = await MonthlyProductionPlan.find_one(
            MonthlyProductionPlan.month == month_str,
            MonthlyProductionPlan.item_description == part_desc
        )

        monthly_schedule = monthly_plan.schedule if monthly_plan else None
        daily_target = None
        if monthly_schedule:
            # Calculate working days (exclude Sundays)
            working_days = sum(
                1 for d in range(1, 32) 
                if datetime(year, month, d).weekday() != 6
            )
            if working_days > 0:
                daily_target = int(monthly_schedule / working_days)

        # 5. SMART ROLLOVER (Automated Opening Stock)
        opening_stock = 0
        opening_bins = BinInventory()

        if auto_rollover:
            # Strategy A: Check yesterday (Most common case)
            prev_date = (dt - timedelta(days=1)).strftime("%Y-%m-%d")
            prev_stock = await FGStockDocument.find_one(
                FGStockDocument.date == prev_date,
                FGStockDocument.variant_name == variant_name
            )

            # Strategy B: If yesterday missing (Weekend/Holiday), find LATEST record
            if not prev_stock:
                prev_stock = await FGStockDocument.find(
                    FGStockDocument.variant_name == variant_name,
                    FGStockDocument.date < date # Look for any day before today
                ).sort(-FGStockDocument.date).limit(1).to_list()
                prev_stock = prev_stock[0] if prev_stock else None
            
            # Apply Rollover
            if prev_stock:
                opening_stock = prev_stock.closing_stock
                opening_bins = prev_stock.bins_available
                logger.info(f"Smart Rollover: Stock for {variant_name} on {date} initialized from {prev_stock.date}")

        # 6. Create New Document
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
        logger.info(f"Created new FG Stock record for {variant_name} on {date}")
        return stock

    @staticmethod
    async def update_from_hourly_production(
        doc: HourlyProductionDocument,
        user_id: Optional[str] = None
    ):
        """
        Syncs stock from Hourly Production Document.
        Called automatically via Triggers or manually.
        """
        variant_name = f"{doc.part_description} {doc.side}" if doc.side else doc.part_description
        
        # Get or create daily stock wrapper
        stock = await FGStockService.get_or_create_stock(doc.date, variant_name)

        # Calculate Total Production for this part/date
        # (Summing all hourly docs for this part in case of multiple shifts)
        hourly_docs = await HourlyProductionDocument.find(
            HourlyProductionDocument.date == doc.date,
            HourlyProductionDocument.part_description == doc.part_description,
            HourlyProductionDocument.side == doc.side
        ).to_list()

        production_qty = sum(h.totals.total_ok_qty for h in hourly_docs)
        
        # Update Logic
        old_production = stock.production_added
        stock.production_added = production_qty
        
        stock.recalculate_closing_stock()
        stock.last_synced_at = get_ist_now()

        # Audit Trail
        stock.add_transaction(
            transaction_type="PRODUCTION",
            quantity_change=production_qty - old_production,
            user_id=user_id,
            reference_doc_no=str(doc.id),
            remarks="Auto-sync from hourly production"
        )

        await stock.save()
        logger.info(f"Auto-synced {variant_name}: {old_production} -> {production_qty}")

    @staticmethod
    async def manual_stock_adjustment(
        payload: ManualStockAdjustmentRequest,
        current_user: Dict[str, Any]
    ) -> FGStockDocument:
        stock = await FGStockService.get_or_create_stock(payload.date, payload.variant_name)
        
        # BUG FIX: Correct field name
        inspection_qty = payload.inspection_qty

        if inspection_qty < 0:
            raise HTTPException(400, "Inspection quantity cannot be negative")

        # Safety: Inspection cannot exceed production
        if inspection_qty > stock.production_added:
            raise HTTPException(400, "Inspection quantity cannot exceed production")

        old_inspection = stock.inspection_qty
        stock.inspection_qty = inspection_qty
        
        stock.recalculate_closing_stock()

        if stock.closing_stock < 0:
            raise HTTPException(400, "Inspection would result in negative stock")

        stock.add_transaction(
            transaction_type="INSPECTION",
            quantity_change=-(inspection_qty - old_inspection),
            user_id=current_user.get('emp_id'),
            remarks=payload.remarks
        )

        await stock.save()
        return stock

    @staticmethod
    async def manual_bin_update(payload: ManualBinUpdateRequest, current_user: Dict[str, Any]):
        stock = await FGStockService.get_or_create_stock(payload.date, payload.variant_name)
        
        bins_change = {}
        if payload.rabs_bins is not None:
            bins_change["rabs_bins"] = payload.rabs_bins - stock.bins_available.rabs_bins
            stock.bins_available.rabs_bins = payload.rabs_bins
            
        if payload.ijl_bins is not None:
            bins_change["ijl_bins"] = payload.ijl_bins - stock.bins_available.ijl_bins
            stock.bins_available.ijl_bins = payload.ijl_bins
        
        stock.updated_at = get_ist_now()
        
        stock.add_transaction(
            transaction_type="MANUAL_BIN_UPDATE",
            quantity_change=0,
            bins_change=bins_change,
            user_id=current_user.emp_id,
            remarks=payload.remarks
        )

        await stock.save()
        return stock

    @staticmethod
    async def record_dispatch(payload: DispatchRequest, current_user: Dict[str, Any]):
        """
        Production Grade Dispatch with Atomic Updates (Fixed API method).
        """
        
        # 1. Snapshot Current State for Logic (Bin Calculation)
        stock_snapshot = await FGStockDocument.find_one(
            FGStockDocument.date == payload.date,
            FGStockDocument.variant_name == payload.variant_name
        )
        
        if not stock_snapshot:
            raise HTTPException(404, "Stock record not found")

        # 2. Calculate Bin Transfer based on Snapshot
        bins_to_transfer = 0
        if payload.auto_transfer_bins and stock_snapshot.bin_size:
            calc_bins = payload.dispatched_qty // stock_snapshot.bin_size
            if calc_bins > 0:
                # Ensure we don't transfer more than we have
                bins_to_transfer = min(calc_bins, stock_snapshot.bins_available.rabs_bins)

        # 3. Define Atomic Update Query
        update_query = {
            "$inc": {
                "dispatched": payload.dispatched_qty,
                "closing_stock": -payload.dispatched_qty,
                "bins_available.rabs_bins": -bins_to_transfer,
                "bins_available.ijl_bins": bins_to_transfer
            },
            "$set": {
                "updated_at": get_ist_now()
            },
            "$push": {
                "transactions": {
                    "timestamp": get_ist_now(),
                    "transaction_type": "DISPATCH",
                    "quantity_change": -payload.dispatched_qty,
                    "bins_change": {
                        "rabs_bins": -bins_to_transfer,
                        "ijl_bins": bins_to_transfer
                    } if bins_to_transfer > 0 else None,
                    "user_id": current_user.emp_id,
                    "remarks": "Dispatch"
                }
            }
        }

        # 4. Execute Atomic Update using Raw Motor Collection
        # FIX: Changed get_motor_collection to get_pymongo_collection based on your error
        collection = FGStockDocument.get_pymongo_collection()
        
        query_filter = {
            "date": payload.date,
            "variant_name": payload.variant_name,
            "closing_stock": {"$gte": payload.dispatched_qty} # CRITICAL SAFETY CHECK (The Lock)
        }

        # Perform the update
        result_dict = await collection.find_one_and_update(
            filter=query_filter,
            update=update_query,
            return_document=True # Return the modified document
        )

        # 5. Handle Failure
        if not result_dict:
            # If it returns None, the condition failed (Stock < Qty)
            exists_check = await FGStockDocument.find_one(
                FGStockDocument.date == payload.date,
                FGStockDocument.variant_name == payload.variant_name
            )
            if not exists_check:
                raise HTTPException(404, "Stock record not found")
            else:
                logger.warning(f"Concurrent dispatch failed for {payload.variant_name}: Insufficient stock")
                raise HTTPException(400, "Insufficient stock to complete dispatch (Concurrent update detected)")

        # 6. Parse result back to Beanie Document
        return FGStockDocument(**result_dict)
    

    @staticmethod
    async def transfer_bins(payload: BinTransferRequest, current_user: Dict[str, Any]):
        stock = await FGStockService.get_or_create_stock(payload.date, payload.variant_name)
        
        if stock.bins_available.rabs_bins < payload.bins_to_transfer:
            raise HTTPException(400, "Insufficient RABS bins to transfer")
        
        stock.bins_available.rabs_bins -= payload.bins_to_transfer
        stock.bins_available.ijl_bins += payload.bins_to_transfer
        stock.updated_at = get_ist_now()
        
        stock.add_transaction(
            transaction_type="BIN_TRANSFER",
            quantity_change=0,
            bins_change={
                "rabs_bins": -payload.bins_to_transfer,
                "ijl_bins": payload.bins_to_transfer
            },
            user_id=current_user.get('emp_id'),
            remarks="Manual Bin Transfer"
        )
        await stock.save()
        return stock

    @staticmethod
    async def get_daily_stocks(date: str, part_description: Optional[str] = None) -> List[FGStockDocument]:
        """
        Generates daily stock for all active parts.
        Implements auto-rollover logic for every part.
        """
        stocks = []
        
        # Query Logic
        if part_description:
            part = await PartConfiguration.find_one(
                PartConfiguration.part_description == part_description,
                PartConfiguration.is_active == True
            )
            if part:
                variants = part.variations if part.variations else [part.part_description]
                for variant in variants:
                    stock = await FGStockService.get_or_create_stock(date, variant)
                    stocks.append(stock)
        else:
            # Fetch ALL active parts
            parts = await PartConfiguration.find(PartConfiguration.is_active == True).to_list()
            for part in parts:
                variants = part.variations if part.variations else [part.part_description]
                for variant in variants:
                    stock = await FGStockService.get_or_create_stock(date, variant)
                    stocks.append(stock)
        
        return stocks

    @staticmethod
    async def get_monthly_summary(year: int, month: int, part_description: Optional[str] = None):
        # 1. Fetch all daily stock records
        query = {"year": year, "month": month}
        if part_description:
            query["part_description"] = part_description

        stocks = await FGStockDocument.find(query).to_list()
        
        # 2. Group by Variant (e.g., "ALTROZ BRACKET-D LH")
        variant_map: Dict[str, List[FGStockDocument]] = {}
        for s in stocks:
            variant_map.setdefault(s.variant_name, []).append(s)

        summaries = []
        month_str = f"{year}-{str(month).zfill(2)}"

        # 3. Iterate through unique variants
        for variant, rows in variant_map.items():
            rows.sort(key=lambda x: x.date)

            # Calculate totals from Daily Stock
            total_production = sum(r.production_added for r in rows)
            total_dispatch = sum(r.dispatched for r in rows)
            total_inspection = sum(r.inspection_qty for r in rows)

            # --- LIVE LOOKUP ---
            parts = variant.rsplit(" ", 1)
            base_part_desc = parts[0] if len(parts) == 2 else variant

            # Query the Plan Table DIRECTLY (Source of Truth)
            monthly_plan_obj = await MonthlyProductionPlan.find_one(
                MonthlyProductionPlan.month == month_str,
                MonthlyProductionPlan.item_description == base_part_desc
            )
            
            current_schedule = monthly_plan_obj.schedule if monthly_plan_obj else None
            # ------------------------------

            # Calculate Averages
            days_count = len(rows) if rows else 1
            avg_daily_prod = float(total_production) / days_count
            avg_daily_dispatch = float(total_dispatch) / days_count

            # Calculate Percentage
            plan_achievement_pct = None
            if current_schedule and current_schedule > 0:
                plan_achievement_pct = (total_production / current_schedule) * 100.0

            # Determine Side for Response
            side = parts[1] if len(parts) == 2 and parts[1] in ("LH", "RH") else None

            summaries.append({
                "year": year,
                "month": month,
                "variant_name": variant,
                "part_description": base_part_desc,
                "side": side,
                "opening_stock_month": rows[0].opening_stock,
                "total_production": total_production,
                "total_dispatched": total_dispatch,
                "inspection_qty": total_inspection,
                "closing_stock_month": rows[-1].closing_stock,
                "monthly_plan": current_schedule,
                "plan_achievement_pct": plan_achievement_pct,
                "average_daily_production": avg_daily_prod,
                "average_daily_dispatch": avg_daily_dispatch
            })

        return summaries