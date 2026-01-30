import os
import aiofiles
import logging
from typing import Optional, List, Dict
from fastapi import HTTPException, status, UploadFile

from app.core.models.hr import EmployeeProfile, LoginCredential
from app.core.setting import config
from app.shared.timezone import get_ist_now

logger = logging.getLogger(__name__)


class ProfileUtils:
    """Utility functions for profile operations - file handling and database helpers"""
    
    # ==================== FILE OPERATIONS ====================
    
    @staticmethod
    def _get_unique_filename(filename: str) -> str:
        """Generate unique filename with timestamp"""
        now_str = get_ist_now().strftime("%Y%m%d%H%M%S")
        safe_name = "".join([c for c in filename if c.isalnum() or c in ('.','_')]).strip()
        return f"{now_str}_{safe_name}"

    @staticmethod
    def _get_file_url(emp_id: str, folder: str, filename: str) -> str:
        """Generate file URL path"""
        return f"/static/uploads/employee_data/{emp_id}/{folder}/{filename}"

    @staticmethod
    async def save_file(file: UploadFile, emp_id: str, subfolder: str) -> str:
        """Save uploaded file asynchronously and return URL"""
        target_dir = os.path.join(config.UPLOAD_DIR, "employee_data", emp_id, subfolder)
        os.makedirs(target_dir, exist_ok=True)
        
        filename = ProfileUtils._get_unique_filename(file.filename)
        file_path = os.path.join(target_dir, filename)
        
        try:
            async with aiofiles.open(file_path, 'wb') as out_file:
                while content := await file.read(1024 * 1024):  # Read in 1MB chunks
                    await out_file.write(content)
        except Exception as e:
            logger.error(f"Failed to save file {filename}: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to save file {filename}."
            )
        return ProfileUtils._get_file_url(emp_id, subfolder, filename)

    @staticmethod
    async def append_files(
        profile: EmployeeProfile, 
        files: Optional[List[UploadFile]], 
        subfolder: str, 
        list_attr: str
    ):
        """Append multiple files to profile document list"""
        if files:
            for file in files:
                url = await ProfileUtils.save_file(file, profile.emp_id, subfolder)
                current_list = getattr(profile.user_info.user_documents, list_attr)
                current_list.append(url)

    # ==================== DATABASE OPERATIONS ====================

    @staticmethod
    async def get_profile_by_id(emp_id: str) -> EmployeeProfile:
        """Get employee profile by ID"""
        profile = await EmployeeProfile.find_one(EmployeeProfile.emp_id == emp_id)
        if not profile:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Employee with ID {emp_id} not found."
            )
        return profile

    @staticmethod
    async def get_all_profiles(skip: int = 0, limit: int = 100) -> List[EmployeeProfile]:
        """Get all employee profiles with pagination"""
        return await EmployeeProfile.find_all().skip(skip).limit(limit).to_list()

    # ==================== VALIDATION ====================

    @staticmethod
    async def check_email_uniqueness(email: str, exclude_emp_id: Optional[str] = None):
        """Check if email already exists"""
        query = EmployeeProfile.user_info.email == email
        if exclude_emp_id:
            query = query & (EmployeeProfile.emp_id != exclude_emp_id)
        
        existing = await EmployeeProfile.find_one(query)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="An employee with this email address already exists."
            )

    @staticmethod
    async def check_phone_uniqueness(phone: str, exclude_emp_id: Optional[str] = None):
        """Check if phone already exists"""
        query = LoginCredential.username == phone
        if exclude_emp_id:
            query = query & (LoginCredential.emp_id != exclude_emp_id)
        
        existing = await LoginCredential.find_one(query)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="An employee with this phone number already exists."
            )

    # ==================== PROFILE UPDATE HELPERS ====================

    @staticmethod
    async def update_profile_fields(
        profile: EmployeeProfile,
        form_data: Dict,
        avatar: Optional[UploadFile] = None,
        id_proof: Optional[List[UploadFile]] = None,
        education_certificates: Optional[List[UploadFile]] = None,
        experience_letters: Optional[List[UploadFile]] = None,
        other_documents: Optional[List[UploadFile]] = None
    ) -> EmployeeProfile:
        """Update profile fields and documents"""
        
        # Update text fields
        for field, value in form_data.items():
            if hasattr(profile.user_info, field):
                setattr(profile.user_info, field, value)

        # Update avatar
        if avatar:
            profile.user_info.user_documents.avatar = await ProfileUtils.save_file(
                avatar, profile.emp_id, "avatar"
            )

        # Append document lists
        await ProfileUtils.append_files(profile, id_proof, "id_proof", "id_proof")
        await ProfileUtils.append_files(profile, education_certificates, "education_certificates", "education_certificates")
        await ProfileUtils.append_files(profile, experience_letters, "experience_letters", "experience_letters")
        await ProfileUtils.append_files(profile, other_documents, "other_documents", "other_documents")

        profile.updated_at = get_ist_now()
        await profile.save()

        return profile

    @staticmethod
    async def sync_login_credential(
        emp_id: str, 
        phone: Optional[str] = None, 
        department: Optional[str] = None, 
        full_name: Optional[str] = None, 
        designation: Optional[str] = None
    ):
        """Sync LoginCredential with profile changes"""
        login_cred = await LoginCredential.find_one(LoginCredential.emp_id == emp_id)
        if not login_cred:
            return
        
        if phone and login_cred.username != phone:
            login_cred.username = phone
        
        if department:
            login_cred.role = department
        
        if full_name:
            login_cred.full_name = full_name
        
        if designation:
            login_cred.role2 = designation.value
        
        await login_cred.save()