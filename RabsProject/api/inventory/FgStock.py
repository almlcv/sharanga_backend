# from datetime import datetime, date
# from fastapi import APIRouter, Depends, HTTPException, Path, Query
# import os, sys
# from datetime import timedelta
# from fastapi import Body
# from bson import ObjectId
# from zoneinfo import ZoneInfo
# from dateutil.relativedelta import relativedelta
# from dotenv import load_dotenv
# load_dotenv()
# HOSTING_LINK = os.getenv("HOSTING_LINK", "http://127.0.0.1:8015") 

# from RabsProject.pymodels.models import *
# from RabsProject.services.mongodb import MongoDBHandlerSaving  
# from RabsProject.cores.auth.authorise import get_current_user, admin_required, production_required
# from RabsProject.config.FgStockConfig import DEFAULT_DAILY_FG_STOCK_ENTRIES



# router = APIRouter(tags=["Fg Stock Monitoring Board"])

# mongo_handler = MongoDBHandlerSaving()
# ist = datetime.now(ZoneInfo("Asia/Kolkata"))




# ########################################## Daily FG stock update ##########################################


# @router.post("/submit_Fg_stock_monitoring_sheet_entry", response_model=dict)
# def submit_Fg_stock_monitoring_sheet_entry_daily(entry: DailyFgStockEntrySheet, current_user: User = Depends(production_required)):
#     monthly_config = mongo_handler.get_Fg_stock_entries_by_month(entry.item_description)
#     if not monthly_config:
#         monthly_config["schedule"] = 0
#         monthly_config["maximum"] = 0
#         raise HTTPException(status_code=400, detail="Monthly schedule stock and maximum quantity not found for item_description")

#     entry_dict = entry.dict()

#     current_stock = entry_dict.get("current", 0)
#     dispatched_qty = entry_dict.get("dispatched", 0) or 0

#     # Apply dispatch logic
#     if dispatched_qty <= current_stock:
#         current_stock -= dispatched_qty

#     entry_dict["current"] = current_stock  # ✅ keep as int
#     entry_dict["schedule"] = monthly_config.get("schedule")
#     entry_dict["maximum"] = monthly_config.get("maximum")
#     entry_dict["timestamp"] = datetime.now().strftime("%d-%m-%Y %I:%M:%S %p")
#     entry_dict["balance"] = entry_dict["schedule"] - dispatched_qty

#     inserted_id = mongo_handler.insert_daily_Fg_stock_entry(entry_dict)
#     return {"message": "Entry submitted", "id": inserted_id}


# @router.put("/update_Fg_stock_monitoring_sheet_entry/{entry_id}", response_model=dict)
# def update_Fg_stock_monitoring_sheet_entry_daily(
#     entry_id: str,
#     year: int,
#     month: int,
#     date: int,
#     updated_entry: DailyFgStockEntrySheet = Body(...),
#     current_user: User = Depends(production_required)
# ):
#     try:
#         month_str = f"{year}-{str(month).zfill(2)}"
#         monthly_config = mongo_handler.monthly_fg_stock_config.find_one({
#             "item_description": updated_entry.item_description,
#             "month": month_str
#         })

#         if not monthly_config:
#             raise HTTPException(status_code=400, detail="Monthly config not found for item_description")

#         schedule = monthly_config.get("schedule", 0)
#         maximum = monthly_config.get("maximum", 0)

#         # 🔹 Step 1: Fetch existing entry
#         existing_entry = mongo_handler.Daily_Fg_stock_collection.find_one({"_id": ObjectId(entry_id)})
#         if not existing_entry:
#             raise HTTPException(status_code=404, detail="Entry not found")

#         # 🔹 Step 2: Accumulate dispatch
#         previous_dispatch = existing_entry.get("dispatched", 0) or 0
#         new_dispatch = updated_entry.dispatched or 0
#         total_dispatch = previous_dispatch + new_dispatch

#         # 🔹 Step 3: Update current stock after dispatch
#         current_stock = existing_entry.get("current", 0)
#         if new_dispatch <= current_stock:   # only subtract today's new dispatch
#             current_stock -= new_dispatch

#         # 🔹 Step 4: Prepare update dict
#         updated_dict = updated_entry.dict(exclude_unset=True)
#         updated_dict["dispatched"] = total_dispatch
#         updated_dict["current"] = current_stock
#         updated_dict["balance"] = schedule - total_dispatch
#         updated_dict["schedule"] = schedule
#         updated_dict["maximum"] = maximum
#         updated_dict["year"] = year
#         updated_dict["month"] = month
#         updated_dict["day"] = date

