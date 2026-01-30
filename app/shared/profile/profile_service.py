from typing import Optional, List, Dict
from fastapi import UploadFile, HTTPException
from passlib.context import CryptContext
import re
import logging

from app.core.models.hr import EmployeeProfile, LoginCredential, UserInfo
from app.shared.timezone import get_ist_now
from app.shared.profile.profile_utils import ProfileUtils

logger = logging.getLogger(__name__)
pwd_context = CryptContext(
    schemes=["pbkdf2_sha256", "bcrypt"],
    # deprecated=["bcrypt"]
)


class ProfileService:
    """
    Unified service for profile operations used by both Employee and HR modules.
    Contains all business logic for profile management.
    """

    # ==================== EMPLOYEE ID GENERATION ====================

    @staticmethod
    async def _generate_emp_id() -> str:
        """Generate next sequential Employee ID (e.g., RI_001)"""
        last_profile = await EmployeeProfile.find().sort(-EmployeeProfile.emp_id).first_or_none()
        if not last_profile:
            return "RI_001"
        
        try:
            num_part = int(last_profile.emp_id.split("_")[1])
            return f"RI_{num_part + 1:03d}"
        except (IndexError, ValueError):
            return "RI_001"

    # ==================== PASSWORD VALIDATION ====================

    @staticmethod
    def _validate_password(password: str):
        """Validate password strength"""
        if len(password) < 8:
            raise HTTPException(
                status_code=422, 
                detail="Password must be at least 8 characters long."
            )
        if not re.search(r"[A-Z]", password):
            raise HTTPException(
                status_code=422, 
                detail="Password must contain an uppercase letter."
            )
        if not re.search(r"[a-z]", password):
            raise HTTPException(
                status_code=422, 
                detail="Password must contain a lowercase letter."
            )
        if not re.search(r"\d", password):
            raise HTTPException(
                status_code=422, 
                detail="Password must contain a number."
            )

    # ==================== CREATE EMPLOYEE ====================

    @staticmethod
    async def create_employee_profile(
        form_data: Dict,
        password: str,
        avatar: Optional[UploadFile] = None,
        id_proof: Optional[List[UploadFile]] = None,
        education_certificates: Optional[List[UploadFile]] = None,
        experience_letters: Optional[List[UploadFile]] = None,
        other_documents: Optional[List[UploadFile]] = None,
        created_by: str = "system"
    ) -> EmployeeProfile:
        """
        Create new employee profile - used by both Employee and HR modules
        
        Args:
            form_data: Dictionary containing all profile fields
            password: Plain text password (will be hashed)
            avatar: Profile picture upload
            id_proof: ID proof documents
            education_certificates: Educational certificates
            experience_letters: Experience letters
            other_documents: Other documents
            created_by: Who created this profile ("employee", "hr", or "system")
        
        Returns:
            Created EmployeeProfile instance
        """
        
        # Validate password
        ProfileService._validate_password(password)
        
        phone = form_data.get("phone")
        email = form_data.get("email")
        
        # Check uniqueness
        if phone:
            await ProfileUtils.check_phone_uniqueness(phone)
        if email:
            await ProfileUtils.check_email_uniqueness(email)

        # Generate employee ID
        emp_id = await ProfileService._generate_emp_id()
        
        # Build user info data with required fields
        user_info_data = {
            "full_name": form_data["full_name"],
            "dob": form_data["dob"],
            "gender": form_data["gender"],
            "phone": form_data["phone"],
            "department": form_data["department"],
        }
        
        # Add optional fields
        optional_fields = [
            "email", "experience", "experience_level", "designation",
            "aadhaar_number", "address", "qualification", "qualification_level",
            "employees_role", "emergency_contact_number", "salary_account_number",
            "blood_group", "marital_status"
        ]
        
        for field in optional_fields:
            if field in form_data and form_data[field] is not None:
                user_info_data[field] = form_data[field]
        
        # Create profile
        user_info = UserInfo(**user_info_data)
        profile = EmployeeProfile(emp_id=emp_id, user_info=user_info)
        
        # Handle file uploads
        if avatar:
            profile.user_info.user_documents.avatar = await ProfileUtils.save_file(
                avatar, emp_id, "avatar"
            )

        await ProfileUtils.append_files(profile, id_proof, "id_proof", "id_proof")
        await ProfileUtils.append_files(profile, education_certificates, "education_certificates", "education_certificates")
        await ProfileUtils.append_files(profile, experience_letters, "experience_letters", "experience_letters")
        await ProfileUtils.append_files(profile, other_documents, "other_documents", "other_documents")

        profile.updated_at = get_ist_now()
        await profile.save()

        # Create login credential
        login_role = profile.user_info.department.value 
        hashed_password = pwd_context.hash(password)
        
        new_login = LoginCredential(
            emp_id=emp_id,
            full_name=profile.user_info.full_name,
            username=phone,
            email=email or "",
            role=login_role,
            role2=profile.user_info.designation.value if profile.user_info.designation else None,
            password=hashed_password 
        )
        await new_login.insert()
        
        logger.info(f"Employee created: {emp_id} (created by: {created_by})")
        return profile

    # ==================== GET PROFILE ====================

    @staticmethod
    async def get_profile(emp_id: str) -> EmployeeProfile:
        """
        Get employee profile by ID - used by both modules
        
        Args:
            emp_id: Employee ID
        
        Returns:
            EmployeeProfile instance
        """
        return await ProfileUtils.get_profile_by_id(emp_id)

    # ==================== UPDATE PROFILE ====================

    @staticmethod
    async def update_employee_profile(
        emp_id: str,
        form_data: Dict,
        avatar: Optional[UploadFile] = None,
        id_proof: Optional[List[UploadFile]] = None,
        education_certificates: Optional[List[UploadFile]] = None,
        experience_letters: Optional[List[UploadFile]] = None,
        other_documents: Optional[List[UploadFile]] = None,
        updated_by: str = "system"
    ) -> EmployeeProfile:
        """
        Update employee profile - used by both Employee and HR modules
        
        Args:
            emp_id: Employee ID to update
            form_data: Dictionary of fields to update (only non-None values)
            avatar: New profile picture (optional)
            id_proof: Additional ID proofs (optional)
            education_certificates: Additional certificates (optional)
            experience_letters: Additional experience letters (optional)
            other_documents: Additional documents (optional)
            updated_by: Who updated this profile ("employee", "hr", or "system")
        
        Returns:
            Updated EmployeeProfile instance
        """
        
        # Get existing profile
        profile = await ProfileUtils.get_profile_by_id(emp_id)

        # Check uniqueness if email or phone changed
        if "email" in form_data and form_data["email"]:
            await ProfileUtils.check_email_uniqueness(form_data["email"], emp_id)
        if "phone" in form_data and form_data["phone"]:
            await ProfileUtils.check_phone_uniqueness(form_data["phone"], emp_id)

        # Update profile fields and documents
        profile = await ProfileUtils.update_profile_fields(
            profile=profile,
            form_data=form_data,
            avatar=avatar,
            id_proof=id_proof,
            education_certificates=education_certificates,
            experience_letters=experience_letters,
            other_documents=other_documents
        )

        # Sync login credential with any changes
        await ProfileUtils.sync_login_credential(
            emp_id=emp_id,
            full_name=form_data.get("full_name"),
            phone=form_data.get("phone"),
            department=form_data.get("department").value if form_data.get("department") else None,
            designation=form_data.get("designation")
        )

        logger.info(f"Employee updated: {emp_id} (updated by: {updated_by})")
        return profile

    # ==================== GET ALL PROFILES (WITH COMPLETE DETAILS) ====================

    @staticmethod
    async def get_all_profiles(skip: int = 0, limit: int = 100, detailed: bool = True) -> List[Dict]:
        """
        Get all employee profiles - can return basic or complete details
        
        Args:
            skip: Number of records to skip (pagination)
            limit: Maximum number of records to return
            detailed: If True, return all fields; if False, return basic fields only
        
        Returns:
            List of employee dictionaries with complete or basic info
        """
        profiles = await ProfileUtils.get_all_profiles(skip=skip, limit=limit)
        
        if detailed:
            # Return COMPLETE details with ALL fields
            return [
                {
                    # System fields
                    "id": str(profile.id) if profile.id else None,
                    "emp_id": profile.emp_id,
                    "created_at": profile.created_at,
                    "updated_at": profile.updated_at,
                    
                    # Personal information (required + optional)
                    "full_name": profile.user_info.full_name,
                    "dob": profile.user_info.dob,
                    "gender": profile.user_info.gender,
                    "phone": profile.user_info.phone,
                    "email": profile.user_info.email,
                    "marital_status": profile.user_info.marital_status,
                    
                    # Professional information
                    "experience": profile.user_info.experience,
                    "experience_level": profile.user_info.experience_level,
                    "designation": profile.user_info.designation,
                    "department": profile.user_info.department,
                    "qualification": profile.user_info.qualification,
                    "qualification_level": profile.user_info.qualification_level,
                    "employees_role": profile.user_info.employees_role,
                    "salary_account_number": profile.user_info.salary_account_number,
                    
                    # Identification & emergency
                    "aadhaar_number": profile.user_info.aadhaar_number,
                    "address": profile.user_info.address,
                    "blood_group": profile.user_info.blood_group,
                    "emergency_contact_number": profile.user_info.emergency_contact_number,
                    
                    # Documents
                    "documents": {
                        "avatar": profile.user_info.user_documents.avatar,
                        "id_proof": profile.user_info.user_documents.id_proof,
                        "education_certificates": profile.user_info.user_documents.education_certificates,
                        "experience_letters": profile.user_info.user_documents.experience_letters,
                        "other_documents": profile.user_info.user_documents.other_documents,
                    }
                }
                for profile in profiles
            ]
        else:
            # Return basic info only (backward compatible)
            return [
                {
                    "id": str(profile.id) if profile.id else None,
                    "emp_id": profile.emp_id,
                    "full_name": profile.user_info.full_name,
                    "email": profile.user_info.email,
                    "phone": profile.user_info.phone,
                    "department": profile.user_info.department,
                    "designation": profile.user_info.designation,
                    "created_at": profile.created_at
                }
                for profile in profiles
            ]

    # ==================== DELETE PROFILE ====================

    @staticmethod
    async def delete_employee_profile(emp_id: str) -> None:
        """
        Delete employee profile and login credentials - used by HR module
        
        Args:
            emp_id: Employee ID to delete
        """
        profile = await ProfileUtils.get_profile_by_id(emp_id)
        await profile.delete()
        
        login_cred = await LoginCredential.find_one(LoginCredential.emp_id == emp_id)
        if login_cred:
            await login_cred.delete()
        
        logger.info(f"Employee deleted: {emp_id}")