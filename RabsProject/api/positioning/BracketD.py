from datetime import datetime
from ultralytics import YOLO
import logging
import os
from datetime import timedelta, datetime
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from dotenv import load_dotenv
from RabsProject.pymodels.models import User
from RabsProject.cores.auth.authorise import get_current_user, production_required
from RabsProject.cores.prediction_logic.image_utils import create_user_dir, process_image

# Setup
logger = logging.getLogger(__name__)
load_dotenv()

HOSTING_LINK = os.getenv("HOSTING_LINK", "http://127.0.0.1:8015")


# FastAPI Router
router = APIRouter(tags=["Bracket D LH-RH positioning detection"])

# Load Models
detect_model = YOLO("models/d-bracket-det-newV5.pt")
classify_model = YOLO("models/d-bracket-cls-newV5.pt")

# Sound path
ALARM_PATH = "static/alarm.wav"

# In-memory tracking
file_id_mapping = {}


# @router.post("/upload-bracketD-classification", response_model=dict)
# def upload_bracketD_image(expected_type: str, file: UploadFile = File(...), current_user: User = Depends(production_required)):
#     try:
#         if not file.filename:
#             raise HTTPException(status_code=400, detail="Invalid file")
#         if not file.content_type or not file.content_type.startswith("image"):
#             raise HTTPException(status_code=400, detail="Uploaded file is not an image")

#         if expected_type not in {"LH", "RH"}:
#             raise HTTPException(status_code=400, detail="Invalid expected_type. Use 'LH' or 'RH'.")

#         # Process the image
#         category = "BracketD"
#         result = process_image(
#             file, current_user.email, detect_model, classify_model, expected_type, category )

#         file_id = result["file_id"]
#         original_filename = result["original_filename"]
#         processed_filename = result["processed_filename"]
#         original_path = result["original_path"]
#         processed_path = result["processed_path"]
#         timestamp = result["timestamp"]  # This is likely a string
#         incorrect_count = result["incorrect_count"]
#         total_count = result["total_count"]

#         # Convert string timestamp to datetime if needed
#         if isinstance(timestamp, str):
#             try:
#                 timestamp = datetime.strptime(timestamp, "%Y%m%d_%H%M%S")
#             except ValueError:
#                 logger.warning(f"Unrecognized timestamp format: {timestamp}")
#                 timestamp = datetime.utcnow()

#         # Convert UTC to IST
#         ist_timestamp = timestamp + timedelta(hours=5, minutes=30)
#         date_str = ist_timestamp.date().isoformat()
#         time_str = ist_timestamp.time().strftime("%H:%M:%S")

#         file_id_mapping[file_id] = {
#             "original": original_path,
#             "processed": processed_path,
#             "user_email": current_user.email,
#             "original_filename": file.filename,
#             "timestamp": timestamp
#         }

#         # Trigger alarm if there are incorrect brackets
#         if incorrect_count > 0:
#             if os.path.exists(ALARM_PATH):
#                 os.system(f"aplay {ALARM_PATH}")
#             else:
#                 logger.warning("Alarm sound file not found at static/alarm.wav")

#         return {
#             "success": True,
#             "date": date_str,
#             "time": time_str,
#             "category": category,
#             "total_brackets_detected": total_count,
#             "incorrect_brackets": incorrect_count,
#             "file_id": file_id,
#             "original_url": f"{HOSTING_LINK}/classification/uploads/{category}/{current_user.email}/{original_filename}",
#             "processed_url": f"{HOSTING_LINK}/classification/uploads/{category}/{current_user.email}/{processed_filename}"
#         }

#     except Exception as e:
#         logger.error(f"Upload error: {e}")
#         raise HTTPException(status_code=500, detail=str(e))


# @router.get("/bracketD-images-data-classification", response_model=dict)
# def get_all_bracketD_user_images(current_user: User = Depends(production_required)):
#     user_email = current_user.email
#     category = "BracketD"
#     user_dir = os.path.join("classification/uploads", category, user_email)

