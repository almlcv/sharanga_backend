
from fastapi import APIRouter, Depends, HTTPException, Body
from datetime import datetime
from datetime import datetime, timedelta
from bson import ObjectId
import calendar
from typing import Optional
from fastapi import Body, Query
from calendar import monthrange
from zoneinfo import ZoneInfo
from bson import ObjectId
from datetime import datetime, timezone
from RabsProject.config.ProductionPConfig import PART_CYCLE_TIME_MAP
from RabsProject.config.FgStockConfig import DEFAULT_DAILY_FG_STOCK_ENTRIES
from RabsProject.config.ProductionPConfig import DEFAULT_MONTHLY_PRODUCTION_PLAN_ENTRIES, ALTERNATE_PART_GROUPS, UNIQUE_PART_NAMES
from RabsProject.services.mongodb import MongoDBHandlerSaving
from RabsProject.pymodels.models import ProductionPlanDetail, User
from RabsProject.cores.auth.authorise import get_current_user, admin_required, production_required
from RabsProject.pymodels.models import ProductionPlanDetail, MonthlyProductionPlan, User


router = APIRouter(tags=["Production Plan Detail"])
mongo_handler = MongoDBHandlerSaving()
ist = datetime.now(ZoneInfo("Asia/Kolkata"))






def convert_objectid(doc):
    if isinstance(doc, ObjectId):
        return str(doc)
    if isinstance(doc, list):
        return [convert_objectid(i) for i in doc]
    if isinstance(doc, dict):
        return {k: convert_objectid(v) for k, v in doc.items()}
    return doc

def safe_float(value):
    try:
        return float(value)
    except (ValueError, TypeError):
        return 0.0

def safe_int(value):
    try:
        return int(value)
    except (ValueError, TypeError):
        return 0
    
def convert_objectid_to_str(obj):
    """Recursively convert ObjectId objects to strings in nested dictionaries/lists"""
    if isinstance(obj, ObjectId):
        return str(obj)
    elif isinstance(obj, dict):
        return {key: convert_objectid_to_str(value) for key, value in obj.items()}
    elif isinstance(obj, list):
        return [convert_objectid_to_str(item) for item in obj]
    return obj


#################################### Daily Production Detail ###########################################

