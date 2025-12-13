"""Tests for CLI user listing functionality."""

import pytest

from novem.cli.filter import (
    ColumnFilter,
    FilterMode,
    apply_filters,
    get_conn_display_value,
    matches_filter,
    parse_filter,
)
from novem.cli.gql import _transform_users_response


class TestGetConnDisplayValue:
    """Tests for get_conn_display_value function."""

    def test_connected_only(self) -> None:
        item = {"connected": True, "follower": False, "following": False}
        assert get_conn_display_value(item) == "C - - -"

    def test_follower_only(self) -> None:
        item = {"connected": False, "follower": True, "following": False}
        assert get_conn_display_value(item) == "- F - -"

    def test_following_only(self) -> None:
        item = {"connected": False, "follower": False, "following": True}
        assert get_conn_display_value(item) == "- - F -"

    def test_connected_and_following(self) -> None:
        item = {"connected": True, "follower": False, "following": True}
        assert get_conn_display_value(item) == "C - F -"

    def test_all_relationships(self) -> None:
        item = {"connected": True, "follower": True, "following": True}
        assert get_conn_display_value(item) == "C F F -"

    def test_no_relationships(self) -> None:
        item = {"connected": False, "follower": False, "following": False}
        assert get_conn_display_value(item) == "- - - -"

    def test_empty_item(self) -> None:
        item: dict = {}
        assert get_conn_display_value(item) == "- - - -"

    def test_none_values(self) -> None:
        item = {"connected": None, "follower": None, "following": None}
        assert get_conn_display_value(item) == "- - - -"


class TestParseFilterUserColumns:
    """Tests for parsing user-specific filter columns."""

    def test_username_column(self) -> None:
        f = parse_filter("username~sondov")
        assert f.column == "username"
        assert f.pattern == "sondov"
        assert f.mode == FilterMode.REGEX

    def test_username_exact(self) -> None:
        f = parse_filter("username=sondov")
        assert f.column == "username"
        assert f.pattern == "sondov"
        assert f.mode == FilterMode.EXACT

    def test_conn_column(self) -> None:
        f = parse_filter("conn~C")
        assert f.column == "conn"
        assert f.pattern == "C"
        assert f.mode == FilterMode.REGEX

    def test_conn_dot_column(self) -> None:
        f = parse_filter("conn.~C")
        assert f.column == "conn"
        assert f.pattern == "C"

    def test_connection_column(self) -> None:
        f = parse_filter("connection~C")
        assert f.column == "conn"
        assert f.pattern == "C"

    def test_bio_column(self) -> None:
        f = parse_filter("bio~developer")
        assert f.column == "bio"
        assert f.pattern == "developer"
        assert f.mode == FilterMode.REGEX

    def test_biography_column(self) -> None:
        f = parse_filter("biography~engineer")
        assert f.column == "bio"
        assert f.pattern == "engineer"

    def test_groups_column(self) -> None:
        f = parse_filter("groups~2")
        assert f.column == "groups"
        assert f.pattern == "2"

    def test_social_column(self) -> None:
        f = parse_filter("social~3")
        assert f.column == "social"
        assert f.pattern == "3"


