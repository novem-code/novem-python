import json
import re

from novem.cli.gql import (
    _aggregate_activity,
    _get_gql_endpoint,
)
from novem.cli.vis import _compact_num, _format_activity, _format_views
from novem.utils import API_ROOT, colors

from .utils import write_config

gql_endpoint = _get_gql_endpoint(API_ROOT)

auth_req = {
    "username": "demouser",
    "password": "demopass",
    "token_name": "demotoken",
    "token_description": "test token",
}


def _strip_ansi(s: str) -> str:
    """Remove ANSI escape codes for easier assertion."""
    return re.sub(r"\033\[[0-9;]*m", "", s)


# --- Unit tests for helpers ---


# --- Unit tests for query building ---


# --- Unit tests for _has_truncated_replies ---


# --- Unit tests for render_topics ---


# --- CLI integration tests ---


def test_comments_empty(cli, requests_mock, fs) -> None:
    """Test --comments on a plot with no topics."""
    write_config(auth_req)

    gql_response = {"data": {"plots": [{"topics": []}]}}
    requests_mock.register_uri("POST", gql_endpoint, text=lambda r, c: json.dumps(gql_response))
    requests_mock.register_uri("PUT", "https://api.novem.io/v1/vis/plots/my_plot", status_code=201)

    out, err = cli("-p", "my_plot", "--comments")
    assert "No topics" in out


def test_comments_with_data(cli, requests_mock, fs) -> None:
    """Test --comments shows topic and comment content."""
    write_config(auth_req)

    gql_response = {
        "data": {
            "plots": [
                {
                    "topics": [
                        {
                            "topic_id": 1,
                            "slug": "test-topic",
                            "message": "Discussion about the chart",
                            "audience": "public",
                            "status": "active",
                            "num_comments": 1,
                            "likes": 0,
                            "dislikes": 0,
                            "edited": False,
                            "created": "Mon, 10 Feb 2026 12:00:00 UTC",
                            "updated": "Mon, 10 Feb 2026 12:00:00 UTC",
                            "creator": {"username": "alice"},
                            "comments": [
                                {
                                    "comment_id": 1,
                                    "slug": "comment-1",
                                    "message": "Looks good!",
                                    "depth": 0,
                                    "deleted": False,
                                    "edited": False,
                                    "num_replies": 0,
                                    "likes": 0,
                                    "dislikes": 0,
                                    "created": "Mon, 10 Feb 2026 12:05:00 UTC",
                                    "updated": "Mon, 10 Feb 2026 12:05:00 UTC",
                                    "creator": {"username": "bob"},
                                    "replies": [],
                                }
                            ],
                        }
                    ]
                }
            ]
        }
    }
    requests_mock.register_uri("POST", gql_endpoint, text=lambda r, c: json.dumps(gql_response))
    requests_mock.register_uri("PUT", "https://api.novem.io/v1/vis/plots/my_plot", status_code=201)

    out, err = cli("-p", "my_plot", "--comments")
    plain = _strip_ansi(out)
    assert "@alice" in plain
    assert "Discussion about the chart" in plain
    assert "@bob" in plain
    assert "Looks good!" in plain


def test_comments_sends_correct_gql_query(cli, requests_mock, fs) -> None:
    """Test --comments sends a properly formed GQL query with vis ID."""
    write_config(auth_req)

    captured_query = None

    def capture_gql(request, context):
        nonlocal captured_query
        body = request.json()
        captured_query = body.get("query", "")
        return json.dumps({"data": {"plots": [{"topics": []}]}})

    requests_mock.register_uri("POST", gql_endpoint, text=capture_gql)
    requests_mock.register_uri("PUT", "https://api.novem.io/v1/vis/plots/test_chart", status_code=201)

    cli("-p", "test_chart", "--comments")

    assert captured_query is not None
    assert "plots(id: $id, author: $author)" in captured_query
    assert "topics" in captured_query
    assert "comments" in captured_query


def test_comments_grid(cli, requests_mock, fs) -> None:
    """Test --comments works with grids too."""
    write_config(auth_req)

    captured_query = None

    def capture_gql(request, context):
        nonlocal captured_query
        body = request.json()
        captured_query = body.get("query", "")
        return json.dumps({"data": {"grids": [{"topics": []}]}})

    requests_mock.register_uri("POST", gql_endpoint, text=capture_gql)
    requests_mock.register_uri("PUT", "https://api.novem.io/v1/vis/grids/my_grid", status_code=201)

    out, err = cli("-g", "my_grid", "--comments")
    assert "No topics" in out
    assert captured_query is not None
    assert "grids(id: $id, author: $author)" in captured_query


def test_comments_mail(cli, requests_mock, fs) -> None:
    """Test --comments works with mails too."""
    write_config(auth_req)

    def return_gql(request, context):
        return json.dumps({"data": {"mails": [{"topics": []}]}})

    requests_mock.register_uri("POST", gql_endpoint, text=return_gql)
    requests_mock.register_uri("PUT", "https://api.novem.io/v1/vis/mails/my_mail", status_code=201)

    out, err = cli("-m", "my_mail", "--comments")
    assert "No topics" in out


