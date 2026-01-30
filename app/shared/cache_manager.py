from app.core.cache.cache_manager import get_dragonfly_client
from datetime import datetime
from app.shared.timezone import get_ist_now
import json

# -------------------------------------------------------------------
# 1. MONTHLY PLAN CACHE REFRESHER
# -------------------------------------------------------------------

async def refresh_monthly_plan_cache(year: str, month: str):
    """
    INVALIDATES -> FETCHES -> SAVES Monthly Plan Cache.
    
    Usage:
        Call this after POST / PUT / DELETE operations on Monthly Plans.
        
    Logic:
        1. Deletes old key.
        2. Fetches latest plans from MongoDB (Beanie).
        3. Calculates TTL valid until END of month.
        4. Saves to Dragonfly.
    """
    # 1. Standardize Month String (YYYY-MM)
    month_str = f"{year}-{month.zfill(2)}"
    
    # 2. Define Cache Key
    cache_key = f"monthly_plan:{year}:{month.zfill(2)}"
    
    # 3. Invalidate (Delete Old Key)
    client = get_dragonfly_client()
    client.delete(cache_key)
    
    # 4. Fetch Data from MongoDB (Using Beanie)
    # Note: Import model inside function to avoid circular imports if needed
    from app.core.models.production.production_plan import MonthlyProductionPlan
    
    plans = await MonthlyProductionPlan.find(
        MonthlyProductionPlan.month == month_str
    ).to_list()
    
    # 5. Serialize for JSON
    formatted_plans = [plan.model_dump(mode='json') for plan in plans]
    
    # 6. Calculate Dynamic TTL (Time until end of month)
    current_year = int(year)
    current_month = int(month)
    
    # Calculate first day of next month
    if current_month == 12:
        next_month_start = datetime(current_year + 1, 1, 1)
    else:
        next_month_start = datetime(current_year, current_month + 1, 1)
        
    # Get current time (Timezone Aware)
    now = get_ist_now()
    
    # === CRITICAL FIX ===
    # Attach the timezone from 'now' to 'next_month_start' so they are compatible
    next_month_start = next_month_start.replace(tzinfo=now.tzinfo)
    # ====================
    
    ttl_seconds = int((next_month_start - now).total_seconds())
    
    # Safety Check: If date is in the past, default to 1 day
    if ttl_seconds < 0:
        ttl_seconds = 86400 # 1 Day in seconds

    # 7. Save New Key
    client.setex(cache_key, ttl_seconds, json.dumps(formatted_plans))
    
    print(f"Monthly Plan Cache Refreshed: {cache_key} | TTL: {ttl_seconds}s | Records: {len(formatted_plans)}")
    
# -------------------------------------------------------------------
# 2. PART CONFIGURATION CACHE REFRESHER
# -------------------------------------------------------------------

async def refresh_part_config_cache():
    """
    INVALIDATES -> FETCHES -> SAVES Part Configuration Cache.
    
    Usage:
        Call this after POST / PUT / PATCH operations on Part Configurations.
    
    Logic:
        1. Deletes old key.
        2. Fetches latest active parts from MongoDB (Beanie).
        3. Sets Fixed TTL (24 Hours).
        4. Saves to Dragonfly.
    """
    
    # 1. Define Cache Key
    cache_key = f"part_configs:all"
    
    # 2. Invalidate (Delete Old Key)
    client = get_dragonfly_client()
    client.delete(cache_key)
    
    # 3. Fetch Data from MongoDB (Using Beanie)
    # Import model locally
    from app.core.models.parts_config import PartConfiguration
    
    configs = await PartConfiguration.find(
        PartConfiguration.is_active == True
    ).to_list()
    
    # 4. Serialize for JSON
    formatted_configs = [config.model_dump(mode='json') for config in configs]
    
    # 5. Set Fixed TTL (24 Hours = 86400 seconds)
    # Fixed TTL is better for Master Data that doesn't depend on calendar dates
    ttl_seconds = 86400 
    
    client.setex(cache_key, ttl_seconds, json.dumps(formatted_configs))
    
    print(f"Part Config Cache Refreshed: {cache_key} | TTL: 24H | Records: {len(formatted_configs)}")