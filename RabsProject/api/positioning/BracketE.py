from datetime import datetime
from ultralytics import YOLO
import logging
import os
from datetime import timedelta, datetime
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from dotenv import load_dotenv
from RabsProject.pymodels.models import User
from RabsProject.services.mongodb import MongoDBHandlerSaving  # Your MongoDB handler
from RabsProject.cores.auth.authorise import get_current_user, production_required
from RabsProject.cores.prediction_logic.image_utils import create_user_dir, process_image

# Setup
logger = logging.getLogger(__name__)
load_dotenv()

HOSTING_LINK = os.getenv("HOSTING_LINK", "http://127.0.0.1:8015")
# MongoDB Setup
mongo_handler = MongoDBHandlerSaving()

# FastAPI Router
router = APIRouter(tags=["Bracket E LH-RH positioning detection"])

# Load Models
detect_model = YOLO("models/e-bracket-det-v2.pt")
classify_model = YOLO("models/e-bracket-cls-v2.pt")

# Sound path
ALARM_PATH = "static/alarm.wav"

# In-memory tracking
file_id_mapping = {}



# @router.post("/upload-bracketE-classification", response_model=dict)
# def upload_bracketE_image(expected_type: str, file: UploadFile = File(...), current_user: User = Depends(production_required)):
#     """
#     Endpoint to upload an image for bracket detection & classification.
#     Expects `expected_type` to be either 'LH' or 'RH'.
#     """
#     try:
#         if not file.filename:
#             raise HTTPException(status_code=400, detail="Invalid file")
#         if not file.content_type or not file.content_type.startswith("image"):
#             raise HTTPException(status_code=400, detail="Uploaded file is not an image")

#         if expected_type not in {"LH", "RH"}:
#             raise HTTPException(status_code=400, detail="Invalid expected_type. Use 'LH' or 'RH'.")

#         # Process the image
#         category = "BracketE"
#         result = process_image(
#             file, current_user.email, detect_model, classify_model, expected_type, category
#         )

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



# @router.get("/bracketE-images-data-classification", response_model=dict)
# def get_all_bracketE_user_images(current_user: User = Depends(production_required)):
#     """
#     Retrieve all images uploaded by the current user.
#     """
#     user_email = current_user.email
#     category = "BracketE"
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


# @router.delete("/delete-bracketE-classification/{file_id}", response_model=dict)
# def delete_bracketE_uploaded_file(file_id: str, current_user: User = Depends(production_required)):
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



# ======================================================
# 🧠 Upload and Process Bracket E Image
# ======================================================
@router.post("/upload-bracketE-classification", response_model=dict)
def upload_bracketE_image(
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

        category = "BracketE"

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
        logger.info(f"✅ Saved BracketE classification data to MongoDB for {current_user.name}")

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



# ======================================================
# 📦 Retrieve All Records for Current User
# ======================================================
@router.get("/bracketE-images-data-classification", response_model=dict)
def get_all_bracketE_user_images(current_user: User = Depends(production_required)):
    try:
        # user_name = current_user.name
        part_name = "BracketE"
        # Find all user-specific BracketE records
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
        logger.error(f"Error fetching BracketE records: {e}")
        raise HTTPException(status_code=500, detail=str(e))