#         success = mongo_handler.update_daily_Fg_stock_entry(entry_id, updated_dict)
#         if not success:
#             raise HTTPException(status_code=404, detail="Failed to update entry")

#         return {"message": "Entry updated successfully", "dispatched": total_dispatch, "current": current_stock}

#     except Exception as e:
#         raise HTTPException(status_code=500, detail=str(e))


# ########################################## Monthly FG stock update #######################################


# @router.post("/set_monthly_schedule_and_maximum_quantity_in_fgstock", response_model=dict)
# def set_monthly_schedule_and_maximum_quantity_in_fgstock( config: MonthlyFgStockEntrySheet, current_user: User = Depends(production_required)):
#     result = mongo_handler.monthly_insert_Fg_stock_entry(config.dict())

#     if result["upserted_id"]:
#         message = "Monthly config inserted for item_description"
#         inserted_id = str(result["upserted_id"])
#     else:
#         message = "Monthly config updated for item_description"
#         inserted_id = None

#     return {
#         "message": message,
#         "inserted_id": inserted_id
#     }


# @router.put("/update_monthly_schedule_and_maximum_quantity_in_fgstock", response_model=dict)
# def update_monthly_schedule_and_maximum_quantity_in_fgstock(config: MonthlyFgStockEntrySheet, current_user: User = Depends(production_required)):
#     month_str = f"{config.year}-{str(config.month).zfill(2)}"

#     result = mongo_handler.monthly_fg_stock_config.update_one(
#         {
#             "item_description": config.item_description,
#             "month": month_str
#         },
#         {
#             "$set": {
#                 "schedule": config.schedule,
#                 "maximum": config.maximum,
#                 "timestamp": datetime(int(config.year), int(config.month), 1)
#             }
#         }
#     )

#     if result.matched_count == 0:
#         raise HTTPException(status_code=404, detail="Monthly config not found for item_description and month")

#     return {
#         "message": "Monthly config updated successfully",
#         "modified_count": result.modified_count
#     }


# ########################################### DAILY SHEET FOR FG STOCK ######################################





# @router.get("/get_daily_Fg_stock_monitoring_sheets/{year}/{month}/{day}")
# async def get_daily_Fg_stock_monitoring_sheets(
#     year: int = Path(..., ge=2000, le=2100, description="Year in YYYY format"),
#     month: int = Path(..., ge=1, le=12, description="Month between 1 and 12"),
#     day: int = Path(..., ge=1, le=31, description="Day of the month"),
#     current_user: User = Depends(production_required)
# ):
#     try:
   
#         query_date = datetime(year, month, day)
#         month_key = f"{year}-{str(month).zfill(2)}"

#         # Step 1: Fetch existing daily entries
#         existing_entries = list(mongo_handler.Daily_Fg_stock_collection.find({
#             "year": year,
#             "month": month,
#             "day": day
#         }))

#         if existing_entries:
#             updated_entries = []
#             for entry in existing_entries:
#                 monthly_config = mongo_handler.get_Fg_stock_entries_by_month(
#                     entry["item_description"], month_str=month_key
#                 )
#                 entry["schedule"] = monthly_config.get("schedule", 0) if monthly_config else 0
#                 entry["maximum"] = monthly_config.get("maximum", 0) if monthly_config else 0
#                 entry_copy = entry.copy()
#                 entry_copy["_id"] = str(entry_copy["_id"])
#                 updated_entries.append(entry_copy)

#             return {"message": "Entries fetched from MongoDB", "entries": updated_entries}

#         # Step 2: Check if any monthly config exists
#         has_valid_monthly_config = False
#         for entry in DEFAULT_DAILY_FG_STOCK_ENTRIES:
#             config = mongo_handler.get_Fg_stock_entries_by_month(entry["item_description"], month_str=month_key)
#             if config:
#                 has_valid_monthly_config = True
#                 break

#         if not has_valid_monthly_config:
#             return {
#                 "message": f"No monthly config found for {month_key}. Please submit monthly data first.",
#                 "entries": []
#             }

#         # Step 3: Insert default entries with rollover stock
#         inserted_entries = []
#         for entry in DEFAULT_DAILY_FG_STOCK_ENTRIES:
#             entry_copy = entry.copy()

#             # Get monthly config
#             monthly_config = mongo_handler.get_Fg_stock_entries_by_month(
#                 entry_copy["item_description"], month_str=month_key
#             )

