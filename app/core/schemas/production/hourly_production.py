from typing import List, Optional, Literal
from datetime import datetime
from pydantic import BaseModel, Field, validator


# -----------------------------
# Enums
# -----------------------------

DocumentStatus = Literal[
    "OPEN",
    "PENDING_APPROVAL",
    "APPROVED",
    "BLOCKED"
]

EntryStatus = Literal[
    "DRAFT",
    "SUBMITTED",
    "FINAL"
]


# -----------------------------
# Signature & Approval (Import from models instead of duplicating)
# -----------------------------

from app.core.models.production.hourly_production import (
    VerificationRecord as VerificationRecordSchema,
    DocumentApprovalRecord as DocumentApprovalRecordSchema,
    DocumentTotals as DocumentTotalsSchema
)


# -----------------------------
# Hourly Entry Input - FIXED VALIDATION
# -----------------------------

class HourlyProductionEntryInput(BaseModel):
    """Input schema for hourly production entry."""
    
    time_slot: str = Field(..., example="08:00-09:00")

    plan_qty: int = Field(..., ge=0, description="Planned quantity")
    actual_qty: int = Field(..., ge=0, description="Actual produced quantity")

    ok_qty: int = Field(0, ge=0, description="OK/accepted quantity")
    rejected_qty: int = Field(0, ge=0, description="Rejected quantity")

    # Downtime
    downtime_code: Optional[str] = Field(None, description="Downtime reason code")
    downtime_from: Optional[str] = Field(None, description="Downtime start time (HH:MM)")
    downtime_to: Optional[str] = Field(None, description="Downtime end time (HH:MM)")

    # Rejection
    rejection_reason: Optional[str] = Field(None, description="Rejection reason")

    # Manual weight entry
    lumps_kgs: float = Field(0, ge=0, description="Lumps weight in kg")

    @validator("time_slot")
    def validate_time_slot(cls, v):
        """Validate time slot format HH:MM-HH:MM"""
        if not isinstance(v, str):
            raise ValueError("Time slot must be a string")
        
        try:
            parts = v.split("-")
            if len(parts) != 2:
                raise ValueError("Must contain exactly one '-' separator")
            
            start, end = parts
            datetime.strptime(start.strip(), "%H:%M")
            datetime.strptime(end.strip(), "%H:%M")
            return v
        except ValueError as e:
            raise ValueError(f"Time slot must be in HH:MM-HH:MM format. Error: {e}")

    @validator("rejected_qty")
    def validate_quantities_sum(cls, rejected_qty, values):
        """
        Validate that ok_qty + rejected_qty <= actual_qty.
        
        This runs after all previous fields are validated.
        """
        if "actual_qty" not in values or "ok_qty" not in values:
            return rejected_qty
        
        actual = values["actual_qty"]
        ok = values["ok_qty"]
        
        # Individual checks
        if ok > actual:
            raise ValueError(
                f"OK quantity ({ok}) cannot exceed Actual quantity ({actual})"
            )
        
        if rejected_qty > actual:
            raise ValueError(
                f"Rejected quantity ({rejected_qty}) cannot exceed Actual quantity ({actual})"
            )
        
        # Sum check
        total = ok + rejected_qty
        if total > actual:
            raise ValueError(
                f"Sum of OK ({ok}) and Rejected ({rejected_qty}) quantities "
                f"({total}) cannot exceed Actual quantity ({actual})"
            )
        
        return rejected_qty
    
    @validator("downtime_from", "downtime_to")
    def validate_downtime_format(cls, v):
        """Validate downtime time format if provided"""
        if v is None:
            return v
        
        try:
            datetime.strptime(v.strip(), "%H:%M")
            return v
        except ValueError:
            raise ValueError(f"Downtime time must be in HH:MM format, got: {v}")

    class Config:
        json_schema_extra = {
            "example": {
                "time_slot": "08:00-09:00",
                "plan_qty": 100,
                "actual_qty": 95,
                "ok_qty": 93,
                "rejected_qty": 2,
                "downtime_code": "M001",
                "downtime_from": "08:15",
                "downtime_to": "08:30",
                "rejection_reason": "Surface defect",
                "lumps_kgs": 0.5
            }
        }


# -----------------------------
# Hourly Entry Response
# -----------------------------

class HourlyProductionEntryResponse(BaseModel):
    """Response schema for hourly production entry."""
    
    time_slot: str

    plan_qty: int
    actual_qty: int

    ok_qty: int
    rejected_qty: int

    downtime_code: Optional[str]
    downtime_from: Optional[str]
    downtime_to: Optional[str]
    downtime_minutes: float

    rejection_reason: Optional[str]
    lumps_kgs: float

    shift_name: Optional[str]
    status: EntryStatus
    
    production_timestamp: Optional[datetime]
    submission_timestamp: Optional[datetime]


# -----------------------------
# Initialize Document
# -----------------------------

