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
    "job id": "id",
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
    # Job-specific headers
    "status": "last_run_status",
    "trigger": "triggers",
    "triggers": "triggers",
    "schedule": "schedule",
    "steps": "job_steps",
    "runs": "run_count",
    # User-specific headers
    "username": "username",
    "conn": "conn",
    "conn.": "conn",
    "connection": "conn",
    "relation": "relation",
    "relations": "relation",
    "p": "public",
    "public": "public",
    "groups": "groups",
    "social": "social",
    "bio": "bio",
    "biography": "bio",
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


def get_triggers_display_value(triggers: List[str]) -> str:
    """
    Convert the triggers list to display format for filtering.

    Example: ["mail", "api"] -> "M - A -"
    """
    tset = set(t.lower() for t in triggers) if triggers else set()
    mail = "M" if "mail" in tset else "-"
    sched = "S" if "schedule" in tset else "-"
    api = "A" if "api" in tset else "-"
    commit = "C" if "commit" in tset else "-"
    return f"{mail} {sched} {api} {commit}"


def get_conn_display_value(item: Dict[str, Any]) -> str:
    """
    Convert connection fields to display format for filtering.

    Example: connected=True, follower=False, following=True -> "C - F -"
    """
    connected = "C" if item.get("connected") else "-"
    follower = "F" if item.get("follower") else "-"
    following = "F" if item.get("following") else "-"
    ignoring = "I" if item.get("ignoring") else "-"
    return f"{connected} {follower} {following} {ignoring}"


def get_public_display_value(item: Dict[str, Any]) -> str:
    """
    Convert public field to display format for filtering.

    Example: public=True -> "P", public=False -> "-"
    """
    return "P" if item.get("public") else "-"


def get_filter_value(item: Dict[str, Any], column: str) -> str:
    """
    Get the filterable value for a column from an item.
    Handles special columns like 'shared', 'triggers', 'conn', 'relation', and 'public'.
    """
    value = item.get(column, "")

    if column == "shared" and isinstance(value, list):
        return get_shared_display_value(value)

    if column == "triggers" and isinstance(value, list):
        return get_triggers_display_value(value)

    if column == "conn":
        return get_conn_display_value(item)

    if column == "relation":
        return get_conn_display_value(item)

    if column == "public":
        return get_public_display_value(item)

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
        # Special handling for triggers column: check exact flag combination
        if filter_obj.column == "triggers":
            # For triggers, exact match means "exactly these flags and no others"
            # e.g., trigger=S matches "- S - -" (only schedule)
            # e.g., trigger=MSA matches "M S A -" (mail + schedule + api, no commit)
            pattern_upper = filter_obj.pattern.upper()
            # Build expected display value from pattern
            mail = "M" if "M" in pattern_upper else "-"
            sched = "S" if "S" in pattern_upper else "-"
            api = "A" if "A" in pattern_upper else "-"
            commit = "C" if "C" in pattern_upper else "-"
            expected = f"{mail} {sched} {api} {commit}"
            return value == expected
        # Special handling for conn/relation column: check exact flag combination
        if filter_obj.column in ("conn", "relation"):
            # For conn/relation, exact match means "exactly these flags and no others"
            # e.g., conn=C matches "C - - -" (only connected)
            # e.g., conn=CF matches "C F - -" (connected + follower, no following)
            # e.g., relation=I matches "- - - I" (only ignoring)
            pattern_upper = filter_obj.pattern.upper()
            # Build expected display value from pattern
            # Note: F appears twice (follower and following), use position to distinguish
            connected = "C" if "C" in pattern_upper else "-"
            # Count F's: first F = follower, second F = following
            f_count = pattern_upper.count("F")
            follower = "F" if f_count >= 1 else "-"
            following = "F" if f_count >= 2 else "-"
            ignoring = "I" if "I" in pattern_upper else "-"
            expected = f"{connected} {follower} {following} {ignoring}"
            return value == expected
        # Special handling for public column: check exact match
        if filter_obj.column == "public":
            # For public, exact match: p=P matches public users, p= or p=- matches non-public
            pattern_upper = filter_obj.pattern.upper()
            if pattern_upper == "P":
                return value == "P"
            elif pattern_upper in ("", "-"):
                return value == "-"
            return value.lower() == filter_obj.pattern.lower()
        # Case-insensitive exact match for other columns
        return value.lower() == filter_obj.pattern.lower()

    elif filter_obj.mode == FilterMode.REGEX:
        # Special handling for shared column: check if flags are present (subset match)
        if filter_obj.column == "shared":
            # For shared regex, check if all specified flags are present
            # e.g., shared~P matches any with public (could have others)
            # e.g., shared~P@ matches any with public AND user group
            pattern_upper = filter_obj.pattern.upper()
            if all(c in "PC@+" for c in pattern_upper):
                # Pattern is just flags, do subset match
                if "P" in pattern_upper and "P" not in value:
                    return False
                if "C" in pattern_upper and "C" not in value:
                    return False
                if "@" in pattern_upper and "@" not in value:
                    return False
                if "+" in pattern_upper and value.count("+") == 0:
                    return False
                return True
        # Special handling for triggers column: check if flags are present (subset match)
        if filter_obj.column == "triggers":
            # For triggers regex, check if all specified flags are present
            # e.g., trigger~M matches any with mail (could have others)
            # e.g., trigger~SA matches any with schedule AND api
            pattern_upper = filter_obj.pattern.upper()
            if all(c in "MSAC" for c in pattern_upper):
                # Pattern is just flags, do subset match
                if "M" in pattern_upper and "M" not in value:
                    return False
                if "S" in pattern_upper and "S" not in value:
                    return False
                if "A" in pattern_upper and "A" not in value:
                    return False
                if "C" in pattern_upper and "C" not in value:
                    return False
                return True
        # Special handling for conn/relation column: check if flags are present (subset match)
        if filter_obj.column in ("conn", "relation"):
            # For conn/relation regex, check if all specified flags are present
            # e.g., conn~C matches any connected user (could have others)
            # e.g., conn~CF matches any connected AND follower
            # e.g., relation~I matches any user being ignored
            pattern_upper = filter_obj.pattern.upper()
            if all(c in "CFI" for c in pattern_upper):
                # Pattern is just flags, do subset match
                if "C" in pattern_upper and "C" not in value:
                    return False
                # F means at least one F (follower or following) is present
                if "F" in pattern_upper and "F" not in value:
                    return False
                if "I" in pattern_upper and "I" not in value:
                    return False
                return True
        # Special handling for public column: check if flag is present
        if filter_obj.column == "public":
            # For public regex, p~P matches public users
            pattern_upper = filter_obj.pattern.upper()
            if pattern_upper == "P":
                return "P" in value
            # Fall through to normal regex matching
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