#             # Get yesterday's stock for rollover
#             yesterday = query_date - timedelta(days=1)
#             yesterday_entry = mongo_handler.Daily_Fg_stock_collection.find_one({
#                 "item_description": entry_copy["item_description"],
#                 "year": yesterday.year,
#                 "month": yesterday.month,
#                 "day": yesterday.day
#             })

#             previous_stock = int(yesterday_entry.get("current", 0)) if yesterday_entry else 0

#             # ✅ Dispatch accumulation logic
#             if yesterday_entry and yesterday.month == month:
#                 # Same month → carry forward yesterday's dispatch
#                 previous_dispatch = int(yesterday_entry.get("dispatched", 0))
#             else:
#                 # New month or no yesterday entry → reset
#                 previous_dispatch = 0

#             # Update entry fields
#             entry_copy.update({
#                 "schedule": monthly_config.get("schedule", 0) if monthly_config else 0,
#                 "maximum": monthly_config.get("maximum", 0) if monthly_config else 0,
#                 "timestamp": query_date,
#                 "year": year,
#                 "month": month,
#                 "day": day,
#                 "current": previous_stock,
#                 "dispatched": previous_dispatch
#             })

#             inserted_id = mongo_handler.insert_daily_Fg_stock_entry(entry_copy)
#             entry_copy["_id"] = str(inserted_id)
#             inserted_entries.append(entry_copy)

#         return {"message": "Default entries created", "entries": inserted_entries}

#     except Exception as e:
#         raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


# ###########################################  NEW MONTHLY SHEET FOR FG STOCK #############################


# @router.get("/get_fgstock_summary_by_year", response_model=List[dict])
# async def get_fgstock_summary_by_year(
#     year: int = Query(..., ge=2000, le=2100, description="Year in YYYY format"),
#     current_user: User = Depends(production_required)):
#     try:
#         yearly_summary = []

#         for item in DEFAULT_DAILY_FG_STOCK_ENTRIES:
#             item_description = item["item_description"]

#             # Aggregated monthly dispatched data (but now latest entry, not sum)
#             monthly_agg = mongo_handler.get_yearly_fgstock_summary(item_description, year)

#             # Prepare map for quick lookup
#             monthly_map = {entry["month"]: entry for entry in monthly_agg}

#             monthly_data = []
#             for month in range(1, 13):
#                 config = mongo_handler.monthly_fg_stock_config.find_one({
#                     "item_description": item_description,
#                     "year": year,
#                     "month": month
#                 })

#                 monthly_schedule = None
#                 if config and config.get("schedule"):
#                     monthly_schedule = config["schedule"]
#                 elif month in monthly_map:
#                     monthly_schedule = monthly_map[month].get("schedule")

#                 monthly_dispatched = monthly_map.get(month, {}).get("monthly_dispatched", 0)

#                 monthly_data.append({
#                     "month": month,
#                     "monthly_schedule": monthly_schedule,
#                     "monthly_dispatched": monthly_dispatched,
#                     "last_date": monthly_map.get(month, {}).get("last_date")  # optional, for clarity
#                 })

#             yearly_summary.append({
#                 "item_description": item_description,
#                 "year": year,
#                 "monthly_data": monthly_data
#             })

#         return yearly_summary

#     except Exception as e:
#         raise HTTPException(status_code=500, detail=str(e))

# ###########################################  Delete Records ##############################################

# @router.delete("/delete_Fg_stock_monitoring_entries/{year}/{month}", response_model=dict)
# def delete_Fg_stock_monitoring_entries(
#     year: int = Path(..., ge=2000, le=2100, description="Year in YYYY format"),
#     month: int = Path(..., ge=1, le=12, description="Month between 1 and 12"),
#     current_user: User = Depends(admin_required)  # ✅ only admin should delete
# ):
#     try:
#         # 🔹 Convert to YYYY-MM format for safety (if you store month like that)
#         month_str = f"{year}-{str(month).zfill(2)}"

#         # Delete all daily entries for that year & month
#         result = mongo_handler.Daily_Fg_stock_collection.delete_many({
#             "year": year,
#             "month": month
#         })

#         if result.deleted_count == 0:
#             raise HTTPException(status_code=404, detail="No entries found for the given month")

#         return {
#             "message": f"Deleted {result.deleted_count} FG Stock entries for {month_str}",
#             "deleted_count": result.deleted_count
#         }

#     except Exception as e:
#         raise HTTPException(status_code=500, detail=str(e))


