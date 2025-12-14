"""Tests for CLI organization listing functionality."""

import pytest

from novem.cli.gql import _transform_org_members_response, _transform_orgs_response


class TestTransformOrgsResponse:
    """Tests for _transform_orgs_response in gql.py."""

    def test_basic_transform_founder(self) -> None:
        """Test basic org transformation for founder role."""
        data = {
            "me": {
                "founder": [
                    {
                        "id": "my_org",
                        "type": "org",
                        "name": "My Organization",
                        "public": True,
                        "is_open": False,
                        "enable_subdomain": True,
                        "groups": [{"id": "g1"}, {"id": "g2"}],
                        "founders": [{"username": "me"}],
                        "admins": [{"username": "admin1"}],
                        "superusers": [],
                        "members": [{"username": "member1"}, {"username": "member2"}],
                        "created": "2024-01-15T10:00:00Z",
                    }
                ],
                "admin": [],
                "superuser": [],
                "member": [],
            }
        }

        result = _transform_orgs_response(data)
        assert len(result) == 1

        org = result[0]
        assert org["id"] == "my_org"
        assert org["name"] == "My Organization"
        assert org["role"] == "founder"
        assert org["public"] is True
        assert org["is_open"] is False
        assert org["enable_subdomain"] is True
        assert org["groups_count"] == 2
        assert org["members_count"] == 4  # 1 founder + 1 admin + 0 superusers + 2 members
        assert org["created"] == "2024-01-15T10:00:00Z"

    def test_member_count_sums_all_roles(self) -> None:
        """Test that members_count sums founders + admins + superusers + members."""
        data = {
            "me": {
                "founder": [
                    {
                        "id": "test_org",
                        "type": "org",
                        "name": "Test Org",
                        "public": False,
                        "is_open": False,
                        "enable_subdomain": False,
                        "groups": [],
                        "founders": [{"username": "f1"}, {"username": "f2"}],
                        "admins": [{"username": "a1"}, {"username": "a2"}, {"username": "a3"}],
                        "superusers": [{"username": "s1"}],
                        "members": [{"username": "m1"}, {"username": "m2"}, {"username": "m3"}, {"username": "m4"}],
                        "created": "2024-01-01T00:00:00Z",
                    }
                ],
                "admin": [],
                "superuser": [],
                "member": [],
            }
        }

        result = _transform_orgs_response(data)
        assert result[0]["members_count"] == 10  # 2 + 3 + 1 + 4

    def test_role_priority_founder_first(self) -> None:
        """Test that founder role takes priority over other roles for same org."""
        data = {
            "me": {
                "founder": [
                    {
                        "id": "dual_role_org",
                        "type": "org",
                        "name": "Dual Role Org",
                        "public": False,
                        "is_open": False,
                        "enable_subdomain": False,
                        "groups": [],
                        "founders": [{"username": "me"}],
                        "admins": [],
                        "superusers": [],
                        "members": [],
                        "created": "2024-01-01T00:00:00Z",
                    }
                ],
                "admin": [
                    {
                        "id": "dual_role_org",  # Same org appears in admin list too
                        "type": "org",
                        "name": "Dual Role Org",
                        "public": False,
                        "is_open": False,
                        "enable_subdomain": False,
                        "groups": [],
                        "founders": [{"username": "me"}],
                        "admins": [],
                        "superusers": [],
                        "members": [],
                        "created": "2024-01-01T00:00:00Z",
                    }
                ],
                "superuser": [],
                "member": [],
            }
        }

        result = _transform_orgs_response(data)
        assert len(result) == 1  # Deduped
        assert result[0]["role"] == "founder"  # Highest role kept

    def test_filters_non_org_types(self) -> None:
        """Test that non-org types (org_group, user_group) are filtered out."""
        data = {
            "me": {
                "founder": [
                    {
                        "id": "my_org",
                        "type": "org",
                        "name": "My Org",
                        "public": False,
                        "is_open": False,
                        "enable_subdomain": False,
                        "groups": [],
                        "founders": [],
                        "admins": [],
                        "superusers": [],
                        "members": [],
                        "created": "2024-01-01T00:00:00Z",
                    },
                    {
                        "id": "my_group",
                        "type": "org_group",  # Should be filtered out
                        "name": "My Group",
                        "public": False,
                        "is_open": False,
                        "enable_subdomain": False,
                        "groups": [],
                        "founders": [],
                        "admins": [],
                        "superusers": [],
                        "members": [],
                        "created": "2024-01-01T00:00:00Z",
                    },
                ],
                "admin": [],
                "superuser": [],
                "member": [],
            }
        }

        result = _transform_orgs_response(data)
        assert len(result) == 1
        assert result[0]["id"] == "my_org"

    def test_multiple_orgs_different_roles(self) -> None:
        """Test multiple orgs with different roles."""
        data = {
            "me": {
                "founder": [
                    {
                        "id": "org_a",
                        "type": "org",
                        "name": "Org A",
                        "public": False,
                        "is_open": False,
                        "enable_subdomain": False,
                        "groups": [],
                        "founders": [{"username": "me"}],
                        "admins": [],
                        "superusers": [],
                        "members": [],
                        "created": "2024-01-01T00:00:00Z",
                    }
                ],
                "admin": [
                    {
                        "id": "org_b",
                        "type": "org",
                        "name": "Org B",
                        "public": True,
                        "is_open": True,
                        "enable_subdomain": False,
                        "groups": [{"id": "g1"}],
                        "founders": [{"username": "other"}],
                        "admins": [{"username": "me"}],
                        "superusers": [],
                        "members": [],
                        "created": "2024-02-01T00:00:00Z",
                    }
                ],
                "superuser": [],
                "member": [
                    {
                        "id": "org_c",
                        "type": "org",
                        "name": "Org C",
                        "public": False,
                        "is_open": False,
                        "enable_subdomain": True,
                        "groups": [],
                        "founders": [{"username": "owner"}],
                        "admins": [],
                        "superusers": [],
                        "members": [{"username": "me"}, {"username": "other"}],
                        "created": "2024-03-01T00:00:00Z",
                    }
                ],
            }
        }

        result = _transform_orgs_response(data)
        assert len(result) == 3

        # Check each org
        org_a = next(o for o in result if o["id"] == "org_a")
        assert org_a["role"] == "founder"
        assert org_a["members_count"] == 1

        org_b = next(o for o in result if o["id"] == "org_b")
        assert org_b["role"] == "admin"
        assert org_b["public"] is True
        assert org_b["is_open"] is True
        assert org_b["groups_count"] == 1
        assert org_b["members_count"] == 2

        org_c = next(o for o in result if o["id"] == "org_c")
        assert org_c["role"] == "member"
        assert org_c["enable_subdomain"] is True
        assert org_c["members_count"] == 3

    def test_empty_me_response(self) -> None:
        """Test handling of empty me response."""
        data = {"me": None}
        result = _transform_orgs_response(data)
        assert result == []

    def test_empty_role_lists(self) -> None:
        """Test handling of empty role lists."""
        data = {
            "me": {
                "founder": [],
                "admin": [],
                "superuser": [],
                "member": [],
            }
        }
        result = _transform_orgs_response(data)
        assert result == []

    def test_null_fields_handled(self) -> None:
        """Test that null fields are handled gracefully."""
        data = {
            "me": {
                "founder": [
                    {
                        "id": "org_null",
                        "type": "org",
                        "name": None,
                        "public": None,
                        "is_open": None,
                        "enable_subdomain": None,
                        "groups": None,
                        "founders": None,
                        "admins": None,
                        "superusers": None,
                        "members": None,
                        "created": None,
                    }
                ],
                "admin": None,
                "superuser": None,
                "member": None,
            }
        }

        result = _transform_orgs_response(data)
        assert len(result) == 1

        org = result[0]
        assert org["id"] == "org_null"
        assert org["name"] == ""
        assert org["public"] is False
        assert org["is_open"] is False
        assert org["enable_subdomain"] is False
        assert org["groups_count"] == 0
        assert org["members_count"] == 0
        assert org["created"] == ""


