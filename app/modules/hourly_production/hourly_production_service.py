from typing import List, Optional, Dict, Any
from datetime import datetime
from zoneinfo import ZoneInfo
import logging

from fastapi import HTTPException, status
from pymongo import DESCENDING

from app.core.models.production.hourly_production import (
    HourlyProductionDocument,
    HourlyProductionEntry,
    VerificationRecord,
    DocumentApprovalRecord,
    DocumentTotals,
)
from app.core.schemas.production.hourly_production import (
    InitializeDocumentRequest,
    SubmitHourlyDataRequest,
    UpdateDocumentDetailsRequest,
    SignDocumentRequest,
    ReviewDocumentStatusRequest,
    FinalizeDocumentRequest,
    HourlyProductionEntryInput,
)
from app.shared.current_shift_data import (
    calculate_production_timestamp,
    get_active_shift_info,
    determine_document_status,
)
from app.modules.hourly_production.hourly_production_calculator import HourlyProductionCalculator
from app.modules.fg_stock.fg_stock_service import FGStockService


logger = logging.getLogger(__name__)


# -----------------------------
# Hourly Production Service
# -----------------------------
class HourlyProductionService:
    """Service layer for hourly production document management."""
    
    TIMEZONE = ZoneInfo("Asia/Kolkata")

    # -------------------------
    # Helper Methods
    # -------------------------
    
    @staticmethod
    async def _get_document_or_404(doc_no: str) -> HourlyProductionDocument:
        """Fetch document by doc_no or raise 404."""
        doc = await HourlyProductionDocument.find_one(
            HourlyProductionDocument.doc_no == doc_no
        )
        if not doc:
            logger.warning(f"Document not found: {doc_no}")
            raise HTTPException(
                status.HTTP_404_NOT_FOUND,
                detail=f"Document '{doc_no}' not found"
            )
        # Coerce legacy operator_name string into list for backward compatibility
        try:
            if hasattr(doc, "operator_name"):
                if isinstance(doc.operator_name, str):
                    doc.operator_name = [doc.operator_name]
                elif doc.operator_name is None:
                    doc.operator_name = []
        except Exception:
            # If coercion fails, leave as-is and let later validation handle it
            pass
        return doc
    
    @staticmethod
    async def _get_editable_document(doc_no: str) -> HourlyProductionDocument:
        """Fetch document and ensure it's not finalized."""
        doc = await HourlyProductionService._get_document_or_404(doc_no)
        
        if doc.is_finalized:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                detail=f"Document '{doc_no}' is finalized and cannot be edited"
            )
        return doc
    
    @staticmethod
    def _check_user_has_role(current_user: Dict[str, Any], required_role: str) -> bool:
        """Check if user has required role in primary or secondary role."""
        return (
            current_user.role == required_role or 
            current_user.role2 == required_role
        )
    
    @staticmethod
    def _find_entry(
        doc: HourlyProductionDocument, 
        time_slot: str
    ) -> Optional[HourlyProductionEntry]:
        """Find entry by time slot in document."""
        return next(
            (e for e in doc.entries if e.time_slot == time_slot), 
            None
        )

    @staticmethod
    def _canonicalize_downtime(code: Optional[str]) -> Optional[str]:
        """Map various downtime code spellings to canonical schema literals."""
        if code is None:
            return None
        mapping = {
            "m/c bd": "M/C BD",
            "tool bd": "Tool BD",
            "power failure": "Power failure",
            "quality issue": "Quality issue",
            "material shortage": "Material shortage",
            "mc/tool maintenance": "MC/Tool Maintenance",
            "rm loading": "RM Loading",
            "new operator": "New Operator",
            "operator on leave / permission": "Operator on leave / Permission",
            "setting": "Setting",
            "no manpower": "No manpower",
            "trial": "Trial",
            "startup": "Startup",
            "mold change": "Mold change",
            "molding change": "Mold change",
            "other": "Other",
        }
        norm = str(code).strip().lower()
        return mapping.get(norm, "Other")
    
    @staticmethod
    def _update_existing_entry(
        entry: HourlyProductionEntry,
        incoming: HourlyProductionEntryInput,
        calculated_downtime: float,
        production_ts: datetime,
        submission_ts: datetime,
        shift_info: Dict[str, Any],
        status: str = "SUBMITTED"
    ) -> None:
        """Update an existing entry with new data."""
        entry.plan_qty = incoming.plan_qty
        entry.actual_qty = incoming.actual_qty
        entry.ok_qty = incoming.ok_qty
        entry.rejected_qty = incoming.rejected_qty
        entry.rejection_reason = incoming.rejection_reason
        entry.downtime_code = incoming.downtime_code
        entry.downtime_from = incoming.downtime_from
        entry.downtime_to = incoming.downtime_to
        entry.downtime_minutes = calculated_downtime
        entry.lumps_kgs = incoming.lumps_kgs
        entry.submission_timestamp = submission_ts
        entry.shift_name = shift_info["name"]
        # Status is passed in, but typically SUBMITTED after passing gate
        entry.status = status
        
    @staticmethod
    def _create_new_entry(
        incoming: HourlyProductionEntryInput,
        calculated_downtime: float,
        production_ts: datetime,
        submission_ts: datetime,
        shift_info: Dict[str, Any],
        status: str = "SUBMITTED"
    ) -> HourlyProductionEntry:
        """Create a new entry from input data."""
        return HourlyProductionEntry(
            time_slot=incoming.time_slot,
            plan_qty=incoming.plan_qty,
            actual_qty=incoming.actual_qty,
            ok_qty=incoming.ok_qty,
            rejected_qty=incoming.rejected_qty,
            rejection_reason=incoming.rejection_reason,
            downtime_code=incoming.downtime_code,
            downtime_from=incoming.downtime_from,
            downtime_to=incoming.downtime_to,
            downtime_minutes=calculated_downtime,
            lumps_kgs=incoming.lumps_kgs,
            production_timestamp=production_ts,
            submission_timestamp=submission_ts,
            shift_name=shift_info["name"],
            shift_definition_id=shift_info.get("setting_id"),
            status=status
        )

    # -------------------------
    # Document Initialization with Status Gate
    # -------------------------

    @staticmethod
    async def initialize_document(
        payload: InitializeDocumentRequest
    ) -> HourlyProductionDocument:
        """Initialize a new document with automatic document_status determination."""
        # Fixed document number used for all initialized documents
        fixed_doc_no = "RI/PRD/R/70A"

        # Note: fixed `doc_no` is allowed to repeat; no uniqueness check performed

        # Determine document status based on age
        now = datetime.now(HourlyProductionService.TIMEZONE)
        doc_status, age_info = await determine_document_status(payload.date, now)
        
        # If BLOCKED, raise error immediately
        if doc_status == "BLOCKED":
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot initialize document: {age_info['message']}. "
                       f"Document age: {age_info['age_days']} days "
                       f"(maximum allowed: {age_info['max_age_days']} days)"
            )

        # Create document with determined status and fixed doc number
        doc = HourlyProductionDocument(
            date=payload.date,
            doc_no=fixed_doc_no,
            document_status=doc_status,
            side=payload.side,
            part_number=payload.part_number,
            part_description=payload.part_description,
            operator_name=payload.operator_name,
            customer_name=payload.customer_name,
            no_of_cavity=payload.no_of_cavity,
            cycle_time=payload.cycle_time,
            part_weight=payload.part_weight,
            runner_weight=payload.runner_weight,
            # REMOVED: no_of_runner=payload.no_of_runner,
            rm_mb=payload.rm_mb,
            lot_no=payload.lot_no,
            lot_no_production=payload.lot_no_production,
            entries=[],
            totals=DocumentTotals(),
        )
        
        try:
            await doc.insert()
        except Exception as e:
            logger.error(f"Failed to insert document {fixed_doc_no}: {e}")
            raise HTTPException(
                status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create document. Please try again."
            )

        logger.info(
            f"Document initialized: {fixed_doc_no} for date {payload.date}. "
            f"Status: {doc_status}. Age: {age_info['age_days']} days. "
            f"Side: {payload.side}"
        )

        return doc

    # -------------------------
    # Get Pending Documents (Admin Inbox)
    # -------------------------

    @staticmethod
    async def get_pending_documents(current_user: Dict[str, Any]) -> List[HourlyProductionDocument]:
        """
        Retrieve all documents currently in PENDING_APPROVAL status.
        
        Authorization: Restricted to 'Admin' only.
        
        Returns:
            List of documents sorted by date (newest first).
        """
        # Authorization: Only Admins can see the pending list
        if not HourlyProductionService._check_user_has_role(current_user, "Admin"):
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                detail="Only Admin users can view pending approval documents."
            )
            
        # Query for documents with status PENDING_APPROVAL
        # Sort by date descending (newest pending issues first)
        docs = await HourlyProductionDocument.find(
            HourlyProductionDocument.document_status == "PENDING_APPROVAL"
        ).sort(
            [(HourlyProductionDocument.date, DESCENDING)]
        ).to_list()
        
        # Normalize operator_name and downtime_code for response validation
        for doc in docs:
            try:
                if isinstance(doc.operator_name, str):
                    doc.operator_name = [doc.operator_name]
                elif doc.operator_name is None:
                    doc.operator_name = []
            except Exception:
                doc.operator_name = []

            for e in doc.entries:
                try:
                    e.downtime_code = HourlyProductionService._canonicalize_downtime(e.downtime_code)
                except Exception:
                    e.downtime_code = "Other"

            try:
                doc._id = str(doc.id)
            except Exception:
                doc._id = None

        logger.info(
            f"Admin {current_user.emp_id} retrieved {len(docs)} pending documents."
        )

        return docs

    # -------------------------
    # Submit Hourly Data (WITH STATUS GATE & TRANSACTION SAFETY)
    # -------------------------

    @staticmethod
    async def submit_hourly_data(
        payload: SubmitHourlyDataRequest, 
        current_user: Dict[str, Any]
    ) -> HourlyProductionDocument:
        """
        Submit hourly entries - ONLY if document_status is OPEN or APPROVED.
        """
        # Fetch by MongoDB _id only
        try:
            doc = await HourlyProductionDocument.get(payload.document_id)
        except Exception:
            try:
                doc = await HourlyProductionDocument.find_one({"_id": payload.document_id})
            except Exception:
                doc = None

        if doc is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Target document not found. Provide document_id (_id)")
        
        # Check if finalized
        if doc.is_finalized:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                detail=f"Document '{doc.doc_no}' is finalized and locked"
            )

        # ===== STATUS GATE =====
        if doc.document_status not in ["OPEN", "APPROVED"]:
            if doc.document_status == "PENDING_APPROVAL":
                raise HTTPException(
                    status.HTTP_409_CONFLICT,
                    detail="Document requires admin approval before data entry. "
                           "Please contact your supervisor to review and approve this document."
                )
            elif doc.document_status == "BLOCKED":
                raise HTTPException(
                    status.HTTP_409_CONFLICT,
                    detail="Document is blocked. Cannot submit entries to documents older than 7 days."
                )
            else:
                raise HTTPException(
                    status.HTTP_409_CONFLICT,
                    detail=f"Cannot submit entries. Document status: {doc.document_status}"
                )
        # =======================

        now = datetime.now(HourlyProductionService.TIMEZONE)
        
        # ===== PHASE 1: VALIDATE ALL ENTRIES (No modifications yet) =====
        entries_to_process = []
        
        for incoming in payload.entries:
            try:
                # Calculate timestamps
                production_ts = calculate_production_timestamp(doc.date, incoming.time_slot)
                submission_ts = now
                
                # Get shift info
                shift_info = await get_active_shift_info(production_ts)

                # Calculate downtime
                calculated_downtime = HourlyProductionCalculator.calculate_downtime_minutes(
                    incoming.downtime_from, 
                    incoming.downtime_to
                )
                
                # Check if entry exists and is editable
                existing_entry = HourlyProductionService._find_entry(doc, incoming.time_slot)
                if existing_entry and existing_entry.status == "FINAL":
                    raise HTTPException(
                        status.HTTP_400_BAD_REQUEST,
                        detail=f"Entry for time slot {incoming.time_slot} is finalized and cannot be edited"
                    )
                
                # Store validated data for processing
                entries_to_process.append({
                    'incoming': incoming,
                    'calculated_downtime': calculated_downtime,
                    'production_ts': production_ts,
                    'submission_ts': submission_ts,
                    'shift_info': shift_info,
                    'existing_entry': existing_entry
                })
                
                logger.debug(f"Validated entry: {incoming.time_slot} for document {doc.doc_no}")

            except HTTPException:
                raise
            except Exception as e:
                logger.error(f"Validation error for entry {incoming.time_slot}: {e}")
                raise HTTPException(
                    status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid entry data for time slot {incoming.time_slot}: {str(e)}"
                )
        
        # ===== PHASE 2: APPLY ALL CHANGES (Atomic) =====
        try:
            for entry_data in entries_to_process:
                if entry_data['existing_entry']:
                    # Update existing entry
                    HourlyProductionService._update_existing_entry(
                        entry_data['existing_entry'],
                        entry_data['incoming'],
                        entry_data['calculated_downtime'],
                        entry_data['production_ts'],
                        entry_data['submission_ts'],
                        entry_data['shift_info']
                    )
                else:
                    # Create new entry
                    new_entry = HourlyProductionService._create_new_entry(
                        entry_data['incoming'],
                        entry_data['calculated_downtime'],
                        entry_data['production_ts'],
                        entry_data['submission_ts'],
                        entry_data['shift_info']
                    )
                    doc.entries.append(new_entry)
            
            # Recalculate totals
            HourlyProductionCalculator.recalculate_totals(doc)
            
            # Save document
            await doc.save()
            
            logger.info(
                f"Successfully submitted {len(entries_to_process)} entries "
                f"for document {doc.doc_no} by user {current_user.emp_id}"
            )
            
        except Exception as e:
            logger.error(f"Failed to save document {doc.doc_no}: {e}")
            raise HTTPException(
                status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to save entries. Please try again."
            )
        
        try:
            await FGStockService.update_from_hourly_production(
                doc, 
                current_user.emp_id
            )
            logger.info(f"FG Stock updated for document {doc.doc_no}")
        except Exception as e:
            # Don't fail hourly submission if FG stock update fails
            logger.error(f"FG Stock update failed for {doc.doc_no}: {e}", exc_info=True)
            # Could send alert to admin here
        # Normalize operator_name and downtime_code for response validation
        try:
            if isinstance(doc.operator_name, str):
                doc.operator_name = [doc.operator_name]
            elif doc.operator_name is None:
                doc.operator_name = []
        except Exception:
            doc.operator_name = []

        for e in doc.entries:
            try:
                e.downtime_code = HourlyProductionService._canonicalize_downtime(e.downtime_code)
            except Exception:
                e.downtime_code = "Other"

        return doc

    # -------------------------
    # UNIFIED: Review Document Status (Approve/Reject)
    # -------------------------

    @staticmethod
    async def review_document_status(
        payload: ReviewDocumentStatusRequest, 
        current_user: Dict[str, Any]
    ) -> HourlyProductionDocument:
        """Unified endpoint for approving or rejecting a document's status."""
        # Authorization check
        if not HourlyProductionService._check_user_has_role(current_user, "Admin"):
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                detail="Only Admin users can approve or reject document status"
            )
        
        # Fetch document (by _id or doc_no fallback)
        doc = None
        if getattr(payload, "document_id", None):
            try:
                doc = await HourlyProductionDocument.get(payload.document_id)
            except Exception:
                try:
                    doc = await HourlyProductionDocument.find_one({"_id": payload.document_id})
                except Exception:
                    doc = None
        if doc is None and getattr(payload, "doc_no", None):
            doc = await HourlyProductionService._get_document_or_404(payload.doc_no)
        if doc is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Target document not found")

        # Validate current status
        if doc.document_status != "PENDING_APPROVAL":
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Only documents with PENDING_APPROVAL status can be reviewed. "
                    f"Current status: {doc.document_status}"
                )
            )

        # Process action
        if payload.action == "APPROVE":
            doc.document_status = "APPROVED"
            action_label = "APPROVED"
            logger.info(
                f"Document {doc.doc_no} approved by {current_user.full_name} "
                f"({current_user.emp_id})"
            )
            
        elif payload.action == "REJECT":
            doc.document_status = "BLOCKED"
            action_label = "REJECTED"
            logger.info(
                f"Document {doc.doc_no} rejected by {current_user.full_name} "
                f"({current_user.emp_id})"
            )
            
        else:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid action: {payload.action}. Must be APPROVE or REJECT"
            )

        # Record approval/rejection
        doc.document_approval = DocumentApprovalRecord(
            approved_by=current_user.emp_id,
            approved_by_name=current_user.full_name,
            action=action_label,
            remarks=payload.remarks or f"Document {action_label.lower()} by admin"
        )

        try:
            await doc.save()
        except Exception as e:
            logger.error(f"Failed to save document review for {doc.doc_no}: {e}")
            raise HTTPException(
                status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to save document review. Please try again."
            )
        
        return doc

    # -------------------------
    # Sign Document
    # -------------------------

    @staticmethod
    async def sign_document(
        payload: SignDocumentRequest, 
        current_user: Dict[str, Any]
    ) -> HourlyProductionDocument:
        """Add digital signature to document."""
        doc = None
        if getattr(payload, "document_id", None):
            try:
                doc = await HourlyProductionDocument.get(payload.document_id)
            except Exception:
                try:
                    doc = await HourlyProductionDocument.find_one({"_id": payload.document_id})
                except Exception:
                    doc = None
        if doc is None and getattr(payload, "doc_no", None):
            doc = await HourlyProductionService._get_editable_document(payload.doc_no)
        if doc is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Target document not found")

        # Authorization check based on signature type
        if payload.signature_type == "OPERATOR":
            if not HourlyProductionService._check_user_has_role(current_user, "Operator"):
                raise HTTPException(
                    status.HTTP_403_FORBIDDEN,
                    detail="Only users with 'Operator' role can sign as OPERATOR"
                )

        elif payload.signature_type == "PRODUCTION_HEAD":
            if not HourlyProductionService._check_user_has_role(current_user, "Production Head"):
                raise HTTPException(
                    status.HTTP_403_FORBIDDEN,
                    detail="Only users with 'Production Head' role can sign as PRODUCTION_HEAD"
                )
        else:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid signature type: {payload.signature_type}"
            )

        # Create signature record
        user_id = current_user.emp_id
        user_name = current_user.full_name
        
        if not user_id or not user_name:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                detail="User information incomplete. Cannot create signature."
            )
        
        record = VerificationRecord(
            user_id=user_id,
            user_name=user_name
        )

        # Add signature (check for duplicates)
        if payload.signature_type == "OPERATOR":
            if any(sig.user_id == user_id for sig in doc.operator_signatures):
                raise HTTPException(
                    status.HTTP_400_BAD_REQUEST,
                    detail="User has already signed as OPERATOR"
                )
            doc.operator_signatures.append(record)

        elif payload.signature_type == "PRODUCTION_HEAD":
            if any(sig.user_id == user_id for sig in doc.production_head_signatures):
                raise HTTPException(
                    status.HTTP_400_BAD_REQUEST,
                    detail="User has already signed as PRODUCTION_HEAD"
                )
            doc.production_head_signatures.append(record)

        try:
            await doc.save()
        except Exception as e:
            logger.error(f"Failed to save signature for {doc.doc_no}: {e}")
            raise HTTPException(
                status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to save signature. Please try again."
            )
        
        logger.info(
            f"Document {doc.doc_no} signed by {user_name} ({user_id}) "
            f"as {payload.signature_type}"
        )

        return doc

    # -------------------------
    # Finalize Document
    # -------------------------

    @staticmethod
    async def finalize_document(
        payload: FinalizeDocumentRequest, 
        current_user: Any
    ) -> HourlyProductionDocument:
        """
        Finalize document to prevent further edits.
        
        Authorization: Restricted to 'Admin' or 'Production Head' only.
        """
        # 1. Fetch Document (prefer document_id)
        doc = None
        if getattr(payload, "document_id", None):
            try:
                doc = await HourlyProductionDocument.get(payload.document_id)
            except Exception:
                try:
                    doc = await HourlyProductionDocument.find_one({"_id": payload.document_id})
                except Exception:
                    doc = None
        if doc is None and getattr(payload, "doc_no", None):
            doc = await HourlyProductionService._get_document_or_404(payload.doc_no)
        if doc is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Target document not found")
        
        # ============================================================
        # 2. AUTHORIZATION GATE (Admin or Production Head only)

        user_role = getattr(current_user, 'role', None)
        user_role2 = getattr(current_user, 'role2', None)
        
        allowed_roles = ["Admin", "Production Head"]
        
        is_authorized = user_role in allowed_roles or user_role2 in allowed_roles
        
        if not is_authorized:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                detail="Only users with 'Admin' or 'Production Head' role can finalize documents."
            )
        # ============================================================

        # 3. Check if already finalized
        if doc.is_finalized:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                detail=f"Document '{doc.doc_no}' is already finalized"
            )

        # 4. Change all entries to FINAL
        finalized_count = 0
        for entry in doc.entries:
            if entry.status in ["DRAFT", "SUBMITTED"]:
                entry.status = "FINAL"
                finalized_count += 1

        doc.is_finalized = True
        doc.finalized_at = datetime.now(HourlyProductionService.TIMEZONE)
        
        try:
            await doc.save()
        except Exception as e:
            logger.error(f"Failed to finalize document {doc.doc_no}: {e}")
            raise HTTPException(
                status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to finalize document. Please try again."
            )
        
        logger.info(
            f"Document {doc.doc_no} finalized by {current_user.full_name} "
            f"({current_user.emp_id}). {finalized_count} entries marked as FINAL."
        )
        
        return doc

    # -------------------------
    # Update Document Details
    # -------------------------

    @staticmethod
    async def update_document_details(
        payload: UpdateDocumentDetailsRequest
    ) -> HourlyProductionDocument:
        """Update document-level details (Manual Totals)."""
        doc = None
        if getattr(payload, "document_id", None):
            try:
                doc = await HourlyProductionDocument.get(payload.document_id)
            except Exception:
                try:
                    doc = await HourlyProductionDocument.find_one({"_id": payload.document_id})
                except Exception:
                    doc = None
        if doc is None and getattr(payload, "doc_no", None):
            doc = await HourlyProductionService._get_document_or_404(payload.doc_no)
        if doc is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Target document not found")

        # Track what was updated
        updates = []
        
        # Update Manual Totals
        if payload.total_lumps_kgs is not None:
            doc.totals.total_lumps_kgs = payload.total_lumps_kgs
            updates.append(f"total_lumps_kgs={payload.total_lumps_kgs}")
            logger.info(
                f"Updated total lumps for document {doc.doc_no} to {payload.total_lumps_kgs} kg"
            )

        if payload.total_runner_weight_kgs is not None:
            doc.totals.total_runner_weight_kgs = payload.total_runner_weight_kgs
            updates.append(f"total_runner_weight_kgs={payload.total_runner_weight_kgs}")
            logger.info(
                f"Updated total runner weight for document {doc.doc_no} to {payload.total_runner_weight_kgs} kg"
            )

        if not updates:
            logger.info(f"No fields to update for document {doc.doc_no}")
            return doc

        try:
            await doc.save()
        except Exception as e:
            logger.error(f"Failed to update document {doc.doc_no}: {e}")
            raise HTTPException(
                status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update document. Please try again."
            )
        
        logger.info(f"Updated document {doc.doc_no}: {', '.join(updates)}")
        
        return doc

    # -------------------------
    # Get Documents
    # -------------------------

    @staticmethod
    async def get_documents(
        date: str,
        shift_name: Optional[str] = None,
    ) -> List[HourlyProductionDocument]:
        """Retrieve production documents with optional filtering."""
        # Validate date format
        try:
            datetime.strptime(date, "%Y-%m-%d")
        except ValueError:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid date format: {date}. Expected YYYY-MM-DD"
            )
        
        # Build query (only date filter supported)
        query = {"date": date}
        
        try:
            docs = await HourlyProductionDocument.find(query).to_list()
        except Exception as e:
            logger.error(f"Database error while fetching documents: {e}")
            raise HTTPException(
                status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to retrieve documents. Please try again."
            )
        
        # Filter entries if needed
        # Normalize legacy operator_name (string -> list) and sanitize downtime_code values
        allowed_downtimes = {
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
        }

        for doc in docs:
            # operator_name may be stored as a single string in older records
            try:
                if isinstance(doc.operator_name, str):
                    doc.operator_name = [doc.operator_name]
                elif doc.operator_name is None:
                    doc.operator_name = []
            except Exception:
                doc.operator_name = []

            # sanitize downtime codes in entries to ensure response schema accepts them
            for e in doc.entries:
                try:
                    e.downtime_code = HourlyProductionService._canonicalize_downtime(e.downtime_code)
                except Exception:
                    e.downtime_code = "Other"

            # expose MongoDB id as `_id` string for API consumers
            try:
                doc._id = str(doc.id)
            except Exception:
                doc._id = None

        if shift_name:
            for doc in docs:
                filtered = [e for e in doc.entries if e.shift_name == shift_name]
                doc.entries = filtered
        
        logger.info(
            f"Retrieved {len(docs)} documents for date {date} "
            f"(shift_name={shift_name})"
        )

        # Convert Beanie documents to plain dicts and inject `_id` for API
        results = []
        for doc in docs:
            try:
                data = doc.model_dump() if hasattr(doc, "model_dump") else doc.dict()
            except Exception:
                # fallback: attempt to build minimal dict
                data = {
                    "date": getattr(doc, "date", None),
                    "doc_no": getattr(doc, "doc_no", None),
                    "created_at": getattr(doc, "created_at", None),
                }

            data["_id"] = str(getattr(doc, "id", getattr(doc, "_id", None)))
            results.append(data)

        return results