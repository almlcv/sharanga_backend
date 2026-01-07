import os, sys
import ast
import logging
from fastapi import APIRouter, Depends, HTTPException
from RabsProject.services.mongodb import MongoDBHandlerSaving
from RabsProject.exception import RabsException
from fastapi import  HTTPException, Depends, status
from fastapi.responses import StreamingResponse
from fastapi import BackgroundTasks
from datetime import datetime, timedelta
from jose import jwt, JWTError
from RabsProject.cores.CameraStream.camera_system import *
from RabsProject.pymodels.models import *
from RabsProject.cores.auth.authorise import get_current_active_user, admin_required, get_current_user, get_user, create_access_token
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)
from fastapi import Query
from dotenv import load_dotenv
load_dotenv()


SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = os.getenv("ALGORITHM")
HOSTING_LINK = os.getenv("HOSTING_LINK", "http://192.168.1.152:8015")  # Default to localhost if not set
ACCESS_TOKEN_EXPIRE_MINUTES = 1440
running_camera_systems = {}


router = APIRouter(
    tags=["Multi-Cameras Streaming"] )




@router.post("/start_streaming")
async def start_streaming(

    background_tasks: BackgroundTasks,
    category: str = Query(..., description="Camera category to start streaming"),
    current_user: User = Depends(admin_required)):
    try:
        global running_camera_systems

        unique_stream_id = f"{current_user.email}_{category}"

        if unique_stream_id in running_camera_systems:
            raise HTTPException(status_code=400, detail="Streaming is already running for this user and category")

        if category == "ppe":
            camera_system = MultiCameraSystemSafty(
                email=current_user.email,
                model_path="models/ppeV1.pt",
                category=category    )

        elif category == "truck":
            camera_system = MultiCameraSystemTruck(
                email=current_user.email,
                model_path="models/truck.pt",
                category=category   )

        elif category == "fire":
            camera_system = MultiCameraSystemFire(
                email=current_user.email,
                model_path="models/fireV1.pt",
                category=category    )
            
            
        elif category == "smoke":
            camera_system = MultiCameraSystemSmoke(
                email=current_user.email,
                model_path="models/fireV1.pt",
                category=category   )
            
        else:
            raise HTTPException(status_code=400, detail="Invalid category")

        background_tasks.add_task(lambda: camera_system)

        running_camera_systems[unique_stream_id] = camera_system
        logger.info(f"Streaming started for {current_user.email} in category {category}")

        # Create a special long-lived token for streaming
        streaming_token_expires = timedelta(hours=24)
        streaming_token = create_access_token(
            data={"sub": current_user.email, "purpose": "streaming", "category": category},
            expires_delta=streaming_token_expires)

        # Generate the streaming URL with the token
        server_address = HOSTING_LINK #"http://192.168.3.5:8015"  # Update if necessary
        stream_url = f"{server_address}/stream?token={streaming_token}"
        
        return {
            "message": "Streaming started",
            "stream_url": stream_url,
            "token": streaming_token,
            "category": category    }

    except Exception as e:
        raise RabsException(e, sys) from e


@router.get("/stream")
async def stream_video(token: str = None, authorization: str = None):
    try:
        streaming_token = token

        if not streaming_token and authorization:
            if authorization.startswith("Bearer "):
                streaming_token = authorization.split(" ")[1]

        if not streaming_token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="No valid token provided",
                headers={"WWW-Authenticate": "Bearer"},
            )

        try:
            payload = jwt.decode(streaming_token, SECRET_KEY, algorithms=[ALGORITHM])
            token_email = payload.get("sub")
            token_category = payload.get("category")  # Get category too
           
     
            print("payload",payload)

            if not token_email or not token_category:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid token format"
                )

            user = get_user(token_email)
            if not user:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="User not found"
                )

        except JWTError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token",
                headers={"WWW-Authenticate": "Bearer"},
            )

        unique_stream_id = f"{user.email}_{token_category}"

        if unique_stream_id not in running_camera_systems:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Streaming not found for this user and category"
            )

        camera_system = running_camera_systems[unique_stream_id]

        return StreamingResponse(
            camera_system.get_video_frames(),
            media_type="multipart/x-mixed-replace; boundary=frame"
        )

    except Exception as e:
        raise RabsException(e, sys) from e


@router.get("/running_cameras")
async def running_cameras(current_user: User = Depends(admin_required)):
    try:
        """Check which cameras are currently streaming"""
        global running_camera_systems
        active_streams = {
            email: {
                "cameras": list(system.camera_processors.keys()),
                "count": len(system.camera_processors)
            } for email, system in running_camera_systems.items()
        }
        return {"active_streams": active_streams}

    except Exception as e:
        raise RabsException(e, sys) from e
  

@router.post("/stop_streaming")
async def stop_streaming(category: str, current_user: User = Depends(admin_required)):
    try:
        global running_camera_systems
        key = f"{current_user.email}_{category}"

        if key not in running_camera_systems:
            raise HTTPException(status_code=404, detail="No active streaming found for this user")

        camera_system = running_camera_systems[key]
        camera_system.stop()  # Assuming this stops all camera threads/processors
        del running_camera_systems[key]

        return {"message": f"Streaming stopped for user {current_user.email} in category {category}"}

    except Exception as e:
        raise RabsException(e, sys) from e

