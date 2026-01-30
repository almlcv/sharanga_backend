from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import JSONResponse

from app.core.schemas.production.hourly_production import (
    InitializeDocumentRequest,
    SubmitHourlyDataRequest,
    UpdateDocumentDetailsRequest,
    SignDocumentRequest,
    ReviewDocumentStatusRequest,
    FinalizeDocumentRequest,
    HourlyProductionDocumentResponse,
)
from app.modules.hourly_production.hourly_production_service import HourlyProductionService
from app.core.auth.deps import get_current_user


router = APIRouter(
    prefix="/production/hourly",
    tags=["Hourly Production"],
)


@router.post(
    "/documents/initialize",
    response_model=HourlyProductionDocumentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Initialize a new hourly production document",
    description="""
    Create a new hourly production document with automatic status determination.
    
    **Document Status Logic (The Gate):**
    - **Age ≤ 24h after last shift end**: Status = `OPEN` (immediate data entry)
    - **Age 24h-7 days**: Status = `PENDING_APPROVAL` (requires admin approval)
    - **Age > 7 days**: `BLOCKED` (raises 400 error, cannot create)
    
    **Purpose:** Start a new production tracking document before entering hourly data.
    
    **Business Rules:**
    - Document number must be unique for the given date
    - Must specify side: LH or RH
    - Single `part_weight` field (no more LH/RH confusion)
    - Once created with OPEN status, hourly entries can be submitted immediately
    - If PENDING_APPROVAL, admin must approve before data entry
    
    **Example Use Case:**
    Initialize document "DOC-2026-001" for date "2026-01-20" to track production
    for part "PART-12345" throughout the day.
    """,
    responses={
        201: {
            "description": "Document created successfully",
            "content": {
                "application/json": {
                    "example": {
                        "date": "2026-01-20",
                        "doc_no": "DOC-2026-001",
                        "document_status": "OPEN",
                        "side": "LH",
                        "part_weight": 500,
                        "created_at": "2026-01-20T07:30:00+05:30",
                        "entries": [],
                        "totals": {
                            "total_plan_qty": 0,
                            "total_actual_qty": 0
                        },
                        "is_finalized": False
                    }
                }
            }
        },
        400: {"description": "Document already exists, invalid data, or too old (>7 days)"},
    }
)
async def initialize_document(
    payload: InitializeDocumentRequest,
    current_user: dict = Depends(get_current_user)
):
    """Initialize a new hourly production document with automatic status"""
    return await HourlyProductionService.initialize_document(payload)


@router.post(
    "/documents/submit",
    response_model=HourlyProductionDocumentResponse,
    summary="Submit hourly production entries",
    description="""
    Submit one or more hourly production entries to an existing document.
    
    **STATUS GATE: Can only submit if document_status is OPEN or APPROVED**
    
    **Document Status Check:**
    - `OPEN` or `APPROVED`: Entry submission allowed
    - `PENDING_APPROVAL`: Blocked - requires admin approval first
    - `BLOCKED`: Blocked - too old, cannot be used
    
    **Automatic Calculations:**
    The system automatically calculates these fields (do NOT include in request):
    - `production_timestamp`: Calculated from date + time_slot
    - `submission_timestamp`: Current server time when request is received
    - `shift_name`: Determined from production_timestamp
    - `shift_definition_id`: Reference to active shift configuration
    
    **Validation:**
    - OK + Rejected quantities cannot exceed Actual quantity
    - Cannot edit entries with status "FINAL"
    - Cannot submit to finalized documents
    
    **Simplified Data Structure:**
    - No more LH/RH quantity fields in entries
    - Single `ok_qty` and `rejected_qty` fields
    - Side context (LH/RH) comes from document header
    
    **Example Workflow:**
    1. Document initialized with status OPEN → Submit entries immediately
    2. Document initialized with PENDING_APPROVAL → Admin must approve first
    3. After admin approves → Document becomes APPROVED → Submit entries
    """,
    responses={
        200: {
            "description": "Entries submitted successfully",
            "content": {
                "application/json": {
                    "example": {
                        "date": "2026-01-20",
                        "doc_no": "DOC-2026-001",
                        "document_status": "OPEN",
                        "entries": [
                            {
                                "time_slot": "08:00-09:00",
                                "plan_qty": 100,
                                "actual_qty": 95,
                                "ok_qty": 93,
                                "rejected_qty": 2,
                                "shift_name": "Morning",
                                "status": "SUBMITTED"
                            }
                        ],
                        "totals": {
                            "total_plan_qty": 100,
                            "total_actual_qty": 95,
                            "total_ok_qty": 93,
                            "total_rejected_qty": 2
                        }
                    }
                }
            }
        },
        400: {"description": "Validation error or document finalized"},
        403: {"description": "Document status does not allow data entry"},
        404: {"description": "Document not found"},
    }
)
async def submit_hourly_data(
    payload: SubmitHourlyDataRequest,
    current_user: dict = Depends(get_current_user)
):
    """Submit hourly production entries with status gate enforcement"""
    service = HourlyProductionService()
    return await service.submit_hourly_data(payload, current_user)