# @router.delete("/delete_Fg_stock_monitoring_entry/{year}/{month}/{day}", response_model=dict)
# def delete_Fg_stock_monitoring_entry_daily(
#     year: int = Path(..., ge=2000, le=2100, description="Year in YYYY format"),
#     month: int = Path(..., ge=1, le=12, description="Month between 1 and 12"),
#     day: int = Path(..., ge=1, le=31, description="Day of entry to delete (1-31)"),
#     current_user: User = Depends(admin_required)  # ✅ only admin can delete
# ):
#     try:
#         # 🔹 Delete all entries for that specific day
#         result = mongo_handler.Daily_Fg_stock_collection.delete_many({
#             "year": year,
#             "month": month,
#             "day": day
#         })

#         if result.deleted_count == 0:
#             raise HTTPException(
#                 status_code=404, 
#                 detail=f"No FG Stock entries found for {day}-{month}-{year}"
#             )

#         return {
#             "message": f"Deleted {result.deleted_count} FG Stock entries for {day}-{month}-{year}",
#             "deleted_count": result.deleted_count
#         }

#     except Exception as e:
#         raise HTTPException(status_code=500, detail=str(e))

#################################################################################################
#################################################################################################
###################################################################################################

from datetime import datetime, date
from fastapi import APIRouter, Depends, HTTPException, Path, Query
import os
from datetime import timedelta
from fastapi import Body
from bson import ObjectId
from zoneinfo import ZoneInfo
from dotenv import load_dotenv
load_dotenv()
HOSTING_LINK = os.getenv("HOSTING_LINK", "http://127.0.0.1:8015") 

from RabsProject.pymodels.models import *
from RabsProject.services.mongodb import MongoDBHandlerSaving  
from RabsProject.cores.auth.authorise import get_current_user, admin_required, production_required, dispatch_required
from RabsProject.config.FgStockConfig import DEFAULT_DAILY_FG_STOCK_ENTRIES, PART_NAMES, BIN_SIZE_MAP



router = APIRouter(tags=["Fg Stock Monitoring Board"])

mongo_handler = MongoDBHandlerSaving()
ist = datetime.now(ZoneInfo("Asia/Kolkata"))




########################################## Daily FG stock update ##########################################


@router.post("/submit_Fg_stock_monitoring_sheet_entry", response_model=dict)
def submit_Fg_stock_monitoring_sheet_entry_daily(
    entry: DailyFgStockEntrySheet,
    current_user: User = Depends(production_required)
):
    # Fetch monthly config
    year, month = datetime.now().year, datetime.now().month
    month_key = f"{year}-{str(month).zfill(2)}"
    monthly_config = mongo_handler.get_Fg_stock_entries_by_month(entry.item_description, month_str=month_key)
    if not monthly_config:
        raise HTTPException(
            status_code=400,
            detail="Monthly schedule stock and maximum quantity not found for item_description"
        )

    schedule = monthly_config.get("schedule", 0)
    maximum = monthly_config.get("maximum", 0)

    # Convert entry to dict
    entry_dict = entry.dict()

    # Ensure bins_available is always a dict
    bins = entry_dict.get("bins_available")
    if not bins or not isinstance(bins, dict):
        entry_dict["bins_available"] = {"rabs_bins": 0, "ijl_bins": 0}

    # dispatched Quantity fetching
    dispatched_qty = entry_dict.get("dispatched", 0) or 0

    # Set schedule, maximum, balance, timestamp
    entry_dict["schedule"] = schedule
    entry_dict["maximum"] = maximum
    entry_dict["balance"] = schedule - dispatched_qty
    entry_dict["timestamp"] = datetime.now()

    # Save entry to Mongo
    inserted_id = mongo_handler.insert_daily_Fg_stock_entry(entry_dict)

    return {"message": "Entry submitted", "id": inserted_id}




