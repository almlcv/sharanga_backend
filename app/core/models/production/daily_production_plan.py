"""
Daily Production Plan - one document per (month, variant).
Stores planned quantity per calendar day for each variant (LH/RH).
Aligns with Excel "RABS INDUSTRIES - DAILY PRODUCTION" section.
"""
from typing import Dict
from beanie import Document
from pydantic import Field
from pymongo import ASCENDING


class DailyProductionPlanDocument(Document):
    """
    Daily production plan per variant for a given month.
    Keys in daily_targets are dates "YYYY-MM-DD", values are planned quantities.
    """

    month: str = Field(..., description="YYYY-MM (e.g. '2026-01')")
    variant_name: str = Field(..., description="e.g. 'ALTROZ INNER LENS LH', 'PES COVER A RH'")
    part_description: str = Field(..., description="Base part name without side (for linking to MonthlyProductionPlan)")

    # Planned quantity per calendar day. Key = "YYYY-MM-DD", value = planned qty (0 if no production that day)
    daily_targets: Dict[str, int] = Field(
        default_factory=dict,
        description="Map of date string (YYYY-MM-DD) to planned production quantity for that day"
    )

    # Denormalized for display (from MonthlyProductionPlan at plan creation time)
    monthly_schedule: int | None = Field(None, description="Total monthly target (from monthly plan)")

    class Settings:
        name = "daily_production_plan"
        indexes = [
            [("month", ASCENDING), ("variant_name", ASCENDING)],  # unique lookup
        ]
