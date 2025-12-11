"""Tests for CLI column-based filtering."""

import pytest

from novem.cli.filter import (
    ColumnFilter,
    FilterMode,
    apply_filters,
    get_shared_display_value,
    matches_filter,
    parse_filter,
)


class TestParseFilter:
    def test_legacy_mode(self) -> None:
        f = parse_filter("aapl")
        assert f.column is None
        assert f.pattern == "aapl"
        assert f.mode == FilterMode.LEGACY

    def test_exact_match_key(self) -> None:
        f = parse_filter("id=aapl_px")
        assert f.column == "id"
        assert f.pattern == "aapl_px"
        assert f.mode == FilterMode.EXACT

    def test_regex_match_key(self) -> None:
        f = parse_filter("name~apple.*chart")
        assert f.column == "name"
        assert f.pattern == "apple.*chart"
        assert f.mode == FilterMode.REGEX

    def test_quoted_header_name(self) -> None:
        f = parse_filter('"Plot ID"=aapl_px')
        assert f.column == "id"
        assert f.pattern == "aapl_px"
        assert f.mode == FilterMode.EXACT

    def test_quoted_header_name_grid(self) -> None:
        f = parse_filter('"Grid ID"=my_grid')
        assert f.column == "id"
        assert f.pattern == "my_grid"

    def test_quoted_header_name_mail(self) -> None:
        f = parse_filter('"Mail ID"=daily_summary')
        assert f.column == "id"
        assert f.pattern == "daily_summary"

    def test_case_insensitive_column(self) -> None:
        f = parse_filter("NAME=test")
        assert f.column == "name"

        f = parse_filter("Type=bar")
        assert f.column == "type"

    def test_url_maps_to_uri(self) -> None:
        f = parse_filter("url~novem.io")
        assert f.column == "uri"

    def test_unknown_column(self) -> None:
        with pytest.raises(ValueError, match="Unknown column"):
            parse_filter("unknown=value")

    def test_value_with_equals(self) -> None:
        # First = is the delimiter, rest is the value
        f = parse_filter("name=test=value")
        assert f.column == "name"
        assert f.pattern == "test=value"

    def test_empty_value(self) -> None:
        f = parse_filter("name=")
        assert f.column == "name"
        assert f.pattern == ""
        assert f.mode == FilterMode.EXACT


class TestGetSharedDisplayValue:
    def test_public_only(self) -> None:
        assert get_shared_display_value(["public"]) == "P - - -"

    def test_user_group(self) -> None:
        assert get_shared_display_value(["@"]) == "- - @ -"

    def test_org_group(self) -> None:
        assert get_shared_display_value(["+"]) == "- - - +"

    def test_chat(self) -> None:
        assert get_shared_display_value(["chat"]) == "- C - -"

    def test_combined(self) -> None:
        assert get_shared_display_value(["public", "@", "+"]) == "P - @ +"

    def test_all(self) -> None:
        assert get_shared_display_value(["public", "chat", "@", "+"]) == "P C @ +"

    def test_empty(self) -> None:
        assert get_shared_display_value([]) == "- - - -"


