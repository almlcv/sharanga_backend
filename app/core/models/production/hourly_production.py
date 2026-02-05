from typing import List, Optional, Literal
from datetime import datetime
from zoneinfo import ZoneInfo

from beanie import Document
from pydantic import BaseModel, Field
from pymongo import ASCENDING, DESCENDING


IST = ZoneInfo("Asia/Kolkata")


# -----------------------------
# Document Status (Gate Control)
# -----------------------------

DocumentStatus = Literal[
    "OPEN",              # Can submit entries freely
    "PENDING_APPROVAL",  # Requires admin approval to open
    "APPROVED",          # Admin approved, now OPEN
    "BLOCKED"            # Too old, cannot be used
]


# -----------------------------
# Entry Status
# -----------------------------

EntryStatus = Literal[
    "DRAFT",
    "SUBMITTED",
    "FINAL"
]

# -----------------------------
# Downtime Codes
# -----------------------------
DowntimeCode = Literal[
    "M/C BD (Machine Breakdown)",
    "Tool BD",
    "Power failure",
    "Quality issue",
    "Material shortage",
    "MC/Tool Maintenance",
    "RM Loading",
    "New Operator",
    "Operator on leave / Permission",
    "Setting",
    "No manpower",
    "Trial",
    "startup",
    "molding change",
    "other",
]


# -----------------------------
# Signature & Approval Records
# -----------------------------

class VerificationRecord(BaseModel):
    """Digital signature record."""
    
    user_id: str
    user_name: str
    verified_at: datetime = Field(default_factory=lambda: datetime.now(IST))


class DocumentApprovalRecord(BaseModel):
    """Document-level approval record (when document_status is PENDING_APPROVAL)."""
    
    approved_by: str
    approved_by_name: str
    approved_at: datetime = Field(default_factory=lambda: datetime.now(IST))
    action: Literal["APPROVED", "REJECTED"]
    remarks: Optional[str] = None


# -----------------------------
# Totals Section (Bottom)
# -----------------------------

class DocumentTotals(BaseModel):
    """Aggregated totals for the document."""
    
    # Quantity Summary
    total_plan_qty: int = 0
    total_actual_qty: int = 0
    total_ok_qty: int = 0
    total_rejected_qty: int = 0

    # Downtime
    total_downtime_minutes: float = 0.0

    # Weight Summary (Kgs)
    total_ok_weight_kgs: float = 0.0
    total_rejected_weight_kgs: float = 0.0
    total_runner_weight_kgs: float = 0.0  # Manual Entry

    # Manual
    total_lumps_kgs: float = 0.0  # Manual Entry


# -----------------------------
# Hourly Entry (Table Section) - CLEANED
# -----------------------------

class HourlyProductionEntry(BaseModel):
    """
    Individual hourly entry.
    
    CLEANED: No redundant header fields.
    All context comes from parent document.
    """
    
    # ---- Time-wise Data ----
    time_slot: str  # 08:00-09:00
    plan_qty: int = 0
    actual_qty: int = 0

    ok_qty: int = 0
    rejected_qty: int = 0

    # ---- Rejection & Downtime ----
    rejection_reason: Optional[str] = None
    # Allow any string in the DB (legacy codes may exist). API schemas validate allowed codes.
    downtime_code: Optional[str] = None
    downtime_from: Optional[str] = None
    downtime_to: Optional[str] = None
    downtime_minutes: float = 0.0  # AUTO-CALCULATED

    # ---- Manual Weight ----
    lumps_kgs: float = 0.0

    # ---- Auto Fields ----
    shift_name: Optional[str] = None
    shift_definition_id: Optional[str] = None

    production_timestamp: Optional[datetime] = None
    submission_timestamp: Optional[datetime] = None

    status: EntryStatus = "DRAFT"


# -----------------------------
# Document (Top Section) - CLEANED
# -----------------------------

class HourlyProductionDocument(Document):
    """Main hourly production document."""
    
    # ---- Primary Identity ----
    date: str
    doc_no: str = Field(default="RI/PRD/R/70A", description="Fixed document number assigned on initialization")
    created_at: datetime = Field(default_factory=lambda: datetime.now(IST))
    
    # ---- DOCUMENT STATUS (GATE) ----
    document_status: DocumentStatus = "OPEN"
    document_approval: Optional[DocumentApprovalRecord] = None

    # ---- Side (LH or RH) ----
    # Optional: some parts are single-sided and have no side value
    side: Optional[Literal["LH", "RH"]] = None

    # ---- Identification & General Info ----
    part_number: str
    part_description: Optional[str] = None
    # Accept either a list of names or a legacy single string in stored documents
    operator_name: Optional[list | str] = Field(default_factory=list, description="One or more operator names")
    customer_name: Optional[str] = None

    # ---- Technical ----
    no_of_cavity: Optional[int] = None
    cycle_time: Optional[float] = None

    # ---- SIMPLIFIED WEIGHTS ----
    part_weight: float = 0  # Single weight field (grams)
    runner_weight: float = 0  # Kept for reference, but not used in auto-calc
    # REMOVED: no_of_runner

    # ---- Material Info ----
    rm_mb: Optional[str] = None
    lot_no: Optional[str] = None
    lot_no_production: Optional[str] = None

    # ---- Entries (CLEANED) ----
    entries: List[HourlyProductionEntry] = Field(default_factory=list)

    # ---- Totals ----
    totals: DocumentTotals = Field(default_factory=DocumentTotals)

    # ---- Signatures ----
    operator_signatures: List[VerificationRecord] = Field(default_factory=list)
    production_head_signatures: List[VerificationRecord] = Field(default_factory=list)

    # ---- Locking ----
    is_finalized: bool = False
    finalized_at: Optional[datetime] = None

    class Settings:
        name = "hourly_production_documents"
        # Indexes
        indexes = [
            [("date", ASCENDING)],
            [("date", ASCENDING), ("part_description", ASCENDING)],
        ]