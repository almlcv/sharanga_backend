from typing import Optional
from pydantic import BaseModel, Field

# --- Request ---
class LoginRequest(BaseModel):
    login_id: str = Field(..., description="Enter your Username or Email Address")
    password: str = Field(..., description="The password for the account.")

# --- Response ---
class LoginResponse(BaseModel):
    access_token: str = Field(..., description="The access token for subsequent requests.")
    token_type: str = Field(default="bearer", description="Type of the token.")
    emp_id: str = Field(..., description="The Employee ID associated with the account.")
    role: str = Field(..., description="The user's role (e.g., Admin, Manager, Staff).")
    email: str = Field(..., description="The user's email address.")
    full_name: Optional[str] = Field(None, description="The user's full name.")

# --- Internal Schema for Dependency ---
# This is what get_current_user returns to your routes
class CurrentUser(BaseModel):

    emp_id: str
    role: str
    role2: Optional[str] = None
    email: str
    full_name: Optional[str]