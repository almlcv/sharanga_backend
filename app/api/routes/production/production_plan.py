from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import List
from beanie import PydanticObjectId
import json

# App Imports
from app.core.schemas.production.production_plan import MonthlyPlanRequest, MonthlyPlanResponse
from app.core.models.production.production_plan import MonthlyProductionPlan
from app.core.models.parts_config import PartConfiguration
from app.core.schemas.auth import CurrentUser
from app.core.auth.deps import require_roles
from app.shared.cache_manager import refresh_monthly_plan_cache
from app.shared.timezone import get_ist_now

router = APIRouter(tags=["Production Plan"], prefix="/production/plan")


@router.post(
    "/monthly/schedule",
    response_model=MonthlyPlanResponse,
    status_code=status.HTTP_200_OK,
    summary="Set Monthly Schedule"
)
async def set_monthly_production_plan(
    plan_data: MonthlyPlanRequest,
    current_user: CurrentUser = Depends(require_roles("Admin", "Production"))
):
    """
    Sets the monthly production schedule.
    Validates part against PartConfiguration and invalidates cache.
    """

    # 1. Validate against PartConfiguration & Fetch Part Number
    config = await PartConfiguration.find_one({
        "part_description": plan_data.item_description,
        "is_active": True
    })
    
    if not config:
        raise HTTPException(
            status_code=400, 
            detail=f"Part '{plan_data.item_description}' not found in active configurations."
        )
    
    # Extract Part Number (Item Code)
    part_number = config.part_number

    # 2. Prepare Payload (Standardize Date)
    month_str = f"{plan_data.year}-{plan_data.month.zfill(2)}"
    
    # Check if plan already exists
    existing = await MonthlyProductionPlan.find_one({
        "month": month_str,
        "item_description": plan_data.item_description
    })

    if existing:
        raise HTTPException(
            status_code=400, 
            detail="Plan already exists for this part and month. Use Update endpoint."
        )

    # 3. Create Document (Beanie)
    new_plan = MonthlyProductionPlan(
        month=month_str,
        item_description=plan_data.item_description,
        part_number=part_number, # Linked from Configuration
        schedule=int(plan_data.schedule),
        dispatch_quantity_per_day=plan_data.dispatch_quantity_per_day,
        day_stock_to_kept=plan_data.day_stock_to_kept,
        resp_person=plan_data.resp_person
    )
    
    await new_plan.insert()
    
    # 4. Refresh Cache (The "Delete & Save" Logic)
    await refresh_monthly_plan_cache(year=plan_data.year, month=plan_data.month)
    
    return MonthlyPlanResponse(
        message="Schedule created successfully",
        month_str=month_str,
        item_description=plan_data.item_description,
        part_number=part_number,
        upserted_id=str(new_plan.id)
    )


@router.put(
    "/monthly/schedule/{plan_id}",
    response_model=MonthlyPlanResponse,
    summary="Update Monthly Schedule"
)
async def update_monthly_production_plan(
    plan_id: PydanticObjectId,
    update_data: MonthlyPlanRequest,
    current_user: CurrentUser = Depends(require_roles("Admin", "Production"))
):
    """
    Updates an existing monthly plan.
    Validates part existence and invalidates cache.
    """
    
    # 1. Fetch Existing Document
    plan = await MonthlyProductionPlan.get(plan_id)
    
    if not plan:
        raise HTTPException(status_code=404, detail="Monthly plan not found")
    
    # 2. Validate (Optional: Check if Part is still active)
    config = await PartConfiguration.find_one(
        PartConfiguration.part_description == update_data.item_description
    )
    
    if not config:
        raise HTTPException(
            status_code=400, 
            detail=f"Part '{update_data.item_description}' not found in configurations."
        )

    # 3. Update Fields
    month_str = f"{update_data.year}-{update_data.month.zfill(2)}"
    
    # Ensure we aren't changing the month/part identity illegally
    if plan.month != month_str or plan.item_description != update_data.item_description:
        raise HTTPException(
            status_code=400, 
            detail="Cannot change Month or Part Description via update. Delete and recreate if needed."
        )
    
    plan.schedule = int(update_data.schedule)
    plan.dispatch_quantity_per_day = update_data.dispatch_quantity_per_day
    plan.day_stock_to_kept = update_data.day_stock_to_kept
    plan.resp_person = update_data.resp_person
    # Update part_number in case config changed
    plan.part_number = config.part_number
    
    await plan.save()
    
    # 4. Refresh Cache (The "Delete & Save" Logic)
    # We use the original year/month from the DB record to ensure correct key deletion
    year_from_db = plan.month.split("-")[0]
    month_from_db = plan.month.split("-")[1]
    await refresh_monthly_plan_cache(year=year_from_db, month=month_from_db)
    
    return MonthlyPlanResponse(
        message="Schedule updated successfully",
        month_str=month_str,
        item_description=plan.item_description,
        part_number=plan.part_number,
        upserted_id=str(plan.id)
    )


