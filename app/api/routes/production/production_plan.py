from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import List
from beanie import PydanticObjectId
import json

# App Imports
from app.core.schemas.production.production_plan import (
    MonthlyPlanRequest,
    MonthlyPlanResponse,
    # DailyPlanMonthResponse,
    # SetDailyPlanRequest,
    # GenerateDailyPlanRequest,
)
from app.core.models.production.production_plan import MonthlyProductionPlan
from app.core.models.parts_config import PartConfiguration
from app.core.schemas.auth import CurrentUser
from app.core.auth.deps import require_roles

# from app.modules.daily_plan.daily_plan_service import DailyPlanService

router = APIRouter(tags=["Production Plan"], prefix="/production/plan")


@router.post(
    "/monthly/schedule",
    response_model=MonthlyPlanResponse,
    status_code=status.HTTP_200_OK,
    summary="Set Monthly Production Schedule",
    description="""
    Create a monthly production schedule for a specific part.
    
    **Authorization:** Requires Admin or Production role.
    
    **Request Body:**
    - `year`: Year (e.g., "2026")
    - `month`: Month (e.g., "01" or "1")
    - `item_description`: Part description (must exist in active part configurations)
    - `schedule`: Total monthly production target
    - `dispatch_quantity_per_day`: Expected daily dispatch quantity
    - `day_stock_to_kept`: Buffer stock to maintain (in days)
    - `resp_person`: Responsible person name
    
    **Business Rules:**
    - Part must exist in active part configurations
    - One schedule per part per month
    - Part number is automatically fetched from configuration
    - Month format: YYYY-MM
    - Use update endpoint if schedule already exists
    
    **Use Case:**
    Production planning team sets monthly targets:
    1. Review customer orders
    2. Calculate production requirements
    3. Set monthly schedule with buffer stock
    4. Assign responsibility
    
    **Example:**
    Set schedule for "Part A" in January 2026: 10,000 units total, 400/day dispatch, 2 days buffer stock.
    """,
    responses={
        200: {"description": "Schedule created successfully"},
        400: {"description": "Part not found, invalid data, or schedule already exists"},
        401: {"description": "Not authenticated"},
        403: {"description": "Insufficient permissions"}
    }
)
async def set_monthly_production_plan(
    plan_data: MonthlyPlanRequest,
    current_user: CurrentUser = Depends(require_roles("Admin", "Production"))
):
    """
    Sets the monthly production schedule.
    Validates part against PartConfiguration.
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
    
    # REMOVED: Cache refresh logic
    
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
    summary="Update Monthly Production Schedule",
    description="""
    Update an existing monthly production schedule.
    
    **Authorization:** Requires Admin or Production role.
    
    **Path Parameters:**
    - `plan_id`: MongoDB ObjectId of the plan to update
    
    **Request Body:**
    - `year`: Year (must match existing plan)
    - `month`: Month (must match existing plan)
    - `item_description`: Part description (must match existing plan)
    - `schedule`: Updated monthly production target
    - `dispatch_quantity_per_day`: Updated daily dispatch quantity
    - `day_stock_to_kept`: Updated buffer stock days
    - `resp_person`: Updated responsible person
    
    **Business Rules:**
    - Cannot change month, year, or part description via update
    - Only schedule values can be updated
    - Part must still exist in configurations
    - To change month/part, delete and recreate
    
    **Use Case:**
    Adjust production targets when:
    - Customer orders change
    - Production capacity changes
    - Buffer stock requirements change
    - Responsibility transfers
    
    **Example:**
    Increase monthly target from 10,000 to 12,000 units due to new orders.
    """,
    responses={
        200: {"description": "Schedule updated successfully"},
        400: {"description": "Cannot change month/part, or invalid data"},
        401: {"description": "Not authenticated"},
        403: {"description": "Insufficient permissions"},
        404: {"description": "Plan not found"}
    }
)
async def update_monthly_production_plan(
    plan_id: PydanticObjectId,
    update_data: MonthlyPlanRequest,
    current_user: CurrentUser = Depends(require_roles("Admin", "Production"))
):
    """
    Updates an existing monthly plan.
    Validates part existence.
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
    
    # REMOVED: Cache refresh logic
    
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
    summary="Delete Monthly Production Schedule",
    description="""
    Permanently delete a monthly production schedule.
    
    **Authorization:** Requires Admin or Production role.
    
    **Path Parameters:**
    - `plan_id`: MongoDB ObjectId of the plan to delete
    
    **Warning:**
    - This is a permanent deletion
    - Cannot be undone
    - Use when schedule was created incorrectly
    - Consider updating instead if only values need correction
    
    **Use Case:**
    Remove incorrectly created schedules:
    - Wrong part selected
    - Wrong month entered
    - Duplicate schedule created
    - Part discontinued
    
    **Note:** After deletion, a new schedule can be created for the same part/month combination.
    """,
    responses={
        200: {"description": "Schedule deleted successfully"},
        401: {"description": "Not authenticated"},
        403: {"description": "Insufficient permissions"},
        404: {"description": "Plan not found"}
    }
)
async def delete_monthly_production_plan(
    plan_id: PydanticObjectId,
    current_user: CurrentUser = Depends(require_roles("Admin", "Production"))
):
    """
    Permanently deletes a monthly plan that was set incorrectly.
    """
    
    # 1. Fetch Existing Document
    plan = await MonthlyProductionPlan.get(plan_id)
    
    if not plan:
        raise HTTPException(status_code=404, detail="Monthly plan not found")
    
    # 2. Capture details for response
    month_str = plan.month
    item_desc = plan.item_description
    
    # 3. Delete from Database
    await plan.delete()
    
    # REMOVED: Cache refresh logic
    
    return MonthlyPlanResponse(
        message="Schedule deleted successfully",
        month_str=month_str,
        item_description=item_desc,
        upserted_id=None # Deleted, so no ID
    )