class InitializeDocumentRequest(BaseModel):
    """Request schema for initializing a new document."""
    
    date: str = Field(..., example="2026-01-20", description="Production date (YYYY-MM-DD)")
    doc_no: str = Field(..., example="DOC-2026-001", description="Unique document number")

    # Side
    side: Literal["LH", "RH"] = Field(..., example="LH", description="Side: Left Hand or Right Hand")

    # Part info
    part_number: str = Field(..., description="Part number")
    part_description: Optional[str] = Field(None, description="Part description")
    operator_name: Optional[str] = Field(None, description="Operator name")
    customer_name: Optional[str] = Field(None, description="Customer name")

    # Technical
    no_of_cavity: Optional[int] = Field(None, ge=1, description="Number of cavities")
    cycle_time: Optional[float] = Field(None, ge=0, description="Cycle time in seconds")

    # SIMPLIFIED WEIGHTS
    part_weight: float = Field(..., ge=0, description="Part weight in grams")
    runner_weight: float = Field(0, ge=0, description="Runner weight in grams")
    # REMOVED: no_of_runner

    # Material
    rm_mb: Optional[str] = Field(None, description="Raw material / Master batch code")
    lot_no: Optional[str] = Field(None, description="Lot number")
    lot_no_production: Optional[str] = Field(None, description="Production lot number")
    
    @validator("date")
    def validate_date_format(cls, v):
        """Validate date format"""
        try:
            datetime.strptime(v, "%Y-%m-%d")
            return v
        except ValueError:
            raise ValueError("Date must be in YYYY-MM-DD format")


# -----------------------------
# Submit Hourly Data
# -----------------------------

class SubmitHourlyDataRequest(BaseModel):
    """Request schema for submitting hourly entries."""
    
    doc_no: str = Field(..., description="Document number")
    entries: List[HourlyProductionEntryInput] = Field(
        ..., 
        min_items=1,
        description="List of hourly entries to submit")
    
#-----------------------------
#Update Document
#-----------------------------
class UpdateDocumentDetailsRequest(BaseModel):
    """Request schema for updating document details."""
    doc_no: str = Field(..., description="Document number")
    
    # Manual Total Entries
    total_lumps_kgs: Optional[float] = Field(
        None, 
        ge=0, 
        description="Total manual lumps weight in kg"
    )
    total_runner_weight_kgs: Optional[float] = Field(
        None,
        ge=0,
        description="Total runner weight in kg (Manual Entry)"
    )

#-----------------------------
#Sign Document
#-----------------------------
class SignDocumentRequest(BaseModel):
    """Request schema for signing a document."""
    doc_no: str = Field(..., description="Document number")
    signature_type: Literal["OPERATOR", "PRODUCTION_HEAD"] = Field(
        ...,
        description="Type of signature"
    )
#-----------------------------
#UNIFIED: Review Document Status
#-----------------------------
class ReviewDocumentStatusRequest(BaseModel):
    """
    Unified request schema for approving or rejecting document status.
    Admin can approve PENDING_APPROVAL documents to make them OPEN,
    or reject them to make them BLOCKED.
    """
    doc_no: str = Field(..., example="DOC-2026-018-001", description="Document number")
    action: Literal["APPROVE", "REJECT"] = Field(..., example="APPROVE", description="Action to take")
    remarks: Optional[str] = Field(
        None, 
        example="Approved: Valid reason for late entry provided by operator",
        description="Admin remarks explaining the decision"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "doc_no": "DOC-2026-018-001",
                "action": "APPROVE",
                "remarks": "Machine breakdown caused delay in document creation"
            }
        }

# -----------------------------
# Finalize Document
#-----------------------------
class FinalizeDocumentRequest(BaseModel):
    """Request schema for finalizing a document."""
    doc_no: str = Field(..., description="Document number")

#-----------------------------
#Full Document Response
#-----------------------------
class HourlyProductionDocumentResponse(BaseModel):
    """Complete response schema for hourly production document."""
    date: str
    doc_no: str
    created_at: datetime

    # DOCUMENT STATUS
    document_status: DocumentStatus
    document_approval: Optional[DocumentApprovalRecordSchema]

    # Side
    side: Literal["LH", "RH"]

    # Identity
    part_number: str
    part_description: Optional[str]
    operator_name: Optional[str]
    customer_name: Optional[str]

    # Technical
    no_of_cavity: Optional[int]
    cycle_time: Optional[float]

    # SIMPLIFIED WEIGHTS
    part_weight: float
    runner_weight: float
    # REMOVED: no_of_runner

    # Material
    rm_mb: Optional[str]
    lot_no: Optional[str]
    lot_no_production: Optional[str]

    # Rows
    entries: List[HourlyProductionEntryResponse]

    # Totals
    totals: DocumentTotalsSchema

    # Signatures
    operator_signatures: List[VerificationRecordSchema]
    production_head_signatures: List[VerificationRecordSchema]

    is_finalized: bool
    finalized_at: Optional[datetime]