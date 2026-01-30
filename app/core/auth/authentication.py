from datetime import datetime, timedelta
from fastapi import HTTPException, status
from passlib.context import CryptContext
from jose import jwt
from app.core.setting import config
from app.shared.timezone import get_naive_utc_now

# --- SECURITY CONFIGURATION ---
pwd_context = CryptContext(
    schemes=["pbkdf2_sha256", "bcrypt"],
    deprecated=["bcrypt"]
)

SECRET_KEY = config.SECRET_KEY
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = config.ACCESS_TOKEN_EXPIRE_MINUTES

from app.core.models.hr import LoginCredential

class AuthService:
    
    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        try:
            return pwd_context.verify(plain_password, hashed_password)
        except Exception:
            # bcrypt 72-byte limit or any verify failure
            return False

    

    @staticmethod
    def create_access_token(data: dict):
        """Generates a JWT token."""
        to_encode = data.copy()
        expire = get_naive_utc_now() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        to_encode.update({"exp": expire})
        encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
        return encoded_jwt
    
    @staticmethod
    def create_user_token(user: LoginCredential):
        """
        Generates a token containing all non-sensitive user details.
        """
        token_data = {
            "sub": user.emp_id,
            "_id": str(user.id),          
            "emp_id": user.emp_id,
            "username": user.username,
            "email": user.email,
            "role": user.role,
            "full_name": user.full_name,
            "role2": getattr(user, "role2", None) 
        }
        
        return AuthService.create_access_token(token_data)

    @staticmethod
    async def authenticate_user(login_id: str, password: str):
        login_user = await LoginCredential.find_one(
            {
                "$or": [
                    {"username": login_id},
                    {"email": login_id}
                ]
            }
        )
        
        if not login_user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect username/email or password"
            )
        
        if not AuthService.verify_password(password, login_user.password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect username/email or password"
            )
            
        return login_user

    @staticmethod
    async def get_full_user_data(emp_id: str):
        """
        Fetches the LoginCredential.
        Used by get_current_user dependency.
        """
        # 1. Get Role/Email

        login = await LoginCredential.find_one(LoginCredential.emp_id == emp_id)
        if not login:
            return None

        return {
            "emp_id": login.emp_id,
            "full_name": login.full_name,
            "username": login.username,
            "email": login.email,
            "role": login.role,
            "role2": getattr(login, "role2", None)
        }