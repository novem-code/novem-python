from datetime import datetime, timezone

from novem.utils import parse_api_datetime


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