def test_comments_adaptive_depth(cli, requests_mock, fs) -> None:
    """Test --comments re-fetches with deeper query when replies are truncated."""
    write_config(auth_req)

    call_count = 0

    def adaptive_gql(request, context):
        nonlocal call_count
        call_count += 1
        body = request.json()
        query = body.get("query", "")
        depth = query.count("replies {")

        if depth <= 3:
            # First fetch: return truncated comment (num_replies > 0 but no replies)
            return json.dumps(
                {
                    "data": {
                        "plots": [
                            {
                                "topics": [
                                    {
                                        "topic_id": 1,
                                        "slug": "t1",
                                        "message": "Topic",
                                        "audience": "public",
                                        "status": "active",
                                        "num_comments": 2,
                                        "likes": 0,
                                        "dislikes": 0,
                                        "my_reaction": None,
                                        "edited": False,
                                        "created": "Mon, 10 Feb 2026 12:00:00 UTC",
                                        "updated": "Mon, 10 Feb 2026 12:00:00 UTC",
                                        "creator": {"username": "alice"},
                                        "comments": [
                                            {
                                                "comment_id": 1,
                                                "slug": "c1",
                                                "message": "Deep thread",
                                                "depth": 0,
                                                "deleted": False,
                                                "edited": False,
                                                "num_replies": 1,
                                                "likes": 0,
                                                "dislikes": 0,
                                                "my_reaction": None,
                                                "created": "Mon, 10 Feb 2026 12:05:00 UTC",
                                                "updated": "Mon, 10 Feb 2026 12:05:00 UTC",
                                                "creator": {"username": "bob"},
                                                "replies": [],
                                            }
                                        ],
                                    }
                                ]
                            }
                        ]
                    }
                }
            )
        else:
            # Deeper fetch: return full tree with replies resolved
            return json.dumps(
                {
                    "data": {
                        "plots": [
                            {
                                "topics": [
                                    {
                                        "topic_id": 1,
                                        "slug": "t1",
                                        "message": "Topic",
                                        "audience": "public",
                                        "status": "active",
                                        "num_comments": 2,
                                        "likes": 0,
                                        "dislikes": 0,
                                        "my_reaction": None,
                                        "edited": False,
                                        "created": "Mon, 10 Feb 2026 12:00:00 UTC",
                                        "updated": "Mon, 10 Feb 2026 12:00:00 UTC",
                                        "creator": {"username": "alice"},
                                        "comments": [
                                            {
                                                "comment_id": 1,
                                                "slug": "c1",
                                                "message": "Deep thread",
                                                "depth": 0,
                                                "deleted": False,
                                                "edited": False,
                                                "num_replies": 1,
                                                "likes": 0,
                                                "dislikes": 0,
                                                "my_reaction": None,
                                                "created": "Mon, 10 Feb 2026 12:05:00 UTC",
                                                "updated": "Mon, 10 Feb 2026 12:05:00 UTC",
                                                "creator": {"username": "bob"},
                                                "replies": [
                                                    {
                                                        "comment_id": 2,
                                                        "slug": "c2",
                                                        "message": "Deep reply",
                                                        "depth": 1,
                                                        "deleted": False,
                                                        "edited": False,
                                                        "num_replies": 0,
                                                        "likes": 0,
                                                        "dislikes": 0,
                                                        "my_reaction": None,
                                                        "created": "Mon, 10 Feb 2026 12:10:00 UTC",
                                                        "updated": "Mon, 10 Feb 2026 12:10:00 UTC",
                                                        "creator": {"username": "carol"},
                                                        "replies": [],
                                                    }
                                                ],
                                            }
                                        ],
                                    }
                                ]
                            }
                        ]
                    }
                }
            )

    requests_mock.register_uri("POST", gql_endpoint, text=adaptive_gql)
    requests_mock.register_uri("PUT", "https://api.novem.io/v1/vis/plots/deep_plot", status_code=201)

    out, err = cli("-p", "deep_plot", "--comments")
    plain = _strip_ansi(out)

    # Should have fetched twice (depth=3 truncated, depth=6 resolved)
    assert call_count == 2
    # Deep reply should be present in output
    assert "Deep reply" in plain
    assert "@carol" in plain


# --- Unit tests for _compact_num ---


class TestCompactNum:
    def test_zero(self) -> None:
        assert _compact_num(0) == "-"

    def test_small(self) -> None:
        assert _compact_num(1) == "1"
        assert _compact_num(42) == "42"
        assert _compact_num(999) == "999"

    def test_thousands(self) -> None:
        assert _compact_num(1000) == "1k"
        assert _compact_num(1200) == "1.2k"
        assert _compact_num(1050) == "1.1k"
        assert _compact_num(9999) == "10k"
        assert _compact_num(10000) == "10k"
        assert _compact_num(99999) == "100k"

    def test_large(self) -> None:
        assert _compact_num(100000) == "100k"
        assert _compact_num(999999) == "999k"
        assert _compact_num(1000000) == "1M"
        assert _compact_num(1500000) == "1.5M"
        assert _compact_num(10000000) == "10M"