@router.delete(
    "/monthly/schedule/{plan_id}",
    response_model=MonthlyPlanResponse,
    summary="Delete Monthly Schedule"
)
async def delete_monthly_production_plan(
    plan_id: PydanticObjectId,
    current_user: CurrentUser = Depends(require_roles("Admin", "Production"))
):
    """
    Permanently deletes a monthly plan that was set incorrectly.
    Invalidates cache to reflect removal.
    """
    
    # 1. Fetch Existing Document
    plan = await MonthlyProductionPlan.get(plan_id)
    
    if not plan:
        raise HTTPException(status_code=404, detail="Monthly plan not found")
    
    # 2. Capture details for response
    month_str = plan.month
    item_desc = plan.item_description
    
    year_from_db = plan.month.split("-")[0]
    month_from_db = plan.month.split("-")[1]
    
    # 3. Delete from Database
    await plan.delete()
    
    # 4. Refresh Cache (The "Delete & Save" Logic)
    await refresh_monthly_plan_cache(year=year_from_db, month=month_from_db)
    
    return MonthlyPlanResponse(
        message="Schedule deleted successfully",
        month_str=month_str,
        item_description=item_desc,
        upserted_id=None # Deleted, so no ID
    )


@router.get(
    "/monthly/schedule",
    summary="Get Monthly Production Plan",
    response_model=List[dict]
)
async def get_monthly_production_plan(
    year: str = Query(..., description="Year (e.g., 2026)"),
    month: str = Query(..., description="Month (e.g., 01 or 1)"),
    current_user: CurrentUser = Depends(require_roles("Admin", "Production", "Viewer"))
):
    """
    Retrieves the production plan for all parts in a specific month.
    Uses DragonflyDB caching for performance.
    """
    
    # 1. Database Check
    from app.core.cache.cache_manager import get_dragonfly_client
    client = get_dragonfly_client()
    
    # 2. Combine Year and Month to match DB format (YYYY-MM)
    # zfill(2) ensures "1" becomes "01"
    month_str = f"{year}-{month.zfill(2)}"
    
    # 3. Check Dragonfly Cache
    cache_key = f"monthly_plan:{year}:{month.zfill(2)}"
    cached_data = client.get(cache_key)
    
    if cached_data:
        return json.loads(cached_data)

    # 4. Query Database
    plans = await MonthlyProductionPlan.find(
        MonthlyProductionPlan.month == month_str
    ).to_list()
    
    # 5. Convert cursor to list and serialize
    # Note: Since we handle cache miss here, we serialize normally
    formatted_plans = [plan.model_dump(mode='json') for plan in plans]
        
    # 6. Save to Cache (TTL handled in refresh_monthly_plan_cache if we used that, 
    # but here we are in GET. Let's use the helper to keep it DRY)
    # We call the helper to ensure consistent TTL logic
    # Note: The helper will fetch AGAIN which is redundant.
    # Optimization: Just setex here if we miss, but for consistency let's call helper logic conceptually
    # For this code, I will manually set the cached data to avoid double fetch.
    
    # To avoid double DB fetch, we calculate TTL here and save:
    from datetime import datetime
    current_year = int(year)
    current_month = int(month)
    
    if current_month == 12:
        next_month_start = datetime(current_year + 1, 1, 1)
    else:
        next_month_start = datetime(current_year, current_month + 1, 1)
        
    now = get_ist_now()
    ttl_seconds = int((next_month_start - now).total_seconds())
    
    if ttl_seconds < 0: ttl_seconds = 86400

    client.setex(cache_key, ttl_seconds, json.dumps(formatted_plans))
        
    return formatted_plans