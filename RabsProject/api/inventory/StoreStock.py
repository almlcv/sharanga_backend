from copy import deepcopy
from datetime import datetime, date, timezone
from fastapi import APIRouter, Depends, HTTPException, Path, Query
import os, sys
from pymongo import DESCENDING
from datetime import timedelta
from zoneinfo import ZoneInfo
from dotenv import load_dotenv
import yaml
from fastapi import APIRouter, Depends, HTTPException
load_dotenv()
HOSTING_LINK = os.getenv("HOSTING_LINK", "http://127.0.0.1:8015") 

from RabsProject.pymodels.models import *
from RabsProject.config.StoreStockConfig import DEFAULT_DAILY_STORE_STOCK_ENTRIES
from RabsProject.services.mongodb import MongoDBHandlerSaving  
from RabsProject.cores.auth.authorise import get_current_user, admin_required, production_required



router = APIRouter(tags=["Store Stock Monitoring Board"])

mongo_handler = MongoDBHandlerSaving()



def safe_int(value):
    try:
        if isinstance(value, (int, float)):
            return int(value)
        return int(float(value.strip()))
    except Exception as e:
        print(f"[safe_int] Failed to convert: {value} ({type(value)}) -> {e}")
        return 0


def shift_location_priorities(location: LocationPriority) -> LocationPriority:
    loc = location.dict()

    def is_empty(val):
        return val is None or val == "" or val == 0 or val == "0"

    # Shift up if p1 is empty
    if is_empty(loc.get("p1")):
        loc["p1"] = loc.get("p2")
        loc["p2"] = loc.get("p3")
        loc["p3"] = None

    # After above, check again: if p2 is now empty, shift p3 → p2 and clear p3
    if is_empty(loc.get("p2")):
        loc["p2"] = loc.get("p3")
        loc["p3"] = None

    return LocationPriority(**loc)

########################################## DAILY STORE STOCK  ##########################################

@router.post("/submit_store_stock_monitoring_sheet_entry", response_model=dict)
def submit_store_stock_monitoring_sheet_entry_daily(
    entry: StoreStockMonitoringSheet, 
    current_user: User = Depends(production_required) ):
    
    
    now = datetime.now()
    year = now.year
    month = now.month
    day = now.day
    month_str = datetime.now().strftime("%Y-%m") 
    # Fetch monthly config (numeric format)
    monthly_config = mongo_handler.get_store_stock_entries_by_month(
        entry.item_description, month_str=month_str
    )
    if not monthly_config:
        raise HTTPException(
            status_code=400, 
            detail=f"Monthly schedule stock not found for item_description={entry.item_description}, month={month}, year={year}"
        )

    # Prepare entry dict for insertion
    entry_dict = entry.dict()
    entry_dict["schedule"] = monthly_config.get("schedule", 0)
    entry_dict["day"] = day
    entry_dict["month"] = month
    entry_dict["year"] = year
    entry_dict["timestamp"] = now.strftime("%d-%m-%Y %I:%M:%S %p")

    inserted_id = mongo_handler.insert_store_stock_entry(entry_dict)
    return {"message": "Entry submitted", "id": inserted_id}



@router.put("/update_store_stock_monitoring_sheet_entry/{entry_id}", response_model=dict)
def update_store_stock_monitoring_sheet_entry(
    entry_id: str,
    updated_entry: StoreStockMonitoringSheet,
    current_user: User = Depends(production_required)
):
    try:
        # Get old entry before update
        old_entry = mongo_handler.get_store_stock_entry_by_id(entry_id)
        if not old_entry:
            raise HTTPException(status_code=404, detail="Entry not found")

        updated_entry.location = shift_location_priorities(updated_entry.location)
        update_data = updated_entry.dict(exclude_unset=True)

        # 🔹 Auto-calc current again on update
        total = 0
        for key in ["p1", "p2", "p3"]:
            val = getattr(updated_entry.location, key, None)
            if val:
                nums = [float(n) for n in re.findall(r"\d+(?:\.\d+)?", str(val))]
                total += sum(nums)
        update_data["current"] = total  

        update_data["timestamp"] = datetime.now().strftime("%d-%m-%Y %I:%M:%S %p")

        # ---- AUDIT LOGGING ----
        audit_changes = {}
        if "actual" in update_data and  update_data["actual"] != 0:
            audit_changes["actual"] = {
                "old": old_entry.get("actual"),
                "new": update_data["actual"]
            }
        if "location" in update_data and update_data["location"] != old_entry.get("location"):
            audit_changes["location"] = {
                "old": old_entry.get("location"),
                "new": update_data["location"]
            }

        if audit_changes:
            audit_log = {
                "entry_id": entry_id,
                "changes": audit_changes,
                "updated_by": {
                    "name": current_user.name,
                    "email": current_user.email,
                    "role": current_user.role
                },
                "timestamp":  datetime.now(ZoneInfo("Asia/Kolkata")).strftime("%d-%m-%Y %I:%M:%S %p"),
                "year_month": datetime.now(ZoneInfo("Asia/Kolkata")).strftime("%Y-%m")
            }
            mongo_handler.store_stock_audit_collection.insert_one(audit_log)

        # -----------------------

        mongo_handler.update_store_stock_entry(entry_id, update_data)
        return {
            "message": "Entry updated successfully",
            "id": entry_id,
            "updated_data": update_data
        }

    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/get_daily_store_stock_monitoring_sheets/{year}/{month}/{day}")