#     if not os.path.exists(user_dir):
#         return {"total_pairs": 0, "images": []}

#     images = []
#     files = os.listdir(user_dir)
#     originals = [f for f in files if not f.startswith("processed_")]

#     for original in originals:
#         processed = f"processed_{original}"
#         if os.path.exists(os.path.join(user_dir, processed)):
#             parts = original.split('_')
#             timestamp = parts[0] if len(parts) > 0 else None
#             images.append({
#                 "file_id": original,
#                 "original_url": f"{HOSTING_LINK}/classification/uploads/{category}/{user_email}/{original}",
#                 "processed_url": f"{HOSTING_LINK}/classification/uploads/{category}/{user_email}/{processed}",
#                 "timestamp": timestamp
#             })

#     return {
#         "total_pairs": len(images),
#         "images": images
#     }


# @router.delete("/delete-bracketD-classification/{file_id}", response_model=dict)
# def delete_bracketD_uploaded_file(file_id: str, current_user: User = Depends(production_required)):
#     """
#     Delete original and processed images associated with a given file_id.
#     """
#     try:
#         # Step 1: Check file_id exists
#         if file_id not in file_id_mapping:
#             raise HTTPException(status_code=404, detail="File ID not found")

#         file_info = file_id_mapping[file_id]

#         # Step 2: Check if user is authorized to delete this file
#         if file_info["user_email"] != current_user.email:
#             raise HTTPException(status_code=403, detail="Not authorized to delete this file")

#         # Step 3: Attempt deletion
#         deleted_files = []
#         for path_key in ["original", "processed"]:
#             path = file_info.get(path_key)
#             if path and os.path.exists(path):
#                 os.remove(path)
#                 deleted_files.append(path)

#         # Step 4: Clean up mapping
#         del file_id_mapping[file_id]

#         return {
#             "success": True,
#             "deleted_files": deleted_files,
#             "file_id": file_id,
#             "message": "Files deleted successfully"
#         }

#     except Exception as e:
#         logger.error(f"File deletion error for file_id={file_id}: {str(e)}")
#         raise HTTPException(status_code=500, detail="Internal server error")




#########################################################################################################
#######################################  New Updated code  ##############################################
#########################################################################################################




from datetime import datetime, timedelta
from ultralytics import YOLO
import logging
import os
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from dotenv import load_dotenv
from RabsProject.pymodels.models import User
from RabsProject.cores.auth.authorise import production_required
from RabsProject.cores.prediction_logic.image_utils import process_image
from RabsProject.services.mongodb import MongoDBHandlerSaving  # Your MongoDB handler


from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional
from RabsProject.services.mongodb import MongoDBHandlerSaving
from RabsProject.cores.auth.authorise import production_required
from RabsProject.pymodels.models import User
from pymongo import ASCENDING
import re
import math


# ======================================================
# Setup
# ======================================================
logger = logging.getLogger(__name__)
load_dotenv()

HOSTING_LINK = os.getenv("HOSTING_LINK", "http://127.0.0.1:8015")

router = APIRouter(tags=["Bracket D LH-RH positioning detection"])

# Load YOLO models
detect_model = YOLO("models/d-bracket-det-newV5.pt")
classify_model = YOLO("models/d-bracket-cls-newV5.pt")

# Sound path
ALARM_PATH = "static/alarm.wav"

# MongoDB Setup
mongo_handler = MongoDBHandlerSaving()