@router.post(
    "/documents/review-status",
    response_model=HourlyProductionDocumentResponse,
    summary="UNIFIED: Approve or Reject Document Status (Admin only)",
    description="""
    Unified endpoint for approving or rejecting a document's status.
    
    **Authorization:** Only users with Admin role can review document status.
    
    **Actions:**
    
    **1. APPROVE:**
    - Changes: `PENDING_APPROVAL` → `APPROVED`
    - Effect: Document is now OPEN for data entry
    - Use case: Late document creation was justified
    
    **2. REJECT:**
    - Changes: `PENDING_APPROVAL` → `BLOCKED`
    - Effect: Document is permanently blocked, cannot be used
    - Use case: Late document creation was not justified
    
    **Workflow Example:**
    1. Operator creates document 5 days late → Auto status: `PENDING_APPROVAL`
    2. Operator tries to submit entries → Blocked with message
    3. Admin reviews and approves with reason → Status: `APPROVED`
    4. Operator can now submit entries → Success
    
    **Business Rules:**
    - Only documents with `PENDING_APPROVAL` status can be reviewed
    - Admin must provide remarks explaining the decision
    - Action is recorded with timestamp and admin details
    - Approved documents behave exactly like OPEN documents
    - Rejected documents can never be used (permanent block)
    """,
    responses={
        200: {
            "description": "Document status reviewed successfully",
            "content": {
                "application/json": {
                    "examples": {
                        "approved": {
                            "summary": "Document Approved",
                            "value": {
                                "date": "2026-01-18",
                                "doc_no": "DOC-2026-018-001",
                                "document_status": "APPROVED",
                                "document_approval": {
                                    "approved_by": "ADM001",
                                    "approved_by_name": "Admin User",
                                    "approved_at": "2026-01-23T10:30:00+05:30",
                                    "action": "APPROVED",
                                    "remarks": "Machine breakdown caused delay in document creation"
                                }
                            }
                        },
                        "rejected": {
                            "summary": "Document Rejected",
                            "value": {
                                "date": "2026-01-18",
                                "doc_no": "DOC-2026-018-001",
                                "document_status": "BLOCKED",
                                "document_approval": {
                                    "approved_by": "ADM001",
                                    "approved_by_name": "Admin User",
                                    "approved_at": "2026-01-23T10:30:00+05:30",
                                    "action": "REJECTED",
                                    "remarks": "No valid justification for late submission"
                                }
                            }
                        }
                    }
                }
            }
        },
        403: {"description": "User is not an Admin"},
        404: {"description": "Document not found"},
        400: {"description": "Document is not in PENDING_APPROVAL status"},
    }
)
async def review_document_status(
    payload: ReviewDocumentStatusRequest,
    current_user: dict = Depends(get_current_user)
):
    """Unified endpoint for approving or rejecting document status"""
    return await HourlyProductionService.review_document_status(payload, current_user)


@router.post(
    "/documents/sign",
    response_model=HourlyProductionDocumentResponse,
    summary="Add digital signature to document",
    description="""
    Add a digital signature to approve the document.
    
    **Signature Types:**
    - **OPERATOR**: Production operator signature
    - **PRODUCTION_HEAD**: Production head signature
    
    **Business Rules:**
    - Each user can sign only once per signature type
    - Cannot sign finalized documents
    - Signature includes user ID, name, and timestamp
    
    **Workflow:**
    Operators and Production Heads digitally sign to verify accuracy before finalization.
    """,
    responses={
        200: {"description": "Signature added successfully"},
        400: {"description": "Already signed or document finalized"},
        403: {"description": "User does not have required role"},
        404: {"description": "Document not found"},
    }
)
async def sign_document(
    payload: SignDocumentRequest,
    current_user: dict = Depends(get_current_user)
):
    """Add digital signature to document"""
    return await HourlyProductionService.sign_document(payload, current_user)