@router.post("/save_production_plan_detail", response_model=dict)
def save_production_plan_detail(day:int, entry: ProductionPlanDetail, current_user: User = Depends(production_required)):
    try:

        # ✅ Validate part name
        if entry.part_description not in UNIQUE_PART_NAMES:
            raise HTTPException(status_code=400, detail="This part is not available in production.")

        now = datetime.now()
        year, month = now.year, now.month

        entry_dict = entry.dict()
        entry_dict["year"] = year
        entry_dict["month"] = month
        entry_dict['timestamp'] = datetime(year, month, day, tzinfo=timezone.utc)

        # ✅ Check if data already exists (same date + part_description)
        existing_entry = mongo_handler.production_plan_detail_collection.find_one({
            "year": year,
            "month": month,
            "timestamp": entry_dict['timestamp'],
            "part_description": entry.part_description
        })

        if existing_entry:
            raise HTTPException(status_code=400, detail="Data already exists for this date and part description.")


        if entry.part_description == "ALTROZ BRACKET-D" or entry.part_description == "ALTROZ BRACKET-E":
            entry_dict['machine'] = "120T"
        elif entry.part_description == "ALTROZ PES COVER A" or entry.part_description == "ALTROZ PES COVER B":
            entry_dict['machine'] = "250T"
        elif entry.part_description == "ALTROZ INNER LENS A" or entry.part_description == "ALTROZ SHADE A MG":
            entry_dict['machine'] = "470T"
        else:
            entry_dict['machine'] = "Unknown"

        inserted_id = mongo_handler.save_production_plan_detail(entry_dict)

        # --- Step 3: Update FG stock ---
        part_desc = entry.part_description

        # Helper function to update/insert FG stock
        def update_fg_stock(item_desc: str, add_qty):
            try:
                add_qty = int(add_qty or 0)
            except ValueError:
                add_qty = 0

            fg_entry = mongo_handler.Daily_Fg_stock_collection.find_one({
                "item_description": item_desc,
                "year": year,
                "month": month,
                "day": day
            })

            if fg_entry:
                current_stock = int(fg_entry.get("current") or 0)
                new_stock = current_stock + add_qty
                mongo_handler.Daily_Fg_stock_collection.update_one(
                    {"_id": fg_entry["_id"]},
                    {"$set": {"current": new_stock}}
                )

        # LH stock update
        if entry.actual_LH is not None:
            item_desc_lh = f"{part_desc} LH"
            update_fg_stock(item_desc_lh, entry.actual_LH)

        # RH stock update
        if entry.actual_RH is not None:
            item_desc_rh = f"{part_desc} RH"
            update_fg_stock(item_desc_rh, entry.actual_RH)

        return {
            "message": "Production plan detail saved successfully and FG stock updated",
            "entry_id": str(inserted_id)
        }

    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except HTTPException as he:
        # ✅ Reraise the actual HTTP error so FastAPI handles it properly
        raise he
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/update_production_plan_detail/{entry_id}", response_model=dict)
def update_production_plan_detail(
    entry_id: str, 
    updated_entry: ProductionPlanDetail, 
    current_user: User = Depends(production_required)):
    try:
        # --- Step 1: Check if entry exists in production plan ---
        existing_entry = mongo_handler.production_plan_detail_collection.find_one(
            {"_id": ObjectId(entry_id)}
        )
        if not existing_entry:
            raise HTTPException(status_code=404, detail="Production plan detail not found")

        # --- Step 2: Update allowed fields ---
        updated_dict = {
            "actual_RH": updated_entry.actual_RH,
            "actual_LH": updated_entry.actual_LH,
            "resp_person": updated_entry.resp_person
        }
        mongo_handler.production_plan_detail_collection.update_one(
            {"_id": ObjectId(entry_id)},
            {"$set": updated_dict}
        )

        # --- Step 3: Update FG stock ---
        today = datetime.now()
        year, month, day = today.year, today.month, today.day

        part_desc = updated_entry.part_description or existing_entry.get("part_description")

        # Helper function to update/insert FG stock
        def update_fg_stock(item_desc: str, add_qty):
            try:
                add_qty = int(add_qty or 0)   # 🔹 force to int
            except ValueError:
                add_qty = 0

            fg_entry = mongo_handler.Daily_Fg_stock_collection.find_one({
                "item_description": item_desc,
                "year": year,
                "month": month,
                "day": day
            })

            if fg_entry:
                current_stock = int(fg_entry.get("current") or 0)
                new_stock = current_stock + add_qty
                mongo_handler.Daily_Fg_stock_collection.update_one(
                    {"_id": fg_entry["_id"]},
                    {"$set": {"current": new_stock}}
                )


        # LH stock update
        if updated_entry.actual_LH is not None:
            item_desc_lh = f"{part_desc} LH"
            update_fg_stock(item_desc_lh, updated_entry.actual_LH)

        # RH stock update
        if updated_entry.actual_RH is not None:
            item_desc_rh = f"{part_desc} RH"
            update_fg_stock(item_desc_rh, updated_entry.actual_RH)

        return {
            "message": "Production plan detail updated successfully and FG stock synced",
            "entry_id": entry_id,
            "updated_fields": updated_dict
        }

    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/get_production_plan_details_by_month", response_model=dict)
