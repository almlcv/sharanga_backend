from app.shared.timezone import get_ist_now
from datetime import datetime
from typing import Optional
from beanie import Document
from pydantic import BaseModel, Field
from pymongo import ASCENDING, DESCENDING


class StockTransaction(BaseModel):
    """Individual stock transaction for audit trail"""
    timestamp: datetime = Field(default_factory=get_ist_now)
    transaction_type: str  # "PRODUCTION", "DISPATCH", "INSPECTION_QTY"
    quantity_change: int
    user_id: Optional[str] = None
    remarks: Optional[str] = None
    reference_doc_no: Optional[str] = None 


class FGStockDocument(Document):
    """
    Daily FG Stock tracking per part variant (LH/RH)
    
    SIMPLIFIED - NO BIN TRACKING
    Matches Excel structure exactly
    """
    
    # Primary Identity
    date: str = Field(..., description="YYYY-MM-DD")
    variant_name: str = Field(..., description="e.g., 'ALTROZ BRACKET-D LH'")
    part_number: str
    part_description: str  # Without LH/RH
    side: Optional[str] = None  # "LH" or "RH"; optional for single-sided parts
    
    # Date components for querying
    year: int
    month: int
    day: int
    
    # Stock Quantities (EXACTLY AS IN EXCEL)
    opening_stock: int = Field(default=0, ge=0, description="Opening stock for the day")
    production_added: int = Field(default=0, ge=0, description="Production added today")
    inspection_qty: int = Field(default=0, ge=0, description="Damaged/Rejected quantity")
    dispatched: int = Field(default=0, ge=0, description="Dispatched quantity")
    closing_stock: int = Field(default=0, description="Closing stock (can be negative in theory)")
    
    # Monthly Plan Reference
    monthly_schedule: Optional[int] = None
    daily_target: Optional[int] = None
    
    # Audit Trail
    transactions: list[StockTransaction] = Field(default_factory=list)
    
    # Metadata
    created_at: datetime = Field(default_factory=get_ist_now)
    updated_at: datetime = Field(default_factory=get_ist_now)
    last_synced_at: Optional[datetime] = None  # Last sync from hourly production
    
    class Settings:
        name = "fg_stock_daily"
        indexes = [
            [("date", ASCENDING), ("variant_name", ASCENDING)],
            [("year", ASCENDING), ("month", ASCENDING), ("variant_name", ASCENDING)],
            [("part_description", ASCENDING), ("date", DESCENDING)],
        ]
    
    def recalculate_closing_stock(self):
        """
        Recalculate closing stock from components
        FORMULA: Closing = Opening + Production - Inspection - Dispatch
        """
        self.closing_stock = (
            self.opening_stock + 
            self.production_added - 
            self.inspection_qty - 
            self.dispatched
        )
        self.updated_at = get_ist_now()
    
    def add_transaction(
        self, 
        transaction_type: str, 
        quantity_change: int,
        user_id: Optional[str] = None,
        remarks: Optional[str] = None,
        reference_doc_no: Optional[str] = None
    ):
        """Add transaction to audit trail"""
        self.transactions.append(StockTransaction(
            transaction_type=transaction_type,
            quantity_change=quantity_change,
            user_id=user_id,
            remarks=remarks,
            reference_doc_no=reference_doc_no
        ))