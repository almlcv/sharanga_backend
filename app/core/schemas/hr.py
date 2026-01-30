from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, field_validator, Field
from bson import ObjectId

from app.core.models.hr import (
    GenderEnum, 
    MaritalStatusEnum, 
    EmployeeRoleEnum, 
    BloodGroupEnum,
    DepartmentEnum,
    DesignationEnum,
    QualificationLevel, 
    ExperienceLevel 
)

class UserDocumentsResponse(BaseModel):
    avatar: Optional[str] = Field(
        None, 
        description="URL path to the employee's profile avatar image.",
        examples=["https://cdn.company.com/avatars/emp_001.jpg"]
    )
    id_proof: Optional[List[str]] = Field(
        default_factory=list, 
        description="List of URL paths for uploaded ID proof documents.",
        examples=[["https://s3.bucket/aadhaar.pdf", "https://s3.bucket/pan.jpg"]]
    )
    education_certificates: Optional[List[str]] = Field(
        default_factory=list, 
        description="List of URL paths for uploaded educational certificates."
    )
    experience_letters: Optional[List[str]] = Field(
        default_factory=list, 
        description="List of URL paths for uploaded experience letters."
    )
    other_documents: List[str] = Field(
        default_factory=list, 
        description="List of URL paths for any other uploaded documents."
    )

class UserInfoResponse(BaseModel):
    full_name: str = Field(..., 
        description="The legal full name of the employee.",
        examples=["Jane Smith"]
    )
    dob: str = Field(...,
        description="Date of Birth in YYYY-MM-DD format.",
        examples=["1992-08-20"]
    )
    gender: GenderEnum = Field(...,description="Gender identity of the employee.")
    
    phone: str = Field(...,
        description="Primary contact phone number.",
        examples=["9876543210"]
    )
    
    email: Optional[str] = Field(
        None, 
        description="Primary email address for communication.",
        examples=["jane.smith@company.com"]
    )
    
    experience: Optional[str] = Field(
        None, 
        description="Experience grade or level.",
        examples=["Senior", "Grade_4"]
    )

    experience_level: Optional[ExperienceLevel] = Field(
        None, 
        description="Standardized work experience level.",
        examples=[ExperienceLevel.SENIOR]
    )
    
    designation: Optional[DesignationEnum] = Field(
        None, 
        description="Job title or designation within the company.",
        examples=[DesignationEnum.manager]
    )
    
    department: DepartmentEnum = Field(...,
        description="Department to which the employee is assigned.",
        examples=[DepartmentEnum.it_support]
    )
    
    aadhaar_number: Optional[str] = Field(
        None, 
        description="12-digit unique identification number (Masked for privacy).",
        examples=["XXXXXXXX1234"]
    )

    @field_validator('aadhaar_number', mode='before')
    @classmethod
    def mask_aadhaar(cls, v: str) -> Optional[str]:
        if v and len(v) == 12:
            return f"XXXXXXXX{v[-4:]}"
        return v

    address: Optional[str] = Field(
        None, 
        description="Current residential address.",
        examples=["123, Maple Street, Springfield, IL"]
    )
    
    qualification: Optional[str] = Field(
        None, 
        description="Highest educational qualification obtained.",
        examples=["B.Tech Computer Science"]
    )

    qualification_level: Optional[QualificationLevel] = Field(
        None, 
        description="Standardized education level.",
        examples=[QualificationLevel.GRADUATE]
    )

    employees_role: Optional[EmployeeRoleEnum] = Field(
        None, 
        description="Employment type.",
        examples=[EmployeeRoleEnum.permanent]
    )
    
    emergency_contact_number: Optional[str] = Field(
        None, 
        description="Contact number for use in case of emergencies.",
        examples=["9123456780"]
    )
    
    salary_account_number: Optional[str] = Field(
        None, 
        description="Bank account number for salary transfers.",
        examples=["1234567890"]
    )
    
    blood_group: Optional[BloodGroupEnum] = Field(
        None, 
        description="Blood group for medical records.",
        examples=[BloodGroupEnum.o_pos]
    )
    
    marital_status: Optional[MaritalStatusEnum] = Field(
        None, 
        description="Current marital status.",
        examples=[MaritalStatusEnum.single]
    )
    
    user_documents: UserDocumentsResponse = Field(
        default_factory=UserDocumentsResponse, 
        description="Container for URLs of uploaded employee documents."
    )

class EmployeeProfileResponse(BaseModel):
    id: Optional[str] = Field(
        None, 
        description="Internal MongoDB Object ID (unique identifier).",
        examples=["507f1f77bcf86cd799439011"]
    )
    emp_id: str = Field(
        ..., 
        description="Public Employee ID (e.g., RI_001) used for references.",
        examples=["RI_001"]
    )
    user_info: UserInfoResponse = Field(
        ..., 
        description="Detailed personal and professional information about the employee."
    )
    created_at: datetime = Field(
        ..., 
        description="Timestamp when the profile was created.",
        examples=["2023-01-15T10:30:00"]
    )
    updated_at: datetime = Field(
        ..., 
        description="Timestamp when the profile was last modified.",
        examples=["2023-10-05T14:20:00"]
    )

    class Config:
        from_attributes = True

    @field_validator('id', mode='before')
    @classmethod
    def convert_objectid_to_str(cls, v):
        if isinstance(v, ObjectId):
            return str(v)
        return v


class EmployeeListResponse(BaseModel):
    """Simplified response for employee list"""
    id: Optional[str] = None
    emp_id: str
    full_name: str
    email: Optional[str] = None
    phone: str
    department: DepartmentEnum
    designation: Optional[DesignationEnum] = None
    created_at: datetime

    class Config:
        from_attributes = True

    @field_validator('id', mode='before')
    @classmethod
    def convert_objectid_to_str(cls, v):
        if isinstance(v, ObjectId):
            return str(v)
        return v


class EmployeeListResponse(BaseModel):
    """Simplified response for employee list"""
    id: Optional[str] = None
    emp_id: str
    full_name: str
    email: Optional[str] = None
    phone: str
    department: DepartmentEnum
    designation: Optional[DesignationEnum] = None
    created_at: datetime

    class Config:
        from_attributes = True

    @field_validator('id', mode='before')
    @classmethod
    def convert_objectid_to_str(cls, v):
        if isinstance(v, ObjectId):
            return str(v)
        return v
    
    @classmethod
    def from_employee_profile(cls, profile):
        """Convert EmployeeProfile to EmployeeListResponse"""
        return cls(
            id=profile.id,
            emp_id=profile.emp_id,
            full_name=profile.user_info.full_name,
            email=profile.user_info.email,
            phone=profile.user_info.phone,
            department=profile.user_info.department,
            designation=profile.user_info.designation,
            created_at=profile.created_at
        )