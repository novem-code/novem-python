"""Tests for CLI organization listing functionality."""

import pytest

from novem.cli.gql import _transform_orgs_response


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