class TestMatchesFilterConn:
    """Tests for conn column filtering."""

    @pytest.fixture
    def connected_user(self) -> dict:
        return {
            "username": "alice",
            "name": "Alice",
            "connected": True,
            "follower": False,
            "following": True,
            "bio": "Software engineer",
        }

    @pytest.fixture
    def follower_user(self) -> dict:
        return {
            "username": "bob",
            "name": "Bob",
            "connected": False,
            "follower": True,
            "following": False,
            "bio": "Data scientist",
        }

    @pytest.fixture
    def unrelated_user(self) -> dict:
        return {
            "username": "charlie",
            "name": "Charlie",
            "connected": False,
            "follower": False,
            "following": False,
            "bio": "Designer",
        }

    def test_conn_regex_connected(self, connected_user: dict, follower_user: dict) -> None:
        f = ColumnFilter(column="conn", pattern="C", mode=FilterMode.REGEX)
        assert matches_filter(connected_user, f) is True
        assert matches_filter(follower_user, f) is False

    def test_conn_regex_follower(self, connected_user: dict, follower_user: dict) -> None:
        # F matches either follower or following
        f = ColumnFilter(column="conn", pattern="F", mode=FilterMode.REGEX)
        assert matches_filter(connected_user, f) is True  # has following
        assert matches_filter(follower_user, f) is True  # has follower

    def test_conn_regex_no_match(self, unrelated_user: dict) -> None:
        f = ColumnFilter(column="conn", pattern="C", mode=FilterMode.REGEX)
        assert matches_filter(unrelated_user, f) is False

        f = ColumnFilter(column="conn", pattern="F", mode=FilterMode.REGEX)
        assert matches_filter(unrelated_user, f) is False

    def test_conn_exact_connected_only(self) -> None:
        # User is ONLY connected, nothing else
        user = {"connected": True, "follower": False, "following": False}
        f = ColumnFilter(column="conn", pattern="C", mode=FilterMode.EXACT)
        assert matches_filter(user, f) is True

    def test_conn_exact_connected_and_follower(self) -> None:
        # User is connected and follower
        user = {"connected": True, "follower": True, "following": False}
        f = ColumnFilter(column="conn", pattern="CF", mode=FilterMode.EXACT)
        assert matches_filter(user, f) is True

        # But not if we only specify C
        f = ColumnFilter(column="conn", pattern="C", mode=FilterMode.EXACT)
        assert matches_filter(user, f) is False

    def test_conn_exact_connected_and_following(self) -> None:
        # User is connected and following (2 F's = follower + following)
        user = {"connected": True, "follower": False, "following": True}
        f = ColumnFilter(column="conn", pattern="CFF", mode=FilterMode.EXACT)
        assert matches_filter(user, f) is False  # Only 1 F (following), not 2

    def test_conn_exact_case_insensitive(self) -> None:
        user = {"connected": True, "follower": False, "following": False}
        f = ColumnFilter(column="conn", pattern="c", mode=FilterMode.EXACT)
        assert matches_filter(user, f) is True

    def test_conn_regex_with_general_regex(self, connected_user: dict) -> None:
        # Can also use general regex patterns
        f = ColumnFilter(column="conn", pattern="C.*F", mode=FilterMode.REGEX)
        assert matches_filter(connected_user, f) is True  # "C - F -" matches


class TestMatchesFilterUsername:
    """Tests for username column filtering."""

    @pytest.fixture
    def sample_users(self) -> list:
        return [
            {"username": "sondov", "name": "Sondov Engen"},
            {"username": "alice_test", "name": "Alice"},
            {"username": "bob", "name": "Bob"},
        ]

    def test_username_exact_match(self, sample_users: list) -> None:
        f = ColumnFilter(column="username", pattern="sondov", mode=FilterMode.EXACT)
        assert matches_filter(sample_users[0], f) is True
        assert matches_filter(sample_users[1], f) is False

    def test_username_regex_partial(self, sample_users: list) -> None:
        f = ColumnFilter(column="username", pattern="alice", mode=FilterMode.REGEX)
        assert matches_filter(sample_users[0], f) is False
        assert matches_filter(sample_users[1], f) is True

    def test_username_regex_pattern(self, sample_users: list) -> None:
        f = ColumnFilter(column="username", pattern=".*_test", mode=FilterMode.REGEX)
        assert matches_filter(sample_users[0], f) is False
        assert matches_filter(sample_users[1], f) is True


class TestMatchesFilterBio:
    """Tests for bio column filtering."""

    def test_bio_regex_match(self) -> None:
        user = {"username": "test", "bio": "Software engineer with 10 years experience"}
        f = ColumnFilter(column="bio", pattern="engineer", mode=FilterMode.REGEX)
        assert matches_filter(user, f) is True

    def test_bio_regex_no_match(self) -> None:
        user = {"username": "test", "bio": "Data scientist"}
        f = ColumnFilter(column="bio", pattern="engineer", mode=FilterMode.REGEX)
        assert matches_filter(user, f) is False

    def test_bio_empty(self) -> None:
        user = {"username": "test", "bio": ""}
        f = ColumnFilter(column="bio", pattern="anything", mode=FilterMode.REGEX)
        assert matches_filter(user, f) is False

    def test_bio_none(self) -> None:
        user = {"username": "test", "bio": None}
        f = ColumnFilter(column="bio", pattern="", mode=FilterMode.EXACT)
        assert matches_filter(user, f) is True


