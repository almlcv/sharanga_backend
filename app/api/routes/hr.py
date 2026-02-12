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
    description="""
    Create a new employee profile with complete information and document uploads.
    
    **Authorization:** Requires Admin or HR role.
    
    **Request Body (multipart/form-data):**
    
    **Personal Information (Required):**
    - `full_name`: Employee's full name
    - `dob`: Date of birth (YYYY-MM-DD format)
    - `gender`: Gender (Male/Female/Other)
    - `phone`: Contact phone number
    - `department`: Department assignment
    - `password`: Login password (minimum 8 characters)
    
    **Personal Information (Optional):**
    - `email`: Email address
    - `marital_status`: Marital status
    
    **Professional Information (Optional):**
    - `experience`: Years of experience
    - `experience_level`: Experience level (Fresher/Intermediate/Expert)
    - `designation`: Job designation
    - `qualification`: Educational qualification
    - `qualification_level`: Qualification level
    - `employees_role`: System role (Admin/HR/Production/Employee)
    - `salary_account_number`: Bank account number
    
    **Identification & Emergency (Optional):**
    - `aadhaar_number`: Aadhaar card number
    - `address`: Residential address
    - `blood_group`: Blood group
    - `emergency_contact_number`: Emergency contact
    
    **File Uploads (Optional):**
    - `avatar`: Profile picture
    - `id_proof`: ID proof documents (multiple files)
    - `education_certificates`: Education certificates (multiple files)
    - `experience_letters`: Experience letters (multiple files)
    - `other_documents`: Other documents (multiple files)
    
    **Business Rules:**
    - Employee ID is auto-generated
    - Phone number must be unique
    - Email must be unique (if provided)
    - Password is securely hashed before storage
    - Files are uploaded to configured storage
    
    **Use Case:**
    HR creates a new employee profile during onboarding process.
    """,
    responses={
        201: {"description": "Employee profile created successfully"},
        400: {"description": "Invalid data or duplicate phone/email"},
        401: {"description": "Not authenticated"},
        403: {"description": "Insufficient permissions (requires Admin or HR role)"}
    }
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
    description="""
    Retrieve complete profile information for a specific employee by their employee ID.
    
    **Authorization:** Requires Admin or HR role.
    
    **Path Parameters:**
    - `emp_id`: Employee ID (e.g., "EMP001")
    
    **Returns:**
    Complete employee profile including personal, professional, identification details, and document URLs.
    
    **Use Case:**
    HR views detailed employee information for verification, updates, or administrative purposes.
    """,
    responses={
        200: {"description": "Employee profile retrieved successfully"},
        401: {"description": "Not authenticated"},
        403: {"description": "Insufficient permissions (requires Admin or HR role)"},
        404: {"description": "Employee not found"}
    }
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
    description="""
    Update an existing employee's profile information and documents.
    
    **Authorization:** Requires Admin or HR role.
    
    **Path Parameters:**
    - `emp_id`: Employee ID to update
    
    **Request Body (multipart/form-data):**
    All fields are optional - only provide fields that need to be updated.
    
    **Updatable Fields:**
    - Personal information (name, DOB, gender, phone, email, marital status)
    - Professional information (experience, designation, department, qualification, role, salary account)
    - Identification (Aadhaar, address, blood group, emergency contact)
    - Documents (avatar, ID proofs, certificates, letters)
    
    **Business Rules:**
    - Only provided fields are updated (partial update)
    - Phone and email must remain unique
    - New files replace existing ones
    - Employee ID cannot be changed
    
    **Use Case:**
    HR updates employee information when details change (promotion, address change, document updates, etc.).
    """,
    responses={
        200: {"description": "Employee profile updated successfully"},
        400: {"description": "Invalid data or duplicate phone/email"},
        401: {"description": "Not authenticated"},
        403: {"description": "Insufficient permissions"},
        404: {"description": "Employee not found"}
    }
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
    description="""
    Soft delete an employee from the system.
    
    **Authorization:** Requires Admin or HR role.
    
    **Path Parameters:**
    - `emp_id`: Employee ID to delete
    
    **Behavior:**
    - Performs a soft delete (marks as deleted, doesn't remove from database)
    - Employee cannot log in after deletion
    - Historical data and records are preserved
    - Can be restored by database administrator if needed
    
    **Use Case:**
    HR removes an employee who has left the organization.
    
    **Note:** This is a soft delete operation. The employee record is marked as deleted but not permanently removed from the database.
    """,
    responses={
        204: {"description": "Employee deleted successfully (no content returned)"},
        401: {"description": "Not authenticated"},
        403: {"description": "Insufficient permissions"},
        404: {"description": "Employee not found"}
    }
)
async def delete_employee(
    emp_id: str,
    current_user: CurrentUser = Depends(require_roles("Admin", "HR"))
):
    """Soft delete employee (HR only)"""
    await HRService.delete_employee(emp_id)
    return None