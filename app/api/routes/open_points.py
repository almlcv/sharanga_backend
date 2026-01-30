from fastapi import APIRouter, Depends, status
from typing import List, Dict, Any

# Import Service and Schemas
from app.modules.open_points.open_points_service import OpenPointsService
from app.core.schemas.open_points import (
    CreateProjectRequest, 
    CreatePointRequest, 
    UpdatePointRequest,
    AddMemberRequest, 
    RemoveMemberRequest, 
    AssignProjectsRequest
)
from app.core.auth.deps import get_current_user
router = APIRouter(prefix="/open-points", tags=["Open Points"])

# =============================================================================
# PROJECT ENDPOINTS
# =============================================================================

@router.post(
    "/projects", 
    response_model=Dict[str, str], 
    summary="Create a new project",
    status_code=status.HTTP_201_CREATED
)
async def create_project(
    request: CreateProjectRequest, 
    current_user = Depends(get_current_user)
):
    """Create Project"""
    return await OpenPointsService.create_project(request, current_user)

@router.get(
    "/my-projects", 
    response_model=List[Dict[str, Any]], 
    summary="Get user's accessible projects"
)
async def get_my_projects(current_user = Depends(get_current_user)):
    """Get My Projects"""
    return await OpenPointsService.get_my_projects(current_user)

@router.get(
    "/project/{projectId}", 
    summary="Get project details"
)
async def get_project_details(projectId: str, current_user = Depends(get_current_user)):
    """Get project details"""
    return await OpenPointsService.get_project_details(projectId, current_user)

@router.post(
    "/project/{projectId}/add-member",
    summary="Add members to project"
)
async def add_member(
    projectId: str, 
    request: AddMemberRequest, 
    current_user = Depends(get_current_user)
):
    """Add Member"""
    return await OpenPointsService.add_member(projectId, request, current_user)

@router.post(
    "/project/{projectId}/remove-member",
    summary="Remove members from project"
)
async def remove_member(
    projectId: str, 
    request: RemoveMemberRequest, 
    current_user = Depends(get_current_user)
):
    """Remove Member"""
    return await OpenPointsService.remove_member(projectId, request, current_user)

@router.delete(
    "/project/{projectId}",
    summary="Delete project"
)
async def delete_project(projectId: str, current_user = Depends(get_current_user)):
    """Delete Project"""
    return await OpenPointsService.delete_project(projectId, current_user)

# =============================================================================
# POINT ENDPOINTS
# =============================================================================

@router.get(
    "/project/{projectId}/points",
    summary="Get all points for a project"
)
async def get_project_points(projectId: str, current_user = Depends(get_current_user)):
    """Get Points"""
    return await OpenPointsService.get_project_points(projectId, current_user)

@router.post(
    "/points",
    summary="Create a new point",
    status_code=status.HTTP_201_CREATED
)
async def create_point(
    request: CreatePointRequest, 
    current_user = Depends(get_current_user)
):
    """Create Point"""
    return await OpenPointsService.create_point(request, current_user)

@router.put(
    "/points/{pointId}",
    summary="Update a point"
)
async def update_point(
    pointId: str, 
    request: UpdatePointRequest, 
    current_user = Depends(get_current_user)
):
    """Update Point"""
    return await OpenPointsService.update_point(pointId, request, current_user)

@router.delete(
    "/points/{pointId}",
    summary="Delete a point"
)
async def delete_point(pointId: str, current_user = Depends(get_current_user)):
    """Delete Point"""
    return await OpenPointsService.delete_point(pointId, current_user)

# =============================================================================
# ANALYTICS
# =============================================================================

@router.get(
    "/analytics/global",
    summary="Get global analytics"
)
async def get_analytics(current_user = Depends(get_current_user)):
    """Global Analytics"""
    return await OpenPointsService.get_analytics(current_user)

# =============================================================================
# ASSIGNMENT ENDPOINTS
# =============================================================================

@router.get(
    "/all-project-names",
    summary="Get all project names"
)
async def get_all_project_names(current_user = Depends(get_current_user)):
    """Get all project names"""
    return await OpenPointsService.get_all_project_names(current_user)

@router.get(
    "/user/{username}/assigned-projects",
    summary="Get user's assigned project names"
)
async def get_user_assigned_projects(username: str, current_user = Depends(get_current_user)):
    """Get user assigned projects"""
    return await OpenPointsService.get_user_assigned_projects(username, current_user)

@router.get(
    "/users/all",
    summary="Get All Employee Names"
)
async def get_all_users():
    """Retrieves all users."""
    return await OpenPointsService.get_all_users()

@router.post(
    "/user/{username}/assign-projects",
    summary="Assign projects to user"
)
async def assign_projects_to_user(
    username: str, 
    request: AssignProjectsRequest, 
    current_user = Depends(get_current_user)
):
    """Assign Projects"""
    return await OpenPointsService.assign_projects_to_user(username, request, current_user)