from datetime import datetime, timezone
from typing import Any

from novem.utils import ansi_escape, colors, parse_api_datetime, pretty_format_inner


def test_pretty_format_basic() -> None:
    obj = [
        {
            "id": "apple",
            "type": "fruit",
        },
        {
            "id": "potato",
            "type": "dirty-ground-vegetable",
        },
    ]

    h = [
        {
            "key": "id",
            "header": "ID",
            "type": "text",
            "overflow": "keep",
        },
        {
            "key": "type",
            "header": "Type of thing in list",
            "type": "text",
            "overflow": "truncate",
        },
    ]
    res = pretty_format_inner(obj, h, col=100)

    # strip all ansi color codes, and trailing whitespace
    res = "\n".join(x.strip() for x in ansi_escape.sub("", res).split("\n"))

    assert (
        res
        == """\
ID      Type of thing in list
╌╌╌╌╌╌  ╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌
apple   fruit
potato  dirty-ground-vegetable
"""
    )


def test_pretty_format_hard_truncate() -> None:
    obj = [
        {
            "id": "apple",
            "type": "fruit",
        },
        {
            "id": "potato",
            "type": "dirty-ground-vegetable",
        },
    ]

    h = [
        {
            "key": "id",
            "header": "ID",
            "type": "text",
            "overflow": "keep",
        },
        {
            "key": "type",
            "header": "Type of thing in list",
            "type": "text",
            "overflow": "truncate",
        },
    ]
    res = pretty_format_inner(obj, h, col=10)

    # strip all ansi color codes, and trailing whitespace
    res = "\n".join(x.strip() for x in ansi_escape.sub("", res).split("\n"))

    assert (
        res
        == """\
ID      Type of thing in list
╌╌╌╌╌╌  ╌╌╌╌╌
apple   fruit
potato  di...
"""
    )


def test_pretty_format_fmt_receives_original_value() -> None:
    """Test that fmt function receives the original value, not a truncated string."""
    colors()

    # Simulates the share_fmt pattern: fmt receives a list and extracts first chars
    def share_fmt(share: Any, _cl: Any) -> str:
        # This should receive a list like ["public", "+"], not a string like "['pu..."
        sl = [x[0] for x in share]
        pub = "P" if "p" in sl else "-"
        org = "+" if "+" in sl else "-"
        return f"{pub} {org}"

    obj = [
        {"id": "item1", "shared": ["public", "+"]},
        {"id": "item2", "shared": ["public"]},
        {"id": "item3", "shared": ["+"]},
    ]

    h = [
        {"key": "id", "header": "ID", "type": "text", "overflow": "keep"},
        {"key": "shared", "header": "Shared", "type": "text", "fmt": share_fmt, "overflow": "keep"},
    ]

    res = pretty_format_inner(obj, h, col=100)
    res = "\n".join(x.strip() for x in ansi_escape.sub("", res).split("\n"))

    assert (
        res
        == """\
ID     Shared
╌╌╌╌╌  ╌╌╌╌╌╌
item1  P +
item2  P -
item3  - +
"""
    )


def test_pretty_format_fmt_with_list_not_truncated_to_string() -> None:
    """Regression test: ensure list values aren't converted to string before fmt."""
    colors()

    # Track what the fmt function receives
    received_values: list = []

    def tracking_fmt(value: Any, _cl: Any) -> str:
        received_values.append(value)
        if isinstance(value, list):
            return f"list:{len(value)}"
        return f"other:{type(value).__name__}"

    obj = [
        {"id": "test", "data": ["a", "b", "c", "d", "e"]},
    ]

    h = [
        {"key": "id", "header": "ID", "type": "text", "overflow": "keep"},
        {"key": "data", "header": "Data", "type": "text", "fmt": tracking_fmt, "overflow": "keep"},
    ]

    pretty_format_inner(obj, h, col=100)

    # The fmt function is called twice: once for width calculation, once for rendering
    # Both times it should receive the original list, not a string
    assert len(received_values) == 2
    for val in received_values:
        assert isinstance(val, list)
        assert val == ["a", "b", "c", "d", "e"]


def test_parse_api_datetime_utc_suffix() -> None:
    """Test parsing dates with UTC suffix (as returned by the API)."""
    result = parse_api_datetime("Mon, 05 Jan 2026 23:40:13 UTC")
    assert result is not None
    assert result.year == 2026
    assert result.month == 1
    assert result.day == 5
    assert result.hour == 23
    assert result.minute == 40
    assert result.second == 13
    assert result.tzinfo == timezone.utc


def test_parse_api_datetime_gmt_suffix() -> None:
    """Test parsing dates with GMT suffix."""
    result = parse_api_datetime("Fri, 12 Dec 2025 12:55:17 GMT")
    assert result is not None
    assert result.year == 2025
    assert result.month == 12
    assert result.day == 12
    assert result.hour == 12
    assert result.minute == 55
    assert result.second == 17
    assert result.tzinfo == timezone.utc


def test_parse_api_datetime_numeric_offset() -> None:
    """Test parsing dates with numeric timezone offset."""
    result = parse_api_datetime("Sun, 14 Dec 2025 15:05:53 +0000")
    assert result is not None
    assert result.year == 2025
    assert result.month == 12
    assert result.day == 14
    assert result.hour == 15
    assert result.minute == 5
    assert result.second == 53
    assert result.tzinfo == timezone.utc


def test_parse_api_datetime_empty_string() -> None:
    """Test that empty string returns None."""
    assert parse_api_datetime("") is None


def test_parse_api_datetime_none_like_empty() -> None:
    """Test that None-like empty input returns None."""
    assert parse_api_datetime("") is None


def test_parse_api_datetime_invalid_format() -> None:
    """Test that invalid date format returns None."""
    assert parse_api_datetime("not a date") is None
    assert parse_api_datetime("2025-01-05") is None  # ISO format not supported


def test_parse_api_datetime_returns_timezone_aware() -> None:
    """Test that returned datetime is always timezone-aware."""
    result = parse_api_datetime("Mon, 05 Jan 2026 23:40:13 UTC")
    assert result is not None
    assert result.tzinfo is not None
    # Should be able to compare with other tz-aware datetimes without error
    now = datetime.now(timezone.utc)
    _ = now - result  # This would raise if result is naive
