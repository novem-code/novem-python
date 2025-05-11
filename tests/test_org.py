import configparser
import json
import os
import re
from functools import partial

from novem import Org


def test_org_profile_prop(requests_mock):
    org_id = "test_org"
    org_name = "long test name"
    org_description = "long test description"

    base = os.path.dirname(os.path.abspath(__file__))
    config_file = f"{base}/test.conf"

    config = configparser.ConfigParser()
    config.read(config_file)
    api_root = config["general"]["api_root"]

    gcheck = {
        "create": False,
        "desc": False,
        "name": False,
        "is_open": False,
        "enable_subdomain": False,
        "show_description": False,
        "show_members": False,
        "show_profile": False,
    }

    cache = {
        "desc": "NA",
        "name": "NA",
        "is_open": "no",
        "enable_subdomain": "no",
        "show_description": "no",
        "show_members": "no",
        "show_profile": "no",
    }

    def verify_write(key, val, request, context):
        gcheck[key] = True
        cache[key] = val
        assert request.text == val
        return ""

    def verify_read(key, val, request, context):
        gcheck[key] = True
        return cache[key]

    def verify_create(request, context):
        gcheck["create"] = True
        return ""

    # Plot creation endpoint
    requests_mock.register_uri(
        "put",
        f"{api_root}admin/orgs/{org_id}",
        text=verify_create,
    )

    # basic profile settings
    requests_mock.register_uri(
        "post",
        f"{api_root}admin/orgs/{org_id}/profile/name",
        text=partial(verify_write, "name", org_name),
    )
    requests_mock.register_uri(
        "get",
        f"{api_root}admin/orgs/{org_id}/profile/name",
        text=partial(verify_read, "name", org_name),
    )

    requests_mock.register_uri(
        "post",
        f"{api_root}admin/orgs/{org_id}/profile/description",
        text=partial(verify_write, "desc", org_description),
    )

    requests_mock.register_uri(
        "get",
        f"{api_root}admin/orgs/{org_id}/profile/description",
        text=partial(verify_read, "desc", org_description),
    )

    # basic profile options
    for opt in ["is_open", "enable_subdomain", "show_description", "show_members", "show_profile"]:
        requests_mock.register_uri(
            "post", f"{api_root}admin/orgs/{org_id}/profile/options/{opt}", text=partial(verify_write, opt, "yes")
        )
        requests_mock.register_uri(
            "get", f"{api_root}admin/orgs/{org_id}/profile/options/{opt}", text=partial(verify_read, opt, "yes")
        )

    # Create org instance
    n = Org(
        org_id,
        config_path=config_file,
    )

    assert n.profile.name == "NA"
    assert n.profile.description == "NA"

    # Test basic properties
    n.profile.name = org_name
    n.profile.description = org_description

    assert n.profile.name == org_name
    assert n.profile.description == org_description

    assert n.profile.options.is_open is False
    n.profile.options.is_open = True
    assert n.profile.options.is_open is True

    assert n.profile.options.enable_subdomain is False
    n.profile.options.enable_subdomain = True
    assert n.profile.options.enable_subdomain is True

    assert n.profile.options.show_members is False
    n.profile.options.show_members = True
    assert n.profile.options.show_members is True

    assert n.profile.options.show_description is False
    n.profile.options.show_description = True
    assert n.profile.options.show_description is True

    assert n.profile.options.show_profile is False
    n.profile.options.show_profile = True
    assert n.profile.options.show_profile is True

    # Verify all operations were performed
    for k, v in gcheck.items():
        assert v is True, f"Operation {k} was not performed"

    assert n._api_root == "https://api.novem.io/v1/"


