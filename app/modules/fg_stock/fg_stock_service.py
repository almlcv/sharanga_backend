from datetime import datetime, timedelta
from app.shared.timezone import get_ist_now
from app.shared.variant_utils import construct_variant_name, parse_variant_name
from typing import List, Optional, Dict, Any
from fastapi import HTTPException
import logging
import asyncio

from app.core.models.fg_stock import FGStockDocument
from app.core.models.parts_config import PartConfiguration
from app.core.models.production.production_plan import MonthlyProductionPlan
from app.core.models.production.hourly_production import HourlyProductionDocument
from app.core.schemas.fg_stock import (
    ManualStockAdjustmentRequest,
    DispatchRequest,
)

logger = logging.getLogger(__name__)


class FGStockService:
    """
    FG Stock service.
    
    ARCHITECTURE DECISION:
    - Store of Truth: Daily FG Stock Documents.
    - Monthly Reports: Aggregated on-demand using MongoDB Pipeline.
    - Benefit: No sync issues, simpler code, always accurate data.
    """

    @staticmethod
    async def get_or_create_stock(
        date: str,
        variant_name: str,
        auto_rollover: bool = True
    ) -> FGStockDocument:
        """
        Retrieves or creates a stock document.
        
        ENHANCEMENT: Self-healing logic.
        If a record exists but has no monthly plan (null), it will check the 
        MonthlyProductionPlan collection again and update itself automatically.
        This ensures plans added late in the month are reflected everywhere.
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

        # 2. Parse Part Details (LH/RH Logic)
        part_desc, side = parse_variant_name(variant_name)

        # 3. Fetch Part Configuration (Source of Truth)
        part_config = await PartConfiguration.find_one(
            PartConfiguration.part_description == part_desc,
            PartConfiguration.is_active == True
        )

        if not part_config:
            logger.error(f"Part configuration not found for '{part_desc}' (variant: '{variant_name}')")
            raise HTTPException(404, f"Part configuration not found for '{part_desc}'. Please ensure the part is configured in the system.")

        # ==========================================
        # 4. FETCH MONTHLY PLAN LOGIC (Reusable)
        # ==========================================
        month_str = f"{year}-{str(month).zfill(2)}"
        monthly_plan = await MonthlyProductionPlan.find_one(
            MonthlyProductionPlan.month == month_str,
            MonthlyProductionPlan.item_description == part_desc
        )

        monthly_schedule = monthly_plan.schedule if monthly_plan else None
        daily_target = None
        
        if monthly_schedule:
            # Calculate working days (exclude Sundays)
            from calendar import monthrange

            _, num_days = monthrange(year, month)

            # Parse the current stock date
            current_date = datetime.strptime(date, "%Y-%m-%d").date()
            month_start = datetime(year, month, 1).date()

            # If we're already in this month, count remaining working days
            if current_date >= month_start:
                remaining_days = sum(
                    1 for d in range(current_date.day, num_days + 1)
                    if datetime(year, month, d).weekday() != 6
                )
                working_days = remaining_days if remaining_days > 0 else 1
            else:
                # Future month - use full month
                working_days = sum(
                    1 for d in range(1, num_days + 1)
                    if datetime(year, month, d).weekday() != 6
                )

            daily_target = int(monthly_schedule / working_days) if working_days > 0 else 0
        # ==========================================

        # 5. Logic: Create New OR Self-Heal Existing
        collection = FGStockDocument.get_pymongo_collection()

        if not stock:
            # --- CASE A: Creating a NEW record ---
            
            # SMART ROLLOVER (Automated Opening Stock)
            opening_stock = 0
            if auto_rollover:
                # Strategy A: Check yesterday
                prev_date = (dt - timedelta(days=1)).strftime("%Y-%m-%d")
                prev_stock = await FGStockDocument.find_one(
                    FGStockDocument.date == prev_date,
                    FGStockDocument.variant_name == variant_name
                )
                # Strategy B: Find LATEST record
                if not prev_stock:
                    prev_stock = await FGStockDocument.find(
                        FGStockDocument.variant_name == variant_name,
                        FGStockDocument.date < date
                    ).sort(-FGStockDocument.date).limit(1).to_list()
                    prev_stock = prev_stock[0] if prev_stock else None
                
                if prev_stock:
                    opening_stock = prev_stock.closing_stock
                    logger.info(f"📦 SMART ROLLOVER: Stock for {variant_name} on {date} initialized from {prev_stock.date} (closing: {opening_stock})")
                else:
                    logger.info(f"📦 NO PREVIOUS STOCK: {variant_name} on {date} - starting with opening_stock=0")

            # Create the document
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
                closing_stock=opening_stock, # Initialize closing = opening
                monthly_schedule=monthly_schedule,
                daily_target=daily_target,
                version=0
            )
            await stock.insert()
            logger.info(f"✨ CREATED NEW: FG Stock record for {variant_name} on {date} (opening={opening_stock}, closing={opening_stock})")

        else:
            # --- CASE B: Healing an EXISTING record ---
            # Check if the plan data in DB is stale (null) or different from current plan
            needs_update = False
            
            if stock.monthly_schedule != monthly_schedule:
                needs_update = True
            
            # Also check daily target (in case schedule changed but number remained same by chance)
            # or if schedule is null but daily_target exists (data mismatch)
            if stock.daily_target != daily_target:
                needs_update = True

            if needs_update:
                # Update the existing document in place
                await collection.update_one(
                    {"_id": stock.id},
                    {
                        "$set": {
                            "monthly_schedule": monthly_schedule,
                            "daily_target": daily_target,
                            "updated_at": get_ist_now()
                        }
                    }
                )
                # Update local object so the API returns the new value immediately
                stock.monthly_schedule = monthly_schedule
                stock.daily_target = daily_target
                logger.info(f"🔧 HEALED EXISTING: Stock plan for {variant_name} on {date}: Schedule={monthly_schedule}, Target={daily_target}")
            else:
                logger.info(f"📋 FOUND EXISTING: FG Stock record for {variant_name} on {date} (no healing needed)")

        return stock

    @staticmethod
    async def update_from_hourly_production(
        doc: HourlyProductionDocument,
        user_id: Optional[str] = None
    ):
        """
        Thread-safe production sync with optimistic locking.
        
        FIXED: Uses consistent variant_name construction via utility function.
        ENHANCED: Better error handling and logging for debugging.
        """
        # Construct variant name consistently
        variant_name = construct_variant_name(doc.part_description, doc.side)
        
        logger.info(
            f"🔄 SYNC START: Syncing hourly production to FG stock: "
            f"part={doc.part_description}, side={doc.side}, variant={variant_name}, date={doc.date}, "
            f"total_ok_qty={doc.totals.total_ok_qty}"
        )
        
        # Calculate Total Production for this part/date (read-only operation)
        hourly_docs = await HourlyProductionDocument.find(
            HourlyProductionDocument.date == doc.date,
            HourlyProductionDocument.part_description == doc.part_description,
            HourlyProductionDocument.side == doc.side
        ).to_list()

        production_qty = sum(h.totals.total_ok_qty for h in hourly_docs)
        
        logger.info(
            f"📊 PRODUCTION CALC: Found {len(hourly_docs)} hourly documents for {variant_name} on {doc.date}. "
            f"Total OK qty: {production_qty}"
        )
        
        if production_qty == 0:
            logger.warning(f"⚠️  ZERO PRODUCTION: No production data found for {variant_name} on {doc.date}")
        
        # Atomic update with optimistic locking
        collection = FGStockDocument.get_pymongo_collection()
        
        max_retries = 3
        for attempt in range(max_retries):
            try:
                # Get or create stock document
                stock = await FGStockService.get_or_create_stock(doc.date, variant_name)
                current_version = stock.version
                old_production = stock.production_added
                
                # Calculate changes
                production_change = production_qty - old_production
                
                logger.info(
                    f"🔄 ATTEMPT {attempt + 1}/{max_retries}: Updating FG stock for {variant_name}. "
                    f"Old production: {old_production}, New production: {production_qty}, "
                    f"Change: {production_change}, Version: {current_version}"
                )
                
                # Atomic update with version check
                update_query = {
                    "$set": {
                        "production_added": production_qty,
                        "last_synced_at": get_ist_now(),
                        "updated_at": get_ist_now(),
                        "version": current_version + 1
                    },
                    "$inc": {
                        "closing_stock": production_change
                    },
                    "$push": {
                        "transactions": {
                            "timestamp": get_ist_now(),
                            "transaction_type": "PRODUCTION",
                            "quantity_change": production_change,
                            "user_id": user_id,
                            "reference_doc_no": str(doc.id),
                            "remarks": f"Auto-sync from hourly production (doc_no: {doc.doc_no})"
                        }
                    }
                }
                
                result = await collection.update_one(
                    filter={
                        "date": doc.date,
                        "variant_name": variant_name,
                        "version": current_version 
                    },
                    update=update_query
                )
                
                if result.modified_count > 0:
                    logger.info(
                        f"✅ SYNC SUCCESS: Successfully synced production for {variant_name} on {doc.date}: "
                        f"{old_production} → {production_qty} (change: {production_change}, attempt {attempt + 1})"
                    )
                    return
                
                # Version conflict - retry with exponential backoff
                logger.warning(f"⚠️  VERSION CONFLICT: {variant_name} on attempt {attempt + 1}, retrying...")
                await asyncio.sleep(0.1 * (2 ** attempt))  # 0.1s, 0.2s, 0.4s
                
            except Exception as e:
                logger.error(
                    f"❌ SYNC ERROR (attempt {attempt + 1}/{max_retries}) for {variant_name}: {e}",
                    exc_info=True
                )
                if attempt == max_retries - 1:
                    raise
                await asyncio.sleep(0.1 * (2 ** attempt))
        
        raise HTTPException(
            409, 
            f"Failed to sync production for {variant_name} after {max_retries} retries (concurrent modification)"
        )

    @staticmethod
    async def manual_stock_adjustment(
        payload: ManualStockAdjustmentRequest,
        current_user: Dict[str, Any]
    ) -> FGStockDocument:
        """
        Atomic manual stock adjustment.
        """
        
        # Validate
        if payload.inspection_qty < 0:
            raise HTTPException(400, "Inspection quantity cannot be negative")
        
        # Ensure stock document exists
        stock = await FGStockService.get_or_create_stock(payload.date, payload.variant_name)
        
        # Capture version for Optimistic Locking
        current_version = stock.version
        
        # Atomic update with safety check
        collection = FGStockDocument.get_pymongo_collection()
        
        # Calculate what closing stock would be
        potential_closing = (
            stock.opening_stock +
            stock.production_added -
            payload.inspection_qty -
            stock.dispatched
        )
        
        if potential_closing < 0:
            raise HTTPException(
                400,
                f"Adjustment would result in negative stock: {potential_closing}"
            )
        
        old_inspection = stock.inspection_qty
        inspection_change = payload.inspection_qty - old_inspection
        
        update_query = {
            "$set": {
                "inspection_qty": payload.inspection_qty,
                "closing_stock": potential_closing,
                "updated_at": get_ist_now()
            },
            "$inc": {
                "version": 1
            },
            "$push": {
                "transactions": {
                    "timestamp": get_ist_now(),
                    "transaction_type": "INSPECTION",
                    "quantity_change": -inspection_change, 
                    "user_id": current_user.emp_id, 
                    "remarks": payload.remarks
                }
            }
        }
        
        # Add version check to filter to prevent race conditions
        result_dict = await collection.find_one_and_update(
            filter={
                "date": payload.date,
                "variant_name": payload.variant_name,
                "version": current_version
            },
            update=update_query,
            return_document=True
        )
        
        if not result_dict:
            # Distinguish between "Not Found" and "Version Conflict"
            fresh_stock = await FGStockDocument.find_one(
                FGStockDocument.date == payload.date,
                FGStockDocument.variant_name == payload.variant_name
            )
            
            if not fresh_stock:
                raise HTTPException(404, "Stock record not found")
            
            # If the record exists, the update failed due to version mismatch
            raise HTTPException(409, "Record was modified by another user. Please try again.")
        
        logger.info(
            f"Manual adjustment for {payload.variant_name} on {payload.date}: "
            f"Inspection {old_inspection} → {payload.inspection_qty}"
        )
        
        return FGStockDocument(**result_dict)
    

    @staticmethod
    async def record_dispatch(
        payload: DispatchRequest,
        current_user: Dict[str, Any]
    ) -> FGStockDocument:
        """
        Record dispatch transaction and reduce available stock.
        
        UPDATED: Now creates the daily record if it doesn't exist (fixes 404 error).
        """
        
        # FIX 1: Ensure the stock document exists for this date.
        # This handles the rollover (getting opening stock from previous days) automatically.
        stock = await FGStockService.get_or_create_stock(payload.date, payload.variant_name)
        
        # FIX 2: Atomic update with safety check
        collection = FGStockDocument.get_pymongo_collection()
        
        update_query = {
            "$inc": {
                "dispatched": payload.dispatched_qty,
                "closing_stock": -payload.dispatched_qty,
                "version": 1
            },
            "$set": {
                "updated_at": get_ist_now()
            },
            "$push": {
                "transactions": {
                    "timestamp": get_ist_now(),
                    "transaction_type": "DISPATCH",
                    "quantity_change": -payload.dispatched_qty,
                    "user_id": current_user.emp_id,
                    "remarks": "Dispatch"
                }
            }
        }

        # We use optimistic locking here (check version)
        # Note: We use the version from the object we just fetched/found
        current_version = stock.version

        result_dict = await collection.find_one_and_update(
            filter={
                "date": payload.date,
                "variant_name": payload.variant_name,
                "version": current_version, # Ensure no one else modified it since we fetched it
                "closing_stock": {"$gte": payload.dispatched_qty}  # Safety: Prevent negative
            },
            update=update_query,
            return_document=True
        )

        if not result_dict:
            # If it failed, it's likely a race condition (version mismatch) or insufficient stock
            # Re-fetch to give a specific error message
            fresh_stock = await FGStockDocument.find_one(
                FGStockDocument.date == payload.date,
                FGStockDocument.variant_name == payload.variant_name
            )
            
            if not fresh_stock:
                raise HTTPException(404, "Stock record disappeared (race condition)")
            
            if fresh_stock.closing_stock < payload.dispatched_qty:
                logger.warning(f"Dispatch failed for {payload.variant_name}: Insufficient stock")
                raise HTTPException(
                    400, 
                    f"Insufficient stock. Available: {fresh_stock.closing_stock}, Requested: {payload.dispatched_qty}"
                )
            
            # If stock was sufficient, it was a version conflict
            raise HTTPException(409, "Record was modified by another user. Please try again.")

        logger.info(f"Dispatched {payload.dispatched_qty} units of {payload.variant_name} on {payload.date}")
        
        # We do NOT trigger monthly summary update here (as per previous architecture decision)
        
        return FGStockDocument(**result_dict)

    @staticmethod
    async def get_monthly_summary(
        year: int, 
        month: int, 
        part_description: Optional[str] = None
    ) -> List[Dict]:
        """
        Get monthly summary by AGGREGATING daily records on the fly.
        
        FIX: Uses raw Motor client for aggregation AND raw dict for Beanie find query
        to avoid 'ExpressionField' errors.
        """
        
        # 1. Build Match Stage
        match_query = {
            "year": year,
            "month": month
        }
        if part_description:
            match_query["part_description"] = part_description

        # 2. Define Aggregation Pipeline
        pipeline = [
            # Step 1: Filter for the specific month/year/part
            {"$match": match_query},
            
            # Step 2: Sort by date to ensure $first (Opening) and $last (Closing) work correctly
            {"$sort": {"date": 1}},
            
            # Step 3: Group by Variant
            {
                "$group": {
                    "_id": "$variant_name",
                    "year": {"$first": "$year"},
                    "month": {"$first": "$month"},
                    "variant_name": {"$first": "$variant_name"},
                    "part_description": {"$first": "$part_description"},
                    "side": {"$first": "$side"},
                    
                    # Financials: Sum the daily changes
                    "total_production": {"$sum": "$production_added"},
                    "total_inspection": {"$sum": "$inspection_qty"},
                    "total_dispatched": {"$sum": "$dispatched"},
                    
                    # Boundaries: First day's opening, Last day's closing
                    "opening_stock_month": {"$first": "$opening_stock"},
                    "closing_stock_month": {"$last": "$closing_stock"},
                    
                    # Statistics
                    "working_days": {
                        "$sum": {
                            "$cond": [{"$gt": ["$production_added", 0]}, 1, 0]
                        }
                    }
                }
            },
            
            # Step 4: Project (Format the output and calculate averages)
            {
                "$project": {
                    "_id": 0, # Remove internal MongoDB ID
                    "year": 1,
                    "month": 1,
                    "variant_name": 1,
                    "part_description": 1,
                    "side": 1,
                    "opening_stock_month": 1,
                    "closing_stock_month": 1,
                    "total_production": 1,
                    "total_inspection": 1,
                    "total_dispatched": 1,
                    "working_days": 1,
                    
                    # Calculate Averages on the fly
                    "average_daily_production": {
                        "$cond": [
                            {"$gt": ["$working_days", 0]}, 
                            {"$divide": ["$total_production", "$working_days"]}, 
                            0
                        ]
                    },
                    "average_daily_dispatch": {
                        "$cond": [
                            {"$gt": ["$working_days", 0]}, 
                            {"$divide": ["$total_dispatched", "$working_days"]}, 
                            0
                        ]
                    }
                }
            }
        ]

        # 3. Execute Aggregation using RAW Motor Client
        collection = FGStockDocument.get_pymongo_collection()
        cursor = collection.aggregate(pipeline)
        results = await cursor.to_list(None)
        
        # 4. Enrich with Monthly Plan
        month_str = f"{year}-{str(month).zfill(2)}"
        
        if results:
            part_descs = list(set(r['part_description'] for r in results))
            
            # FIX: Use raw dict query instead of .in_() to prevent TypeError
            plans = await MonthlyProductionPlan.find({
                "month": month_str,
                "item_description": {"$in": part_descs}
            }).to_list()
            
            plan_map = {p.item_description: p.schedule for p in plans}
            
            for r in results:
                schedule = plan_map.get(r['part_description'])
                r['monthly_plan'] = schedule
                
                if schedule and schedule > 0:
                    r['plan_achievement_pct'] = round((r['total_production'] / schedule) * 100.0, 2)
                else:
                    r['plan_achievement_pct'] = None
                
                # Rename for consistency with schema
                r['inspection_qty'] = r.pop('total_inspection')

        return results

    @staticmethod
    async def get_daily_stocks(
        date: str, 
        part_description: Optional[str] = None
    ) -> List[FGStockDocument]:
        """
        Get daily stock for all active parts.
        Auto-creates missing records with rollover.
        Skips invalid part configurations gracefully.
        """
        stocks = []
        
        if part_description:
            part = await PartConfiguration.find_one(
                PartConfiguration.part_description == part_description,
                PartConfiguration.is_active == True
            )
            if part:
                variants = part.variations if part.variations else [part.part_description]
                for variant in variants:
                    try:
                        stock = await FGStockService.get_or_create_stock(date, variant)
                        stocks.append(stock)
                    except Exception as e:
                        logger.warning(f"Failed to get stock for variant '{variant}': {str(e)}")
                        continue
        else:
            # Fetch ALL active parts
            parts = await PartConfiguration.find(PartConfiguration.is_active == True).to_list()
            for part in parts:
                # Skip parts with invalid descriptions
                if not part.part_description or part.part_description.strip() == "":
                    logger.warning(f"Skipping part configuration with invalid description: {part.part_description}")
                    continue
                
                variants = part.variations if part.variations else [part.part_description]
                for variant in variants:
                    try:
                        stock = await FGStockService.get_or_create_stock(date, variant)
                        stocks.append(stock)
                    except Exception as e:
                        logger.warning(f"Failed to get stock for variant '{variant}': {str(e)}")
                        continue
        
        return stocks