class TestOrgStateFlags:
    """Tests for org state flag combinations."""

    @pytest.fixture
    def org_with_state(self) -> dict:
        """Create an org with configurable state flags."""

        def _create(public: bool = False, is_open: bool = False, enable_subdomain: bool = False) -> dict:
            return {
                "me": {
                    "founder": [
                        {
                            "id": "test_org",
                            "type": "org",
                            "name": "Test",
                            "public": public,
                            "is_open": is_open,
                            "enable_subdomain": enable_subdomain,
                            "groups": [],
                            "founders": [],
                            "admins": [],
                            "superusers": [],
                            "members": [],
                            "created": "",
                        }
                    ],
                    "admin": [],
                    "superuser": [],
                    "member": [],
                }
            }

        return _create

    def test_all_flags_false(self, org_with_state: dict) -> None:
        data = org_with_state(public=False, is_open=False, enable_subdomain=False)
        result = _transform_orgs_response(data)
        assert result[0]["public"] is False
        assert result[0]["is_open"] is False
        assert result[0]["enable_subdomain"] is False

    def test_public_only(self, org_with_state: dict) -> None:
        data = org_with_state(public=True, is_open=False, enable_subdomain=False)
        result = _transform_orgs_response(data)
        assert result[0]["public"] is True
        assert result[0]["is_open"] is False
        assert result[0]["enable_subdomain"] is False

    def test_is_open_only(self, org_with_state: dict) -> None:
        data = org_with_state(public=False, is_open=True, enable_subdomain=False)
        result = _transform_orgs_response(data)
        assert result[0]["public"] is False
        assert result[0]["is_open"] is True
        assert result[0]["enable_subdomain"] is False

    def test_subdomain_only(self, org_with_state: dict) -> None:
        data = org_with_state(public=False, is_open=False, enable_subdomain=True)
        result = _transform_orgs_response(data)
        assert result[0]["public"] is False
        assert result[0]["is_open"] is False
        assert result[0]["enable_subdomain"] is True

    def test_all_flags_true(self, org_with_state: dict) -> None:
        data = org_with_state(public=True, is_open=True, enable_subdomain=True)
        result = _transform_orgs_response(data)
        assert result[0]["public"] is True
        assert result[0]["is_open"] is True
        assert result[0]["enable_subdomain"] is True


