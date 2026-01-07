from copy import deepcopy
from datetime import datetime, date, timezone
from fastapi import APIRouter, Depends, HTTPException, Path, Query # type: ignore
import os, sys
import base64
from pymongo import DESCENDING # type: ignore
from datetime import timedelta
from zoneinfo import ZoneInfo
from dotenv import load_dotenv # type: ignore
import yaml
from zoneinfo import ZoneInfo
from bson import ObjectId
from bson import ObjectId # type: ignore
import re
from fastapi import APIRouter, Depends, HTTPException # type: ignore
load_dotenv()
from pymongo import DESCENDING, ReturnDocument # type: ignore


from RabsProject.pymodels.models import *
from RabsProject.config.StoreStockConfig import DEFAULT_DAILY_STORE_STOCK_ENTRIES
from RabsProject.services.mongodb import MongoDBHandlerSaving  
from RabsProject.cores.auth.authorise import get_current_user, admin_required, production_required, dispatch_required


router = APIRouter(tags=["Store Stock Register Board"])
mongo_handler = MongoDBHandlerSaving()

HOSTING_LINK = os.getenv("HOSTING_LINK", "http://127.0.0.1:8015") 
BASE_DIR = "INVENTORY"


# Folder for storing files
UPLOAD_DIR = "./INVENTORY/StoreStockRegister"
os.makedirs(UPLOAD_DIR, exist_ok=True)

#######################################################################################################
#######################################################################################################

def safe_int(value):
    try:
        return int(value)
    except (ValueError, TypeError):
        return 0

def shift_location_priorities(location: LocationPriority) -> LocationPriority:
    loc = location.dict()

    def is_empty(val):
        return val is None or val == "" or val == 0 or val == "0"

    # Keep shifting until no empty slot at p1 or p2 with stock below
    while True:
        shifted = False

        # Shift p1 if empty
        if is_empty(loc.get("p1")):
            if not is_empty(loc.get("p2")):
                loc["p1"] = loc.get("p2")
                loc["p2"] = loc.get("p3")
                loc["p3"] = None
                shifted = True
            elif not is_empty(loc.get("p3")):
                loc["p1"] = loc.get("p3")
                loc["p3"] = None
                shifted = True

        # Shift p2 if empty
        if is_empty(loc.get("p2")) and not is_empty(loc.get("p3")):
            loc["p2"] = loc.get("p3")
            loc["p3"] = None
            shifted = True

        if not shifted:
            break

    return LocationPriority(**loc)

def save_entry_files(item_description: str, category: str, files: List[Base64File], date_str: str) -> List[str]:
    folder_path = os.path.join(BASE_DIR, "StoreStockRegister", "InwardStock", date_str, item_description, category)
    os.makedirs(folder_path, exist_ok=True)
    saved_urls = []

    for file in files:
        filename = f"{file.filename}"
        file_path = os.path.join(folder_path, filename)
        content = file.content.split(",", 1)[1] if "," in file.content else file.content
        with open(file_path, "wb") as f:
            f.write(base64.b64decode(content))

        fetching_path = "INVENTORY/StoreStockRegister/InwardStock"
        relative_path = f"{fetching_path}/{date_str}/{item_description}/{category}/{filename}"
        saved_urls.append(f"{HOSTING_LINK}/{relative_path}")
    return saved_urls

def save_exit_files(item_description: str, category: str, files: List[Base64File], date_str: str) -> List[str]:
    folder_path = os.path.join(BASE_DIR, "StoreStockRegister", "OutwardStock", date_str, item_description, category)
    os.makedirs(folder_path, exist_ok=True)
    saved_urls = []

    for file in files:
        filename = f"{file.filename}"
        file_path = os.path.join(folder_path, filename)
        content = file.content.split(",", 1)[1] if "," in file.content else file.content
        with open(file_path, "wb") as f:
            f.write(base64.b64decode(content))
        fetching_path = "INVENTORY/StoreStockRegister/OutwardStock"
        relative_path = f"{fetching_path}/{date_str}/{item_description}/{category}/{filename}"
        saved_urls.append(f"{HOSTING_LINK}/{relative_path}")
    return saved_urls


#######################################################################################################
# #------------------------------------- DAILY STORE STOCK  --------------------------------------
#######################################################################################################