@router.get(
    "/monthly/schedule",
    summary="Get Monthly Production Plan",
    response_model=List[dict],
    description="""
    Retrieve production schedules for all parts in a specific month.
    
    **Authorization:** Requires Admin, Production, or Viewer role.
    
    **Query Parameters:**
    - `year` (required): Year (e.g., "2026")
    - `month` (required): Month (e.g., "01" or "1")
    
    **Returns:**
    List of all production schedules for the specified month, each containing:
    - Part description and number
    - Monthly production target (schedule)
    - Daily dispatch quantity
    - Buffer stock days
    - Responsible person
    - Creation and update timestamps
    
    **Use Case:**
    Production team reviews monthly plans to:
    - View all part targets for the month
    - Plan resource allocation
    - Coordinate with dispatch team
    - Monitor progress against targets
    
    **Example:**
    Get all production schedules for January 2026 to plan machine allocation and manpower.
    """,
    responses={
        200: {"description": "Production schedules retrieved successfully"},
        400: {"description": "Invalid year or month format"},
        401: {"description": "Not authenticated"},
        403: {"description": "Insufficient permissions"}
    }
)
async def get_monthly_production_plan(
    year: str = Query(..., description="Year (e.g., 2026)"),
    month: str = Query(..., description="Month (e.g., 01 or 1)"),
    current_user: CurrentUser = Depends(require_roles("Admin", "Production", "Viewer"))
):
    """
    Retrieves the production plan for all parts in a specific month.
    Direct MongoDB query (Cache removed).
    """
    
    # 1. Combine Year and Month to match DB format (YYYY-MM)
    month_str = f"{year}-{month.zfill(2)}"
    
    # 2. Query Database Directly
    plans = await MonthlyProductionPlan.find(
        MonthlyProductionPlan.month == month_str
    ).to_list()
    
    # 3. Convert cursor to list and serialize
    formatted_plans = [plan.model_dump(mode='json') for plan in plans]
        
    return formatted_plans