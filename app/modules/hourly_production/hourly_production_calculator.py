from datetime import datetime
from typing import TYPE_CHECKING
import logging

if TYPE_CHECKING:
    from app.core.models.production.hourly_production import HourlyProductionDocument

logger = logging.getLogger(__name__)


class HourlyProductionCalculator:
    """
    Calculator for hourly production metrics.
    
    Handles:
    - Downtime calculations
    - Weight calculations (OK, Rejected)
    - Document totals aggregation (Runner/Lumps are manual entry)
    """
    
    @staticmethod
    def calculate_downtime_minutes(
        start_str: str | None, 
        end_str: str | None
    ) -> float:
        """
        Calculate downtime in minutes from start and end times (HH:MM).
        
        Args:
            start_str: Start time in HH:MM format (e.g., "10:30")
            end_str: End time in HH:MM format (e.g., "11:45")
            
        Returns:
            float: Downtime in minutes (0.0 if invalid input)
            
        Examples:
            >>> calculate_downtime_minutes("10:00", "10:30")
            30.0
            >>> calculate_downtime_minutes("10:30", "10:00")
            0.0  # Negative time treated as 0
            >>> calculate_downtime_minutes(None, "10:00")
            0.0
        """
        if not start_str or not end_str:
            return 0.0
        
        try:
            fmt = "%H:%M"
            t_start = datetime.strptime(start_str.strip(), fmt)
            t_end = datetime.strptime(end_str.strip(), fmt)
            
            delta_seconds = (t_end - t_start).total_seconds()
            delta_minutes = delta_seconds / 60
            
            # Return 0 for negative durations (end before start)
            return max(delta_minutes, 0.0)
            
        except (ValueError, AttributeError) as e:
            logger.warning(
                f"Invalid downtime format: start='{start_str}', end='{end_str}'. "
                f"Error: {e}. Returning 0."
            )
            return 0.0

    @staticmethod
    def recalculate_totals(doc: 'HourlyProductionDocument') -> None:
        """
        Recalculate totals in the document using all hourly entries.
        
        Weight Calculations:
        - OK Weight = ok_qty × (part_weight_grams / 1000)
        - Rejected Weight = rejected_qty × (part_weight_grams / 1000)
        
        Manual Entries (Not calculated here):
        - Runner Weight (Updated via Update Document Details)
        - Lumps (Updated via Update Document Details)
        
        Args:
            doc: HourlyProductionDocument to recalculate
            
        Side Effects:
            Modifies doc.totals in place
            
        Raises:
            ValueError: If document has invalid weight configuration
        """
        from app.core.models.production.hourly_production import DocumentTotals
        
        # Validate document has required fields
        if not hasattr(doc, 'part_weight'):
            raise ValueError("Document missing part_weight field")
        
        if doc.part_weight < 0:
            raise ValueError(f"Invalid part_weight: {doc.part_weight}. Must be >= 0")
        
        # Initialize fresh totals
        totals = DocumentTotals()
        
        # Process each entry
        for idx, entry in enumerate(doc.entries):
            try:
                # Sum quantities
                totals.total_plan_qty += entry.plan_qty or 0
                totals.total_actual_qty += entry.actual_qty or 0
                totals.total_ok_qty += entry.ok_qty or 0
                totals.total_rejected_qty += entry.rejected_qty or 0
                totals.total_downtime_minutes += entry.downtime_minutes or 0.0

                
                # Weight calculations using single part_weight from document
                # Convert from grams to kilograms
                part_weight_kg = doc.part_weight / 1000.0
                
                # OK weight = OK quantity × part weight
                ok_weight = (entry.ok_qty or 0) * part_weight_kg
                totals.total_ok_weight_kgs += ok_weight
                
                # Rejected weight = Rejected quantity × part weight
                rejected_weight = (entry.rejected_qty or 0) * part_weight_kg
                totals.total_rejected_weight_kgs += rejected_weight
                
                
            except (AttributeError, TypeError, ZeroDivisionError) as e:
                logger.error(
                    f"Error calculating totals for entry {idx} in doc {doc.doc_no}: {e}. "
                    f"Entry: {entry}"
                )
                # Continue processing other entries
                continue
        
        # Round totals to 2 decimal places for cleaner display
        totals.total_downtime_minutes = round(totals.total_downtime_minutes, 2)
        totals.total_ok_weight_kgs = round(totals.total_ok_weight_kgs, 2)
        totals.total_rejected_weight_kgs = round(totals.total_rejected_weight_kgs, 2)
        
        
        # Update document totals
        doc.totals = totals
        
        logger.debug(
            f"Recalculated totals for doc {doc.doc_no}: "
            f"OK={totals.total_ok_qty}, Rejected={totals.total_rejected_qty}, "
            f"OK Weight={totals.total_ok_weight_kgs}kg"
        )