@router.post("/submit_store_stock_registering_sheet_entry", response_model=dict)
def submit_store_stock_registering_sheet_entry(
    entry: StoreStockEntry,
    current_user: User = Depends(production_required)
):
    try:
        # now = datetime.now(timezone.utc)
        # today_str = now.strftime("%Y-%m-%d")


        now = datetime.now(ZoneInfo("Asia/Kolkata"))
        today_str = now.strftime("%Y-%m-%d")

        # --- Step 1: Validate QC for all items first ---
        not_approved_items = [item.item_description for item in entry.items if item.QC != "yes"]
        if not_approved_items:
            raise HTTPException(
                status_code=400,
                detail=f"QC permission not granted for: {', '.join(not_approved_items)}. "
                       f"Please contact Ajith Sir."
            )
 
        # --- Step 2: Save shared Invoice once per truck ---
        # invoice_urls = save_entry_files("Invoice", entry.Invoice, today_str) if entry.Invoice else []

        item_entries = []

        # --- Step 3: Process each item only after all QC checks pass ---
        for item in entry.items:
            item_dict = item.dict()
            item_dict["_id"] = ObjectId()
            item_dict['QC_approval_time'] = now.strftime("%d-%m-%Y %I:%M:%S %p")
            item_dict["timestamp"] = now.strftime("%d-%m-%Y %I:%M:%S %p")

            # Save TC files per item_description
            invoice_urls = save_entry_files(item.item_description ,"Invoice", entry.Invoice, today_str)
            tc_urls = save_entry_files(item.item_description, "TC", item.TC, today_str) 
            item_dict["Documents"] = {
                "Invoice": invoice_urls,  # same for all items
                "TC": tc_urls             # unique per item
            }
            item_dict.pop("TC")
            item_entries.append(item_dict)
            

            # --- Update Monitoring Sheet for each item ---
            day, month, year = now.day, now.month, now.year
            monitoring_entry = mongo_handler.store_stock_collection.find_one({
                "item_description": item.item_description,
                "day": day,
                "month": month,
                "year": year
            })

            if monitoring_entry:
                new_actual = monitoring_entry.get("actual", 0) + (item.received_qty or 0)
                new_location = monitoring_entry.get("location", {"p1": None, "p2": None, "p3": None})

                # Shift the location
                loc_obj = LocationPriority(**new_location)
                loc_obj = shift_location_priorities(loc_obj)
                new_location = loc_obj.dict()

                # --- Add new stock to p3 ---
                existing_p3 = new_location.get("p3")
                if existing_p3:
                    existing_qty = sum(int(n) for n in re.findall(r'\d+', str(existing_p3)))
                    total_qty = existing_qty + (item.received_qty or 0)
                    new_location["p3"] = f"{item.location}{total_qty}"
                else:
                    new_location["p3"] = f"{item.location}{item.received_qty or 0}"

                # Calculate total current stock
                total_current = 0
                for key in ["p1", "p2", "p3"]:
                    val = new_location.get(key)
                    if val:
                        total_current += sum([int(n) for n in re.findall(r'\d+', str(val))])

                mongo_handler.store_stock_collection.update_one(
                    {"_id": monitoring_entry["_id"]},
                    {"$set": {
                        "actual": new_actual,
                        "location": new_location,
                        "current": total_current,
                        "timestamp": now.strftime("%d-%m-%Y %I:%M:%S %p")
                    }}
                )

        # --- Step 4: Save all items under same date document ---
        mongo_handler.store_stock_register_collection.find_one_and_update(
            {"date": today_str},
            {
                "$push": {"entries": {"$each": item_entries}},
                "$setOnInsert": {"date": today_str}
            },
            upsert=True,
            return_document=ReturnDocument.AFTER
        )

        return {
            "message": f"{len(item_entries)} items saved successfully with shared Invoice",
            "date": today_str,
            "entry_ids": [str(item["_id"]) for item in item_entries]
        }

    except HTTPException:
        # rethrow custom HTTP exceptions without masking them
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

#######################################################################################################
#------------------------------------- DAILY STORE STOCK EXIT --------------------------------------
#######################################################################################################


