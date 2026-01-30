from typing import Optional, List, Dict
from fastapi import UploadFile

from app.core.models.hr import EmployeeProfile
from app.shared.profile.profile_service import ProfileService


class HRService:
    """
    HR-specific service for employee management
    Thin wrapper that delegates to ProfileService
    """
    
    @staticmethod
    async def create_employee(
        form_data: Dict,
        password: str,
        avatar: Optional[UploadFile] = None,
        id_proof: Optional[List[UploadFile]] = None,
        education_certificates: Optional[List[UploadFile]] = None,
        experience_letters: Optional[List[UploadFile]] = None,
        other_documents: Optional[List[UploadFile]] = None
    ) -> EmployeeProfile:
        """Create new employee profile (HR)"""
        return await ProfileService.create_employee_profile(
            form_data=form_data,
            password=password,
            avatar=avatar,
            id_proof=id_proof,
            education_certificates=education_certificates,
            experience_letters=experience_letters,
            other_documents=other_documents,
            created_by="hr"
        )

    @staticmethod
    async def get_all_employees(skip: int = 0, limit: int = 100, detailed: bool = True) -> List[Dict]:
        """
        Get all employees with complete or basic info
        
        Args:
            skip: Number of records to skip (pagination)
            limit: Maximum number of records to return
            detailed: If True, return all 27 fields; if False, return basic 8 fields
        
        Returns:
            List of employee dictionaries
        """
        return await ProfileService.get_all_profiles(skip=skip, limit=limit, detailed=detailed)

    @staticmethod
    async def get_employee_by_id(emp_id: str) -> EmployeeProfile:
        """Get employee by ID"""
        return await ProfileService.get_profile(emp_id)

    @staticmethod
    async def update_employee_profile(
        emp_id: str,
        form_data: Dict,
        avatar: Optional[UploadFile] = None,
        id_proof: Optional[List[UploadFile]] = None,
        education_certificates: Optional[List[UploadFile]] = None,
        experience_letters: Optional[List[UploadFile]] = None,
        other_documents: Optional[List[UploadFile]] = None
    ) -> EmployeeProfile:
        """Update employee profile (HR)"""
        return await ProfileService.update_employee_profile(
            emp_id=emp_id,
            form_data=form_data,
            avatar=avatar,
            id_proof=id_proof,
            education_certificates=education_certificates,
            experience_letters=experience_letters,
            other_documents=other_documents,
            updated_by="hr"
        )

    @staticmethod
    async def delete_employee(emp_id: str) -> None:
        """Delete employee (HR only)"""
        await ProfileService.delete_employee_profile(emp_id)