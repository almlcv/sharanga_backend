from fastapi import APIRouter, status, Depends
from app.core.schemas.auth import LoginRequest, LoginResponse
from app.core.auth.authentication import AuthService
from fastapi.security import OAuth2PasswordRequestForm


router = APIRouter(prefix="/auth", tags=["Authentication"])

@router.post(
    "/login",
    response_model=LoginResponse,
    status_code=status.HTTP_200_OK,
    summary="User Login",
    description="Authenticates a user. Compatible with Swagger UI 'Authorize' button."
)
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    """
    OAuth2 compatible token login, get an access token for future requests.
    """
    # 1. Validate Credentials
    # This returns the full LoginCredential object with all fields
    user_cred = await AuthService.authenticate_user(form_data.username, form_data.password)
    
    # 2. Generate Token
    # PASS THE OBJECT DIRECTLY. Your service method expects 'user: LoginCredential'
    token = AuthService.create_user_token(user_cred)
    
    # 3. Return Response
    return LoginResponse(
        access_token=token,
        emp_id=user_cred.emp_id,
        role=user_cred.role,      
        email=user_cred.email, 
        full_name=user_cred.full_name 
    )