async def get_daily_store_stock_monitoring_sheets(
    year: int, month: int, day: int, 
    current_user: User = Depends(production_required)
):
    try:
        query_date = datetime(year, month, day)
        month_key = f"{year}-{str(month).zfill(2)}"

        # 1️⃣ Case: entries already exist for today
        existing_entries = list(mongo_handler.store_stock_collection.find({
            "year": year,
            "month": month,
            "day": day
        }))

        if existing_entries:
            updated_entries = []
            for entry in existing_entries:
                monthly_config = mongo_handler.get_store_stock_entries_by_month(
                    entry["item_description"], month_str=month_key
                )
                entry["schedule"] = monthly_config.get("schedule", 0) if monthly_config else 0
                entry_copy = entry.copy()
                entry_copy["_id"] = str(entry_copy["_id"])
                updated_entries.append(entry_copy)
            return {"source": "today", "entries": updated_entries}

        # 2️⃣ Case: clone from most recent past entry
        previous_entry = mongo_handler.store_stock_collection.find(
            {
                "$or": [
                    {"year": {"$lt": year}},
                    {"year": year, "month": {"$lt": month}},
                    {"year": year, "month": month, "day": {"$lt": day}}
                ]
            }
        ).sort([("year", -1), ("month", -1), ("day", -1)]).limit(1)

        past_entries = list(previous_entry)

        if past_entries:
            last_date = past_entries[0]["year"], past_entries[0]["month"], past_entries[0]["day"]
            entries_to_copy = list(mongo_handler.store_stock_collection.find({
                "year": last_date[0],
                "month": last_date[1],
                "day": last_date[2]
            }))

            cloned_entries = []
            for entry in entries_to_copy:
                entry.pop("_id", None)

                # 🔹 Always refresh schedule
                monthly_config = mongo_handler.get_store_stock_entries_by_month(
                    entry["item_description"], month_str=month_key
                )
                entry["schedule"] = monthly_config.get("schedule", 0) if monthly_config else 0

                entry.update({
                    "timestamp": datetime.now().strftime("%d-%m-%Y %I:%M:%S %p"),
                    "year": year,
                    "month": month,
                    "day": day
                })
                inserted_id = mongo_handler.insert_store_stock_entry(entry)
                entry["_id"] = str(inserted_id)
                cloned_entries.append(entry)

            return {"message": "Cloned from previous day", "entries": cloned_entries}

        # 3️⃣ Case: no past data, insert defaults
        inserted_entries = []
        for entry in deepcopy(DEFAULT_DAILY_STORE_STOCK_ENTRIES):
            entry_copy = entry.copy()

            # 🔹 Always refresh schedule
            monthly_config = mongo_handler.get_store_stock_entries_by_month(
                entry_copy["item_description"], month_str=month_key
            )
            entry_copy["schedule"] = monthly_config.get("schedule", 0) if monthly_config else 0

            entry_copy.update({
                "timestamp": datetime.now().strftime("%d-%m-%Y %I:%M:%S %p"),
                "year": year,
                "month": month,
                "day": day
            })
            inserted_id = mongo_handler.insert_store_stock_entry(entry_copy)
            entry_copy["_id"] = str(inserted_id)
            inserted_entries.append(entry_copy)

        return {"message": "Default entries created", "entries": inserted_entries}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

########################################## MONTHLY STORE STOCK  ##########################################


@router.post("/set_monthly_schedule_quantity_in_store_stock", response_model=dict)
def set_monthly_schedule_quantity_in_store_stock( config: MonthlyStoreStockEntrySheet, current_user: User = Depends(admin_required)):
    result = mongo_handler.monthly_insert_store_stock_entry(config.dict())
    

    if result["upserted_id"]:
        message = "Monthly config inserted for item_description"
        inserted_id = str(result["upserted_id"])
    else:
        message = "Monthly config updated for item_description"
        inserted_id = None

    return {
        "message": message,
        "inserted_id": inserted_id
    }


