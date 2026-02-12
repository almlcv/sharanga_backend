"""
Utility functions for consistent variant name handling across the application.
"""

from typing import Tuple, Optional


def construct_variant_name(part_description: str, side: Optional[str]) -> str:
    """
    Construct a variant name from part description and side.
    
    Args:
        part_description: Base part description (e.g., "ALTROZ BRACKET-D")
        side: Optional side value ("LH", "RH", or None)
    
    Returns:
        Variant name string:
        - If side is None: returns part_description
        - If side is "LH" or "RH": returns "part_description side"
    
    Examples:
        >>> construct_variant_name("ALTROZ BRACKET-D", "LH")
        'ALTROZ BRACKET-D LH'
        >>> construct_variant_name("ALTROZ BRACKET-D", None)
        'ALTROZ BRACKET-D'
    """
    if side and side.strip():
        return f"{part_description} {side}"
    return part_description


def parse_variant_name(variant_name: str) -> Tuple[str, Optional[str]]:
    """
    Parse a variant name into part description and side.
    
    Args:
        variant_name: Full variant name (e.g., "ALTROZ BRACKET-D LH")
    
    Returns:
        Tuple of (part_description, side):
        - If variant ends with " LH" or " RH": returns (base_name, side)
        - Otherwise: returns (variant_name, None)
    
    Examples:
        >>> parse_variant_name("ALTROZ BRACKET-D LH")
        ('ALTROZ BRACKET-D', 'LH')
        >>> parse_variant_name("ALTROZ BRACKET-D")
        ('ALTROZ BRACKET-D', None)
    """
    parts = variant_name.rsplit(" ", 1)
    if len(parts) == 2 and parts[1] in ("LH", "RH"):
        return parts[0], parts[1]
    return variant_name, None


def validate_side(side: Optional[str]) -> Optional[str]:
    """
    Validate and normalize a side value.
    
    Args:
        side: Side value to validate
    
    Returns:
        Normalized side value (None, "LH", or "RH")
    
    Raises:
        ValueError: If side is not None, "LH", or "RH"
    """
    if side is None:
        return None
    
    side_str = str(side).strip().upper()
    
    if side_str == "":
        return None
    
    if side_str not in ("LH", "RH"):
        raise ValueError(f"Invalid side value: {side}. Must be None, 'LH', or 'RH'")
    
    return side_str