class TestOrgSorting:
    """Tests for org sorting logic."""

    def test_sort_by_role_priority(self) -> None:
        """Test that orgs are sorted by role priority."""
        role_order = {"founder": 0, "admin": 1, "superuser": 2, "member": 3}

        orgs = [
            {"id": "org_member", "role": "member", "name": "A Org"},
            {"id": "org_founder", "role": "founder", "name": "B Org"},
            {"id": "org_admin", "role": "admin", "name": "C Org"},
            {"id": "org_superuser", "role": "superuser", "name": "D Org"},
        ]

        sorted_orgs = sorted(orgs, key=lambda x: (role_order.get(x["role"], 3), x["name"].lower()))

        assert sorted_orgs[0]["role"] == "founder"
        assert sorted_orgs[1]["role"] == "admin"
        assert sorted_orgs[2]["role"] == "superuser"
        assert sorted_orgs[3]["role"] == "member"

    def test_sort_by_name_within_role(self) -> None:
        """Test that orgs with same role are sorted by name."""
        role_order = {"founder": 0, "admin": 1, "superuser": 2, "member": 3}

        orgs = [
            {"id": "org_c", "role": "admin", "name": "Charlie Corp"},
            {"id": "org_a", "role": "admin", "name": "Alpha Inc"},
            {"id": "org_b", "role": "admin", "name": "Beta LLC"},
        ]

        sorted_orgs = sorted(orgs, key=lambda x: (role_order.get(x["role"], 3), x["name"].lower()))

        assert sorted_orgs[0]["name"] == "Alpha Inc"
        assert sorted_orgs[1]["name"] == "Beta LLC"
        assert sorted_orgs[2]["name"] == "Charlie Corp"

    def test_sort_case_insensitive(self) -> None:
        """Test that name sorting is case-insensitive."""
        role_order = {"founder": 0, "admin": 1, "superuser": 2, "member": 3}

        orgs = [
            {"id": "org_upper", "role": "member", "name": "ZEBRA"},
            {"id": "org_lower", "role": "member", "name": "alpha"},
            {"id": "org_mixed", "role": "member", "name": "Beta"},
        ]

        sorted_orgs = sorted(orgs, key=lambda x: (role_order.get(x["role"], 3), x["name"].lower()))

        assert sorted_orgs[0]["name"] == "alpha"
        assert sorted_orgs[1]["name"] == "Beta"
        assert sorted_orgs[2]["name"] == "ZEBRA"


