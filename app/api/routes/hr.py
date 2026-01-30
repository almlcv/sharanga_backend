from fastapi import APIRouter, UploadFile, File, Form, status, Depends, Query
from typing import Optional, List

from app.core.schemas.hr import (
    EmployeeProfileResponse, 
    EmployeeListResponse
)
from app.modules.hr.onboarding import HRService
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
from app.core.auth.deps import require_roles
from app.core.schemas.auth import CurrentUser

router = APIRouter(prefix="/hr", tags=["HR Management"])


@router.post(
    "/employees",
    response_model=EmployeeProfileResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create New Employee Profile",
)
async def create_employee(    
    # --- Personal Information ---
    full_name: str = Form(...),
    dob: str = Form(..., description="YYYY-MM-DD"),
    gender: GenderEnum = Form(...), 
    phone: str = Form(...),
    email: Optional[str] = Form(None),
    marital_status: Optional[MaritalStatusEnum] = Form(None),
    
    # --- Professional Information ---
    experience: Optional[str] = Form(None),
    experience_level: Optional[ExperienceLevel] = Form(None),
    designation: Optional[DesignationEnum] = Form(None),
    department: DepartmentEnum = Form(...),
    qualification: Optional[str] = Form(None),
    qualification_level: Optional[QualificationLevel] = Form(None),
    employees_role: Optional[EmployeeRoleEnum] = Form(None),
    salary_account_number: Optional[str] = Form(None),
    
    # --- Identification & Emergency ---
    aadhaar_number: Optional[str] = Form(None),
    address: Optional[str] = Form(None),
    blood_group: Optional[BloodGroupEnum] = Form(None),
    emergency_contact_number: Optional[str] = Form(None),
    
    # --- Login Credentials ---
    password: str = Form(..., min_length=8),
    
    # --- File Uploads ---
    avatar: Optional[UploadFile] = File(None),
    id_proof: List[UploadFile] = File(default=[]),
    education_certificates: List[UploadFile] = File(default=[]),
    experience_letters: List[UploadFile] = File(default=[]),
    other_documents: List[UploadFile] = File(default=[]),
):
    """Create new employee profile (HR only)"""
    
    form_data = {
        "full_name": full_name,
        "dob": dob,
        "gender": gender,
        "phone": phone,
        "email": email,
        "experience": experience,
        "experience_level": experience_level,
        "designation": designation,
        "department": department,
        "aadhaar_number": aadhaar_number,
        "address": address,
        "qualification": qualification,
        "qualification_level": qualification_level,
        "employees_role": employees_role,
        "emergency_contact_number": emergency_contact_number,
        "salary_account_number": salary_account_number,
        "blood_group": blood_group,
        "marital_status": marital_status,
    }

    return await HRService.create_employee(
        form_data=form_data,
        password=password,
        avatar=avatar,
        id_proof=id_proof,
        education_certificates=education_certificates,
        experience_letters=experience_letters,
        other_documents=other_documents
    )


@router.get(
    "/employees",
    summary="Get All Employees",
    description="""
    Get list of all employees with complete or basic information.
    
    **Query Parameters:**
    - `detailed` (bool): 
        - `true` (default): Returns ALL 27 fields including documents
        - `false`: Returns only 8 basic fields (id, emp_id, name, email, phone, department, designation, created_at)
    - `skip` (int): Number of records to skip for pagination (default: 0)
    - `limit` (int): Maximum records to return (default: 100)
    
    **Complete Details Include:**
    - System: id, emp_id, created_at, updated_at
    - Personal: full_name, dob, gender, phone, email, marital_status
    - Professional: experience, experience_level, designation, department, qualification, qualification_level, employees_role, salary_account_number
    - Identification: aadhaar_number, address, blood_group, emergency_contact_number
    - Documents: avatar, id_proof, education_certificates, experience_letters, other_documents
    """
)
async def get_all_employees(
    current_user: CurrentUser = Depends(require_roles("Admin", "HR")),
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum records to return"),
    detailed: bool = Query(True, description="Return complete details (true) or basic info only (false)")
):
    """
    Get list of all employees
    
    - **detailed=true**: Returns ALL 27 fields (complete employee information)
    - **detailed=false**: Returns only 8 basic fields (for listing views)
    """
    return await HRService.get_all_employees(skip=skip, limit=limit, detailed=detailed)


@router.get(
    "/employees/{emp_id}",
    response_model=EmployeeProfileResponse,
    summary="Get Employee Details by ID",
)
async def get_employee_by_id(
    emp_id: str,
    current_user: CurrentUser = Depends(require_roles("Admin", "HR"))
):
    """Get complete employee profile by employee ID"""
    return await HRService.get_employee_by_id(emp_id)


@router.put(
    "/employees/{emp_id}",
    response_model=EmployeeProfileResponse,
    summary="Update Employee Profile",
)
async def update_employee_profile(
    emp_id: str,
    current_user: CurrentUser = Depends(require_roles("Admin", "HR")),
    # --- Personal Information ---
    full_name: Optional[str] = Form(None),
    dob: Optional[str] = Form(None, description="YYYY-MM-DD"),
    gender: Optional[GenderEnum] = Form(None),
    phone: Optional[str] = Form(None),
    email: Optional[str] = Form(None),
    marital_status: Optional[MaritalStatusEnum] = Form(None),
    
    # --- Professional Information ---
    experience: Optional[str] = Form(None),
    experience_level: Optional[ExperienceLevel] = Form(None),
    designation: Optional[DesignationEnum] = Form(None),
    department: Optional[DepartmentEnum] = Form(None),
    qualification: Optional[str] = Form(None),
    qualification_level: Optional[QualificationLevel] = Form(None),
    employees_role: Optional[EmployeeRoleEnum] = Form(None),
    salary_account_number: Optional[str] = Form(None),
    
    # --- Identification & Emergency ---
    aadhaar_number: Optional[str] = Form(None),
    address: Optional[str] = Form(None),
    blood_group: Optional[BloodGroupEnum] = Form(None),
    emergency_contact_number: Optional[str] = Form(None),
    
    # --- File Uploads ---
    avatar: Optional[UploadFile] = File(None),
    id_proof: List[UploadFile] = File(default=[]),
    education_certificates: List[UploadFile] = File(default=[]),
    experience_letters: List[UploadFile] = File(default=[]),
    other_documents: List[UploadFile] = File(default=[]),
):
    """Update existing employee profile (HR only)"""
    
    form_data = {
        k: v for k, v in {
            "full_name": full_name,
            "dob": dob,
            "gender": gender,
            "phone": phone,
            "email": email,
            "experience": experience,
            "experience_level": experience_level,
            "designation": designation,
            "department": department,
            "aadhaar_number": aadhaar_number,
            "address": address,
            "qualification": qualification,
            "qualification_level": qualification_level,
            "employees_role": employees_role,
            "emergency_contact_number": emergency_contact_number,
            "salary_account_number": salary_account_number,
            "blood_group": blood_group,
            "marital_status": marital_status,
        }.items() if v is not None
    }

    return await HRService.update_employee_profile(
        emp_id=emp_id,
        form_data=form_data,
        avatar=avatar,
        id_proof=id_proof,
        education_certificates=education_certificates,
        experience_letters=experience_letters,
        other_documents=other_documents
    )


@router.delete(
    "/employees/{emp_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete Employee",
)
async def delete_employee(
    emp_id: str,
    current_user: CurrentUser = Depends(require_roles("Admin", "HR"))
):
    """Soft delete employee (HR only)"""
    await HRService.delete_employee(emp_id)
    return None