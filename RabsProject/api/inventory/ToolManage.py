from datetime import datetime, date, timezone
from fastapi import APIRouter, Depends, HTTPException, Path
import os, sys
from zoneinfo import ZoneInfo
from RabsProject.config.ToolMConfig import DEFAULT_MONTHLY_TOOL_MANAGEMENT_ENTRIES
from dotenv import load_dotenv
load_dotenv()
HOSTING_LINK = os.getenv("HOSTING_LINK", "http://127.0.0.1:8015") 

from RabsProject.pymodels.models import *
from RabsProject.services.mongodb import MongoDBHandlerSaving  
from RabsProject.cores.auth.authorise import get_current_user, admin_required, production_required

router = APIRouter(tags=["Tool Manage Board"] )
mongo_handler = MongoDBHandlerSaving()
ist = datetime.now(ZoneInfo("Asia/Kolkata"))


########################################## DAILY TOOL MANAGEMENT ##########################################

@router.post("/submit_tool_management_sheet_entry", response_model=dict)
def submit_tool_management_sheet_entry(entry: ToolManageSheet, current_user: User = Depends(production_required)):
    month, year = datetime.now().month, datetime.now().year
    
    # update using attributes
    entry.month = month
    entry.year = year
    entry.timestamp = datetime.now(timezone.utc)
    
    inserted_id = mongo_handler.insert_tool_management_entry(entry.dict())
    return {"message": "Entry submitted", "id": inserted_id}


@router.put("/update_tool_management_sheet_entry/{entry_id}", response_model=dict)
def update_tool_management_sheet_entry(
    entry_id: str,
    updated_entry: ToolManageSheet,
    current_user: User = Depends(production_required)
):
    try:
        update_data = updated_entry.dict(exclude_unset=True)
        update_data["updated_at"] = datetime.now(timezone.utc)   # <-- correct way

        modified_count = mongo_handler.update_tool_management_entry(entry_id, update_data)
        if not modified_count:
            raise HTTPException(status_code=404, detail="Entry not found")

        return {"message": "Tool management entry updated successfully", "id": entry_id}
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")




@router.get("/get_monthly_tool_management_sheets/{year}/{month}")
async def get_monthly_tool_management_sheets(
    year: int, 
    month: int, 
    current_user: User = Depends(production_required)
):
    try:
        # Fetch existing entries for the given year and month
        existing_entries = list(mongo_handler.tool_manage_collection.find({
            "year": year,
            "month": month
        }))
        updated_entries = []
        if existing_entries:
            # Format entries by converting ObjectId and removing raw _id
            for entry in existing_entries:
                entry_copy = entry.copy()
                entry_copy["_id"] = str(entry_copy["_id"])
                updated_entries.append(entry_copy)
            return {"message": "Entries fetched from MongoDB", "entries": updated_entries}

        # --- If no entries found, insert default entries ---
        # Step 1: Find previous month
        prev_year, prev_month = (year, month - 1) if month > 1 else (year - 1, 12)

        # Step 2: Get last month's entries
        prev_entries = list(mongo_handler.tool_manage_collection.find({
            "year": prev_year,
            "month": prev_month
        }))

        inserted_entries = []
        for entry in DEFAULT_MONTHLY_TOOL_MANAGEMENT_ENTRIES:
            entry_copy = entry.copy()

            # Try to get last_pm_date from previous month actual_pm_date
            last_pm_date = None
            if prev_entries:
                for prev_entry in prev_entries:
                    if prev_entry.get("mould_name") == entry["mould_name"]:
                        last_pm_date = prev_entry.get("actual_pm_date")
                        break

            entry_copy.update({
                "timestamp": datetime.now(timezone.utc),
                "year": year,
                "month": month,
                "last_pm_date": last_pm_date if last_pm_date else entry.get("last_pm_date", "")
            })

            inserted_id = mongo_handler.insert_tool_management_entry(entry_copy)
            entry_copy["_id"] = str(inserted_id)
            inserted_entries.append(entry_copy)

        return {"message": "Default entries created", "entries": inserted_entries}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

