from calendar import monthrange
from datetime import datetime
from typing import List, Dict

from app.core.models.production.production_plan import MonthlyProductionPlan
from app.core.models.production.daily_production_plan import DailyProductionPlanDocument
from app.core.models.parts_config import PartConfiguration
from app.shared.variant_utils import parse_variant_name


def _month_str(year: str, month: str) -> str:
    return f"{year}-{str(int(month)).zfill(2)}"


def _working_dates_in_month(year: int, month: int) -> List[str]:
    """Return list of YYYY-MM-DD dates in month excluding Sundays (weekday 6)."""
    _, num_days = monthrange(year, month)
    out = []
    for d in range(1, num_days + 1):
        dt = datetime(year, month, d)
        if dt.weekday() != 6:  # not Sunday
            out.append(dt.strftime("%Y-%m-%d"))
    return out


class DailyPlanService:
    """Build and manage daily production plans from monthly schedule."""

    @staticmethod
    async def get_daily_plan(year: str, month: str) -> Dict:
        """Get full daily plan for a month (all variants)."""
        month_str = _month_str(year, month)
        docs = await DailyProductionPlanDocument.find(
            DailyProductionPlanDocument.month == month_str
        ).to_list()

        variants = []
        for doc in docs:
            total = sum(doc.daily_targets.values())
            variants.append({
                "variant_name": doc.variant_name,
                "part_description": doc.part_description,
                "monthly_schedule": doc.monthly_schedule,
                "daily_targets": doc.daily_targets,
                "total_planned": total,
            })
        return {"month": month_str, "variants": variants}

    @staticmethod
    async def generate_from_monthly_plans(year: str, month: str) -> List[DailyProductionPlanDocument]:
        """
        Generate daily plan from existing monthly plans.
        For each part in MonthlyProductionPlan, get variants (LH/RH) from PartConfiguration,
        then spread monthly schedule evenly over working days (exclude Sundays).
        """
        year_int = int(year)
        month_int = int(month)
        month_str = _month_str(year, month)
        working_dates = _working_dates_in_month(year_int, month_int)
        if not working_dates:
            return []

        monthly_plans = await MonthlyProductionPlan.find(
            MonthlyProductionPlan.month == month_str
        ).to_list()

        created = []
        for plan in monthly_plans:
            part_desc = plan.item_description
            config = await PartConfiguration.find_one(
                PartConfiguration.part_description == part_desc,
                PartConfiguration.is_active == True
            )
            if not config:
                continue
            variants = config.variations if config.variations else [part_desc]
            schedule_per_variant = plan.schedule
            # If multiple variants (LH/RH), split schedule equally per variant
            if len(variants) > 1:
                schedule_per_variant = plan.schedule // len(variants)
            qty_per_day = schedule_per_variant // len(working_dates) if working_dates else 0
            remainder = schedule_per_variant - (qty_per_day * len(working_dates))

            for variant_name in variants:
                daily_targets = {}
                for i, date in enumerate(working_dates):
                    extra = 1 if i < remainder else 0
                    daily_targets[date] = qty_per_day + extra

                existing = await DailyProductionPlanDocument.find_one(
                    DailyProductionPlanDocument.month == month_str,
                    DailyProductionPlanDocument.variant_name == variant_name
                )
                payload = {
                    "month": month_str,
                    "variant_name": variant_name,
                    "part_description": part_desc,
                    "daily_targets": daily_targets,
                    "monthly_schedule": plan.schedule,
                }
                if existing:
                    existing.daily_targets = daily_targets
                    existing.monthly_schedule = plan.schedule
                    await existing.save()
                    created.append(existing)
                else:
                    doc = DailyProductionPlanDocument(**payload)
                    await doc.insert()
                    created.append(doc)
        return created

    @staticmethod
    async def set_daily_plan(year: str, month: str, variant_name: str, daily_targets: Dict[str, int]) -> DailyProductionPlanDocument:
        """Set or update daily targets for one variant. Derives part_description from variant (strip LH/RH)."""
        month_str = _month_str(year, month)
        
        # Use utility function for consistent parsing
        part_description, _ = parse_variant_name(variant_name)

        existing = await DailyProductionPlanDocument.find_one(
            DailyProductionPlanDocument.month == month_str,
            DailyProductionPlanDocument.variant_name == variant_name
        )
        monthly_schedule = existing.monthly_schedule if existing else None
        if not monthly_schedule and daily_targets:
            monthly_schedule = sum(daily_targets.values())

        if existing:
            existing.daily_targets = daily_targets
            if monthly_schedule is not None:
                existing.monthly_schedule = monthly_schedule
            await existing.save()
            return existing
        doc = DailyProductionPlanDocument(
            month=month_str,
            variant_name=variant_name,
            part_description=part_description,
            daily_targets=daily_targets,
            monthly_schedule=monthly_schedule,
        )
        await doc.insert()
        return doc