class TestApplyFiltersUsers:
    """Tests for applying filters to user lists."""

    @pytest.fixture
    def sample_users(self) -> list:
        return [
            {
                "username": "alice",
                "name": "Alice Smith",
                "connected": True,
                "follower": False,
                "following": True,
                "bio": "Software engineer",
            },
            {
                "username": "bob",
                "name": "Bob Jones",
                "connected": False,
                "follower": True,
                "following": False,
                "bio": "Data scientist",
            },
            {
                "username": "charlie",
                "name": "Charlie Brown",
                "connected": False,
                "follower": False,
                "following": False,
                "bio": "Designer",
            },
            {
                "username": "sondov",
                "name": "Sondov Engen",
                "connected": False,
                "follower": False,
                "following": False,
                "bio": "Developer and founder",
            },
        ]

    def test_filter_by_username(self, sample_users: list) -> None:
        result = apply_filters(sample_users, ["username~alice"])
        assert len(result) == 1
        assert result[0]["username"] == "alice"

    def test_filter_by_conn_connected(self, sample_users: list) -> None:
        result = apply_filters(sample_users, ["conn~C"])
        assert len(result) == 1
        assert result[0]["username"] == "alice"

    def test_filter_by_conn_follower(self, sample_users: list) -> None:
        # F matches follower OR following
        result = apply_filters(sample_users, ["conn~F"])
        assert len(result) == 2
        usernames = [r["username"] for r in result]
        assert "alice" in usernames  # following=True
        assert "bob" in usernames  # follower=True

    def test_filter_by_bio(self, sample_users: list) -> None:
        result = apply_filters(sample_users, ["bio~engineer"])
        assert len(result) == 1
        assert result[0]["username"] == "alice"

    def test_filter_by_name(self, sample_users: list) -> None:
        result = apply_filters(sample_users, ["name~Smith"])
        assert len(result) == 1
        assert result[0]["username"] == "alice"

    def test_multiple_filters(self, sample_users: list) -> None:
        # Connected AND bio contains something
        result = apply_filters(sample_users, ["conn~C", "bio~engineer"])
        assert len(result) == 1
        assert result[0]["username"] == "alice"

    def test_no_matching_users(self, sample_users: list) -> None:
        result = apply_filters(sample_users, ["username=nonexistent"])
        assert len(result) == 0


class TestTransformUsersResponse:
    """Tests for _transform_users_response in gql.py."""

    def test_basic_transform(self) -> None:
        users = [
            {
                "username": "testuser",
                "name": "Test User",
                "type": "REGULAR",
                "bio": "A test bio",
                "relationship": {
                    "orgs": 2,
                    "groups": 3,
                    "follower": True,
                    "connected": True,
                    "following": False,
                },
                "social": {
                    "followers": 10,
                    "following": 5,
                    "connections": 15,
                },
                "plots": [{"id": "p1"}, {"id": "p2"}],
                "grids": [{"id": "g1"}],
                "mails": [],
                "docs": [{"id": "d1"}],
                "repos": [],
                "jobs": [{"id": "j1"}, {"id": "j2"}, {"id": "j3"}],
            }
        ]

        result = _transform_users_response(users, "")
        assert len(result) == 1

        user = result[0]
        assert user["username"] == "testuser"
        assert user["name"] == "Test User"
        assert user["type"] == "REGULAR"
        assert user["bio"] == "A test bio"

        # Relationship
        assert user["connected"] is True
        assert user["follower"] is True
        assert user["following"] is False
        assert user["orgs"] == 2
        assert user["groups"] == 3

        # Social
        assert user["social_connections"] == 15
        assert user["social_followers"] == 10
        assert user["social_following"] == 5

        # Content counts
        assert user["plots"] == 2
        assert user["grids"] == 1
        assert user["mails"] == 0
        assert user["docs"] == 1
        assert user["repos"] == 0
        assert user["jobs"] == 3

        # Verified status
        assert user["verified"] is False

    def test_verified_user(self) -> None:
        users = [
            {
                "username": "verified_user",
                "name": "Verified",
                "type": "VERIFIED",
                "bio": None,
                "relationship": None,
                "social": None,
                "plots": [],
                "grids": [],
                "mails": [],
                "docs": [],
                "repos": [],
                "jobs": [],
            }
        ]

        result = _transform_users_response(users, "")
        assert result[0]["verified"] is True

    def test_novem_user_is_verified(self) -> None:
        users = [
            {
                "username": "novem_user",
                "name": "Novem",
                "type": "NOVEM",
                "bio": None,
                "relationship": None,
                "social": None,
                "plots": [],
                "grids": [],
                "mails": [],
                "docs": [],
                "repos": [],
                "jobs": [],
            }
        ]

        result = _transform_users_response(users, "")
        assert result[0]["verified"] is True

    def test_system_user_is_verified(self) -> None:
        users = [
            {
                "username": "system",
                "name": "System",
                "type": "SYSTEM",
                "bio": None,
                "relationship": None,
                "social": None,
                "plots": [],
                "grids": [],
                "mails": [],
                "docs": [],
                "repos": [],
                "jobs": [],
            }
        ]

        result = _transform_users_response(users, "")
        assert result[0]["verified"] is True

    def test_null_relationship_and_social(self) -> None:
        users = [
            {
                "username": "minimal",
                "name": None,
                "type": "REGULAR",
                "bio": None,
                "relationship": None,
                "social": None,
                "plots": None,
                "grids": None,
                "mails": None,
                "docs": None,
                "repos": None,
                "jobs": None,
            }
        ]

        result = _transform_users_response(users, "")
        user = result[0]

        assert user["name"] == ""
        assert user["bio"] == ""
        assert user["connected"] is False
        assert user["follower"] is False
        assert user["following"] is False
        assert user["orgs"] == 0
        assert user["groups"] == 0
        assert user["social_connections"] == 0
        assert user["social_followers"] == 0
        assert user["social_following"] == 0
        assert user["plots"] == 0
        assert user["grids"] == 0

    def test_empty_users_list(self) -> None:
        result = _transform_users_response([], "")
        assert result == []