# ======================================================
# 🧠 Upload and Process Bracket D Image
# ======================================================
@router.post("/upload-bracketD-classification", response_model=dict)
def upload_bracketD_image(
    expected_type: str,
    file: UploadFile = File(...),
    current_user: User = Depends(production_required)
):
    try:
        # Validate uploaded file
        if not file.filename:
            raise HTTPException(status_code=400, detail="Invalid file")
        if not file.content_type or not file.content_type.startswith("image"):
            raise HTTPException(status_code=400, detail="Uploaded file is not an image")
        if expected_type not in {"LH", "RH"}:
            raise HTTPException(status_code=400, detail="Invalid expected_type. Use 'LH' or 'RH'.")

        category = "BracketD"

        # Process image
        result = process_image(
            file, current_user.name, detect_model, classify_model, expected_type, category
        )

        file_id = result["file_id"]
        original_filename = result["original_filename"]
        processed_filename = result["processed_filename"]
        timestamp = result["timestamp"]
        incorrect_count = result["incorrect_count"]
        total_count = result["total_count"]
        correct_count = total_count - incorrect_count

        # Convert timestamp string → datetime
        if isinstance(timestamp, str):
            try:
                timestamp = datetime.strptime(timestamp, "%Y%m%d_%H%M%S")
            except ValueError:
                logger.warning(f"Unrecognized timestamp format: {timestamp}")
                timestamp = datetime.now()

        # Convert to IST timezone
        # ist_timestamp = timestamp + timedelta(hours=5, minutes=30)
        date_str = timestamp.date().isoformat()
        time_str = timestamp.time().strftime("%H:%M:%S")
        brackets_per_bins = 40  # Assuming fixed value as per original logic

        # Trigger alarm if incorrect detected
        if incorrect_count > 0:
            incorrect_bin = True
            if os.path.exists(ALARM_PATH):
                os.system(f"aplay {ALARM_PATH}")
            else:
                logger.warning("Alarm sound file not found at static/alarm.wav")
        else:
            incorrect_bin = False


        # ======================================================
        # Prepare data for MongoDB (Nested Structure)
        # ======================================================
        record = {
            "part_name": category,
            "details": {
                "incorrect_bin": incorrect_bin,
                "user_name": current_user.name,
                "date": date_str,
                "time": time_str,
                "expected_type": expected_type,
                "total_brackets_detected": total_count,
                "correct_brackets": correct_count,
                "incorrect_brackets": incorrect_count,
                "brackets_per_bins": brackets_per_bins,
                "original_url": f"{HOSTING_LINK}/classification/uploads/{category}/{current_user.name}/{original_filename}",
                "processed_url": f"{HOSTING_LINK}/classification/uploads/{category}/{current_user.name}/{processed_filename}",
                "created_at": datetime.now(),
            },
        }

        # Save to MongoDB
        insert_result = mongo_handler.sharanga_vision_collection.insert_one(record)
        logger.info(f"✅ Saved BracketD classification data to MongoDB for {current_user.name}")

        # Safely convert ObjectId to string before returning
        record["_id"] = str(insert_result.inserted_id)

        # Return clean response
        return {
            "success": True,
            "incorrect_bin": incorrect_bin,
            "date": date_str,
            "time": time_str,
            "total_brackets_detected": total_count,
            "incorrect_brackets": incorrect_count,
            "correct_brackets": correct_count,
            "brackets_per_bins": brackets_per_bins,
            "category": category,
            "details": record["details"],
            "mongo_id": record["_id"]
        }

    except Exception as e:
        logger.error(f"Upload error: {e}")
        raise HTTPException(status_code=500, detail=str(e))



# # ======================================================
# # 📦 Retrieve All Records for Current User
# # ======================================================
# @router.get("/bracketD-images-data-classification", response_model=dict)
# def get_all_bracketD_user_images(current_user: User = Depends(production_required)):
#     try:
#         # user_name = current_user.name
#         part_name = "BracketD"

#         # Find all user-specific BracketD records
#         records = list(
#             mongo_handler.sharanga_vision_collection.find(
#                 {"part_name": part_name},
#                 {"_id": 0}
#             )
#         )

#         return {
#             "total_records": len(records),
#             "records": records
#         }

