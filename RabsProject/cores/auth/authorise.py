import logging
from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
import os, sys
from datetime import datetime, date, timedelta
from typing import List, Dict, Optional
from datetime import datetime, timedelta
from jose import jwt, JWTError
from passlib.context import CryptContext
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
from RabsProject.services.mongodb import MongoDBHandlerSaving
from RabsProject.pymodels.models import *
from RabsProject.logger import logging
from RabsProject.exception import RabsException
from dotenv import load_dotenv
load_dotenv()


SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = os.getenv("ALGORITHM")
mongo_handler = MongoDBHandlerSaving()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


MAX_BCRYPT_LEN = 72

def verify_password(plain_password, hashed_password):
    try:
        truncated_password = plain_password[:MAX_BCRYPT_LEN]  # truncate
        return pwd_context.verify(truncated_password, hashed_password)
    except Exception as e:
        raise RabsException(e, sys) from e



def get_password_hash(password):
    try:
        if len(password.encode('utf-8')) > 72:
            raise HTTPException(
                status_code=400,
                detail="Password too long. Maximum allowed is 72 characters."
            )
        return pwd_context.hash(password)
    except Exception as e:
        raise RabsException(e, sys) from e


def get_user(email: str):
    try:
        user_data = mongo_handler.user_collection.find_one({"email": email}, {"_id": 0})
        if user_data:
            return User(**user_data)
        return None
    
    except Exception as e:
        raise RabsException(e, sys) from e

def authenticate_user(email: str, password: str):
    try:
        user_data = mongo_handler.user_collection.find_one({"email": email})
        
        if not user_data:
            return False

        if not verify_password(password, user_data["password"]):
            return False

        return User(**user_data)  # Convert to Pydantic Model
    
    except Exception as e:
        raise RabsException(e, sys) from e

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    try:
        to_encode = data.copy()
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(hours=12)
        to_encode.update({"exp": expire, "sub": data["sub"]})  # Ensure "sub" is always included
        encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
        return encoded_jwt
    
    except Exception as e:
        raise RabsException(e, sys) from e

async def get_current_user(token: str = Depends(oauth2_scheme)):
    try:
        credentials_exception = HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            email: str = payload.get("sub")
            if email is None:
                raise credentials_exception
        except JWTError:
            raise credentials_exception

        user = get_user(email)
        if user is None:
            raise credentials_exception
        return user
    
    except Exception as e:
        raise RabsException(e, sys) from e

async def get_current_active_user(current_user: User = Depends(get_current_user)):
    try:
        if current_user.disabled is None:
            current_user.disabled = False  # Default to False if missing

        if current_user.disabled:
            raise HTTPException(status_code=400, detail="Inactive user")
        return current_user

    except Exception as e:
        raise RabsException(e, sys) from e

# def admin_required(current_user: User = Depends(get_current_active_user)):
#     if current_user.role != "admin":
#         raise HTTPException(status_code=403, detail="Access forbidden: Admins only")
#     return current_user


# def HR_required(current_user: User = Depends(get_current_active_user)):
#     if current_user.role != "HR":
#         raise HTTPException(status_code=403, detail="Access forbidden: HR only")
#     return current_user



# def QC_required(current_user: User = Depends(get_current_active_user)):
#     if current_user.role != "QC":
#         raise HTTPException(status_code=403, detail="Access forbidden: QC only")
#     return current_user


# def production_required(current_user: User = Depends(get_current_active_user)):
#     if current_user.role != "Production":
#         raise HTTPException(status_code=403, detail="Access forbidden: Production only")
#     return current_user


def admin_required(current_user: User = Depends(get_current_active_user)):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Access forbidden: Admins only")
    return current_user


def HR_required(current_user: User = Depends(get_current_active_user)):
    if current_user.role not in ["HR", "admin"]:
        raise HTTPException(status_code=403, detail="Access forbidden: HR or Admin only")
    return current_user


def QC_required(current_user: User = Depends(get_current_active_user)):
    if current_user.role not in ["QC", "admin"]:
        raise HTTPException(status_code=403, detail="Access forbidden: QC or Admin only")
    return current_user


def production_required(current_user: User = Depends(get_current_active_user)):
    if current_user.role not in ["Production", "admin"]:
        raise HTTPException(status_code=403, detail="Access forbidden: Production or Admin only")
    return current_user

def dispatch_required(current_user: User = Depends(get_current_user)):
    if current_user.role not in ["Production", "admin", "Dispatch"]:
        raise HTTPException(status_code=403, detail="Access forbidden: Dispatch or Production or Admin only")
    return current_user

def authorised_required(current_user: User = Depends(get_current_active_user)):
    if current_user.role not in ["Production", "admin","QC", "HR", "Dispatch"]:
        raise HTTPException(status_code=403, detail="Access forbidden: Production or Admin or QC or HR or Dispatch only")
    return current_user