@router.put("/update_Fg_stock_monitoring_sheet_entry/{entry_id}", response_model=dict)
def update_Fg_stock_monitoring_sheet_entry_daily(
    entry_id: str,
    date:  int ,
    month: int ,
    year: int,
    updated_entry: DailyFgStockEntrySheet = Body(...),
    current_user: User = Depends(production_required)):
    try:
        month_str = f"{year}-{str(month).zfill(2)}"
        monthly_config = mongo_handler.monthly_fg_stock_config.find_one({
            "item_description": updated_entry.item_description,
            "month": month_str
        })

        if not monthly_config:
            raise HTTPException(status_code=400, detail="Monthly config not found for item_description")

        schedule = monthly_config.get("schedule", 0)
        maximum = monthly_config.get("maximum", 0)

        # 🔹 Step 1: Fetch existing entry
        existing_entry = mongo_handler.Daily_Fg_stock_collection.find_one({"_id": ObjectId(entry_id)})
        if not existing_entry:
            raise HTTPException(status_code=404, detail="Entry not found")

        # 🔹 Step 2: Accumulate dispatch
        previous_dispatch = existing_entry.get("dispatched", 0) or 0
        new_dispatch = updated_entry.dispatched or 0
        total_dispatch = previous_dispatch + new_dispatch

        # 🔹 Step 3: Update current stock after dispatch
        current_stock = existing_entry.get("current", 0)
        if new_dispatch <= current_stock:   # only subtract today's new dispatch 
            current_stock -= new_dispatch
        else:
            raise HTTPException(status_code=400, detail="Current stock is not sufficient for the dispatch")

        # 🔹 Step 4: Prepare update dict
        updated_dict = updated_entry.dict(exclude_unset=True)
        updated_dict["dispatched"] = total_dispatch
        updated_dict["current"] = current_stock
        updated_dict["balance"] = schedule - total_dispatch
        updated_dict["schedule"] = schedule
        updated_dict["maximum"] = maximum
        updated_dict["year"] = year
        updated_dict["month"] = month
        updated_dict["day"] = date

        # 🚫 never touch bins_available directly
        updated_dict.pop("bins_available", None)

        item_desc = updated_entry.item_description.strip()
        if item_desc in BIN_SIZE_MAP:
            bin_size = BIN_SIZE_MAP[item_desc]
            bins_to_move = new_dispatch // bin_size

            if bins_to_move > 0:
                entry = mongo_handler.Daily_Fg_stock_collection.find_one({
                    "item_description": item_desc,
                    "year": year,
                    "month": month,
                    "day": date
                })

                if entry:
                    bins_available = entry.get("bins_available", {"rabs_bins": 0, "ijl_bins": 0})

                    # Ensure enough RABS bins
                    transferable = min(bins_to_move, bins_available.get("rabs_bins", 0))

                    bins_available["rabs_bins"] -= transferable
                    bins_available["ijl_bins"] += transferable

                    # Save update
                    mongo_handler.Daily_Fg_stock_collection.update_one(
                        {"_id": entry["_id"]},
                        {"$set": {"bins_available": bins_available, "updated_at": datetime.now()}}
                    )

        # 🔹 Step 6: Update main entry
        success = mongo_handler.update_daily_Fg_stock_entry(entry_id, updated_dict)
        if not success:
            raise HTTPException(status_code=404, detail="Failed to update entry")

        return {
            "message": "Entry updated successfully",
            "dispatched": total_dispatch,
            "current": current_stock,
            "bin available" : bins_available
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))




 ###################################### ADD BINS #########################################




@router.put("/add_bins", response_model=dict)
def add_bins_for_part(
    request: AddBinsRequest = Body(...),
    current_user: User = Depends(admin_required)  # or production_required
):


    part_name = request.part_name.strip()

    if part_name not in PART_NAMES:
        raise HTTPException(status_code=400, detail="Invalid part name")

    # LH & RH item descriptions
    lh_name = f"{part_name} LH"
    rh_name = f"{part_name} RH"

    # Fetch both LH and RH entries for the specific date
    lh_entry = mongo_handler.Daily_Fg_stock_collection.find_one({
        "item_description": lh_name,
        "year": request.year,
        "month": request.month,
        "day": request.day
    })
    rh_entry = mongo_handler.Daily_Fg_stock_collection.find_one({
        "item_description": rh_name,
        "year": request.year,
        "month": request.month,
        "day": request.day
    })

    if not lh_entry or not rh_entry:
        raise HTTPException(status_code=404, detail=f"FG stock entries not found for {part_name} on {request.day}-{request.month}-{request.year}")

    # Divide bins equally
    rabs_half = (request.rabs_bins or 0) // 2
    ijl_half = (request.ijl_bins or 0) // 2

    # Update LH bins
    lh_bins = lh_entry.get("bins_available", {"rabs_bins": 0, "ijl_bins": 0})
    lh_bins["rabs_bins"] += rabs_half
    lh_bins["ijl_bins"] += ijl_half

    mongo_handler.Daily_Fg_stock_collection.update_one(
        {"_id": lh_entry["_id"]},
        {"$set": {"bins_available": lh_bins, "updated_at": datetime.now()}}
    )

    # Update RH bins
    rh_bins = rh_entry.get("bins_available", {"rabs_bins": 0, "ijl_bins": 0})
    rh_bins["rabs_bins"] += rabs_half
    rh_bins["ijl_bins"] += ijl_half

    mongo_handler.Daily_Fg_stock_collection.update_one(
        {"_id": rh_entry["_id"]},
        {"$set": {"bins_available": rh_bins, "updated_at": datetime.now()}}
    )

    return {
        "message": f"Bins updated successfully for {part_name} (divided into LH & RH)",
        "updated_bins": {
            lh_name: lh_bins,
            rh_name: rh_bins
        }
    }



