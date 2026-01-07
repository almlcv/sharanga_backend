from datetime import datetime, date, timezone
from dateutil.relativedelta import relativedelta
from fastapi import APIRouter, Depends, HTTPException, Path
import os, sys
from RabsProject.pymodels.models import *
from zoneinfo import ZoneInfo
from dotenv import load_dotenv
load_dotenv()
HOSTING_LINK = os.getenv("HOSTING_LINK", "http://127.0.0.1:8015") 

from RabsProject.pymodels.models import CustomerComplaintSheet, User
from RabsProject.services.mongodb import MongoDBHandlerSaving  
from RabsProject.cores.auth.authorise import get_current_user, admin_required, QC_required

router = APIRouter(tags=["Customer Complaints Meeting Board"] )
mongo_handler = MongoDBHandlerSaving()
ist = datetime.now(ZoneInfo("Asia/Kolkata"))



@router.post("/submit_customer_complaint_sheet_entry", response_model=dict)
def submit_customer_complaint_sheet_entry(entry: CustomerComplaintSheet,  current_user: User = Depends(QC_required)):
    # entry.timestamp = datetime.now().strftime("%d-%m-%Y %I:%M:%S %p")
    entry.timestamp = datetime.now(timezone.utc)
    inserted_id = mongo_handler.insert_customer_complaint_entry(entry.dict())
    return {"message": "Entry submitted", "id": inserted_id}


@router.get("/get_quarterly_customer_complaint_sheets/{year}/{quarter}")
async def get_quarterly_customer_complaint_sheets(
    year: int = Path(..., ge=2000, le=2100, description="Year in YYYY format"),
    quarter: int = Path(..., ge=1, le=4, description="Quarter (1-4)"),
    current_user: User = Depends(QC_required)):
    try:
        entries = mongo_handler.get_customer_complaint_entry_by_quarter(year, quarter)
        return entries
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/update_customer_complaint_sheet_entry/{entry_id}", response_model=dict)
def update_customer_complaint_sheet_entry(
    entry_id: str,
    updated_entry: CustomerComplaintUpdate,   # use update model
    current_user: User = Depends(QC_required)
):
    try:
        update_data = updated_entry.dict(exclude_unset=True)
        update_data["timestamp"] = datetime.now(timezone.utc)
        mongo_handler.update_customer_complaint_entry(entry_id, update_data)
        return {"message": "customer complaint entry updated successfully", "id": entry_id}
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


