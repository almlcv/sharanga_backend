from fastapi import APIRouter, status, Depends
from typing import List
from app.core.schemas.shift import GlobalSettingCreate, GlobalSettingResponse, MessageResponse
from app.modules.shifts.shift_service import ShiftService

from app.core.auth.deps import require_roles, get_current_user

router = APIRouter(prefix="/v1/shifts/global", tags=["Global Shift Settings"])

@router.get(
    "", 
    response_model=List[GlobalSettingResponse],
    # dependencies=[Depends(get_current_user)],
    summary="Get All Shift Settings",
    description="""
    Retrieve a list of all stored global shift configurations.
    
    **Returns:**
    List of all shift settings, sorted by most recently updated, each containing:
    - Shift definitions (name, start time, end time)
    - Break times and durations
    - Working hours calculation
    - Creation and update timestamps
    - Active status
    
    **Use Cases:**
    - Review all historical shift configurations
    - Compare different shift settings
    - Audit shift changes over time
    - Select specific configuration for editing
    
    **Note:** The most recently updated setting is typically the active one.
    """,
    responses={
        200: {"description": "List of shift settings retrieved successfully"},
        500: {"description": "Server error"}
    }
)
async def get_all_settings():
    return await ShiftService.get_all_settings()


@router.get(
    "/current", 
    response_model=GlobalSettingResponse,
    # dependencies=[Depends(get_current_user)],
    summary="Get Currently Active Shift Setting",
    description="""
    Retrieve the currently active global shift configuration.
    
    **Determination Logic:**
    The active setting is determined by the latest update timestamp.
    The most recently created or updated configuration is considered active.
    
    **Returns:**
    Active shift configuration containing:
    - All shift definitions (Morning, Afternoon, Night, etc.)
    - Each shift's start and end times
    - Break schedules
    - Working hours per shift
    - Configuration metadata
    
    **Use Cases:**
    - Production system: Determine current shift based on time
    - Hourly production: Auto-assign shift to entries
    - Attendance system: Calculate working hours
    - Reports: Display current shift schedule
    
    **Example:**
    System checks current time (14:30) against active shift setting to determine it's "Afternoon Shift".
    """,
    responses={
        200: {"description": "Active shift setting retrieved successfully"},
        404: {"description": "No shift settings found in database - please create one first"}
    }
)
async def get_current_setting():
    return await ShiftService.get_active_setting()

@router.post(
    "", 
    response_model=GlobalSettingResponse,
    # dependencies=[Depends(require_roles("Admin"))], 
    status_code=status.HTTP_201_CREATED,
    summary="Create Global Shift Setting",
    description="""
    Create a new global shift configuration.
    
    **Authorization:** Should require Admin role (currently commented out).
    
    **Request Body:**
    - `shifts`: Array of shift definitions, each containing:
      - `shift_name`: Name of the shift (e.g., "Morning", "Afternoon", "Night")
      - `start_time`: Shift start time (HH:MM format, 24-hour)
      - `end_time`: Shift end time (HH:MM format, 24-hour)
      - `break_duration`: Break duration in minutes (optional)
      - `break_start`: Break start time (optional)
    
    **Validation:**
    - Checks for time overlaps between shifts
    - Validates time format (HH:MM)
    - Ensures end_time is after start_time (handles overnight shifts)
    - Prevents duplicate shift names
    
    **Behavior:**
    - Becomes the active configuration immediately upon creation
    - Replaces previous active configuration
    - All production systems use this new configuration
    
    **Use Cases:**
    - Initial system setup: Define factory shift schedule
    - Seasonal changes: Switch to summer/winter shift timings
    - Process improvement: Adjust shift boundaries
    
    **Example:**
    Create 3-shift system: Morning (06:00-14:00), Afternoon (14:00-22:00), Night (22:00-06:00).
    
    **Warning:** This immediately affects all production tracking. Coordinate with operations before changing.
    """,
    responses={
        201: {"description": "Shift setting created successfully and activated"},
        400: {"description": "Validation error - overlapping shifts or invalid time format"}
    }
)
async def create_global_setting(data: GlobalSettingCreate):
    return await ShiftService.create_setting(data)

@router.put(
    "/{setting_id}", 
    response_model=GlobalSettingResponse,
    # dependencies=[Depends(require_roles("Admin"))],
    summary="Update Global Shift Setting",
    description="""
    Update an existing global shift configuration.
    
    **Authorization:** Should require Admin role (currently commented out).
    
    **Path Parameters:**
    - `setting_id`: MongoDB ObjectId of the shift setting to update
    
    **Request Body:**
    Complete shift configuration (same structure as create)
    - `shifts`: Array of shift definitions with times and breaks
    
    **Validation:**
    - Performs overlap validation on updated shifts
    - Validates time formats
    - Ensures logical time sequences
    
    **Behavior:**
    - Updates become active immediately
    - Changes apply globally across all systems
    - Previous configuration is preserved in history
    - Update timestamp is recorded
    
    **Use Cases:**
    - Adjust shift timings: Modify start/end times
    - Update break schedules: Change break duration or timing
    - Add/remove shifts: Modify number of shifts per day
    - Correct errors: Fix incorrectly configured shifts
    
    **Example:**
    Update Morning shift end time from 14:00 to 14:30 to allow handover time.
    
    **Warning:** 
    - Changes take effect immediately
    - Affects ongoing production tracking
    - Coordinate with operations team before updating
    - Consider creating new setting instead of updating if major changes
    """,
    responses={
        200: {"description": "Shift setting updated successfully"},
        404: {"description": "Setting ID not found"},
        400: {"description": "Validation error - overlapping shifts or invalid data"}
    }
)
async def update_global_setting(setting_id: str, data: GlobalSettingCreate):
    return await ShiftService.update_setting(setting_id, data)