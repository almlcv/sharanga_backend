import os, sys
import logging
from fastapi import APIRouter, Depends, HTTPException
from RabsProject.services.mongodb import MongoDBHandlerSaving
from datetime import datetime, timedelta
from RabsProject.cores.CameraStream.camera_system import *
from RabsProject.pymodels.models import *
from RabsProject.cores.auth.authorise import get_current_active_user, admin_required, get_current_user, get_user, create_access_token
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)
from fastapi import Query
from pydantic import BaseModel
from typing import Optional
from fastapi import APIRouter, HTTPException, Query
from bson import ObjectId
from datetime import datetime, timedelta
from RabsProject.services.mongodb import MongoDBHandlerSaving
from pydantic import BaseModel
from typing import Optional
from dotenv import load_dotenv
load_dotenv()

mongo_handler = MongoDBHandlerSaving()


SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = os.getenv("ALGORITHM")
HOSTING_LINK = os.getenv("HOSTING_LINK", "http://192.168.1.152:8015")  # Default to localhost if not set
ACCESS_TOKEN_EXPIRE_MINUTES = 1440
running_camera_systems = {}


router = APIRouter(
    tags=["Loading and Unloading"] )


class LoadingUnloadingUpdate(BaseModel):
    date: Optional[str] = None
    type_mentioned: Optional[str] = None
    vehicle_type: Optional[str] = None
    entry_time: Optional[str] = None
    exit_time: Optional[str] = None
    duration_seconds: Optional[int] = None
    entry_image_path: Optional[str] = None
    exit_image_path: Optional[str] = None
    remarks: Optional[str] = None


@router.put("/update-loading-unloading/update/{id}")
async def update_loading_unloading(id: str, update_data: LoadingUnloadingUpdate):
    try:

        collection = mongo_handler.loading_unloading_collection

        # Remove None fields
        update_dict = {k: v for k, v in update_data.dict().items() if v is not None}

        result = collection.update_one(
            {"_id": ObjectId(id)},
            {"$set": update_dict}
        )

        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="Record not found")

        updated_doc = collection.find_one({"_id": ObjectId(id)})
        updated_doc["_id"] = str(updated_doc["_id"])

        return {
            "status": "success",
            "message": "Record updated successfully",
            "data": updated_doc
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/get_vehicle-movement/monthly")
async def get_monthly_vehicle_movement(
    year: int = Query(..., description="Year (e.g., 2025)"),
    month: int = Query(..., ge=1, le=12, description="Month (1-12)"),
    current_user: User = Depends(admin_required)
    ):

    try:
        # Compute start and end of month
        start_date = datetime(year, month, 1)
        if month == 12:
            end_date = datetime(year + 1, 1, 1) - timedelta(seconds=1)
        else:
            end_date = datetime(year, month + 1, 1) - timedelta(seconds=1)

        collection = mongo_handler.loading_unloading_collection

        # Query MongoDB
        cursor = collection.find({
            "entry_time": {"$gte": start_date, "$lte": end_date}
        }).sort("entry_time", 1)

        data = []
        for doc in cursor:
            doc["_id"] = str(doc["_id"])

            # Handle entry_time and exit_time
            if "entry_time" in doc:
                doc["entry_time"] = doc["entry_time"].isoformat()
            if "exit_time" in doc and doc["exit_time"]:
                doc["exit_time"] = doc["exit_time"].isoformat()

            # Modify image paths to full URLs
            if "entry_image_path" in doc:
                # Strip the local file path and prepend the public URL
                relative_path = doc["entry_image_path"].replace("/home/aiserver/Desktop/ffmpeg_stream/detected_frames", "")
                doc["entry_image_path"] = f"https://rabs.alvision.in/detected_frames{relative_path}"

            if "exit_image_path" in doc:
                # Strip the local file path and prepend the public URL
                relative_path = doc["exit_image_path"].replace("/home/aiserver/Desktop/ffmpeg_stream/detected_frames", "")
                doc["exit_image_path"] = f"https://rabs.alvision.in/detected_frames{relative_path}"

            data.append(doc)

        return {
            "status": "success",
            "count": len(data),
            "month": month,
            "year": year,
            "data": data
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )


