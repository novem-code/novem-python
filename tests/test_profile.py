import configparser
import os
from functools import partial

from novem import Profile
from novem.utils import API_ROOT, get_config_path


def setup_multi_profile_config(fs, api_root):
    """Set up a fake novem.conf file with multiple profiles."""
    config_dir, config_path = get_config_path()
    fs.create_dir(config_dir)

    config_content = f"""[general]
api_root = {api_root}
profile = default_user

[profile:default_user]
username = default_user
token_name = default-token
token = DEFAULT_TOKEN

[profile:other_user]
username = other_user
token_name = other-token
token = OTHER_TOKEN

[app:cli]
version = 0.5.0

[app:python]

[app:fuse]"""

    fs.create_file(config_path, contents=config_content)
    return config_path


def test_profile_read_write(requests_mock):
    """Test reading and writing profile properties."""
    base = os.path.dirname(os.path.abspath(__file__))
    config_file = f"{base}/test.conf"

    config = configparser.ConfigParser()
    config.read(config_file)
    api_root = config["general"]["api_root"]

    profile_name = "Test User"
    profile_bio = "A test bio for the user"
    profile_timezone = "Europe/Oslo"
    profile_url = "https://novem.no/u/testuser"

    gcheck = {
        "name_read": False,
        "name_write": False,
        "bio_read": False,
        "bio_write": False,
        "timezone_read": False,
        "timezone_write": False,
        "public_read": False,
        "public_write": False,
        "url_read": False,
    }

    def verify_write(key, val, request, context):
        gcheck[key] = True
        assert request.text == val
        return ""

    def verify_read(key, val, request, context):
        gcheck[key] = True
        return val

    # Register mock endpoints
    requests_mock.register_uri(
        "get",
        f"{api_root}admin/profile/name",
        text=partial(verify_read, "name_read", profile_name),
    )
    requests_mock.register_uri(
        "post",
        f"{api_root}admin/profile/name",
        text=partial(verify_write, "name_write", profile_name),
    )

    requests_mock.register_uri(
        "get",
        f"{api_root}admin/profile/bio",
        text=partial(verify_read, "bio_read", profile_bio),
    )
    requests_mock.register_uri(
        "post",
        f"{api_root}admin/profile/bio",
        text=partial(verify_write, "bio_write", profile_bio),
    )

    requests_mock.register_uri(
        "get",
        f"{api_root}admin/profile/timezone",
        text=partial(verify_read, "timezone_read", profile_timezone),
    )
    requests_mock.register_uri(
        "post",
        f"{api_root}admin/profile/timezone",
        text=partial(verify_write, "timezone_write", profile_timezone),
    )

    requests_mock.register_uri(
        "get",
        f"{api_root}admin/profile/public",
        text=partial(verify_read, "public_read", "yes"),
    )
    requests_mock.register_uri(
        "post",
        f"{api_root}admin/profile/public",
        text=partial(verify_write, "public_write", "no"),
    )

    requests_mock.register_uri(
        "get",
        f"{api_root}admin/profile/url",
        text=partial(verify_read, "url_read", profile_url),
    )

    # Create profile instance
    p = Profile(config_path=config_file)

    # Test reading properties
    assert p.name == profile_name
    assert gcheck["name_read"] is True

    assert p.bio == profile_bio
    assert gcheck["bio_read"] is True

    assert p.timezone == profile_timezone
    assert gcheck["timezone_read"] is True

    assert p.public is True
    assert gcheck["public_read"] is True

    assert p.url == profile_url
    assert gcheck["url_read"] is True

    # Test writing properties
    p.name = profile_name
    assert gcheck["name_write"] is True

    p.bio = profile_bio
    assert gcheck["bio_write"] is True

    p.timezone = profile_timezone
    assert gcheck["timezone_write"] is True

    p.public = False
    assert gcheck["public_write"] is True

    # Verify all operations were performed
    for k, v in gcheck.items():
        assert v is True, f"Operation {k} was not performed"


def test_profile_public_truthy_values(requests_mock):
    """Test that public property correctly interprets truthy values."""
    base = os.path.dirname(os.path.abspath(__file__))
    config_file = f"{base}/test.conf"

    config = configparser.ConfigParser()
    config.read(config_file)
    api_root = config["general"]["api_root"]

    # Test various truthy values
    truthy_values = ["yes", "Yes", "YES", "true", "True", "TRUE", "1"]
    falsy_values = ["no", "No", "NO", "false", "False", "FALSE", "0", ""]

    for val in truthy_values:
        requests_mock.register_uri(
            "get",
            f"{api_root}admin/profile/public",
            text=val,
        )
        p = Profile(config_path=config_file)
        assert p.public is True, f"Expected True for '{val}'"

    for val in falsy_values:
        requests_mock.register_uri(
            "get",
            f"{api_root}admin/profile/public",
            text=val,
        )
        p = Profile(config_path=config_file)
        assert p.public is False, f"Expected False for '{val}'"


def test_profile_kwargs_init(requests_mock):
    """Test that profile properties can be set via kwargs."""
    base = os.path.dirname(os.path.abspath(__file__))
    config_file = f"{base}/test.conf"

    config = configparser.ConfigParser()
    config.read(config_file)
    api_root = config["general"]["api_root"]

    profile_name = "Kwargs User"
    profile_bio = "Set via kwargs"

    writes = {"name": False, "bio": False, "public": False}

    def verify_write(key, val, request, context):
        writes[key] = True
        assert request.text == val
        return ""

    requests_mock.register_uri(
        "post",
        f"{api_root}admin/profile/name",
        text=partial(verify_write, "name", profile_name),
    )
    requests_mock.register_uri(
        "post",
        f"{api_root}admin/profile/bio",
        text=partial(verify_write, "bio", profile_bio),
    )
    requests_mock.register_uri(
        "post",
        f"{api_root}admin/profile/public",
        text=partial(verify_write, "public", "yes"),
    )

    # Create profile with kwargs
    Profile(
        config_path=config_file,
        name=profile_name,
        bio=profile_bio,
        public=True,
    )

    # Verify properties were set
    assert writes["name"] is True
    assert writes["bio"] is True
    assert writes["public"] is True


def test_profile_selects_correct_config_profile(requests_mock, fs):
    """Test that profile kwarg selects the correct config profile."""
    setup_multi_profile_config(fs, API_ROOT)

    # Mock endpoint to return the name
    requests_mock.register_uri(
        "get",
        f"{API_ROOT}admin/profile/name",
        text="Test Name",
    )

    # Test default profile (no profile kwarg)
    p_default = Profile()
    assert p_default.token == "DEFAULT_TOKEN"

    # Test selecting other profile via 'profile' kwarg
    p_other = Profile(profile="other_user")
    assert p_other.token == "OTHER_TOKEN"

    # Test that 'config_profile' also works (backwards compatibility)
    p_config = Profile(config_profile="other_user")
    assert p_config.token == "OTHER_TOKEN"


def test_profile_with_direct_token(requests_mock, fs):
    """Test that profile works with direct token kwarg."""
    direct_token = "DIRECT_TOKEN_VALUE"

    requests_mock.register_uri(
        "get",
        f"{API_ROOT}admin/profile/name",
        text="Direct Token User",
    )

    # Create profile with direct token (no config needed)
    p = Profile(token=direct_token)
    assert p.token == direct_token
    assert p.name == "Direct Token User"