def test_org_profile_dict(requests_mock):
    org_id = "test_org"
    org_name = "long test name"
    org_description = "long test description"

    base = os.path.dirname(os.path.abspath(__file__))
    config_file = f"{base}/test.conf"

    config = configparser.ConfigParser()
    config.read(config_file)
    api_root = config["general"]["api_root"]

    gcheck = {
        "create": False,
        "desc": False,
        "name": False,
        "is_open": False,
        "enable_subdomain": False,
        "show_description": False,
        "show_members": False,
        "show_profile": False,
    }

    cache = {
        "desc": "NA",
        "name": "NA",
        "is_open": "no",
        "enable_subdomain": "no",
        "show_description": "no",
        "show_members": "no",
        "show_profile": "no",
    }

    def verify_write(key, val, request, context):
        gcheck[key] = True
        cache[key] = val
        assert request.text == val
        return ""

    def verify_read(key, val, request, context):
        gcheck[key] = True
        return cache[key]

    def verify_create(request, context):
        gcheck["create"] = True
        return ""

    # Plot creation endpoint
    requests_mock.register_uri(
        "put",
        f"{api_root}admin/orgs/{org_id}",
        text=verify_create,
    )

    # basic profile settings
    requests_mock.register_uri(
        "post",
        f"{api_root}admin/orgs/{org_id}/profile/name",
        text=partial(verify_write, "name", org_name),
    )
    requests_mock.register_uri(
        "get",
        f"{api_root}admin/orgs/{org_id}/profile/name",
        text=partial(verify_read, "name", org_name),
    )

    requests_mock.register_uri(
        "post",
        f"{api_root}admin/orgs/{org_id}/profile/description",
        text=partial(verify_write, "desc", org_description),
    )

    requests_mock.register_uri(
        "get",
        f"{api_root}admin/orgs/{org_id}/profile/description",
        text=partial(verify_read, "desc", org_description),
    )

    # basic profile options
    for opt in ["is_open", "enable_subdomain", "show_description", "show_members", "show_profile"]:
        requests_mock.register_uri(
            "post", f"{api_root}admin/orgs/{org_id}/profile/options/{opt}", text=partial(verify_write, opt, "yes")
        )
        requests_mock.register_uri(
            "get", f"{api_root}admin/orgs/{org_id}/profile/options/{opt}", text=partial(verify_read, opt, "yes")
        )

    # Create org instance
    n = Org(
        org_id,
        config_path=config_file,
        profile={
            "name": org_name,
            "description": org_description,
            "options": {
                "is_open": True,
                "enable_subdomain": True,
                "show_members": True,
                "show_description": True,
                "show_profile": True,
            },
        },
    )

    assert n.profile.name == org_name
    assert n.profile.description == org_description
    assert n.profile.options.is_open is True
    assert n.profile.options.enable_subdomain is True
    assert n.profile.options.show_members is True
    assert n.profile.options.show_description is True
    assert n.profile.options.show_profile is True

    # Verify all operations were performed
    for k, v in gcheck.items():
        assert v is True, f"Operation {k} was not performed"

    assert n._api_root == "https://api.novem.io/v1/"


def test_org_roles_prop(requests_mock):
    org_id = "test_org"

    base = os.path.dirname(os.path.abspath(__file__))
    config_file = f"{base}/test.conf"

    config = configparser.ConfigParser()
    config.read(config_file)
    api_root = config["general"]["api_root"]

    gcheck = {
        "create": False,
        "members": False,
        "admins": False,
        "superusers": False,
    }

    cache = {"desc": "NA", "name": "NA", "members": [], "admins": [], "superusers": [], "founders": []}

    def add_cache(key, request, context):

        # Extract user_id from URL
        path_parts = request.path.split("/")
        user_id = path_parts[-1]  # Get the last part of the URL

        cache[key].append(user_id)
        return ""

    def rem_cache(key, request, context):
        cache[key] = [x for x in cache[key] if x != request.text]
        return ""

    def read_cache(key, request, context):
        res = json.dumps([{"name": k} for k in cache[key]])
        return res

    def delete_resource(key, user_id, request, context):
        # Extract user_id from URL
        path_parts = request.path.split("/")
        user_id = path_parts[-1]  # Get the last part of the URL

        # Remove the user from the specified role list
        if user_id in cache[key]:
            cache[key].remove(user_id)

        return ""

    def verify_read(key, val, request, context):
        gcheck[key] = True
        return cache[key]

    def verify_create(request, context):
        gcheck["create"] = True
        return ""

    # Plot creation endpoint
    requests_mock.register_uri(
        "put",
        f"{api_root}admin/orgs/{org_id}",
        text=verify_create,
    )

    # Define all the roles to be mocked
    roles = ["members", "admins", "superusers", "founders"]

    # Register mocks for all roles
    for role in roles:
        # POST - Add a user to a role
        requests_mock.register_uri(
            "put", re.compile(f"{api_root}admin/orgs/{org_id}/roles/{role}/.*"), text=partial(add_cache, role)
        )

        # GET - List all users in a role
        requests_mock.register_uri("get", f"{api_root}admin/orgs/{org_id}/roles/{role}", text=partial(read_cache, role))

        # DELETE - Remove a specific user from a role
        requests_mock.register_uri(
            "delete",
            re.compile(f"{api_root}admin/orgs/{org_id}/roles/{role}/.*"),
            text=partial(delete_resource, role, None),
        )

    # Create org instance
    o = Org(
        org_id,
        config_path=config_file,
    )

    assert len(o.roles.members) == 0
    assert len(o.roles.superusers) == 0
    assert len(o.roles.admins) == 0

    o.roles.members = ["user1", "user2"]
    assert list(o.roles.members) == ["user1", "user2"]
    o.roles.members -= "user2"
    assert list(o.roles.members) == ["user1"]
    o.roles.members += "user3"
    assert list(o.roles.members) == ["user1", "user3"]

    o.roles.superusers = ["suser1", "suser2"]
    assert list(o.roles.superusers) == ["suser1", "suser2"]
    o.roles.superusers -= "suser2"
    assert list(o.roles.superusers) == ["suser1"]
    o.roles.superusers += "suser3"
    assert list(o.roles.superusers) == ["suser1", "suser3"]

    o.roles.admins = ["auser1", "auser2"]
    assert list(o.roles.admins) == ["auser1", "auser2"]
    o.roles.admins -= "auser2"
    assert list(o.roles.admins) == ["auser1"]
    o.roles.admins += "auser3"
    assert list(o.roles.admins) == ["auser1", "auser3"]

    o.roles.founders = ["fuser1", "fuser2"]
    assert list(o.roles.founders) == ["fuser1", "fuser2"]
    o.roles.founders -= "fuser2"
    assert list(o.roles.founders) == ["fuser1"]
    o.roles.founders += "fuser3"
    assert list(o.roles.founders) == ["fuser1", "fuser3"]