class TestMatchesFilter:
    @pytest.fixture
    def sample_item(self) -> dict:
        return {
            "id": "aapl_px",
            "name": "Apple Stock Price",
            "type": "line",
            "shared": ["public", "@"],
            "uri": "https://novem.no/p/abc",
            "updated": "2024-01-15 10:30",
            "summary": "Daily price data",
            "fav": "*",
        }

    def test_exact_match(self, sample_item: dict) -> None:
        f = ColumnFilter(column="id", pattern="aapl_px", mode=FilterMode.EXACT)
        assert matches_filter(sample_item, f) is True

        f = ColumnFilter(column="id", pattern="aapl", mode=FilterMode.EXACT)
        assert matches_filter(sample_item, f) is False

    def test_exact_match_case_insensitive(self, sample_item: dict) -> None:
        f = ColumnFilter(column="id", pattern="AAPL_PX", mode=FilterMode.EXACT)
        assert matches_filter(sample_item, f) is True

    def test_regex_match(self, sample_item: dict) -> None:
        f = ColumnFilter(column="name", pattern="apple.*price", mode=FilterMode.REGEX)
        assert matches_filter(sample_item, f) is True

    def test_regex_match_partial(self, sample_item: dict) -> None:
        f = ColumnFilter(column="name", pattern="Stock", mode=FilterMode.REGEX)
        assert matches_filter(sample_item, f) is True

    def test_regex_case_insensitive(self, sample_item: dict) -> None:
        f = ColumnFilter(column="name", pattern="APPLE", mode=FilterMode.REGEX)
        assert matches_filter(sample_item, f) is True

    def test_shared_column_public(self, sample_item: dict) -> None:
        # shared: ["public", "@"] -> "P - @ -"
        f = ColumnFilter(column="shared", pattern="P", mode=FilterMode.REGEX)
        assert matches_filter(sample_item, f) is True

    def test_shared_column_combined_regex(self, sample_item: dict) -> None:
        # Match items that are public AND have user group
        f = ColumnFilter(column="shared", pattern="P.*@", mode=FilterMode.REGEX)
        assert matches_filter(sample_item, f) is True

    def test_shared_column_no_org(self, sample_item: dict) -> None:
        # This item has no org group (+), so shouldn't match exact +
        f = ColumnFilter(column="shared", pattern="+", mode=FilterMode.REGEX)
        assert matches_filter(sample_item, f) is False  # "P - @ -" doesn't contain "+"

    def test_shared_exact_match_single_flag(self, sample_item: dict) -> None:
        # shared: ["public", "@"] -> "P - @ -"
        # Exact match means ONLY those flags, nothing else
        f = ColumnFilter(column="shared", pattern="P", mode=FilterMode.EXACT)
        assert matches_filter(sample_item, f) is False  # Has @ too, not just P

        f = ColumnFilter(column="shared", pattern="@", mode=FilterMode.EXACT)
        assert matches_filter(sample_item, f) is False  # Has P too, not just @

    def test_shared_exact_match_multiple_flags(self, sample_item: dict) -> None:
        # shared: ["public", "@"] -> "P - @ -"
        # Exact match with P@ should match since item has exactly P and @
        f = ColumnFilter(column="shared", pattern="P@", mode=FilterMode.EXACT)
        assert matches_filter(sample_item, f) is True

        f = ColumnFilter(column="shared", pattern="P+", mode=FilterMode.EXACT)
        assert matches_filter(sample_item, f) is False  # Has @ not +

        f = ColumnFilter(column="shared", pattern="P@+", mode=FilterMode.EXACT)
        assert matches_filter(sample_item, f) is False  # Missing +

    def test_shared_exact_match_case_insensitive(self, sample_item: dict) -> None:
        # shared: ["public", "@"] -> "P - @ -"
        f = ColumnFilter(column="shared", pattern="p@", mode=FilterMode.EXACT)
        assert matches_filter(sample_item, f) is True  # lowercase works

    def test_shared_exact_match_only_public(self) -> None:
        item = {"shared": ["public"]}  # Only public -> "P - - -"
        f = ColumnFilter(column="shared", pattern="P", mode=FilterMode.EXACT)
        assert matches_filter(item, f) is True

    def test_shared_exact_match_no_sharing(self) -> None:
        item = {"shared": []}  # No sharing -> "- - - -"
        f = ColumnFilter(column="shared", pattern="", mode=FilterMode.EXACT)
        assert matches_filter(item, f) is True

    def test_fav_column(self, sample_item: dict) -> None:
        f = ColumnFilter(column="fav", pattern="*", mode=FilterMode.EXACT)
        assert matches_filter(sample_item, f) is True

    def test_legacy_mode_id(self, sample_item: dict) -> None:
        f = ColumnFilter(column=None, pattern="aapl", mode=FilterMode.LEGACY)
        assert matches_filter(sample_item, f) is True

    def test_legacy_mode_name(self, sample_item: dict) -> None:
        f = ColumnFilter(column=None, pattern="Apple", mode=FilterMode.LEGACY)
        assert matches_filter(sample_item, f) is True

    def test_legacy_mode_type(self, sample_item: dict) -> None:
        f = ColumnFilter(column=None, pattern="line", mode=FilterMode.LEGACY)
        assert matches_filter(sample_item, f) is True

    def test_legacy_mode_no_match(self, sample_item: dict) -> None:
        f = ColumnFilter(column=None, pattern="xyz123", mode=FilterMode.LEGACY)
        assert matches_filter(sample_item, f) is False

    def test_invalid_regex_falls_back_to_substring(self, sample_item: dict) -> None:
        # Invalid regex with unclosed bracket - falls back to literal substring match
        f = ColumnFilter(column="name", pattern="[invalid", mode=FilterMode.REGEX)
        # "[invalid" is not a substring of "Apple Stock Price"
        assert matches_filter(sample_item, f) is False

        # But a pattern that IS a substring (even if invalid regex) should match
        f = ColumnFilter(column="uri", pattern="novem.no/p/", mode=FilterMode.REGEX)
        assert matches_filter(sample_item, f) is True

    def test_none_value_handling(self) -> None:
        item = {"id": "test", "name": None, "type": "bar", "shared": []}
        f = ColumnFilter(column="name", pattern="", mode=FilterMode.EXACT)
        assert matches_filter(item, f) is True