class TestTransformOrgMembersResponse:
    """Tests for _transform_org_members_response in gql.py."""

    def test_basic_member_extraction(self) -> None:
        """Test basic extraction of org members with roles."""
        data = {
            "groups": [
                {
                    "id": "test_org",
                    "founders": [
                        {
                            "username": "founder1",
                            "name": "Founder One",
                            "type": "VERIFIED",
                            "public": True,
                            "relationship": {
                                "follower": False,
                                "connected": True,
                                "following": True,
                                "ignoring": False,
                            },
                        }
                    ],
                    "admins": [
                        {
                            "username": "admin1",
                            "name": "Admin One",
                            "type": "REGULAR",
                            "public": False,
                            "relationship": {
                                "follower": True,
                                "connected": False,
                                "following": False,
                                "ignoring": False,
                            },
                        }
                    ],
                    "superusers": [],
                    "members": [
                        {
                            "username": "member1",
                            "name": "Member One",
                            "type": "REGULAR",
                            "public": False,
                            "relationship": None,
                        }
                    ],
                    "groups": [],
                }
            ]
        }

        result = _transform_org_members_response(data, "current_user")
        assert len(result) == 3

        # Check founder
        founder = next(m for m in result if m["username"] == "founder1")
        assert founder["role"] == "founder"
        assert founder["name"] == "Founder One"
        assert founder["type"] == "VERIFIED"
        assert founder["public"] is True
        assert founder["connected"] is True
        assert founder["following"] is True
        assert founder["is_me"] is False

        # Check admin
        admin = next(m for m in result if m["username"] == "admin1")
        assert admin["role"] == "admin"
        assert admin["follower"] is True

        # Check member
        member = next(m for m in result if m["username"] == "member1")
        assert member["role"] == "member"

    def test_role_deduplication_highest_wins(self) -> None:
        """Test that when a user has multiple roles, highest role wins."""
        data = {
            "groups": [
                {
                    "id": "test_org",
                    "founders": [
                        {
                            "username": "multi_role",
                            "name": "Multi Role User",
                            "type": "REGULAR",
                            "public": False,
                            "relationship": None,
                        }
                    ],
                    "admins": [
                        {
                            "username": "multi_role",  # Same user
                            "name": "Multi Role User",
                            "type": "REGULAR",
                            "public": False,
                            "relationship": None,
                        }
                    ],
                    "superusers": [],
                    "members": [
                        {
                            "username": "multi_role",  # Same user again
                            "name": "Multi Role User",
                            "type": "REGULAR",
                            "public": False,
                            "relationship": None,
                        }
                    ],
                    "groups": [],
                }
            ]
        }

        result = _transform_org_members_response(data, "other_user")
        assert len(result) == 1
        assert result[0]["username"] == "multi_role"
        assert result[0]["role"] == "founder"  # Highest role wins

    def test_current_user_is_me_flag(self) -> None:
        """Test that is_me flag is set correctly for current user."""
        data = {
            "groups": [
                {
                    "id": "test_org",
                    "founders": [],
                    "admins": [],
                    "superusers": [],
                    "members": [
                        {
                            "username": "current_user",
                            "name": "Current User",
                            "type": "REGULAR",
                            "public": False,
                            "relationship": None,
                        },
                        {
                            "username": "other_user",
                            "name": "Other User",
                            "type": "REGULAR",
                            "public": False,
                            "relationship": None,
                        },
                    ],
                    "groups": [],
                }
            ]
        }

        result = _transform_org_members_response(data, "current_user")
        current = next(m for m in result if m["username"] == "current_user")
        other = next(m for m in result if m["username"] == "other_user")

        assert current["is_me"] is True
        assert other["is_me"] is False

    def test_vis_count_from_org_groups(self) -> None:
        """Test that vis counts are correctly calculated from org groups."""
        data = {
            "groups": [
                {
                    "id": "test_org",
                    "founders": [
                        {
                            "username": "author1",
                            "name": "Author One",
                            "type": "REGULAR",
                            "public": False,
                            "relationship": None,
                        }
                    ],
                    "admins": [],
                    "superusers": [],
                    "members": [
                        {
                            "username": "author2",
                            "name": "Author Two",
                            "type": "REGULAR",
                            "public": False,
                            "relationship": None,
                        }
                    ],
                    "groups": [
                        {
                            "id": "group1",
                            "plots": [
                                {"id": "plot1", "author": {"username": "author1"}},
                                {"id": "plot2", "author": {"username": "author1"}},
                                {"id": "plot3", "author": {"username": "author2"}},
                            ],
                            "grids": [
                                {"id": "grid1", "author": {"username": "author1"}},
                            ],
                            "mails": [],
                            "docs": [],
                            "repos": [],
                            "jobs": [],
                        },
                        {
                            "id": "group2",
                            "plots": [
                                {"id": "plot4", "author": {"username": "author2"}},
                            ],
                            "grids": [],
                            "mails": [
                                {"id": "mail1", "author": {"username": "author2"}},
                            ],
                            "docs": [],
                            "repos": [],
                            "jobs": [],
                        },
                    ],
                }
            ]
        }

        result = _transform_org_members_response(data, "other")
        author1 = next(m for m in result if m["username"] == "author1")
        author2 = next(m for m in result if m["username"] == "author2")

        # author1 has 2 plots and 1 grid
        assert author1["plots"] == 2
        assert author1["grids"] == 1
        assert author1["mails"] == 0

        # author2 has 2 plots (plot3 + plot4) and 1 mail
        assert author2["plots"] == 2
        assert author2["grids"] == 0
        assert author2["mails"] == 1

    def test_vis_deduplication_across_groups(self) -> None:
        """Test that vis IDs are deduplicated when shared with multiple groups."""
        data = {
            "groups": [
                {
                    "id": "test_org",
                    "founders": [
                        {
                            "username": "author1",
                            "name": "Author",
                            "type": "REGULAR",
                            "public": False,
                            "relationship": None,
                        }
                    ],
                    "admins": [],
                    "superusers": [],
                    "members": [],
                    "groups": [
                        {
                            "id": "group1",
                            "plots": [
                                {"id": "plot1", "author": {"username": "author1"}},
                                {"id": "plot2", "author": {"username": "author1"}},
                            ],
                            "grids": [],
                            "mails": [],
                            "docs": [],
                            "repos": [],
                            "jobs": [],
                        },
                        {
                            "id": "group2",
                            "plots": [
                                {"id": "plot1", "author": {"username": "author1"}},  # Same plot ID
                                {"id": "plot3", "author": {"username": "author1"}},
                            ],
                            "grids": [],
                            "mails": [],
                            "docs": [],
                            "repos": [],
                            "jobs": [],
                        },
                    ],
                }
            ]
        }

        result = _transform_org_members_response(data, "other")
        author = result[0]

        # Should be 3 unique plots (plot1, plot2, plot3), not 4
        assert author["plots"] == 3

    def test_empty_org(self) -> None:
        """Test handling of empty org (no members)."""
        data = {
            "groups": [
                {
                    "id": "empty_org",
                    "founders": [],
                    "admins": [],
                    "superusers": [],
                    "members": [],
                    "groups": [],
                }
            ]
        }

        result = _transform_org_members_response(data, "user")
        assert result == []

    def test_no_groups_in_response(self) -> None:
        """Test handling when groups list is empty."""
        data = {"groups": []}
        result = _transform_org_members_response(data, "user")
        assert result == []

    def test_null_groups_in_response(self) -> None:
        """Test handling when groups is null."""
        data = {"groups": None}
        result = _transform_org_members_response(data, "user")
        assert result == []

    def test_vis_from_non_member_not_counted(self) -> None:
        """Test that vis from non-org-members are not counted."""
        data = {
            "groups": [
                {
                    "id": "test_org",
                    "founders": [
                        {
                            "username": "member1",
                            "name": "Member",
                            "type": "REGULAR",
                            "public": False,
                            "relationship": None,
                        }
                    ],
                    "admins": [],
                    "superusers": [],
                    "members": [],
                    "groups": [
                        {
                            "id": "group1",
                            "plots": [
                                {"id": "plot1", "author": {"username": "member1"}},
                                {"id": "plot2", "author": {"username": "non_member"}},  # Not in org
                            ],
                            "grids": [],
                            "mails": [],
                            "docs": [],
                            "repos": [],
                            "jobs": [],
                        }
                    ],
                }
            ]
        }

        result = _transform_org_members_response(data, "other")
        assert len(result) == 1  # Only member1

        member = result[0]
        assert member["plots"] == 1  # Only plot1, not plot2


