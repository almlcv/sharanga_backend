from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt

# Import schemas and service
from app.core.schemas.auth import CurrentUser
from app.core.auth.authentication import AuthService
from app.core.auth.authentication import SECRET_KEY, ALGORITHM

# This tells FastAPI where to get the token (Authorization header)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

async def get_current_user(token: str = Depends(oauth2_scheme)) -> CurrentUser:
    """
    Dependency that decodes the JWT token and fetches the user's current data.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        emp_id: str = payload.get("sub")
        if emp_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    user_data = await AuthService.get_full_user_data(emp_id)
    
    if user_data is None:
        raise credentials_exception
        
    return CurrentUser(**user_data)

def require_roles(*allowed_roles: str):
    """
    Dependency factory that checks if the current user has one of the allowed roles.
    Checks both 'role' and 'role2'.
    """
    async def role_checker(
        current_user: CurrentUser = Depends(get_current_user),
    ) -> CurrentUser:
        # 1. Check primary role
        is_authorized = current_user.role in allowed_roles
        
        # 2. If primary role fails, check secondary role (role2) if it exists
        # This handles the case where 'role' is "Production" but 'role2' is "Operator"
        if not is_authorized and current_user.role2:
            is_authorized = current_user.role2 in allowed_roles
            
        if not is_authorized:
            # Optional: Provide more info about what roles are needed
            roles_str = ", ".join(allowed_roles)
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Operation not permitted. Requires one of the following roles: {roles_str}",
            )
            
        return current_user

    return role_checker