@router.put("/update_bins_from_ijl_by_part_with_date", response_model=dict)
def update_bins_from_ijl_by_part_with_date(
    request: IJLBinsUpdateRequest,
    current_user: User = Depends(dispatch_required)
):
    part_name = request.part_name.strip()
    bins_quantity = request.bins_quantity
    year, month, day = request.year, request.month, request.day

    if part_name not in PART_NAMES:
        raise HTTPException(status_code=400, detail="Invalid part name")

    if bins_quantity <= 0:
        raise HTTPException(status_code=400, detail="Bins quantity must be positive")

    half_bins = bins_quantity // 2

    # LH & RH item descriptions
    lh_name = f"{part_name} LH"
    rh_name = f"{part_name} RH"

    # Fetch both LH and RH entries for the specific date
    lh_entry = mongo_handler.Daily_Fg_stock_collection.find_one({
        "item_description": lh_name,
        "year": year,
        "month": month,
        "day": day
    })
    rh_entry = mongo_handler.Daily_Fg_stock_collection.find_one({
        "item_description": rh_name,
        "year": year,
        "month": month,
        "day": day
    })

    if not lh_entry or not rh_entry:
        raise HTTPException(status_code=404, detail="FG stock entries for LH/RH not found for this date")

    # Ensure bins_available exists
    lh_bins = lh_entry.get("bins_available", {"rabs_bins": 0, "ijl_bins": 0})
    rh_bins = rh_entry.get("bins_available", {"rabs_bins": 0, "ijl_bins": 0})

    # ✅ New Validation: Ensure IJL has enough bins available
    total_ijl_bins_available = lh_bins["ijl_bins"] + rh_bins["ijl_bins"]
    if total_ijl_bins_available < bins_quantity:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Insufficient IJL bins available. "
                f"Requested: {bins_quantity}, Available: {total_ijl_bins_available}"
            )
        )

    # Calculate actual transferable bins
    transfer_lh = min(half_bins, lh_bins["ijl_bins"])
    transfer_rh = min(half_bins, rh_bins["ijl_bins"])

    # Update bins
    lh_bins["rabs_bins"] += transfer_lh
    lh_bins["ijl_bins"] -= transfer_lh

    rh_bins["rabs_bins"] += transfer_rh
    rh_bins["ijl_bins"] -= transfer_rh

    # Save updates
    mongo_handler.Daily_Fg_stock_collection.update_one(
        {"_id": lh_entry["_id"]},
        {"$set": {"bins_available": lh_bins, "updated_at": datetime.now()}}
    )
    mongo_handler.Daily_Fg_stock_collection.update_one(
        {"_id": rh_entry["_id"]},
        {"$set": {"bins_available": rh_bins, "updated_at": datetime.now()}}
    )

    return {
        "message": f"Bins updated successfully for {part_name} on {day}-{month}-{year}",
        "updated_bins": {
            lh_name: lh_bins,
            rh_name: rh_bins
        }
    }


########################################## Monthly FG stock update #######################################


@router.post("/set_monthly_schedule_and_maximum_quantity_in_fgstock", response_model=dict)
def set_monthly_schedule_and_maximum_quantity_in_fgstock( config: MonthlyFgStockEntrySheet, current_user: User = Depends(production_required)):
    result = mongo_handler.monthly_insert_Fg_stock_entry(config.dict())

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


