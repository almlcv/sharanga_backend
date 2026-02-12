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
    description="""
    Authenticate a user and obtain an access token for API requests.
    
    **Authentication Method:** OAuth2 Password Flow (compatible with Swagger UI 'Authorize' button)
    
    **Request Parameters:**
    - `username`: Employee ID or email address
    - `password`: User password
    
    **Response Fields:**
    - `access_token`: JWT token for authenticating subsequent API requests
    - `token_type`: Always "bearer"
    - `emp_id`: Employee ID
    - `role`: User role (Admin, HR, Production, Employee, etc.)
    - `email`: User email address
    - `full_name`: Employee full name
    
    **Token Usage:**
    Include the token in subsequent requests using the Authorization header:
    ```
    Authorization: Bearer <access_token>
    ```
    
    **Security:**
    - Passwords are securely hashed
    - Tokens have configurable expiration
    - Failed login attempts are logged
    """,
    responses={
        200: {
            "description": "Login successful - returns access token and user information",
            "content": {
                "application/json": {
                    "example": {
                        "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                        "token_type": "bearer",
                        "emp_id": "EMP001",
                        "role": "Employee",
                        "email": "employee@example.com",
                        "full_name": "John Doe"
                    }
                }
            }
        },
        401: {"description": "Invalid credentials - username or password incorrect"},
        400: {"description": "Invalid request format"}
    }
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