def test_org_roles_dict(requests_mock):
    org_id = "test_org"

    base = os.path.dirname(os.path.abspath(__file__))
    config_file = f"{base}/test.conf"

    config = configparser.ConfigParser()
    config.read(config_file)
    api_root = config["general"]["api_root"]

    gcheck = {
        "create": False,
        "members": False,
        "admins": False,
        "superusers": False,
    }

    cache = {"desc": "NA", "name": "NA", "members": [], "admins": [], "superusers": [], "founders": []}

    def add_cache(key, request, context):

        # Extract user_id from URL
        path_parts = request.path.split("/")
        user_id = path_parts[-1]  # Get the last part of the URL

        cache[key].append(user_id)
        return ""

    def rem_cache(key, request, context):
        cache[key] = [x for x in cache[key] if x != request.text]
        return ""

    def read_cache(key, request, context):
        res = json.dumps([{"name": k} for k in cache[key]])
        return res

    def delete_resource(key, user_id, request, context):
        # Extract user_id from URL
        path_parts = request.path.split("/")
        user_id = path_parts[-1]  # Get the last part of the URL

        # Remove the user from the specified role list
        if user_id in cache[key]:
            cache[key].remove(user_id)

        return ""

    def verify_read(key, val, request, context):
        gcheck[key] = True
        return cache[key]

    def verify_create(request, context):
        gcheck["create"] = True
        return ""

    # Plot creation endpoint
    requests_mock.register_uri(
        "put",
        f"{api_root}admin/orgs/{org_id}",
        text=verify_create,
    )

    # Define all the roles to be mocked
    roles = ["members", "admins", "superusers", "founders"]

    # Register mocks for all roles
    for role in roles:
        # POST - Add a user to a role
        requests_mock.register_uri(
            "put", re.compile(f"{api_root}admin/orgs/{org_id}/roles/{role}/.*"), text=partial(add_cache, role)
        )

        # GET - List all users in a role
        requests_mock.register_uri("get", f"{api_root}admin/orgs/{org_id}/roles/{role}", text=partial(read_cache, role))

        # DELETE - Remove a specific user from a role
        requests_mock.register_uri(
            "delete",
            re.compile(f"{api_root}admin/orgs/{org_id}/roles/{role}/.*"),
            text=partial(delete_resource, role, None),
        )

    # Create org instance
    o = Org(
        org_id,
        config_path=config_file,
        roles={
            "members": ["user1", "user3"],
            "admins": ["auser1", "auser3"],
            "founders": ["fuser1", "fuser3"],
            "superusers": ["suser1", "suser3"],
        },
    )

    assert list(o.roles.members) == ["user1", "user3"]
    assert list(o.roles.superusers) == ["suser1", "suser3"]
    assert list(o.roles.admins) == ["auser1", "auser3"]
    assert list(o.roles.founders) == ["fuser1", "fuser3"]


def test_org_permissions(requests_mock):
    org_id = "test_org"

    base = os.path.dirname(os.path.abspath(__file__))
    config_file = f"{base}/test.conf"

    config = configparser.ConfigParser()
    config.read(config_file)
    api_root = config["general"]["api_root"]

    gcheck = {
        "create": False,
    }

    def verify_create(request, context):
        gcheck["create"] = True
        return ""

    # Plot creation endpoint
    requests_mock.register_uri(
        "put",
        f"{api_root}admin/orgs/{org_id}",
        text=verify_create,
    )

    o = Org(org_id, config_path=config_file, permissions="rw")

    assert o.permissions == "rw"
    o.permissions = "x"
    assert o.permissions == "x"
    assert o.w("permissions", "rax").permissions == "rax"
