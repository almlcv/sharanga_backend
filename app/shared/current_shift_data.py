from datetime import datetime, timedelta, time
from fastapi import HTTPException, status
from zoneinfo import ZoneInfo
import logging
from typing import Tuple, Dict, Any
from pymongo import DESCENDING

from app.core.models.shift import GlobalShiftSetting

# ============================================================================
# Configuration & Constants
# ============================================================================

logger = logging.getLogger(__name__)
IST = ZoneInfo("Asia/Kolkata")
TIMEZONE = IST

# Business Constants
GRACE_PERIOD_HOURS = 24
MAX_DOCUMENT_AGE_DAYS = 7

# ============================================================================
# Internal Helpers
# ============================================================================

async def _get_latest_shift_setting() -> GlobalShiftSetting:
    """Internal helper to fetch the most recent shift configuration."""
    setting = await GlobalShiftSetting.find_one(sort=[("updated_at", DESCENDING)])
    
    if not setting:
        logger.error("No shift configuration found in database")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No global shift configuration found. Please contact system administrator."
        )
    
    if not setting.shifts or len(setting.shifts) == 0:
        logger.error("Shift configuration exists but contains no shifts")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Shift configuration is empty. Please add shifts in system settings."
        )
        
    return setting

async def get_last_shift_end_time(production_date_str: str) -> datetime:
    """
    Get the end time of the last shift for a given production date.
    
    This is used to calculate the grace period deadline.
    It calculates start/end times for all shifts on that date and picks the latest end.
    """
    setting = await _get_latest_shift_setting()
    
    try:
        # Parse production date
        prod_date = datetime.strptime(production_date_str, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid date format: {production_date_str}. Expected YYYY-MM-DD"
        )
    
    latest_end = None
    valid_shifts = 0
    
    for shift in setting.shifts:
        try:
            if not shift.start_time:
                continue
            
            # Parse start time
            start_time_obj = datetime.strptime(shift.start_time, "%H:%M").time()
            
            # Calculate shift start datetime on the production date
            start_dt = datetime.combine(prod_date, start_time_obj).replace(tzinfo=TIMEZONE)
            
            # Calculate duration
            duration_hours = (shift.regular_hours or 0) + (shift.overtime_hours or 0)
            
            if duration_hours <= 0:
                continue
            
            # Calculate end datetime
            end_dt = start_dt + timedelta(hours=duration_hours)
            
            valid_shifts += 1
            
            # Track the latest end time
            if latest_end is None or end_dt > latest_end:
                latest_end = end_dt
                
        except (ValueError, AttributeError, TypeError) as e:
            logger.error(f"Error processing shift {getattr(shift, 'name', 'Unknown')}: {e}")
            continue
    
    if latest_end is None or valid_shifts == 0:
        logger.error("Could not determine last shift end time.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not determine shift timing due to invalid shift configuration."
        )
    
    logger.debug(f"Last shift end for {production_date_str}: {latest_end.isoformat()}")
    return latest_end

# ============================================================================
# Time & Status Utilities
# ============================================================================

def calculate_production_timestamp(date_str: str, time_slot: str) -> datetime:
    """
    Converts a Date String and Time Slot String into a timezone-aware datetime.
    Example: "2026-01-20" + "08:00-09:00" -> 2026-01-20 08:00:00 IST
    """
    try:
        # Extract start hour from time slot (e.g., "08:00-09:00" -> "08:00")
        hour_part = time_slot.split("-")[0].strip()
        
        # Parse the combined string
        naive_dt = datetime.strptime(f"{date_str} {hour_part}", "%Y-%m-%d %H:%M")
        
        # Make timezone-aware
        aware_dt = naive_dt.replace(tzinfo=IST)
        
        logger.debug(f"Production timestamp calculated: {aware_dt} from {date_str} + {time_slot}")
        return aware_dt
    
    except Exception as e:
        logger.error(f"Invalid date/time format: {date_str}, {time_slot} - {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail=f"Invalid Date/Time Slot format. Expected YYYY-MM-DD and HH:MM-HH:MM. Error: {str(e)}"
        )

