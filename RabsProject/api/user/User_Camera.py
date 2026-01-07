import os, sys
import ast
import logging
logger = logging.getLogger(__name__)
from fastapi import APIRouter, Depends, HTTPException, status
from datetime import datetime
from fastapi import Depends
from zoneinfo import ZoneInfo
from RabsProject.pymodels.models import UserInput, CameraInput, User, PasswordChangeRequest
from RabsProject.cores.auth.authorise import get_current_active_user, admin_required, get_password_hash
from RabsProject.services.mongodb import MongoDBHandlerSaving
from RabsProject.exception import RabsException



mongo_handler = MongoDBHandlerSaving()
router = APIRouter(
    tags=["User Detail and Camera Management"] )



@router.post("/add_new_user")
def add_user(user: UserInput):
    """API to add a new user to MongoDB (no cameras at creation)."""
    try:
        existing_user = mongo_handler.user_collection.find_one({"email": user.email})

        if existing_user:
            raise HTTPException(status_code=400, detail="User already exists.")

        user_data = {
            "name": user.name,
            "email": user.email,
            "password": get_password_hash(user.password),  # Hash password
            "role": user.role,
            "cameras": {}  # Start with empty camera structure
        }

        result = mongo_handler.user_collection.insert_one(user_data)

        if not result.inserted_id:
            raise HTTPException(status_code=500, detail="Failed to create user.")

        return {
            "message": "User added successfully",
            "email": user.email
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/get_user_details/{email}")
def get_user_details(email: str, current_user: User = Depends(admin_required)):
    """Get user details (admin only)"""
    try:
        user_data = mongo_handler.get_user_data(email)
        
        if not user_data:
            raise HTTPException(
                status_code=404,
                detail="User not found"
            )
            
        return {
            "message": "User details retrieved successfully",
            "user": user_data
        }
        
    except Exception as e:
        raise RabsException(e, sys) from e


@router.get("/get_my_details")
def get_my_details(current_user: User = Depends(get_current_active_user)):
    """Get current user's details"""
    try:
        user_data = mongo_handler.get_user_data(current_user.email)
        
        if not user_data:
            raise HTTPException(
                status_code=404,
                detail="User not found"
            )
            
        return {
            "message": "User details retrieved successfully",
            "user": user_data
        }
        
    except Exception as e:
        raise RabsException(e, sys) from e


@router.delete("/delete_user/{email}")
def delete_user(email: str, current_user: User = Depends(admin_required)):
    """Delete a user (admin only)"""
    try:
        # Prevent admin from deleting themselves
        if email == current_user.email:
            raise HTTPException(
                status_code=400,
                detail="Cannot delete your own admin account"
            )
            
        if mongo_handler.delete_user(email):
            return {
                "message": "User deleted successfully",
                "email": email
            }
        else:
            raise HTTPException(
                status_code=404,
                detail="User not found or deletion failed"
            )
            
    except Exception as e:
        raise RabsException(e, sys) from e


@router.post("/reset_password")
def reset_password(email: str):
    try:
        if mongo_handler.reset_password(email):
            return {
                "message": "Password reset successfully",
                "email": email
            }
        else:
            raise HTTPException(
                status_code=404,
                detail="User not found or password reset failed"
            )
            
    except Exception as e:
        raise RabsException(e, sys) from e
    

@router.post("/change-temp-password")
async def change_temp_password(request: PasswordChangeRequest, current_user: User = Depends(get_current_active_user)):
    """
    Change temporary password to a new permanent password
    """
    try:
        db = MongoDBHandlerSaving()
        
        # Attempt to change password
        result = db.change_temp_password(
            email=current_user.email,
            temp_password=request.temp_password,
            new_password=request.new_password
        )
        
        if result:
            return {
                "status": "success",
                "message": "Password changed successfully",
                "timestamp": datetime.now(ZoneInfo("Asia/Kolkata")).strftime("%d-%m-%Y %I:%M:%S %p")
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to change password. Please verify your credentials."
            )
            
    except Exception as e:
        logger.exception(f"Error in password change API: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error while changing password"
        )
    finally:
        db.close_connection()


@router.post("/add_camera")
def add_camera(data: CameraInput, current_user: User = Depends(admin_required)):
    try:
        if not data.category:
            raise HTTPException(status_code=400, detail="Camera category is required")

        # if data.category == "truck":
        #     if not data.polygon_points:
        #         raise HTTPException(status_code=400, detail="Polygon points required for  category")
            
        #     try:
        #         # Validate that it's a proper list of tuples
        #         parsed_points = ast.literal_eval(data.polygon_points)
        #         if not isinstance(parsed_points, list) or not all(isinstance(point, tuple) and len(point) == 2 for point in parsed_points):
        #             raise ValueError
        #     except Exception:
        #         raise HTTPException(status_code=400, detail="Invalid polygon_points format. Use string like: \"[(x1, y1), (x2, y2)]\"")

        user_data = mongo_handler.user_collection.find_one(
            {"email": current_user.email},
            {"_id": 0, "cameras": 1}
        )

        if not user_data:
            raise HTTPException(status_code=404, detail="User not found")

        cameras_by_category = user_data.get("cameras", {})

        if data.category not in cameras_by_category:
            cameras_by_category[data.category] = []

        if any(cam["camera_id"] == data.camera_id for cam in cameras_by_category[data.category]):
            raise HTTPException(status_code=400, detail="Camera ID already exists in this category")

        new_camera = {
            "camera_id": data.camera_id,
            "rtsp_link": data.rtsp_link
        }

        # if data.category == "truck":
        #     new_camera["polygon_points"] = data.polygon_points  # store as string

        cameras_by_category[data.category].append(new_camera)

        update_result = mongo_handler.user_collection.update_one(
            {"email": current_user.email},
            {"$set": {"cameras": cameras_by_category}}
        )

        if update_result.modified_count == 0:
            raise HTTPException(status_code=500, detail="Failed to add camera")

        return {
            "message": "Camera added successfully",
            "email": current_user.email,
            "category": data.category,
            "camera_id": data.camera_id
        }

    except Exception as e:
        raise RabsException(e, sys) from e


@router.get("/get_cameras")
def get_cameras(current_user: User = Depends(get_current_active_user)):
    try:
        if current_user.email != current_user.email and current_user.role != "admin":
            raise HTTPException(status_code=403, detail="Not authorized to view cameras for this user")

        user_data = mongo_handler.user_collection.find_one(
            {"email": current_user.email},
            {"_id": 0, "cameras": 1}   )

        if not user_data or "cameras" not in user_data:
            raise HTTPException(status_code=404, detail="No cameras found for this user")

        cameras_by_category = user_data["cameras"]

        return {
            "email": current_user.email,
            "cameras": cameras_by_category
        }

    except Exception as e:
        raise RabsException(e, sys) from e


@router.delete("/remove_camera")
def remove_camera(camera_id: str, category: str, current_user: User = Depends(admin_required)):
    try:
        if current_user.role != "admin" and current_user.email != current_user.email:
            raise HTTPException(status_code=403, detail="Not authorized to remove camera")

        user_data = mongo_handler.user_collection.find_one(
            {"email": current_user.email},
            {"_id": 0, "cameras": 1} )

        if not user_data:
            raise HTTPException(status_code=404, detail="User not found")

        cameras_by_category = user_data.get("cameras", {})

        if category not in cameras_by_category:
            raise HTTPException(status_code=404, detail=f"Category '{category}' not found")

        # Filter out the camera by camera_id
        updated_cameras = [
            cam for cam in cameras_by_category[category] if cam["camera_id"] != camera_id
        ]

        if len(updated_cameras) == len(cameras_by_category[category]):
            raise HTTPException(status_code=404, detail="Camera ID not found in the specified category")

        # Update the category with the filtered list
        cameras_by_category[category] = updated_cameras

        # If no cameras left in the category, you can optionally remove the category
        if not updated_cameras:
            del cameras_by_category[category]

        # Save back to DB
        result = mongo_handler.user_collection.update_one(
            {"email": current_user.email},
            {"$set": {"cameras": cameras_by_category}}
        )

        if result.modified_count == 0:
            raise HTTPException(status_code=500, detail="Failed to remove camera")

        logger.info(f"Camera {camera_id} removed successfully from category {category} for {current_user.email}")

        return {
            "message": "Camera removed successfully",
            "email": current_user.email,
            "category": category,
            "camera_id": camera_id
        }

    except Exception as e:
        raise RabsException(e, sys) from e






