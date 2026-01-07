from fastapi import APIRouter, Depends
from RabsProject.cores.auth.authorise import admin_required
from RabsProject.pymodels.models import User
from RabsProject.services.mongodb import MongoDBHandlerSaving
from dotenv import load_dotenv
load_dotenv()


mongo_handler = MongoDBHandlerSaving()
router = APIRouter(tags=["PPE Violations Reports"])


@router.get("/ppe-violations/monthly")
async def get_monthly_ppe_violations(year: int, month: int, current_user: User = Depends(admin_required)):
    
    # MongoDB query to filter records by year and month
    conditions = [
        {"$eq": [{"$year": "$timestamp"}, year]},
        {"$eq": [{"$month": "$timestamp"}, month]}
    ]

    query = {
        "$expr": {
            "$and": conditions
        }
    }

    # Query the MongoDB collection
    cursor = mongo_handler.ppe_violation_collection.find(query).sort("timestamp", -1)

    results = []
    for doc in cursor:
        # Convert the image_path to the public URL format
        if "image_path" in doc:
            # Strip out the absolute path and only keep the relative path
            relative_path = doc["image_path"].replace("/home/aiserver/Desktop/ffmpeg_stream/detected_frames/", "")

            # Ensure no leading slashes are left from the path replacement
            relative_path = relative_path.lstrip("/") 

            # Construct the final image URL
            doc["image_path"] = f"https://rabs.alvision.in/detected_frames/{relative_path}"

        results.append({
            "id": str(doc["_id"]),
            "timestamp": doc["timestamp"],
            "stream_name": doc["stream_name"],
            "image_path": doc["image_path"],
            "voilation_count": doc["voilation_count"]
        })

    return {
        "year": year,
        "month": month,
        "total_records": len(results),
        "data": results
    }