class TestUserSorting:
    """Tests for user sorting logic (tested via sort key behavior)."""

    def test_sort_current_user_first(self) -> None:
        """Current user should always be first."""
        from typing import Tuple

        current_user = "sondov"

        def user_sort_key(u: dict) -> Tuple[bool, bool, bool, bool, int, int, str]:
            is_me = u.get("username", "") == current_user
            return (
                not is_me,
                not u.get("connected", False),
                not u.get("following", False),
                not u.get("follower", False),
                -(u.get("groups", 0) or 0),
                -(u.get("orgs", 0) or 0),
                u.get("username", "").lower(),
            )

        users = [
            {"username": "alice", "connected": True, "following": True, "follower": False, "groups": 5, "orgs": 2},
            {"username": "sondov", "connected": False, "following": False, "follower": False, "groups": 0, "orgs": 0},
            {"username": "bob", "connected": True, "following": False, "follower": True, "groups": 3, "orgs": 1},
        ]

        sorted_users = sorted(users, key=user_sort_key)
        assert sorted_users[0]["username"] == "sondov"

    def test_sort_connected_before_following(self) -> None:
        """Connected users should come before merely following."""
        from typing import Tuple

        def user_sort_key(u: dict) -> Tuple[bool, bool, bool, bool, int, int, str]:
            return (
                True,  # Not current user
                not u.get("connected", False),
                not u.get("following", False),
                not u.get("follower", False),
                -(u.get("groups", 0) or 0),
                -(u.get("orgs", 0) or 0),
                u.get("username", "").lower(),
            )

        users = [
            {
                "username": "following_only",
                "connected": False,
                "following": True,
                "follower": False,
                "groups": 0,
                "orgs": 0,
            },
            {"username": "connected", "connected": True, "following": False, "follower": False, "groups": 0, "orgs": 0},
        ]

        sorted_users = sorted(users, key=user_sort_key)
        assert sorted_users[0]["username"] == "connected"
        assert sorted_users[1]["username"] == "following_only"

    def test_sort_by_groups_then_orgs(self) -> None:
        """Users with more shared groups/orgs should come first among unrelated users."""
        from typing import Tuple

        def user_sort_key(u: dict) -> Tuple[bool, bool, bool, bool, int, int, str]:
            return (
                True,  # Not current user
                True,  # Not connected
                True,  # Not following
                True,  # Not follower
                -(u.get("groups", 0) or 0),
                -(u.get("orgs", 0) or 0),
                u.get("username", "").lower(),
            )

        users = [
            {
                "username": "few_groups",
                "connected": False,
                "following": False,
                "follower": False,
                "groups": 1,
                "orgs": 0,
            },
            {
                "username": "many_groups",
                "connected": False,
                "following": False,
                "follower": False,
                "groups": 5,
                "orgs": 0,
            },
            {
                "username": "some_orgs",
                "connected": False,
                "following": False,
                "follower": False,
                "groups": 5,
                "orgs": 3,
            },
        ]

        sorted_users = sorted(users, key=user_sort_key)
        assert sorted_users[0]["username"] == "some_orgs"  # Same groups but more orgs
        assert sorted_users[1]["username"] == "many_groups"
        assert sorted_users[2]["username"] == "few_groups"

    def test_sort_alphabetically_as_tiebreaker(self) -> None:
        """Alphabetical order as final tiebreaker."""
        from typing import Tuple

        def user_sort_key(u: dict) -> Tuple[bool, bool, bool, bool, int, int, str]:
            return (
                True,
                True,
                True,
                True,
                -(u.get("groups", 0) or 0),
                -(u.get("orgs", 0) or 0),
                u.get("username", "").lower(),
            )

        users = [
            {"username": "charlie", "connected": False, "following": False, "follower": False, "groups": 0, "orgs": 0},
            {"username": "alice", "connected": False, "following": False, "follower": False, "groups": 0, "orgs": 0},
            {"username": "bob", "connected": False, "following": False, "follower": False, "groups": 0, "orgs": 0},
        ]

        sorted_users = sorted(users, key=user_sort_key)
        assert sorted_users[0]["username"] == "alice"
        assert sorted_users[1]["username"] == "bob"
        assert sorted_users[2]["username"] == "charlie"