# --- Main endpoint ---
@router.post("/submit_store_stock_exit_sheet_entry", response_model=dict)
def submit_store_stock_exit_sheet_entry(
    exit_entry: StoreStockExit,
    current_user: User = Depends(production_required)
):
    try:
        # now = datetime.now(timezone.utc)
        # today_str = now.strftime("%Y-%m-%d")

        now = datetime.now(ZoneInfo("Asia/Kolkata"))
        today_str = now.strftime("%Y-%m-%d")

        # --- Fetch monitoring entry ---
        day, month, year = now.day, now.month, now.year
        monitoring_entry = mongo_handler.store_stock_collection.find_one({
            "item_description": exit_entry.item_description,
            "day": day,
            "month": month,
            "year": year
        })

        if not monitoring_entry:
            raise HTTPException(
                status_code=400,
                detail=f"No monitoring entry found for item={exit_entry.item_description} on {day}-{month}-{year}"
            )

        remaining_qty = exit_entry.issued_qty or 0
        location_dict = monitoring_entry.get("location", {"p1": None, "p2": None, "p3": None})


        loc_obj = LocationPriority(**location_dict)
        loc_obj = shift_location_priorities(loc_obj)
        location_dict = loc_obj.dict()

        # --- Helper to split prefix and numeric quantity ---
        def split_prefix_qty(val):
            if val:
                match = re.match(r"([A-Za-z]+)(\d+)", str(val))
                if match:
                    return match.group(1), int(match.group(2))
            return None, 0

        # --- Verify only p1 prefix ---
        def verify_p1_prefix(p1_val: str, requested_location: str):
            if not p1_val:
                raise HTTPException(status_code=400, detail="No location found at p1")
            prefix = ''.join([ch for ch in p1_val if not ch.isdigit()])
            if prefix != requested_location:
                raise HTTPException(
                    status_code=400,
                    detail=f"Location mismatch at p1: found in location '{prefix}', but trying to remove from '{requested_location}'"
                )

        user_prefix = exit_entry.location.strip().upper() if exit_entry.location else None
        if not user_prefix:
            raise HTTPException(status_code=400, detail="Invalid location: must provide a location character (e.g., 'G')")

        # Run prefix check for p1
        verify_p1_prefix(location_dict.get("p1"), user_prefix)

        # --- Deduct from p1 → p2 → p3 ---
        for idx, key in enumerate(["p1", "p2", "p3"]):
            if remaining_qty <= 0:
                break

            slot_val = location_dict.get(key)
            slot_prefix, slot_qty = split_prefix_qty(slot_val)

            if slot_qty == 0:
                continue  # skip empty slot

            # For p1, prefix must match user prefix (already verified)
            # For p2/p3, take any prefix
            if idx == 0 and slot_prefix != user_prefix:
                continue

            if slot_qty >= remaining_qty:
                location_dict[key] = f"{slot_prefix}{slot_qty - remaining_qty}" if (slot_qty - remaining_qty) > 0 else None
                remaining_qty = 0
            else:
                location_dict[key] = None
                remaining_qty -= slot_qty

        # If still qty left → not enough stock
        if remaining_qty > 0:
            raise HTTPException(
                status_code=400,
                detail=f"Not enough quantity in store to remove {exit_entry.issued_qty}"
            )

         # --- Update monitoring sheet ---
        total = 0
        for key in ["p1", "p2", "p3"]:
            val = location_dict.get(key)
            if val:
                # Extract numeric values from location string (e.g., "G50" -> 50)
                nums = [safe_int(n) for n in re.findall(r'\d+(?:\.\d+)?', str(val))]
                total += sum(nums)

        # Save current stock in monitoring entry
        mongo_handler.store_stock_collection.update_one(
            {"_id": monitoring_entry["_id"]},
            {"$set": {
                "current": total,
                "location": location_dict,
                "timestamp": now.strftime("%d-%m-%Y %I:%M:%S %p")
            }}
        )

        # --- Only after monitoring update → Save exit entry in register ---
        exit_dict = exit_entry.dict()
        exit_dict["_id"] = ObjectId()
        exit_dict["timestamp"] = now.strftime("%d-%m-%Y %I:%M:%S %p")



        # Save Approval photos if present
        if exit_entry.approval_photo:
            approval_urls = save_exit_files(exit_entry.item_description, "approvalPhoto", exit_entry.approval_photo, today_str)
        else:
            approval_urls = []

        # Remove raw Base64 field to avoid empty array
        exit_dict.pop("approval_photo", None)

        # Store URLs in Documents and also optional top-level field
        exit_dict["Documents"] = {"approval_photo": approval_urls}

        mongo_handler.store_stock_register_collection.find_one_and_update(
            {"date": today_str},
            {
                "$push": {"exits": exit_dict},
                "$setOnInsert": {"date": today_str}
            },
            upsert=True,
            return_document=ReturnDocument.AFTER
        )

        return {
            "message": "Store stock exit saved successfully & monitoring updated",
            "date": today_str,
            "exit_id": str(exit_dict["_id"])
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                         
#######################################################################################################
#------------------------------------- GET STORE STOCK (DAILY) --------------------------------------
#######################################################################################################


# Recursive serialization for any nested ObjectId
def serialize_objectid(obj):
    if isinstance(obj, list):
        return [serialize_objectid(item) for item in obj]
    elif isinstance(obj, dict):
        return {k: serialize_objectid(v) for k, v in obj.items()}
    elif isinstance(obj, ObjectId):
        return str(obj)
    else:
        return obj


# @router.get("/get_store_stock_register_entries", response_model=dict)
# def get_store_stock_register_entries(
#     day: Optional[int] = Query(None, ge=1, le=31),
#     month: Optional[int] = Query(None, ge=1, le=12),
#     year: Optional[int] = Query(None, ge),
#     item_description: Optional[str] = Query(None, description="Filter by item description"),
#     record_type: Optional[str] = Query(None, regex="^(entries|exits)$", description="Choose between entries or exits"),
#     skip: int = Query(0, ge=0, description="Number of records to skip"),
#     limit: int = Query(50, ge=1, le=200, description="Maximum number of records to return"),
#     sort_field: str = Query("date", description="Field to sort by, e.g. date or timestamp"),
#     sort_order: int = Query(-1, description="Sort order: -1 for descending, 1 for ascending"),
#     current_user: User = Depends(production_required)
# ):
#     try:
#         # validate sort_order
#         if sort_order not in [-1, 1]:
#             raise HTTPException(status_code=400, detail="sort_order must be -1 or 1")

#         query = {}

        

#         # --- Handle date filters ---
#         if day and month and year:
#             query["date"] = f"{year}-{month:02d}-{day:02d}"
#         elif month and year:
#             start_date = datetime(year, month, 1)
#             end_date = datetime(year, month + 1 if month < 12 else 1, 1)
#             query["date"] = {"$gte": start_date.strftime("%Y-%m-%d"),
#                              "$lt": end_date.strftime("%Y-%m-%d")}
#         elif year:
#             start_date = datetime(year, 1, 1)
#             end_date = datetime(year + 1, 1, 1)
#             query["date"] = {"$gte": start_date.strftime("%Y-%m-%d"),
#                              "$lt": end_date.strftime("%Y-%m-%d")}
#         elif not any([day, month, year]):
#             pass
#         else:
#             raise HTTPException(status_code=400, detail="Invalid date filter combination")

#         # --- Fetch with pagination + sorting ---
#         cursor = (
#             mongo_handler.store_stock_register_collection
#             .find(query)
#             .sort(sort_field, sort_order)
#             .skip(skip)
#             .limit(limit)
#         )
#         docs = list(cursor)

#         # --- Apply filters (item_description, record_type) ---
#         if item_description:
#             for doc in docs:
#                 if record_type == "entries":
#                     doc["entries"] = [e for e in doc.get("entries", []) if e.get("item_description") == item_description]
#                 elif record_type == "exits":
#                     doc["exits"] = [e for e in doc.get("exits", []) if e.get("item_description") == item_description]
#                 else:
#                     doc["entries"] = [e for e in doc.get("entries", []) if e.get("item_description") == item_description]
#                     doc["exits"] = [e for e in doc.get("exits", []) if e.get("item_description") == item_description]

#         if record_type:
#             for doc in docs:
#                 if record_type == "entries":
#                     doc.pop("exits", None)
#                 elif record_type == "exits":
#                     doc.pop("entries", None)

#         serialized_docs = [serialize_objectid(d) for d in docs]

#         return {
#             "count": len(serialized_docs),
#             "skip": skip,
#             "limit": limit,
#             "entries": serialized_docs
#         }

#     except Exception as e:
#         raise HTTPException(status_code=500, detail=str(e))



@router.get("/get_store_stock_register_entries", response_model=dict)
def get_store_stock_register_entries(
    day: Optional[int] = Query(None, ge=1, le=31),
    month: Optional[int] = Query(None, ge=1, le=12),
    year: Optional[int] = Query(None),
    item_description: Optional[str] = Query(None, description="Filter by item description"),
    record_type: Optional[str] = Query(None, regex="^(entries|exits)$", description="Choose between entries or exits"),
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(50, ge=1, le=200, description="Maximum number of records to return"),
    sort_field: str = Query("date", description="Field to sort by, e.g. date or timestamp"),
    sort_order: int = Query(-1, description="Sort order: -1 for descending, 1 for ascending"),
    current_user: User = Depends(production_required)
):
    try:
        # validate sort_order
        if sort_order not in [-1, 1]:
            raise HTTPException(status_code=400, detail="sort_order must be -1 or 1")

        query = {}

        # -----------------------------
        # DATE VALIDATION & FILTER LOGIC
        # -----------------------------

        # ❌ Only day provided → invalid
        if day and not (month and year):
            raise HTTPException(
                status_code=400,
                detail="Day filter requires both month and year."
            )

        # ❌ Only month provided → invalid
        if month and not year:
            raise HTTPException(
                status_code=400,
                detail="Month filter requires the year."
            )

        # ONLY YEAR → filter full year
        if year and not month and not day:
            start_date = datetime(year, 1, 1)
            end_date = datetime(year + 1, 1, 1)
            query["date"] = {
                "$gte": start_date.strftime("%Y-%m-%d"),
                "$lt": end_date.strftime("%Y-%m-%d")
            }

        # YEAR + MONTH → filter full month
        elif year and month and not day:
            start_date = datetime(year, month, 1)
            next_month = month + 1 if month < 12 else 1
            next_year = year + 1 if month == 12 else year
            end_date = datetime(next_year, next_month, 1)

            query["date"] = {
                "$gte": start_date.strftime("%Y-%m-%d"),
                "$lt": end_date.strftime("%Y-%m-%d")
            }

        # YEAR + MONTH + DAY → exact date match
        elif year and month and day:
            query["date"] = f"{year}-{month:02d}-{day:02d}"

        # No date filters → get all data
        elif not any([day, month, year]):
            pass

        # Should never reach here; safety check
        else:
            raise HTTPException(status_code=400, detail="Invalid date filter combination.")

        # -----------------------------
        # FETCH WITH PAGINATION + SORT
        # -----------------------------
        cursor = (
            mongo_handler.store_stock_register_collection
            .find(query)
            .sort(sort_field, sort_order)
            .skip(skip)
            .limit(limit)
        )
        docs = list(cursor)

        # -----------------------------
        # ITEM DESCRIPTION + RECORD TYPE FILTERING
        # -----------------------------
        if item_description:
            for doc in docs:
                if record_type == "entries":
                    doc["entries"] = [
                        e for e in doc.get("entries", [])
                        if e.get("item_description") == item_description
                    ]
                elif record_type == "exits":
                    doc["exits"] = [
                        e for e in doc.get("exits", [])
                        if e.get("item_description") == item_description
                    ]
                else:
                    doc["entries"] = [
                        e for e in doc.get("entries", [])
                        if e.get("item_description") == item_description
                    ]
                    doc["exits"] = [
                        e for e in doc.get("exits", [])
                        if e.get("item_description") == item_description
                    ]

        # Remove unwanted record type
        if record_type:
            for doc in docs:
                if record_type == "entries":
                    doc.pop("exits", None)
                elif record_type == "exits":
                    doc.pop("entries", None)

        # -----------------------------
        # SERIALIZATION
        # -----------------------------
        serialized_docs = [serialize_objectid(d) for d in docs]

        return {
            "count": len(serialized_docs),
            "skip": skip,
            "limit": limit,
            "entries": serialized_docs
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))