class TestApplyFilters:
    @pytest.fixture
    def sample_items(self) -> list:
        return [
            {"id": "plot1", "name": "First Plot", "type": "bar", "shared": ["public"]},
            {"id": "plot2", "name": "Second Plot", "type": "line", "shared": ["@"]},
            {"id": "plot3", "name": "Third Plot", "type": "bar", "shared": []},
            {"id": "apple_chart", "name": "Apple Price", "type": "line", "shared": ["public", "+"]},
        ]

    def test_single_filter_exact(self, sample_items: list) -> None:
        result = apply_filters(sample_items, ["type=bar"])
        assert len(result) == 2
        assert result[0]["id"] == "plot1"
        assert result[1]["id"] == "plot3"

    def test_single_filter_regex(self, sample_items: list) -> None:
        result = apply_filters(sample_items, ["name~Plot"])
        assert len(result) == 3
        ids = [r["id"] for r in result]
        assert "plot1" in ids
        assert "plot2" in ids
        assert "plot3" in ids

    def test_multiple_filters_and_logic(self, sample_items: list) -> None:
        result = apply_filters(sample_items, ["type=bar", "id~plot1"])
        assert len(result) == 1
        assert result[0]["id"] == "plot1"

    def test_filter_shared_public(self, sample_items: list) -> None:
        result = apply_filters(sample_items, ["shared~P"])
        assert len(result) == 2
        ids = [r["id"] for r in result]
        assert "plot1" in ids
        assert "apple_chart" in ids

    def test_filter_shared_or_pattern(self, sample_items: list) -> None:
        # Match public OR org group using regex alternation
        result = apply_filters(sample_items, ["shared~P|\\+"])
        assert len(result) == 2

    def test_no_filters(self, sample_items: list) -> None:
        result = apply_filters(sample_items, None)
        assert result == sample_items

        result = apply_filters(sample_items, [])
        assert result == sample_items

    def test_legacy_filter(self, sample_items: list) -> None:
        result = apply_filters(sample_items, ["apple"])
        assert len(result) == 1
        assert result[0]["id"] == "apple_chart"

    def test_no_matches(self, sample_items: list) -> None:
        result = apply_filters(sample_items, ["id=nonexistent"])
        assert len(result) == 0