@router.post(
    "/documents/finalize",
    response_model=HourlyProductionDocumentResponse,
    summary="Finalize document (lock for editing)",
    description="""
    Finalize the document to lock it from further editing.
    
    **Effect:**
    - All SUBMITTED entries become FINAL
    - Document cannot be edited anymore
    - Signatures cannot be added
    - Sets `is_finalized = true` and `finalized_at` timestamp
    
    **Use Case:**
    After all data entry and approvals are complete, Production Head finalizes the document
    for permanent record.
    """,
    responses={
        200: {"description": "Document finalized successfully"},
        400: {"description": "Document already finalized"},
        404: {"description": "Document not found"},
    }
)
async def finalize_document(
    payload: FinalizeDocumentRequest,
    current_user: dict = Depends(get_current_user)
):
    """Finalize document to prevent further edits"""
    return await HourlyProductionService.finalize_document(payload, current_user)


@router.patch(
    "/documents/update-details",
    response_model=HourlyProductionDocumentResponse,
    summary="Update document-level details",
    description="""
    Update common details at the document level.
    
    **Updatable Fields:**
    - Lumps
    - Raw material/Master batch code

    
    **Effect:**
    Updates the specified fields in the document header.
    All entries inherit these values from the document.
    
    """,
    responses={
        200: {"description": "Details updated successfully"},
        404: {"description": "Document not found"},
    }
)
async def update_document_details(
    payload: UpdateDocumentDetailsRequest,
    current_user: dict = Depends(get_current_user)
):
    """Update document-level details"""
    return await HourlyProductionService.update_document_details(payload)


@router.get(
    "/documents/pending-approval",
    response_model=List[HourlyProductionDocumentResponse],
    summary="Get all documents pending approval (Admin only)",
    description="""
    Retrieves a list of all documents with status `PENDING_APPROVAL`.
    
    **Business Logic:**
    - This acts as an "Inbox" for Admins.
    - Returns documents from any date that require review.
    - Sorted by date (most recent late entries first).
    
    **Authorization:** Only users with 'Admin' role can access this endpoint.
    """,
    responses={
        200: {
            "description": "List of pending documents",
            "content": {
                "application/json": {
                    "example": [
                        {
                            "date": "2026-01-25",
                            "doc_no": "DOC-LATE-001",
                            "document_status": "PENDING_APPROVAL",
                            "side": "RH",
                            "part_number": "P-1001-RH",
                            "totals": {
                                "total_actual_qty": 0
                            }
                        }
                    ]
                }
            }
        },
        403: {"description": "User is not an Admin"},
    }
)
async def get_pending_documents(
    current_user: dict = Depends(get_current_user)
):
    """Retrieve all documents pending approval."""
    return await HourlyProductionService.get_pending_documents(current_user)

@router.get(
    "/documents",
    response_model=List[HourlyProductionDocumentResponse],
    summary="Retrieve production documents",
    description="""
    Retrieve hourly production documents with optional filtering.
    
    **Query Parameters:**
    - `date` (required): Production date (YYYY-MM-DD)
    - `doc_no` (optional): Specific document number
    - `shift_name` (optional): Filter entries by shift
    - `status` (optional): Filter entries by status
    
    **Document Status Values:**
    - `OPEN`: Ready for data entry
    - `PENDING_APPROVAL`: Awaiting admin approval
    - `APPROVED`: Approved by admin, now open for data entry
    - `BLOCKED`: Too old, cannot be used
    
    **Use Cases:**
    - Get all documents for a date: `?date=2026-01-20`
    - Get specific document: `?date=2026-01-20&doc_no=DOC-2026-001`
    - Get morning shift data: `?date=2026-01-20&shift_name=Morning`
    - Get documents pending approval: `?date=2026-01-20&document_status=PENDING_APPROVAL`
    """,
    responses={
        200: {
            "description": "List of matching documents",
            "content": {
                "application/json": {
                    "example": [
                        {
                            "date": "2026-01-20",
                            "doc_no": "DOC-2026-001",
                            "document_status": "OPEN",
                            "side": "LH",
                            "entries": [{"time_slot": "08:00-09:00"}],
                            "totals": {"total_actual_qty": 95},
                            "is_finalized": False
                        }
                    ]
                }
            }
        }
    }
)
async def get_documents(
    date: str = Query(..., description="Production date (YYYY-MM-DD)"),
    doc_no: Optional[str] = Query(None, description="Document number"),
    shift_name: Optional[str] = Query(None, description="Shift name filter"),
    status: Optional[str] = Query(None, description="Entry status filter"),
    current_user: dict = Depends(get_current_user)
):
    """Retrieve production documents with optional filtering"""
    return await HourlyProductionService.get_documents(
        date=date,
        doc_no=doc_no,
        shift_name=shift_name,
        status=status
    )