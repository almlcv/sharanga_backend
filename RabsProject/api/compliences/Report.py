from fastapi import APIRouter, Depends, HTTPException
import os, sys
from dotenv import load_dotenv
load_dotenv()
HOSTING_LINK = os.getenv("HOSTING_LINK", "http://127.0.0.1:8015") 

from RabsProject.pymodels.models import *
from RabsProject.services.mongodb import MongoDBHandlerSaving  
from RabsProject.cores.auth.authorise import get_current_user, admin_required



router = APIRouter(
    tags=["Detection Report Snapshots"])

mongo_handler = MongoDBHandlerSaving()

@router.get("/snapdate_count-daywise/{year}/{month}/{day}", response_model=SnapshotCountResponse)
async def get_snapshots_with_count(year: int, month: int, day: int, camera_id: str, category: str, current_user: User = Depends(admin_required)):
    try:
        snapshots = mongo_handler.fetch_snapshots_by_date_and_camera(year, month, day, camera_id, category)
        if snapshots:
            for snap in snapshots:
                if not snap['path'].startswith("http"):
                    snap['path'] = f"{HOSTING_LINK}{snap['path']}"
            return SnapshotCountResponse(count=len(snapshots), snapshots=snapshots)
        raise HTTPException(status_code=404, detail="Snapshots not found for the given date")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/snapdate_count-timerange/{year}/{month}/{day}", response_model=SnapshotCountResponse)
async def get_snapshots_with_count_by_time_range(
    year: int, month: int, day: int, category: str,
    start_time: str, end_time: str, camera_id: str, current_user: User = Depends(admin_required)):
    try:
        snapshots = mongo_handler.fetch_snapshots_by_time_range(year, month, day, start_time, end_time, camera_id, category)
        if snapshots:
            for snap in snapshots:
                if not snap['path'].startswith("http"):
                    snap['path'] = f"{HOSTING_LINK}{snap['path']}"
            return SnapshotCountResponse(count=len(snapshots), snapshots=snapshots)
        raise HTTPException(status_code=404, detail="Snapshots not found for given time range")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/snapmonth/{year}/{month}", response_model=SnapshotCountResponse )
async def get_snapshots_by_month(year: int, month: int, camera_id: str, category: str, current_user: User = Depends(admin_required)):
    try:
        snapshots = mongo_handler.fetch_snapshots_by_month_and_camera(year, month, camera_id, category)
        if snapshots:
            for snap in snapshots:
                if not snap['path'].startswith("http"):
                    snap['path'] = f"{HOSTING_LINK}{snap['path']}"
            return SnapshotCountResponse(count=len(snapshots), snapshots=snapshots)
        raise HTTPException(status_code=404, detail="No snapshots found for the given month")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/snapshots_all-daywise/{year}/{month}/{day}", response_model=SnapshotMultiResponse)
async def get_all_snapshots_by_date( year: int, month: int,  day: int, current_user: User = Depends(admin_required) ):
    try:
        result = mongo_handler.fetch_all_cameras_by_date(year, month, day)
        if not result:
            raise HTTPException(status_code=404, detail="No snapshot data found for the given date.")

        total_images = 0
        response_data = []

        for category, cameras in result.items():
            camera_groups = []
            for camera_id, images in cameras.items():
                for image in images:
                    if not image["path"].startswith("http"):
                        image["path"] = f"{HOSTING_LINK}{image['path']}"
                total_images += len(images)
                camera_groups.append(SnapshotGroup(camera_id=camera_id, images=images))
            response_data.append(SnapshotCategoryData(category=category, cameras=camera_groups))

        return SnapshotMultiResponse(
            date=f"{year:04d}-{month:02d}-{day:02d}",
            total_images=total_images,
            data=response_data
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