@router.put("/update_monthly_schedule_quantity_in_store_stock", response_model=dict)
def update_monthly_schedule_quantity_in_store_stock(config: MonthlyStoreStockEntrySheet, current_user: User = Depends(production_required)):
    
    month_str = f"{config.year}-{str(config.month).zfill(2)}"

    result = mongo_handler.monthly_store_stock_config.update_one(
        {
            "item_description": config.item_description,
            "month": month_str
        },
        {

            "$set": {
                "schedule": config.schedule,
                "timestamp": datetime.now(timezone.utc)
            }
        }
    )

    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Monthly config not found for item_description and month")

    return {
        "message": "Monthly config updated successfully",
        "modified_count": result.modified_count
    }


############################################ YEARLY STORE STOCK ################################################


@router.get("/get_store_stock_yearly_summary", response_model=List[dict])
async def get_store_stock_yearly_summary(
    year: int = Query(..., ge=2000, le=2100, description="Year in YYYY format"),
    current_user: User = Depends(production_required)
):
    try:
        yearly_summary = []

        for item in DEFAULT_DAILY_STORE_STOCK_ENTRIES:
            item_description = item["item_description"]

            # Aggregate pipeline to get latest entry for each month
            pipeline = [
                {"$match": {"item_description": item_description, "year": year}},
                {"$sort": {"month": 1, "day": -1, "timestamp": -1}},  # latest day/timestamp in month
                {
                    "$group": {
                        "_id": "$month",
                        "latest_entry": {"$first": "$$ROOT"}
                    }
                },
                {"$sort": {"_id": 1}}
            ]

            results = list(mongo_handler.store_stock_collection.aggregate(pipeline))

            monthly_data = []
            for month in range(1, 13):
                # fetch schedule for this month from monthly collection
                month_key = f"{year}-{month:02d}"
                monthly_config = mongo_handler.get_store_stock_entries_by_month(
                    item_description, month_str=month_key
                )
                schedule = monthly_config.get("schedule", 0) if monthly_config else 0

                # match latest entry for this month
                match = next((r for r in results if r["_id"] == month), None)
                if match:
                    entry = match["latest_entry"]
                    monthly_data.append({
                        "month": month,
                        "total_current_stock": entry.get("current", 0),
                        "total_schedule": safe_int(schedule),
                        "total_actual": safe_int(entry.get("actual")),
                        "day": entry.get("day")
                    })
                else:
                    monthly_data.append({
                        "month": month,
                        "total_current_stock": 0,
                        "total_schedule": safe_int(schedule),  # schedule still comes from monthly config
                        "total_actual": 0,
                        "day": None
                    })

            yearly_summary.append({
                "item_description": item_description,
                "year": year,
                "monthly_data": monthly_data
            })

        return yearly_summary

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/get_store_stock_audit/{year}/{month}", response_model=dict)
def get_store_stock_audit_by_month(
    year: int,
    month: int,
    current_user: User = Depends(production_required)
):
    try:
        month_str = f"{month:02d}"
        prefix = f"{year}-{month_str}"  # e.g. "2025-09"

        logs = list(
            mongo_handler.store_stock_audit_collection.find(
                {"year_month": prefix}
            ).sort("timestamp", DESCENDING)
        )

        # Convert ObjectId to string
        for log in logs:
            log["_id"] = str(log["_id"])
            # Convert datetime to ISO string for JSON response
            if isinstance(log.get("timestamp"), datetime):
                log["timestamp"] = log["timestamp"].isoformat()

        return {"year_month": prefix, "audit_logs": logs}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    
########################################## DELETE ENTRIES (ADMIN) ##########################################



@router.delete("/delete_store_stock_monitoring_entry/{year}/{month}/{day}", response_model=dict)
def delete_store_stock_monitoring_entry_daily(
    year: int = Path(..., ge=2000, le=2100, description="Year in YYYY format"),
    month: int = Path(..., ge=1, le=12, description="Month between 1 and 12"),
    day: int = Path(..., ge=1, le=31, description="Day of entry to delete (1-31)"),
    current_user: User = Depends(admin_required)  # ✅ only admin can delete
):
    try:
        # 🔹 Delete all entries for that specific day
        result = mongo_handler.store_stock_collection.delete_many({
            "year": year,
            "month": month,
            "day": day
        })

        if result.deleted_count == 0:
            raise HTTPException(
                status_code=404, 
                detail=f"No Store Stock entries found for {day}-{month}-{year}"
            )

        return {
            "message": f"Deleted {result.deleted_count} Store Stock entries for {day}-{month}-{year}",
            "deleted_count": result.deleted_count
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