class TestOrgMemberSorting:
    """Tests for org member sorting logic."""

    def test_sort_current_user_first(self) -> None:
        """Test that current user is sorted first."""
        role_order = {"founder": 0, "admin": 1, "superuser": 2, "member": 3}

        def sort_key(u: dict) -> tuple:
            return (
                not u.get("is_me", False),
                role_order.get(u.get("role", "member"), 3),
                not u.get("connected", False),
                u.get("username", "").lower(),
            )

        members = [
            {"username": "founder", "role": "founder", "is_me": False, "connected": True},
            {"username": "me", "role": "member", "is_me": True, "connected": False},
            {"username": "admin", "role": "admin", "is_me": False, "connected": True},
        ]

        sorted_members = sorted(members, key=sort_key)
        assert sorted_members[0]["username"] == "me"  # Current user first despite being member

    def test_sort_by_role_after_current_user(self) -> None:
        """Test that after current user, sorting is by role."""
        role_order = {"founder": 0, "admin": 1, "superuser": 2, "member": 3}

        def sort_key(u: dict) -> tuple:
            return (
                not u.get("is_me", False),
                role_order.get(u.get("role", "member"), 3),
                not u.get("connected", False),
                u.get("username", "").lower(),
            )

        members = [
            {"username": "member1", "role": "member", "is_me": False, "connected": True},
            {"username": "founder1", "role": "founder", "is_me": False, "connected": False},
            {"username": "admin1", "role": "admin", "is_me": False, "connected": True},
        ]

        sorted_members = sorted(members, key=sort_key)
        assert sorted_members[0]["role"] == "founder"
        assert sorted_members[1]["role"] == "admin"
        assert sorted_members[2]["role"] == "member"

    def test_sort_connected_within_role(self) -> None:
        """Test that connected users come before non-connected within same role."""
        role_order = {"founder": 0, "admin": 1, "superuser": 2, "member": 3}

        def sort_key(u: dict) -> tuple:
            return (
                not u.get("is_me", False),
                role_order.get(u.get("role", "member"), 3),
                not u.get("connected", False),
                u.get("username", "").lower(),
            )

        members = [
            {"username": "not_connected", "role": "member", "is_me": False, "connected": False},
            {"username": "connected", "role": "member", "is_me": False, "connected": True},
        ]

        sorted_members = sorted(members, key=sort_key)
        assert sorted_members[0]["username"] == "connected"
        assert sorted_members[1]["username"] == "not_connected"
