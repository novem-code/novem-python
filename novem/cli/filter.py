"""
Column-based filtering for CLI list views.

Supports:
- column=value  : Exact match (case insensitive)
- column~regex  : Regex match (case insensitive)
- value         : Legacy mode (regex against id, name, type)
"""

import re
import sys
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional


class FilterMode(Enum):
    EXACT = "exact"  # = operator
    REGEX = "regex"  # ~ operator
    LEGACY = "legacy"  # No operator (backward compatible)


@dataclass
class ColumnFilter:
    column: Optional[str]  # None for legacy mode
    pattern: str
    mode: FilterMode


# Maps header names (lowercase) to column keys
HEADER_TO_KEY: Dict[str, str] = {
    # Headers for different vis types
    "plot id": "id",
    "grid id": "id",
    "mail id": "id",
    # Common headers
    "type": "type",
    "shared": "shared",
    "name": "name",
    "url": "uri",
    "uri": "uri",
    "updated": "updated",
    "summary": "summary",
    "fav": "fav",
    # Direct key access
    "id": "id",
}


def parse_filter(filter_str: str) -> ColumnFilter:
    """
    Parse a filter string into a ColumnFilter object.

    Syntax:
    - column=value  -> exact match (case insensitive)
    - column~regex  -> regex match (case insensitive)
    - value         -> legacy mode (matches id, name, type)

    Handles quoted column names: "Plot ID"=value
    """
    # Try to match column-based filter syntax
    # Pattern: optional quotes around column name, then = or ~, then value
    match = re.match(r'^(?:"([^"]+)"|([^=~]+))([=~])(.*)$', filter_str)

    if match:
        # Column-based filter
        column_quoted = match.group(1)  # From "quoted"
        column_unquoted = match.group(2)  # From unquoted
        operator = match.group(3)
        value = match.group(4)

        column = (column_quoted or column_unquoted).strip().lower()

        # Resolve column name to key
        if column not in HEADER_TO_KEY:
            valid_cols = sorted(set(HEADER_TO_KEY.values()))
            raise ValueError(f"Unknown column: {column}. Valid columns: {', '.join(valid_cols)}")

        column_key = HEADER_TO_KEY[column]
        mode = FilterMode.EXACT if operator == "=" else FilterMode.REGEX

        return ColumnFilter(column=column_key, pattern=value, mode=mode)
    else:
        # Legacy mode: no column specified
        return ColumnFilter(column=None, pattern=filter_str, mode=FilterMode.LEGACY)


def get_shared_display_value(shared: List[str]) -> str:
    """
    Convert the shared list to display format for filtering.

    Example: ["public", "@", "+"] -> "P - @ +"
    """
    sl = [x[0] if x else "" for x in shared]
    pub = "P" if "p" in sl else "-"
    chat = "C" if "c" in sl else "-"
    ug = "@" if "@" in sl else "-"
    og = "+" if "+" in sl else "-"
    return f"{pub} {chat} {ug} {og}"


def get_filter_value(item: Dict[str, Any], column: str) -> str:
    """
    Get the filterable value for a column from an item.
    Handles special columns like 'shared'.
    """
    value = item.get(column, "")

    if column == "shared" and isinstance(value, list):
        return get_shared_display_value(value)

    if value is None:
        return ""

    return str(value)


def matches_filter(item: Dict[str, Any], filter_obj: ColumnFilter) -> bool:
    """
    Check if an item matches a single filter.
    """
    if filter_obj.mode == FilterMode.LEGACY:
        # Legacy behavior: match against id, name, type
        pattern = filter_obj.pattern
        if pattern and pattern[0] != "^":
            pattern = f".*{pattern}"
        if pattern and pattern[-1] != "$":
            pattern = f"{pattern}.*"

        regex = re.compile(pattern, re.I)
        return bool(
            regex.match(item.get("id", "") or "")
            or regex.match(item.get("name", "") or "")
            or regex.match(item.get("type", "") or "")
        )

    # Get the value to filter against
    value = get_filter_value(item, filter_obj.column or "")

    if filter_obj.mode == FilterMode.EXACT:
        # Special handling for shared column: check exact flag combination
        if filter_obj.column == "shared":
            # For shared, exact match means "exactly these flags and no others"
            # e.g., shared=P matches "P - - -" (only public)
            # e.g., shared=P@ matches "P - @ -" (public + user group, no chat or org)
            pattern_upper = filter_obj.pattern.upper()
            # Build expected display value from pattern
            pub = "P" if "P" in pattern_upper else "-"
            chat = "C" if "C" in pattern_upper else "-"
            ug = "@" if "@" in pattern_upper else "-"
            og = "+" if "+" in pattern_upper else "-"
            expected = f"{pub} {chat} {ug} {og}"
            return value == expected
        # Case-insensitive exact match for other columns
        return value.lower() == filter_obj.pattern.lower()

    elif filter_obj.mode == FilterMode.REGEX:
        # Case-insensitive regex match
        try:
            regex = re.compile(filter_obj.pattern, re.I)
            return bool(regex.search(value))
        except re.error:
            # Invalid regex, treat as literal substring
            return filter_obj.pattern.lower() in value.lower()

    return False


def apply_filters(items: List[Dict[str, Any]], filter_strs: Optional[List[str]]) -> List[Dict[str, Any]]:
    """
    Apply multiple filters to a list of items.
    Multiple filters use AND logic.

    Args:
        items: List of visualization items
        filter_strs: List of filter strings from -f arguments (may be None)

    Returns:
        Filtered list of items
    """
    if not filter_strs:
        return items

    # Parse all filters
    filters = []
    for fs in filter_strs:
        try:
            filters.append(parse_filter(fs))
        except ValueError as e:
            print(f"Filter error: {e}", file=sys.stderr)
            sys.exit(1)

    # Apply AND logic: item must match ALL filters
    return [item for item in items if all(matches_filter(item, f) for f in filters)]