#   #Schema
# {
#   "Invoice": [
#     {
#       "filename": "invoice123.pdf",
#       "content": ""
#     }
#   ],
#   "items": [
#     {
#       "item_description": "HDPE",
#       "received_qty": 120,
#       "QC": "OK",
#       "location": "P1",
#       "lot_no": "LOT001",
#       "TC": [
#         {
#           "filename": "TC_BracketD_LH.pdf",
#           "content": ""
#         }
#       ],
#       "remark": "First lot for LH"
#     },
#     {
#       "item_description": "PC",
#       "received_qty": 120,
#       "QC": "OK",
#       "location": "P1",
#       "lot_no": "LOT001",
#       "TC": [
#         {
#           "filename": "TC_PC_WHITE.pdf",
#           "content": ""
#         }
#       ],
#       "remark": "First lot for WHITE"
#     },
#     {
#       "item_description": "PC - 10% DIFFUSION WHITE(CLEAR)",
#       "received_qty": 100,
#       "QC": "OK",
#       "location": "P2",
#       "lot_no": "LOT002",
#       "TC": [
#         {
#           "filename": "TC_PC_DIFFUSION_WHITE.pdf",
#           "content": ""
#         }
#       ],
#       "remark": "First lot for DIFFUSION WHITE"
#     }
#   ]
# }