def get_production_plan_details_by_month(
    month: Optional[int] = Query(None, ge=1, le=12),
    year: Optional[int] = Query(None, ge=2000, le=2100),
    current_user: User = Depends(production_required)
):
    try:
        # --- Determine target day ---
        today = datetime.now()
        if year == today.year and month == today.month:
            target_day = today.day
        else:
            target_day = monthrange(year, month)[1]

        # --- Fetch all production plan entries ---
        entries = list(mongo_handler.production_plan_detail_collection.find({
            "year": year,
            "month": month
        }))
        entries = convert_objectid(entries)

        # --- Fetch monthly summary ---
        month_str = f"{year}-{str(month).zfill(2)}"
        monthly_summaries = list(mongo_handler.monthly_production_plan_collection.find({
            "month": month_str
        }))

        unique_parts = {cfg["item_description"] for cfg in monthly_summaries}
        if len(unique_parts) != 6:
            raise HTTPException(
                status_code=400,
                detail=f"Please set the monthly schedule for {month_str}")



        # ✅ Build per-part monthly summary map
        monthly_summary_map = {
            summary["item_description"]: {
                "schedule": safe_float(summary.get("schedule", 0)),
                "dispatch_quantity_per_day": safe_float(summary.get("dispatch_quantity_per_day", 0)),
                "day_stock_to_kept": safe_float(summary.get("day_stock_to_kept", 0))
            }
            for summary in monthly_summaries
        }

        # --- Fetch FG stock for target day ---
        fg_stocks = list(mongo_handler.Daily_Fg_stock_collection.find({
            "year": year,
            "month": month,
            "day": target_day
        }, {"_id": 0, "item_description": 1, "current": 1, "dispatched": 1}))
        fg_map = {fg["item_description"]: fg for fg in fg_stocks}

        # --- Fetch last month FG stock ---
        if month == 1:
            prev_year, prev_month = year - 1, 12
        else:
            prev_year, prev_month = year, month - 1

        last_day_prev_month = monthrange(prev_year, prev_month)[1]
        last_month_fg = list(mongo_handler.Daily_Fg_stock_collection.find({
            "year": prev_year,
            "month": prev_month,
            "day": last_day_prev_month
        }, {"_id": 0, "item_description": 1, "current": 1}))
        last_fg_map = {fg["item_description"]: fg for fg in last_month_fg}

        # --- Build stock summary ---
        stock_summary = []
        unique_parts_seen = set()

        # ✅ Case 1: If entries exist
        if entries:
            for entry in entries:
                part = entry["part_description"]
                lh_desc, rh_desc = f"{part} LH", f"{part} RH"

                part_summary = monthly_summary_map.get(part, {})
                schedule = part_summary.get("schedule", 0)
                dispatch_quantity_per_day = part_summary.get("dispatch_quantity_per_day", 0)
                day_stock_to_kept = part_summary.get("day_stock_to_kept", 0)

                current_LH = fg_map.get(lh_desc, {}).get("current") or 0
                dispatch_LH = fg_map.get(lh_desc, {}).get("dispatched") or 0
                current_RH = fg_map.get(rh_desc, {}).get("current") or 0
                dispatch_RH = fg_map.get(rh_desc, {}).get("dispatched") or 0

                last_current_LH = last_fg_map.get(lh_desc, {}).get("current") or 0
                last_current_RH = last_fg_map.get(rh_desc, {}).get("current") or 0

                if part not in unique_parts_seen:
                    stock_summary.append({
                        "part_name": part,
                        "current_LH": current_LH,
                        "current_RH": current_RH,
                        "dispatch_LH": dispatch_LH,
                        "dispatch_RH": dispatch_RH,
                        "last_month_current_LH": last_current_LH,
                        "last_month_current_RH": last_current_RH,
                        "target_day_stock_to_kept_lh": day_stock_to_kept,
                        "target_day_stock_to_kept_rh": day_stock_to_kept,
                        "projected_stock_in_days_lh": current_LH / dispatch_quantity_per_day if dispatch_quantity_per_day else 0,
                        "projected_stock_in_days_rh": current_RH / dispatch_quantity_per_day if dispatch_quantity_per_day else 0,
                        "target_stock_in_numbers_lh": day_stock_to_kept * dispatch_quantity_per_day,
                        "target_stock_in_numbers_rh": day_stock_to_kept * dispatch_quantity_per_day
                    })
                    unique_parts_seen.add(part)


            for record in stock_summary:
                for key, value in record.items():
                    if isinstance(value, float):
                        record[key] = round(value, 2)

            return {
                "message": "Entries fetched with FG stock",
                "year": year,
                "month": month,
                "day": target_day,
                "schedule": schedule,
                "records": entries,
                "stock_summary": stock_summary
            }

        # ✅ Case 2: No entries → create defaults
        inserted_entries = []
        for entry in DEFAULT_MONTHLY_PRODUCTION_PLAN_ENTRIES:
            entry_copy = entry.copy()
            entry_copy["year"] = year
            entry_copy["month"] = month

            part_description = entry_copy.get("part_description")
            lh_desc, rh_desc = f"{part_description} LH", f"{part_description} RH"  # <-- define here

            # 🚨 Prevent duplicate insertion
            existing = mongo_handler.production_plan_detail_collection.find_one({
                "year": year,
                "month": month,
                "part_description": part_description
            })
            if existing:
                continue

            # --- Fetch monthly config for this part ---
            monthly_config = next(
                (cfg for cfg in monthly_summaries if cfg["item_description"] == part_description),
                None
            )

            if not monthly_config:
                raise HTTPException(
                    status_code=400,
                    detail=f"Monthly config not found for '{part_description}' in {month_str}"
                )

            schedule = float(monthly_config.get("schedule", 0))

            last_current_LH = last_fg_map.get(lh_desc, {}).get("current") or 0
            last_current_RH = last_fg_map.get(rh_desc, {}).get("current") or 0

            entry_copy["schedule"] = schedule
            entry_copy["timestamp"] = datetime(year, month, 1)  # start of month

            # --- Save to DB ---
            inserted_id = mongo_handler.save_production_plan_detail(entry_copy)
            entry_copy["_id"] = str(inserted_id)
            inserted_entries.append(entry_copy)



            # Use last month stock if current month stock is not present
            current_LH = fg_map.get(lh_desc, {}).get("current") or last_fg_map.get(lh_desc, {}).get("current") or 0
            dispatch_LH = fg_map.get(lh_desc, {}).get("dispatched") or 0
            current_RH = fg_map.get(rh_desc, {}).get("current") or last_fg_map.get(rh_desc, {}).get("current") or 0
            dispatch_RH = fg_map.get(rh_desc, {}).get("dispatched") or 0
            last_current_LH = last_fg_map.get(lh_desc, {}).get("current") or 0
            last_current_RH = last_fg_map.get(rh_desc, {}).get("current") or 0

            monthly_config = next((cfg for cfg in monthly_summaries if cfg["item_description"] == part_description), {})
            dispatch_quantity_per_day = safe_float(monthly_config.get("dispatch_quantity_per_day", 0))
            day_stock_to_kept = safe_float(monthly_config.get("day_stock_to_kept", 0))

            stock_summary.append({
                "part_name": part_description,
                "current_LH": current_LH,
                "current_RH": current_RH,
                "dispatch_LH": dispatch_LH,
                "dispatch_RH": dispatch_RH,
                "last_month_current_LH": last_current_LH,
                "last_month_current_RH": last_current_RH,
                "target_day_stock_to_kept_lh": day_stock_to_kept,
                "target_day_stock_to_kept_rh": day_stock_to_kept,
                "projected_stock_in_days_lh": current_LH / dispatch_quantity_per_day if dispatch_quantity_per_day else 0,
                "projected_stock_in_days_rh": current_RH / dispatch_quantity_per_day if dispatch_quantity_per_day else 0,
                "target_stock_in_numbers_lh": dispatch_LH * dispatch_quantity_per_day,
                "target_stock_in_numbers_rh": dispatch_RH * dispatch_quantity_per_day
            })

        return {
            "message": "Default entries created",
            "year": year,
            "month": month,
            "day": target_day,
            "records": convert_objectid(inserted_entries),
            "stock_summary": stock_summary
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

##################################### Monthly Production Detail #########################################

@router.post("/set_monthly_schedule_in_production_plan_sheet", response_model=dict)
def set_monthly_schedule_in_production_plan_sheet(config: MonthlyProductionPlan, current_user: User = Depends(production_required)):
    result = mongo_handler.monthly_insert_production_plan_entry(config.dict())

    # Convert any ObjectId to string
    if "upserted_id" in result and isinstance(result["upserted_id"], ObjectId):
        result["upserted_id"] = str(result["upserted_id"])

    if result.get("upserted_id"):
        message = "Monthly config inserted for item_description"
        inserted_id = result["upserted_id"]
    else:
        message = "Monthly config updated for item_description"
        inserted_id = None

    return {
        "message": message,
        "inserted_id": inserted_id,
        "result": result
    }



@router.put("/update_monthly_schedule_in_production_plan_sheet", response_model=dict)
def update_monthly_schedule_in_production_plan_sheet(config: MonthlyProductionPlan, current_user: User = Depends(production_required)):
    month_str = f"{config.year}-{str(config.month).zfill(2)}"

    result = mongo_handler.monthly_production_plan_collection.update_one(
        {
            "item_description": config.item_description,
            "month": month_str
        },
        {
            "$set": {
                "schedule": config.schedule,
                "timestamp": datetime(int(config.year), int(config.month), 1)
            }
        }
    )

    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Monthly config not found for item_description and month")

    return {
        "message": "Monthly config updated successfully",
        "modified_count": result.modified_count
    }


# @router.post("/generate_and_save_production_plan", response_model=dict)
# def generate_and_save_production_plan(
#     year: int, 
#     month: int, 
#     shift_hours: int, 
#     current_user: dict = Depends(production_required)
# ):


#     # Step 1: Check if already exists
#     existing_data = mongo_handler.production_plan_detail_collection.find_one({
#         "year": year,
#         "month": month
#     })

#     if existing_data:
#         delete_result = mongo_handler.production_plan_detail_collection.delete_many({
#             "year": year,
#             "month": month
#         })



#     shift_seconds = shift_hours * 3600
#     first_day = datetime(year, month, 1)
#     last_day = datetime(year, month, calendar.monthrange(year, month)[1])
#     week_number = 1
#     curr_day = first_day

#     all_daily_records = []


#     # ✅ Loop through default entries instead of DB
#     for entry in DEFAULT_MONTHLY_PRODUCTION_PLAN_ENTRIES:
#         part_name = entry["part_description"]
#         machine = entry["machine"]

#         # --- Fetch monthly config schedule ---
#         month_str = f"{year}-{str(month).zfill(2)}"
#         monthly_config = mongo_handler.monthly_production_plan_collection.find_one({
#             "item_description": part_name,
#             "month": month_str
#         })

#         if not monthly_config:
#             raise HTTPException(
#                 status_code=400,
#                 detail=f"Monthly config not found for '{part_name}' in {month_str}"
#             )

#         scheduled_qty = int(monthly_config.get("schedule", 0))
#         cycle_time = PART_CYCLE_TIME_MAP.get(part_name.upper(), 32)
#         daily_capacity = shift_seconds // cycle_time

#         # --- Day by day allocation ---
#         curr_day = first_day
#         week_number = 1
#         while curr_day <= last_day:
#             if curr_day.weekday() != 6:  # Skip Sundays
#                 # --- Alternation Logic (part-level) ---
#                 selected_for_week = True
#                 if machine in ALTERNATE_PART_GROUPS:
#                     for group in ALTERNATE_PART_GROUPS[machine]:
#                         if part_name in group:
#                             idx = (week_number - 1) % len(group)
#                             selected_base = group[idx]
#                             selected_for_week = (part_name == selected_base)
#                             break

#                 if not selected_for_week:
#                     curr_day += timedelta(days=1)
#                     if curr_day.weekday() == 0:  # Monday → new week
#                         week_number += 1
#                     continue

#                 # --- Already planned qty check ---
#                 already_planned_qty = sum(
#                     safe_int(doc.get("plan"))
#                     for doc in mongo_handler.production_plan_detail_collection.find({
#                         "part_description": part_name,
#                         "year": year,
#                         "month": month
#                     })
#                 )

#                 remaining = scheduled_qty - already_planned_qty
#                 today_qty = min(daily_capacity, remaining) if remaining > 0 else 0

#                 # --- Daily plan doc ---
#                 daily_doc = {
#                     "part_description": part_name,
#                     "machine": machine,
#                     "schedule": scheduled_qty,
#                     "plan": int(today_qty),
#                     "actual_RH": 0,
#                     "actual_LH": 0,
#                     "resp_person": "",
#                     "year": year,
#                     "month": month,
#                     "timestamp": datetime(curr_day.year, curr_day.month, curr_day.day),
#                 }

#                 inserted_id = mongo_handler.save_production_plan_detail(daily_doc)
#                 daily_doc["id"] = str(inserted_id)
#                 if "_id" in daily_doc:
#                     del daily_doc["_id"] 
#                 all_daily_records.append(daily_doc)

#             curr_day += timedelta(days=1)
#             if curr_day.weekday() == 0:  # Monday → new week
#                 week_number += 1

#     return {
#         "message": "Daily flat plan generated from DEFAULT entries + monthly schedule",
#         "year": year,
#         "month": month,
#         "records": all_daily_records
#     }