async def determine_document_status(
    production_date_str: str, 
    current_datetime: datetime
) -> Tuple[str, Dict[str, Any]]:
    """
    Determine document status based on age and shift timing.
    
    Rules:
    1. Future dates: BLOCKED (cannot create)
    2. Age <= Shift End + 24h: OPEN (can submit immediately)
    3. Age > Shift End + 24h AND <= 7 days: PENDING_APPROVAL (needs admin)
    4. Age > 7 days: BLOCKED (rejected)
    
    Args:
        production_date_str: Production date (YYYY-MM-DD)
        current_datetime: Current server datetime (timezone-aware)
        
    Returns:
        tuple: (status, info_dict)
    """
    # 1. Validate Inputs
    try:
        prod_date = datetime.strptime(production_date_str, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid date format: {production_date_str}. Expected YYYY-MM-DD"
        )
    
    if not current_datetime.tzinfo:
        raise ValueError("current_datetime must be timezone-aware")
    
    current_date = current_datetime.date()
    
    # 2. Get Shift Timing Info
    try:
        last_shift_end = await get_last_shift_end_time(production_date_str)
    except HTTPException as e:
        # Re-raise specific DB/Config errors
        raise e
    
    # 3. Calculate Timings
    age_days = (current_date - prod_date).days
    grace_deadline = last_shift_end + timedelta(hours=GRACE_PERIOD_HOURS)
    
    info = {
        "age_days": age_days,
        "production_date": prod_date.isoformat(),
        "current_date": current_date.isoformat(),
        "last_shift_end": last_shift_end.isoformat(),
        "grace_deadline": grace_deadline.isoformat(),
        "max_age_days": MAX_DOCUMENT_AGE_DAYS
    }
    
    # 4. Apply Rules
    
    # Rule 1: Future date - not allowed
    if age_days < 0:
        info["message"] = "Cannot create document for future date."
        logger.warning(f"Document BLOCKED: Future date attempted: {prod_date}")
        return "BLOCKED", info
    
    # Rule 2: Within grace period (24h after last shift ends)
    if current_datetime <= grace_deadline:
        info["message"] = f"Document is OPEN (within {GRACE_PERIOD_HOURS}h grace period)."
        logger.info(f"Document OPEN: {prod_date}")
        return "OPEN", info
    
    # Rule 3: Past grace period, but within max age (7 days)
    if age_days <= MAX_DOCUMENT_AGE_DAYS:
        info["message"] = (
            f"Document requires approval (grace period ended). "
            f"Submitted {age_days} days late."
        )
        logger.info(f"Document PENDING_APPROVAL: {prod_date}")
        return "PENDING_APPROVAL", info
    
    # Rule 4: Older than max age
    info["message"] = (
        f"Document too old ({age_days} days). "
        f"Cannot create documents older than {MAX_DOCUMENT_AGE_DAYS} days."
    )
    logger.warning(f"Document BLOCKED: Too old ({age_days} days). {prod_date}")
    return "BLOCKED", info

def determine_entry_status(
    production_time: datetime,
    submission_time: datetime,
    shift_end: datetime
) -> str:
    """
    Determines workflow status based on submission timing.
    
    Rules:
    1. Submitted <=24h after shift end → SUBMITTED (auto-approved)
    2. Submitted >24h after shift end → PENDING_APPROVAL (locked)
    """
    if not all([production_time.tzinfo, submission_time.tzinfo, shift_end.tzinfo]):
        raise ValueError("All datetime parameters must be timezone-aware")
    
    grace_deadline = shift_end + timedelta(hours=24)
    
    if submission_time <= grace_deadline:
        return "SUBMITTED"
    
    return "PENDING_APPROVAL"

async def get_active_shift_info(target_timestamp: datetime) -> dict:
    """
    Determines which shift is active for a specific datetime.
    
    Supports Shifts that cross midnight by checking both the current date and the previous date.
    """
    if not target_timestamp.tzinfo:
        raise ValueError("target_timestamp must be timezone-aware")
    
    setting = await _get_latest_shift_setting()
    tz_info = target_timestamp.tzinfo
    
    # Check Current Date AND Previous Date (for night shifts)
    dates_to_check = [
        target_timestamp.date(), 
        target_timestamp.date() - timedelta(days=1)
    ]
    
    for shift_item in setting.shifts:
        for check_date in dates_to_check:
            try:
                # 1. Parse shift start time
                start_time_obj = datetime.strptime(shift_item.start_time, "%H:%M").time()
                
                # 2. Combine with date
                start_dt = datetime.combine(check_date, start_time_obj)
                
                # 3. Make timezone-aware
                start_dt = start_dt.replace(tzinfo=tz_info)
                
                # 4. Calculate shift end time using regular_hours + overtime_hours
                duration_hours = shift_item.regular_hours + shift_item.overtime_hours
                end_dt = start_dt + timedelta(hours=duration_hours)
                
                # 5. Check if target falls within this shift
                if start_dt <= target_timestamp < end_dt:
                    logger.info(f"Matched shift '{shift_item.name}': {start_dt} to {end_dt}")
                    return {
                        "name": shift_item.name,
                        "start_time": start_dt,
                        "end_time": end_dt,
                        "duration": duration_hours,
                        "setting_id": str(setting.id)
                    }
            except ValueError:
                continue
    
    # No shift matched
    logger.error(f"No shift found for timestamp {target_timestamp}")
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=f"The timestamp {target_timestamp} does not fall within any defined shift"
    )

def validate_time_slot_format(time_slot: str) -> bool:
    """Validate time slot format (HH:MM-HH:MM)."""
    try:
        start, end = time_slot.split("-")
        datetime.strptime(start.strip(), "%H:%M")
        datetime.strptime(end.strip(), "%H:%M")
        return True
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid time slot format. Expected HH:MM-HH:MM, got: {time_slot}"
        )

def validate_date_format(date_str: str) -> bool:
    """Validate date format (YYYY-MM-DD)."""
    try:
        datetime.strptime(date_str, "%Y-%m-%d")
        return True
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid date format. Expected YYYY-MM-DD, got: {date_str}"
        )