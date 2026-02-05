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

        try:
            dt = datetime.strptime(date, "%Y-%m-%d")
            year, month, day = dt.year, dt.month, dt.day
        except ValueError:
            raise HTTPException(400, f"Invalid date format: {date}")

        stock = await FGStockDocument.find_one(
            FGStockDocument.date == date,
            FGStockDocument.variant_name == variant_name
        )

        if stock:
            return stock

        parts = variant_name.rsplit(" ", 1)
        if len(parts) == 2 and parts[1] in ("LH", "RH"):
            part_desc = parts[0]
            side = parts[1]
        else:
            part_desc = variant_name
            side = None

        part_config = await PartConfiguration.find_one(
            PartConfiguration.part_description == part_desc,
            PartConfiguration.is_active == True
        )

        if not part_config:
            raise HTTPException(404, f"Part configuration not found for '{part_desc}'")

        bin_size = part_config.bin_settings.get(variant_name) if part_config.bin_settings else None

        month_str = f"{year}-{str(month).zfill(2)}"
        monthly_plan = await MonthlyProductionPlan.find_one(
            MonthlyProductionPlan.month == month_str,
            MonthlyProductionPlan.item_description == part_desc
        )

        monthly_schedule = monthly_plan.schedule if monthly_plan else None
        daily_target = None
        if monthly_schedule:
            working_days = sum(
                1 for d in range(1, 32)
                if datetime(year, month, d).weekday() != 6
            )
            daily_target = int(monthly_schedule / working_days)

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
        return stock

    # -------------------------
    # Hourly → FG Sync (Excel SUM)
    # -------------------------

    @staticmethod
    async def update_from_hourly_production(
        doc: HourlyProductionDocument,
        user_id: Optional[str] = None
    ):

        variant_name = f"{doc.part_description} {doc.side}" if doc.side else doc.part_description

        stock = await FGStockService.get_or_create_stock(doc.date, variant_name)

        hourly_docs = await HourlyProductionDocument.find(
            HourlyProductionDocument.date == doc.date,
            HourlyProductionDocument.part_description == doc.part_description,
            HourlyProductionDocument.side == doc.side
        ).to_list()

        production_qty = sum(h.totals.total_ok_qty for h in hourly_docs)

        old_production = stock.production_added
        stock.production_added = production_qty

        stock.recalculate_closing_stock()
        stock.last_synced_at = get_ist_now()

        stock.add_transaction(
            transaction_type="PRODUCTION",
            quantity_change=production_qty - old_production,
            user_id=user_id,
            reference_doc_no=str(doc.id),
            remarks="Auto-sync from hourly production"
        )

        await stock.save()

    # -------------------------
    # Inspection (replaces manual adjustment)
    # -------------------------

    @staticmethod
    async def manual_stock_adjustment(
        payload: ManualStockAdjustmentRequest,
        current_user: Dict[str, Any]
    ) -> FGStockDocument:

        stock = await FGStockService.get_or_create_stock(
            payload.date,
            payload.variant_name
        )

        inspection_qty = payload.inspection_qty

        if inspection_qty < 0:
            raise HTTPException(400, "Inspection quantity cannot be negative")

        # Safety: inspection cannot exceed production
        if inspection_qty > stock.production_added:
            raise HTTPException(400, "Inspection cannot exceed production")

        old_inspection = stock.inspection_qty
        stock.inspection_qty = inspection_qty

        stock.recalculate_closing_stock()

        if stock.closing_stock < 0:
            raise HTTPException(400, "Inspection would result in negative stock")

        stock.add_transaction(
            transaction_type="INSPECTION",
            quantity_change=-(inspection_qty - old_inspection),
            user_id=current_user.emp_id,
            remarks=payload.remarks
        )

        await stock.save()
        return stock

    # -------------------------
    # Bin / Dispatch
    # -------------------------

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

        stock = await FGStockService.get_or_create_stock(payload.date, payload.variant_name)

        if stock.closing_stock < payload.dispatched_qty:
            raise HTTPException(400, "Insufficient stock")

        stock.dispatched += payload.dispatched_qty
        stock.recalculate_closing_stock()

        bins_change = None
        if payload.auto_transfer_bins and stock.bin_size:
            bins_to_transfer = payload.dispatched_qty // stock.bin_size
            bins_to_transfer = min(bins_to_transfer, stock.bins_available.rabs_bins)

            if bins_to_transfer > 0:
                stock.bins_available.rabs_bins -= bins_to_transfer
                stock.bins_available.ijl_bins += bins_to_transfer
                bins_change = {
                    "rabs_bins": -bins_to_transfer,
                    "ijl_bins": bins_to_transfer
                }

        stock.add_transaction(
            transaction_type="DISPATCH",
            quantity_change=-payload.dispatched_qty,
            bins_change=bins_change,
            user_id=current_user.emp_id,
            remarks="Dispatch"
        )

        await stock.save()
        return stock

    # -------------------------
    # Monthly Summary (Inspection aware)
    # -------------------------

    @staticmethod
    async def get_monthly_summary(year: int, month: int, part_description: Optional[str] = None):

        query = {"year": year, "month": month}
        if part_description:
            query["part_description"] = part_description

        stocks = await FGStockDocument.find(query).to_list()

        variant_map: Dict[str, List[FGStockDocument]] = {}
        for s in stocks:
            variant_map.setdefault(s.variant_name, []).append(s)

        summaries = []

        for variant, rows in variant_map.items():
            rows.sort(key=lambda x: x.date)

            total_production = sum(r.production_added for r in rows)
            total_dispatch = sum(r.dispatched for r in rows)
            total_inspection = sum(r.inspection_qty for r in rows)

            summaries.append({
                "variant_name": variant,
                "opening_stock_month": rows[0].opening_stock,
                "closing_stock_month": rows[-1].closing_stock,
                "total_production": total_production,
                "total_dispatched": total_dispatch,
                "total_inspection": total_inspection,
            })

        return summaries
