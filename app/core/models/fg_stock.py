from app.shared.timezone import get_ist_now
from datetime import datetime
from typing import Dict, Optional
from beanie import Document
from pydantic import BaseModel, Field
from pymongo import ASCENDING, DESCENDING


class BinInventory(BaseModel):
    """Bin tracking for RABS and IJL"""
    rabs_bins: int = Field(default=0, ge=0, description="Bins in RABS warehouse")
    ijl_bins: int = Field(default=0, ge=0, description="Bins ready for IJL dispatch")


class StockTransaction(BaseModel):
    """Individual stock transaction for audit trail"""
    timestamp: datetime = Field(default_factory=get_ist_now)
    transaction_type: str  # "PRODUCTION", "DISPATCH", "INSPECTION_QTY", "BIN_TRANSFER"
    quantity_change: int
    bins_change: Optional[Dict[str, int]] = None
    user_id: Optional[str] = None
    remarks: Optional[str] = None
    reference_doc_no: Optional[str] = None  # Link to HourlyProductionDocument


class FGStockDocument(Document):
    """Daily FG Stock tracking per part variant (LH/RH)"""
    
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
    
    # Stock Quantities
    opening_stock: int = Field(default=0, ge=0)
    production_added: int = Field(default=0, ge=0)
    inspection_qty: int = Field(default=0, ge=0)
    dispatched: int = Field(default=0, ge=0)
    closing_stock: int = Field(default=0)
    
    # Bin Tracking
    bins_available: BinInventory = Field(default_factory=BinInventory)
    bin_size: Optional[int] = None  # Cached from PartConfiguration
    
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
        """Recalculate closing stock from components"""
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
        reference_doc_no: Optional[str] = None,
        bins_change: Optional[Dict[str, int]] = None
    ):
        """Add transaction to audit trail"""
        self.transactions.append(StockTransaction(
            transaction_type=transaction_type,
            quantity_change=quantity_change,
            bins_change=bins_change,
            user_id=user_id,
            remarks=remarks,
            reference_doc_no=reference_doc_no
        ))