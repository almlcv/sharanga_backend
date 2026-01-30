from datetime import datetime, date
from typing import List, Optional
from enum import Enum
from beanie import Document
from pymongo import IndexModel, ASCENDING
from pydantic import BaseModel, Field, EmailStr, field_validator

# --- Enums (Creates Dropdowns in Swagger) ---
class GenderEnum(str, Enum):
    male = "male"
    female = "female"
    other = "other"

class MaritalStatusEnum(str, Enum):
    single = "Single"
    married = "Married"
    divorced = "Divorced"
    widowed = "Widowed"

class EmployeeRoleEnum(str, Enum):
    permanent = "Permanent"
    contract = "Contract"
    intern = "Intern"

class BloodGroupEnum(str, Enum):
    a_pos = "A+"
    a_neg = "A-"
    b_pos = "B+"
    b_neg = "B-"
    ab_pos = "AB+"
    ab_neg = "AB-"
    o_pos = "O+"
    o_neg = "O-"

class QualificationLevel(str, Enum):
    TENTH = "10th"
    TWELFTH = "12th"
    ITI = "ITI"
    DIPLOMA = "Diploma"
    GRADUATE = "Graduate"
    POST_GRADUATE = "Post Graduate"
    PHD = "PhD"

class ExperienceLevel(str, Enum):
    FRESHER = "Fresher (0-1 Year)"
    JUNIOR = "Junior (1-3 Years)"
    MID_SENIOR = "Mid-Senior (3-5 Years)"
    SENIOR = "Senior (5+ Years)"

class DepartmentEnum(str, Enum):
    admin = "Admin"
    hr = "HR"
    production = "Production"
    quality_assurance = "Quality Assurance"
    dispatch = "Dispatch"
    sales = "Sales"
    logistics = "Logistics"
    maintenance = "Maintenance"
    management = "Management"
    it_support = "IT Support"

class DesignationEnum(str, Enum):
    manager = "Manager"
    senior_engineer = "Senior Engineer"
    engineer = "Engineer"
    technician = "Technician"
    operator = "Operator"
    supervisor = "Supervisor"
    intern = "Intern"
    executive = "Executive"

# --- Sub-models ---
class UserDocuments(BaseModel):
    avatar: Optional[str] = Field(
        None, 
        description="employee's profile avatar image.",
    )
    id_proof: Optional[List[str]] = Field(
        default_factory=list, 
        description="ID proofs (Aadhaar, PAN, etc.)",
        max_length=5
    )
    education_certificates: List[str] = Field(
        default_factory=list,
        description="graduation/diploma certificates",
        max_length=10
    )
    experience_letters: List[str] = Field(
        default_factory=list,
        description="previous employment experience letters",
        max_length=10
    )
    other_documents: List[str] = Field(
        default_factory=list,
        description="any other relevant documents",
        max_length=10
    )

class UserInfo(BaseModel):
    full_name: str = Field(...,
        description="Legal full name of the employee as per ID proof.",
        min_length=2, 
        max_length=100,
        examples=["John Doe"]
    )
    dob: str = Field(...,
        description="Date of Birth in YYYY-MM-DD format.",
        examples=["1990-05-15"]
    )
    
    @field_validator('dob')
    @classmethod
    def validate_dob(cls, v):
        if v:
            try:
                parsed_date = datetime.strptime(v, "%Y-%m-%d").date()
                if parsed_date > date.today():
                    raise ValueError("Date of birth cannot be in the future.")
            except ValueError:
                raise ValueError("Invalid date format. Please use YYYY-MM-DD.")
        return v

    gender: GenderEnum = Field(..., description="Gender identity.")
    
    phone: str = Field(...,
        description="Primary contact number (10 digits).",
        pattern=r"^[0-9]{10}$",
        examples=["9876543210"]
    )
    
    email: Optional[EmailStr] = Field(None, description="Official or personal email address.")
    
    experience: Optional[str] = Field(
        None, 
        description="Experience grade (e.g., Grade_1, Senior).", 
        max_length=50,
        examples=["Grade_3"]
    )
    
    designation: Optional[DesignationEnum] = Field(None, description="Current job title.")
    department: DepartmentEnum = Field(..., description="Assigned department.")
    
    aadhaar_number: Optional[str] = Field(
        None, 
        description="12-digit unique Aadhaar number.",
        pattern=r"^[0-9]{12}$",
        examples=["123456789012"]
    )
    
    address: Optional[str] = Field(
        None, 
        description="Current residential address.", 
        max_length=500
    )
    
    qualification: Optional[str] = Field(
        None, 
        description="Highest educational qualification.", 
        max_length=100
    )
    
    employees_role: Optional[EmployeeRoleEnum] = Field(None, description="Employment type.")
    
    emergency_contact_number: Optional[str] = Field(
        None, 
        description="Emergency contact (10 digits).",
        pattern=r"^[0-9]{10}$"
    )
    
    salary_account_number: Optional[str] = Field(
        None, 
        description="Bank account number for salary transfers.",
        pattern=r"^[0-9]{9,18}$", # Validates 9 to 18 digits
        examples=["1234567890123"]
    )
    
    blood_group: Optional[BloodGroupEnum] = Field(None, description="Blood group for medical records.")
    marital_status: Optional[MaritalStatusEnum] = Field(None, description="Current marital status.")
    
    user_documents: UserDocuments = Field(
        default_factory=UserDocuments, 
        description="Collection of document URLs."
    )

    qualification_level: Optional[QualificationLevel] = Field(
    None, 
    description="Standardized qualification level (e.g., Graduate, Post Graduate)."
    )

    experience_level: Optional[ExperienceLevel] = Field(
    None, 
    description="Standardized experience level (e.g., Fresher, Junior, Senior)."
    )
# --- Main Documents ---
class EmployeeProfile(Document):
    emp_id: str = Field(
        ..., 
        description="Unique Employee ID (e.g., RI_001).",
        pattern=r"^[A-Za-z]{2,4}_[0-9]{3,5}$"
    )
    user_info: UserInfo = Field(default_factory=UserInfo)
    created_at: datetime = Field(default_factory=datetime.now, description="Record creation timestamp.")
    updated_at: datetime = Field(default_factory=datetime.now, description="Last update timestamp.")

    class Settings:
        name = "employee_profiles"
        indexes = [
            IndexModel([("emp_id", ASCENDING)], unique=True),
        ]
        
class LoginCredential(Document):
    emp_id: str = Field(..., description="Reference Employee ID.")
    full_name: Optional[str] = Field(..., description="Employee full name")
    username: str = Field(..., min_length=3, max_length=50, description="Unique username for login.")
    email: str = Field(..., description="Login email address.")
    role: str = Field(..., description="Assigned system role (e.g., admin, user).")
    role2: Optional[str] = Field(None, description="Secondary role if applicable.")
    password: str = Field(
        ..., 
        min_length=8, 
        description="Hashed password (minimum 8 characters required).",
        
    )

    class Settings:
        name = "login"
        indexes = [
            IndexModel([("emp_id", ASCENDING)], unique=True),
            IndexModel([("username", ASCENDING)], unique=True),
        ]