"""
Centralized timezone management for IST (Indian Standard Time).
All datetime operations should use this module for consistency.
"""

from datetime import datetime, timezone as dt_timezone
from zoneinfo import ZoneInfo

# IST timezone definition
IST = ZoneInfo("Asia/Kolkata")


def get_ist_now() -> datetime:
    """
    Get current datetime in IST timezone.
    
    Returns:
        datetime: Current time in IST (timezone-aware)
    
    Example:
        >>> now = get_ist_now()
        >>> print(now.tzinfo)
        Asia/Kolkata
    """
    return datetime.now(tz=IST)


def get_naive_utc_now() -> datetime:
    """
    Get current datetime in UTC (naive).
    Used for token expiration calculations in JWT.
    
    Returns:
        datetime: Current time in UTC (timezone-aware UTC)
    
    Note:
        This returns UTC (not IST) because JWT tokens use UTC timestamps.
        Use get_ist_now() for all application datetime operations.
    """
    return datetime.now(tz=dt_timezone.utc)


def make_ist_aware(dt: datetime) -> datetime:
    """
    Convert a naive datetime to IST timezone-aware.
    
    Args:
        dt: Naive datetime object
        
    Returns:
        datetime: Timezone-aware datetime in IST
        
    Example:
        >>> naive_dt = datetime(2026, 1, 23, 10, 30, 0)
        >>> aware_dt = make_ist_aware(naive_dt)
        >>> print(aware_dt.tzinfo)
        Asia/Kolkata
    """
    if dt.tzinfo is not None:
        return dt
    return dt.replace(tzinfo=IST)


def utc_to_ist(dt_utc: datetime) -> datetime:
    """
    Convert UTC datetime to IST.
    
    Args:
        dt_utc: UTC timezone-aware datetime
        
    Returns:
        datetime: Datetime converted to IST timezone
    """
    if dt_utc.tzinfo is None:
        raise ValueError("Input datetime must be timezone-aware (UTC)")
    return dt_utc.astimezone(IST)
