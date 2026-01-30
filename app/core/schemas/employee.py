from app.core.schemas.hr import (
    EmployeeProfileResponse,
    UserInfoResponse,
    UserDocumentsResponse
)

# Re-export for employee module
__all__ = [
    "EmployeeProfileResponse",
    "UserInfoResponse", 
    "UserDocumentsResponse"
]