# --- Unit tests for _aggregate_activity ---


class TestAggregateActivity:
    def test_no_topics(self) -> None:
        result = _aggregate_activity({})
        assert result == {"_comments": 0, "_likes": 0, "_dislikes": 0}

    def test_empty_topics(self) -> None:
        result = _aggregate_activity({"topics": []})
        assert result == {"_comments": 0, "_likes": 0, "_dislikes": 0}

    def test_single_topic(self) -> None:
        result = _aggregate_activity({"topics": [{"num_comments": 5, "num_likes": 3, "num_dislikes": 1}]})
        assert result == {"_comments": 6, "_likes": 3, "_dislikes": 1}

    def test_multiple_topics(self) -> None:
        result = _aggregate_activity(
            {
                "topics": [
                    {"num_comments": 2, "num_likes": 1, "num_dislikes": 0},
                    {"num_comments": 3, "num_likes": 4, "num_dislikes": 2},
                ]
            }
        )
        assert result == {"_comments": 7, "_likes": 5, "_dislikes": 2}


# --- Unit tests for _format_activity alignment ---


class TestFormatActivity:
    def _plain(self, p: dict) -> str:
        """Strip ANSI from the _activity value."""
        return _strip_ansi(p["_activity"])

    def test_all_zeros(self) -> None:
        colors()
        plist = [{"_comments": 0, "_likes": 0, "_dislikes": 0}]
        _format_activity(plist)
        # 3 single-char components, total=8, gaps=5 → gap1=3, gap2=2
        assert self._plain(plist[0]) == "-   -  -"

    def test_single_digits(self) -> None:
        colors()
        plist = [{"_comments": 1, "_likes": 2, "_dislikes": 3}]
        _format_activity(plist)
        assert self._plain(plist[0]) == "1   2  3"

    def test_mixed_widths_align(self) -> None:
        colors()
        plist = [
            {"_comments": 1, "_likes": 50, "_dislikes": 0},
            {"_comments": 100, "_likes": 1, "_dislikes": 10},
        ]
        _format_activity(plist)
        p0 = self._plain(plist[0])
        p1 = self._plain(plist[1])
        # All rows should have the same visible width
        assert len(p0) == len(p1)
        # Components right-aligned within sub-columns, gaps evenly distributed
        assert p0 == "  1 50  -"
        assert p1 == "100  1 10"

    def test_thousands(self) -> None:
        colors()
        plist = [
            {"_comments": 1000, "_likes": 50, "_dislikes": 0},
            {"_comments": 1, "_likes": 10000, "_dislikes": 5},
        ]
        _format_activity(plist)
        p0 = self._plain(plist[0])
        p1 = self._plain(plist[1])
        assert len(p0) == len(p1)
        assert "1k" in p0
        assert "10k" in p1

    def test_millions(self) -> None:
        colors()
        plist = [
            {"_comments": 1000000, "_likes": 1500000, "_dislikes": 100},
            {"_comments": 50, "_likes": 1, "_dislikes": 10000000},
        ]
        _format_activity(plist)
        p0 = self._plain(plist[0])
        p1 = self._plain(plist[1])
        assert len(p0) == len(p1)
        assert "1M" in p0
        assert "1.5M" in p0
        assert "10M" in p1

    def test_wide_values_no_header_padding(self) -> None:
        """When values are wider than 'Activity', no extra padding needed."""
        colors()
        plist = [{"_comments": 10000, "_likes": 10000, "_dislikes": 10000}]
        _format_activity(plist)
        p = self._plain(plist[0])
        assert p == "10k 10k 10k"  # 11 chars > 8 ("Activity"), no extra padding

    def test_empty_list(self) -> None:
        colors()
        plist: list = []
        _format_activity(plist)  # should not raise


# --- Unit tests for _format_views ---


class TestFormatViews:
    def test_zero_views(self) -> None:
        colors()
        plist = [{"_views": 0}]
        _format_views(plist)
        assert plist[0]["_views_fmt"].strip() == "-"

    def test_small_views(self) -> None:
        colors()
        plist = [{"_views": 42}]
        _format_views(plist)
        assert plist[0]["_views_fmt"].strip() == "42"

    def test_thousands(self) -> None:
        colors()
        plist = [{"_views": 1200}]
        _format_views(plist)
        assert plist[0]["_views_fmt"].strip() == "1.2k"

    def test_right_aligned(self) -> None:
        colors()
        plist = [{"_views": 5}, {"_views": 1200}]
        _format_views(plist)
        # Both should have same width (right-aligned)
        assert len(plist[0]["_views_fmt"]) == len(plist[1]["_views_fmt"])
        assert plist[0]["_views_fmt"].endswith("5")
        assert plist[1]["_views_fmt"].endswith("1.2k")

    def test_min_header_width(self) -> None:
        """Column should be at least as wide as 'Views' (5 chars)."""
        colors()
        plist = [{"_views": 1}]
        _format_views(plist)
        assert len(plist[0]["_views_fmt"]) >= len("Views")

    def test_empty_list(self) -> None:
        colors()
        plist: list = []
        _format_views(plist)  # should not raise