#     except Exception as e:
#         logger.error(f"Error fetching BracketD records: {e}")
#         raise HTTPException(status_code=500, detail=str(e))


@router.get("/bracketD-images-data-classification", response_model=dict)
def get_all_bracketD_user_images(current_user: User = Depends(production_required)):
    try:
        part_name = "BracketD"

        # Fetch records sorted by created_at DESC (-1)
        records = list(
            mongo_handler.sharanga_vision_collection.find(
                {"part_name": part_name},
                {"_id": 0}
            ).sort("details.created_at", -1)
        )

        return {
            "total_records": len(records),
            "records": records
        }

    except Exception as e:
        logger.error(f"Error fetching BracketD records: {e}")
        raise HTTPException(status_code=500, detail=str(e))



@router.get("/get_sharanga_vision_report", response_model=dict)
def get_sharanga_vision_report(
    part_name: Optional[str] = Query(None, description="Filter by part name (e.g., 'BracketD')"),
    date: Optional[str] = Query(None, description="Filter by date in 'YYYY-MM-DD' format"),
    search: Optional[str] = Query(None, description="Search across any field (part_name, date, user_name, etc.)"),
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(10, ge=1, le=100, description="Results per page"),
    current_user: User = Depends(production_required)
):
    try:
        mongo_handler = MongoDBHandlerSaving()
        collection = mongo_handler.sharanga_vision_collection

        # ---------------------------
        # 🔧 Build dynamic match query
        # ---------------------------
        match_stage = {}
        if part_name:
            match_stage["part_name"] = part_name
        if date:
            match_stage["details.date"] = date
        if search:
            regex = re.compile(search, re.IGNORECASE)
            match_stage["$or"] = [
                {"part_name": regex},
                {"details.date": regex},
                {"details.user_name": regex},
                {"details.expected_type": regex}
            ]

        # ---------------------------
        # 📊 Aggregation Pipeline
        # ---------------------------
        pipeline = [
            {"$match": match_stage} if match_stage else {"$match": {}},
            {
                "$group": {
                    "_id": {
                        "date": "$details.date",
                        "part_name": "$part_name"
                    },
                    "total_bins": {"$sum": 1},
                    "brackets_per_bin": {"$avg": "$details.brackets_per_bins"},
                    "incorrect_bins": {
                        "$sum": {"$cond": [{"$eq": ["$details.incorrect_bin", True]}, 1, 0]}
                    },
                    "total_incorrect_brackets": {"$sum": "$details.incorrect_brackets"}
                }
            },
            {
                "$project": {
                    "_id": 0,
                    "date": "$_id.date",
                    "part_name": "$_id.part_name",
                    "total_bins": 1,
                    "brackets_per_bin": {"$round": ["$brackets_per_bin", 0]},
                    "incorrect_bins": 1,
                    "total_incorrect_brackets": 1
                }
            },
            {"$sort": {"date": 1, "part_name": 1}}
        ]

        all_data = list(collection.aggregate(pipeline))

        # ---------------------------
        # 📄 Pagination Logic
        # ---------------------------
        total = len(all_data)
        total_pages = math.ceil(total / limit)
        start = (page - 1) * limit
        end = start + limit
        paginated_data = all_data[start:end]

        return {
            "success": True,
            "total": total,
            "totalPages": total_pages,
            "currentPage": page,
            "data": paginated_data
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating Sharanga Vision report: {e}")





# @router.get("/get_sharanga_report", response_model=dict)
# def get_sharanga_vision_report(
#     part_name: Optional[str] = Query(None, description="Filter by part name (e.g., 'BracketD')"),
#     date: Optional[str] = Query(None, description="Filter by exact date in 'YYYY-MM-DD' format"),
#     month: Optional[int] = Query(None, ge=1, le=12, description="Filter by month (1-12)"),
#     year: Optional[int] = Query(None, ge=2000, description="Filter by year (e.g., 2025)"),
#     search: Optional[str] = Query(None, description="Search across fields (part_name, date, user_name, expected_type)"),
#     page: int = Query(1, ge=1, description="Page number"),
#     limit: int = Query(10, ge=1, le=100, description="Results per page"),
#     current_user: User = Depends(production_required)
# ):
#     try:
#         mongo_handler = MongoDBHandlerSaving()
#         collection = mongo_handler.sharanga_vision_collection

#         # ---------------------------
#         # 🔧 Build dynamic match query
#         # ---------------------------
#         match_stage = {}

#         if part_name:
#             match_stage["part_name"] = part_name

#         if date:
#             match_stage["details.date"] = date

#         # Month filter → extract month from "YYYY-MM-DD"
#         if month:
#             match_stage["$expr"] = {
#                 "$eq": [
#                     {"$toInt": {"$substr": ["$details.date", 5, 2]}},
#                     month
#                 ]
#             }

#         # Year filter → extract year from "YYYY-MM-DD"
#         if year:
#             year_expr = {
#                 "$eq": [
#                     {"$toInt": {"$substr": ["$details.date", 0, 4]}},
#                     year
#                 ]
#             }

#             # Merge with existing $expr
#             if "$expr" in match_stage:
#                 match_stage["$expr"] = {"$and": [match_stage["$expr"], year_expr]}
#             else:
#                 match_stage["$expr"] = year_expr

#         # Search filter
#         if search:
#             regex = re.compile(search, re.IGNORECASE)
#             match_stage["$or"] = [
#                 {"part_name": regex},
#                 {"details.date": regex},
#                 {"details.user_name": regex},
#                 {"details.expected_type": regex}
#             ]

#         # ---------------------------
#         # 📊 Aggregation Pipeline
#         # ---------------------------
#         pipeline = [
#             {"$match": match_stage if match_stage else {}},
#             {
#                 "$group": {
#                     "_id": {
#                         "date": "$details.date",
#                         "part_name": "$part_name"
#                     },
#                     "total_bins": {"$sum": 1},
#                     "brackets_per_bin": {"$avg": "$details.brackets_per_bins"},
#                     "incorrect_bins": {
#                         "$sum": {"$cond": [{"$eq": ["$details.incorrect_bin", True]}, 1, 0]}
#                     },
#                     "total_incorrect_brackets": {"$sum": "$details.incorrect_brackets"}
#                 }
#             },
#             {
#                 "$project": {
#                     "_id": 0,
#                     "date": "$_id.date",
#                     "part_name": "$_id.part_name",
#                     "total_bins": 1,
#                     "brackets_per_bin": {"$round": ["$brackets_per_bin", 0]},
#                     "incorrect_bins": 1,
#                     "total_incorrect_brackets": 1
#                 }
#             },
#             {"$sort": {"date": 1, "part_name": 1}}
#         ]

#         all_data = list(collection.aggregate(pipeline))

#         # ---------------------------
#         # 📄 Pagination
#         # ---------------------------
#         total = len(all_data)
#         total_pages = math.ceil(total / limit)
#         start = (page - 1) * limit
#         end = start + limit

#         return {
#             "success": True,
#             "total": total,
#             "totalPages": total_pages,
#             "currentPage": page,
#             "data": all_data[start:end]
#         }

#     except Exception as e:
#         raise HTTPException(status_code=500, detail=f"Error generating Sharanga Vision report: {e}")

@router.get("/get_sharanga_report", response_model=dict)
def get_sharanga_vision_report(
    part_name: Optional[str] = Query(None, description="Filter by part name (e.g., 'BracketD')"),
    date: Optional[str] = Query(None, description="Filter by exact date in 'YYYY-MM-DD' format"),
    month: Optional[int] = Query(None, ge=1, le=12, description="Filter by month (1-12)"),
    year: Optional[int] = Query(None, ge=2000, description="Filter by year (e.g., 2025)"),
    search: Optional[str] = Query(None, description="Search across fields (part_name, date, user_name, expected_type)"),
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(10, ge=1, le=100, description="Results per page"),
    current_user: User = Depends(production_required)
):
    try:
        mongo_handler = MongoDBHandlerSaving()
        collection = mongo_handler.sharanga_vision_collection

        # ==========================================================
        # ⭐ Utility to convert Mongo ObjectId → String
        # ==========================================================
        def clean_mongo_document(doc):
            if "_id" in doc:
                doc["_id"] = str(doc["_id"])

            # Convert created_at to ISO string
            if "details" in doc:
                if isinstance(doc["details"].get("created_at"), datetime):
                    doc["details"]["created_at"] = doc["details"]["created_at"].isoformat()

            return doc

        # ==========================================================
        # 🔧 Build dynamic match query
        # ==========================================================
        match_stage = {}

        if part_name:
            match_stage["part_name"] = part_name

        if date:
            match_stage["details.date"] = date

        # Month filter → extract month from "YYYY-MM-DD"
        if month:
            match_stage["$expr"] = {
                "$eq": [
                    {"$toInt": {"$substr": ["$details.date", 5, 2]}},
                    month
                ]
            }

        # Year filter → extract year from "YYYY-MM-DD"
        if year:
            year_expr = {
                "$eq": [
                    {"$toInt": {"$substr": ["$details.date", 0, 4]}},
                    year
                ]
            }

            if "$expr" in match_stage:
                match_stage["$expr"] = {"$and": [match_stage["$expr"], year_expr]}
            else:
                match_stage["$expr"] = year_expr

        # Search filter
        if search:
            regex = re.compile(search, re.IGNORECASE)
            match_stage["$or"] = [
                {"part_name": regex},
                {"details.date": regex},
                {"details.user_name": regex},
                {"details.expected_type": regex}
            ]

        # ==========================================================
        # 📊 Aggregation Pipeline (Grouped Summary)
        # ==========================================================
        pipeline = [
            {"$match": match_stage if match_stage else {}},
            {
                "$group": {
                    "_id": {
                        "date": "$details.date",
                        "part_name": "$part_name"
                    },
                    "total_bins": {"$sum": 1},
                    "brackets_per_bin": {"$avg": "$details.brackets_per_bins"},
                    "incorrect_bins": {
                        "$sum": {"$cond": [{"$eq": ["$details.incorrect_bin", True]}, 1, 0]}
                    },
                    "total_incorrect_brackets": {"$sum": "$details.incorrect_brackets"}
                }
            },
            {
                "$project": {
                    "_id": 0,
                    "date": "$_id.date",
                    "part_name": "$_id.part_name",
                    "total_bins": 1,
                    "brackets_per_bin": {"$round": ["$brackets_per_bin", 0]},
                    "incorrect_bins": 1,
                    "total_incorrect_brackets": 1
                }
            },
            {"$sort": {"date": 1, "part_name": 1}}
        ]

        summary_data = list(collection.aggregate(pipeline))

        # ==========================================================
        # 📄 Pagination for Summary Data
        # ==========================================================
        total = len(summary_data)
        total_pages = math.ceil(total / limit)
        start = (page - 1) * limit
        end = start + limit
        paginated_summary = summary_data[start:end]

        # ==========================================================
        # 📥 Fetch RAW DOCUMENTS (Full MongoDB Records)
        # ==========================================================
        raw_docs = list(collection.find(
            match_stage,
            {"_id": 1, "details": 1, "part_name": 1}
        ))

        # Convert ObjectId → string
        raw_docs = [clean_mongo_document(doc) for doc in raw_docs]

        # ==========================================================
        # ✅ Final Response
        # ==========================================================
        return {
            "success": True,
            "summary": paginated_summary,
            "raw_documents": raw_docs,
            "totalSummaryRows": total,
            "totalPages": total_pages,
            "currentPage": page
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating Sharanga Vision report: {e}")