@router.put("/update_monthly_schedule_and_maximum_quantity_in_fgstock", response_model=dict)
def update_monthly_schedule_and_maximum_quantity_in_fgstock(config: MonthlyFgStockEntrySheet, current_user: User = Depends(production_required)):
    month_str = f"{config.year}-{str(config.month).zfill(2)}"

    result = mongo_handler.monthly_fg_stock_config.update_one(
        {
            "item_description": config.item_description,
            "month": month_str
        },
        {
            "$set": {
                "schedule": config.schedule,
                "maximum": config.maximum,
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


########################################### DAILY SHEET FOR FG STOCK ######################################



@router.get("/get_daily_Fg_stock_monitoring_sheets/{year}/{month}/{day}")
async def get_daily_Fg_stock_monitoring_sheets(
    year: int = Path(..., ge=2000, le=2100, description="Year in YYYY format"),
    month: int = Path(..., ge=1, le=12, description="Month between 1 and 12"),
    day: int = Path(..., ge=1, le=31, description="Day of the month"),
    current_user: User = Depends(production_required)
):
    try:
   
        query_date = datetime(year, month, day)
        month_key = f"{year}-{str(month).zfill(2)}"

        # Step 1: Fetch existing daily entries
        existing_entries = list(mongo_handler.Daily_Fg_stock_collection.find({
            "year": year,
            "month": month,
            "day": day
        }))

        if existing_entries:
            updated_entries = []
            for entry in existing_entries:
                monthly_config = mongo_handler.get_Fg_stock_entries_by_month(
                    entry["item_description"], month_str=month_key
                )
                entry["schedule"] = monthly_config.get("schedule", 0) if monthly_config else 0
                entry["maximum"] = monthly_config.get("maximum", 0) if monthly_config else 0
                entry_copy = entry.copy()
                entry_copy["_id"] = str(entry_copy["_id"])
                updated_entries.append(entry_copy)

            return {"message": "Entries fetched from MongoDB", "entries": updated_entries}

        # Step 2: Check if any monthly config exists
        has_valid_monthly_config = False
        for entry in DEFAULT_DAILY_FG_STOCK_ENTRIES:
            config = mongo_handler.get_Fg_stock_entries_by_month(entry["item_description"], month_str=month_key)
            if config:
                has_valid_monthly_config = True
                break

        if not has_valid_monthly_config:
            return {
                "message": f"No monthly config found for {month_key}. Please submit monthly data first.",
                "entries": []
            }

        # Step 3: Insert default entries with rollover stock
        inserted_entries = []
        for entry in DEFAULT_DAILY_FG_STOCK_ENTRIES:
            entry_copy = entry.copy()

            # Get monthly config
            monthly_config = mongo_handler.get_Fg_stock_entries_by_month(
                entry_copy["item_description"], month_str=month_key
            )

            # Get yesterday's stock for rollover
            yesterday = query_date - timedelta(days=1)
            yesterday_entry = mongo_handler.Daily_Fg_stock_collection.find_one({
                "item_description": entry_copy["item_description"],
                "year": yesterday.year,
                "month": yesterday.month,
                "day": yesterday.day
            })

            previous_stock = int(yesterday_entry.get("current", 0)) if yesterday_entry else 0
            bins_available = yesterday_entry.get("bins_available", {"rabs_bins": 0, "ijl_bins": 0}) if yesterday_entry else {"rabs_bins": 0, "ijl_bins": 0}

            # ✅ Dispatch accumulation logic
            if yesterday_entry and yesterday.month == month:
                # Same month → carry forward yesterday's dispatch
                previous_dispatch = int(yesterday_entry.get("dispatched", 0))
            else:
                # New month or no yesterday entry → reset
                previous_dispatch = 0

            # Update entry fields
            entry_copy.update({
                "schedule": monthly_config.get("schedule", 0) if monthly_config else 0,
                "maximum": monthly_config.get("maximum", 0) if monthly_config else 0,
                "timestamp": query_date,
                "year": year,
                "month": month,
                "day": day,
                "current": previous_stock,
                "bins_available": bins_available,
                "dispatched": previous_dispatch
            })

            inserted_id = mongo_handler.insert_daily_Fg_stock_entry(entry_copy)
            entry_copy["_id"] = str(inserted_id)
            inserted_entries.append(entry_copy)

        return {"message": "Default entries created", "entries": inserted_entries}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")





# ###########################################  NEW MONTHLY SHEET FOR FG STOCK #############################



@router.get("/get_fgstock_summary_by_year", response_model=List[dict])
async def get_fgstock_summary_by_year(
    year: int = Query(..., ge=2000, le=2100, description="Year in YYYY format"),
    current_user: User = Depends(production_required)):
    try:
        yearly_summary = []

        for item in DEFAULT_DAILY_FG_STOCK_ENTRIES:
            item_description = item["item_description"]

            # Aggregated monthly dispatched data (but now latest entry, not sum)
            monthly_agg = mongo_handler.get_yearly_fgstock_summary(item_description, year)

            # Prepare map for quick lookup
            monthly_map = {entry["month"]: entry for entry in monthly_agg}

            monthly_data = []
            for month in range(1, 13):
                config = mongo_handler.monthly_fg_stock_config.find_one({
                    "item_description": item_description,
                    "year": year,
                    "month": month
                })

                monthly_schedule = None
                if config and config.get("schedule"):
                    monthly_schedule = config["schedule"]
                elif month in monthly_map:
                    monthly_schedule = monthly_map[month].get("schedule")

                monthly_dispatched = monthly_map.get(month, {}).get("monthly_dispatched", 0)

                monthly_data.append({
                    "month": month,
                    "monthly_schedule": monthly_schedule,
                    "monthly_dispatched": monthly_dispatched,
                    "last_date": monthly_map.get(month, {}).get("last_date")  # optional, for clarity
                })

            yearly_summary.append({
                "item_description": item_description,
                "year": year,
                "monthly_data": monthly_data
            })

        return yearly_summary

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/get_fgstock_summary_by_specific_months", response_model=List[dict])
async def get_fgstock_summary_by_months(
    year: int = Query(..., ge=2000, le=2100, description="Year in YYYY format"),
    months: List[int] = Query(..., description="List of month numbers (1-12)"),
    current_user: User = Depends(production_required)
):
    """
    Fetch FG stock summary for selected months of a given year.
    """
    try:
        # Validate months
        for month in months:
            if month < 1 or month > 12:
                raise HTTPException(status_code=400, detail=f"Invalid month value: {month}. Must be 1-12.")

        monthly_summary = []

        for item in DEFAULT_DAILY_FG_STOCK_ENTRIES:
            item_description = item["item_description"]

            # Get yearly summary from MongoDB
            monthly_agg = mongo_handler.get_yearly_fgstock_summary(item_description, year)
            monthly_map = {entry["month"]: entry for entry in monthly_agg}

            selected_months_data = []
            for month in months:
                config = mongo_handler.monthly_fg_stock_config.find_one({
                    "item_description": item_description,
                    "year": year,
                    "month": month
                })

                monthly_schedule = None
                if config and config.get("schedule"):
                    monthly_schedule = config["schedule"]
                elif month in monthly_map:
                    monthly_schedule = monthly_map[month].get("schedule")

                monthly_dispatched = monthly_map.get(month, {}).get("monthly_dispatched", 0)

                selected_months_data.append({
                    "month": month,
                    "monthly_schedule": monthly_schedule,
                    "monthly_dispatched": monthly_dispatched,
                    "last_date": monthly_map.get(month, {}).get("last_date")
                })

            monthly_summary.append({
                "item_description": item_description,
                "year": year,
                "monthly_data": selected_months_data
            })

        return monthly_summary

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

###########################################  Delete Records ##############################################

@router.delete("/delete_Fg_stock_monitoring_entries/{year}/{month}", response_model=dict)
def delete_Fg_stock_monitoring_entries(
    year: int = Path(..., ge=2000, le=2100, description="Year in YYYY format"),
    month: int = Path(..., ge=1, le=12, description="Month between 1 and 12"),
    current_user: User = Depends(admin_required)  # ✅ only admin should delete
):
    try:
        # 🔹 Convert to YYYY-MM format for safety (if you store month like that)
        month_str = f"{year}-{str(month).zfill(2)}"

        # Delete all daily entries for that year & month
        result = mongo_handler.Daily_Fg_stock_collection.delete_many({
            "year": year,
            "month": month
        })

        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="No entries found for the given month")

        return {
            "message": f"Deleted {result.deleted_count} FG Stock entries for {month_str}",
            "deleted_count": result.deleted_count
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/delete_Fg_stock_monitoring_entry/{year}/{month}/{day}", response_model=dict)
def delete_Fg_stock_monitoring_entry_daily(
    year: int = Path(..., ge=2000, le=2100, description="Year in YYYY format"),
    month: int = Path(..., ge=1, le=12, description="Month between 1 and 12"),
    day: int = Path(..., ge=1, le=31, description="Day of entry to delete (1-31)"),
    current_user: User = Depends(admin_required)  # ✅ only admin can delete
):
    try:
        # 🔹 Delete all entries for that specific day
        result = mongo_handler.Daily_Fg_stock_collection.delete_many({
            "year": year,
            "month": month,
            "day": day
        })

        if result.deleted_count == 0:
            raise HTTPException(
                status_code=404, 
                detail=f"No FG Stock entries found for {day}-{month}-{year}"
            )

        return {
            "message": f"Deleted {result.deleted_count} FG Stock entries for {day}-{month}-{year}",
            "deleted_count": result.deleted_count
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))



