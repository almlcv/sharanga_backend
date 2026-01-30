from typing import Optional, List, Dict
from fastapi import UploadFile

from app.core.models.hr import EmployeeProfile
from app.shared.profile.profile_service import ProfileService


class EmployeeService:
    """
    Employee self-service operations
    Thin wrapper that delegates to ProfileService
    """

    @staticmethod
    async def get_my_profile(emp_id: str) -> EmployeeProfile:
        """Get own profile"""
        return await ProfileService.get_profile(emp_id)

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
        """Create new employee profile (self-registration)"""
        return await ProfileService.create_employee_profile(
            form_data=form_data,
            password=password,
            avatar=avatar,
            id_proof=id_proof,
            education_certificates=education_certificates,
            experience_letters=experience_letters,
            other_documents=other_documents,
            created_by="employee"
        )

    @staticmethod
    async def update_my_profile(
        emp_id: str,
        form_data: Dict,
        avatar: Optional[UploadFile] = None,
        id_proof: Optional[List[UploadFile]] = None,
        education_certificates: Optional[List[UploadFile]] = None,
        experience_letters: Optional[List[UploadFile]] = None,
        other_documents: Optional[List[UploadFile]] = None
    ) -> EmployeeProfile:
        """Update own complete profile"""
        return await ProfileService.update_employee_profile(
            emp_id=emp_id,
            form_data=form_data,
            avatar=avatar,
            id_proof=id_proof,
            education_certificates=education_certificates,
            experience_letters=experience_letters,
            other_documents=other_documents,
            updated_by="employee"
        )