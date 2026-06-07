import configparser
import os
from unittest.mock import patch

import pytest

from novem import Plot
from novem.exceptions import NovemAuthError
from novem.utils import API_ROOT, ensure_cli_defaults, get_config_path, get_current_config


def setup_fake_config(fs, token, api_root):
    """Set up a fake novem.conf file in the virtual filesystem"""
    # Create the config directory
    config_dir, config_path = get_config_path()
    fs.create_dir(config_dir)

    # Create the config file with the specified content
    config_content = f"""[general]
api_root = {api_root}
profile = demo

[profile:demo]
username = sondov
token_name = test-token-name
token = {token}

[app:cli]
version = 0.5.0

[app:python]

[app:fuse]"""

    fs.create_file(config_path, contents=config_content)

    return config_path


def test_fails_without_token(requests_mock, fs):
    with pytest.raises(NovemAuthError):
        Plot(id="foo", create=False)


def test_accepts_token_from_kwargs(requests_mock, fs):
    requests_mock.register_uri("get", f"{API_ROOT}vis/plots/foo", text='{"id": "foo"}', status_code=200)
    requests_mock.register_uri("get", f"{API_ROOT}vis/plots/foo/url", text="test-url", status_code=200)

    p = Plot(id="foo", token="test_token", create=False)
    assert p.url == "test-url"
    assert p.token == "test_token"


@patch.dict(os.environ, {"NOVEM_TOKEN": "test_token"})
def test_accepts_token_from_env(requests_mock, fs):
    requests_mock.register_uri("get", f"{API_ROOT}vis/plots/foo", text='{"id": "foo"}', status_code=200)
    requests_mock.register_uri("get", f"{API_ROOT}vis/plots/foo/url", text="test-url", status_code=200)

    p = Plot(id="foo", create=False)
    assert p.url == "test-url"
    assert p.token == "test_token"


NOVEM_API_ROOT_TEST = "https://api.novem.test/v1/"


@patch.dict(
    os.environ,
    {
        "NOVEM_TOKEN": "test_token",
        "NOVEM_API_ROOT": NOVEM_API_ROOT_TEST,
    },
)
def test_accepts_api_root_from_env(requests_mock, fs):
    requests_mock.register_uri("get", f"{NOVEM_API_ROOT_TEST}vis/plots/foo", text='{"id": "foo"}', status_code=200)
    requests_mock.register_uri("get", f"{NOVEM_API_ROOT_TEST}vis/plots/foo/url", text="test-url", status_code=200)

    p = Plot(id="foo", create=False)
    assert p.url == "test-url"
    assert p.token == "test_token"


@patch.dict(os.environ, {"NOVEM_TOKEN": "test_token"})
def test_accepts_api_root_from_kwargs(requests_mock, fs):
    requests_mock.register_uri("get", f"{NOVEM_API_ROOT_TEST}vis/plots/foo", text='{"id": "foo"}', status_code=200)
    requests_mock.register_uri("get", f"{NOVEM_API_ROOT_TEST}vis/plots/foo/url", text="test-url", status_code=200)

    p = Plot(id="foo", api_root=NOVEM_API_ROOT_TEST, create=False)
    assert p.url == "test-url"
    assert p.token == "test_token"


def test_accepts_api_root_from_config(requests_mock, fs):
    requests_mock.register_uri("get", f"{NOVEM_API_ROOT_TEST}vis/plots/foo", text='{"id": "foo"}', status_code=200)
    requests_mock.register_uri("get", f"{NOVEM_API_ROOT_TEST}vis/plots/foo/url", text="test-url", status_code=200)

    setup_fake_config(fs, "test_token", NOVEM_API_ROOT_TEST)

    p = Plot(id="foo", create=False)
    assert p.url == "test-url"
    assert p.token == "test_token"


@patch.dict(
    os.environ,
    {
        "NOVEM_TOKEN": "test_token",
        "NOVEM_API_ROOT": "https://this.is.wrong.com/v1/",
    },
)
def test_accepts_api_root_from_kwargs_over_env(requests_mock, fs):
    requests_mock.register_uri("get", f"{NOVEM_API_ROOT_TEST}vis/plots/foo", text='{"id": "foo"}', status_code=200)
    requests_mock.register_uri("get", f"{NOVEM_API_ROOT_TEST}vis/plots/foo/url", text="test-url", status_code=200)

    p = Plot(id="foo", api_root=NOVEM_API_ROOT_TEST, create=False)
    assert p.url == "test-url"
    assert p.token == "test_token"


def test_accepts_api_root_from_kwargs_over_config(requests_mock, fs):
    requests_mock.register_uri("get", f"{NOVEM_API_ROOT_TEST}vis/plots/foo", text='{"id": "foo"}', status_code=200)
    requests_mock.register_uri("get", f"{NOVEM_API_ROOT_TEST}vis/plots/foo/url", text="test-url", status_code=200)

    setup_fake_config(fs, "test_token", API_ROOT)

    p = Plot(id="foo", api_root=NOVEM_API_ROOT_TEST, create=False)
    assert p.url == "test-url"
    assert p.token == "test_token"


@patch.dict(
    os.environ,
    {
        "NOVEM_API_ROOT": "https://this.is.wrong.com/v1/",
    },
)
def test_accepts_api_root_from_config_over_env(requests_mock, fs):
    requests_mock.register_uri("get", f"{NOVEM_API_ROOT_TEST}vis/plots/foo", text='{"id": "foo"}', status_code=200)
    requests_mock.register_uri("get", f"{NOVEM_API_ROOT_TEST}vis/plots/foo/url", text="test-url", status_code=200)

    setup_fake_config(fs, "test_token", NOVEM_API_ROOT_TEST)

    p = Plot(id="foo", create=False)
    assert p.url == "test-url"
    assert p.token == "test_token"


# Test that kwarg > env
@patch.dict(
    os.environ,
    {
        "NOVEM_TOKEN": "test_token",
        "NOVEM_API_ROOT": "https://this.is.wrong.com/v1/",
    },
)
def test_accepts_api_root_from_kwarg_over_env(requests_mock, fs):
    requests_mock.register_uri("get", f"{NOVEM_API_ROOT_TEST}vis/plots/foo", text='{"id": "foo"}', status_code=200)
    requests_mock.register_uri("get", f"{NOVEM_API_ROOT_TEST}vis/plots/foo/url", text="test-url", status_code=200)

    p = Plot(id="foo", api_root=NOVEM_API_ROOT_TEST, create=False)
    assert p.url == "test-url"
    assert p.token == "test_token"


# ---------------------------------------------------------------------------
# get_current_config env-var fallback tests
# ---------------------------------------------------------------------------


def setup_fake_config_no_token(fs, api_root):
    """Config file with general section but profile missing token."""
    config_dir, config_path = get_config_path()
    fs.create_dir(config_dir)
    config_content = f"""[general]
api_root = {api_root}
profile = demo

[profile:demo]
username = sondov
token_name = test-token-name

[app:cli]
version = 0.5.0
"""
    fs.create_file(config_path, contents=config_content)
    return config_path


def setup_fake_config_no_api_root(fs, token):
    """Config file with token but no api_root anywhere."""
    config_dir, config_path = get_config_path()
    fs.create_dir(config_dir)
    config_content = f"""[general]
profile = demo

[profile:demo]
username = sondov
token_name = test-token-name
token = {token}

[app:cli]
version = 0.5.0
"""
    fs.create_file(config_path, contents=config_content)
    return config_path


@patch.dict(os.environ, {"NOVEM_TOKEN": "env_token", "NOVEM_API_ROOT": NOVEM_API_ROOT_TEST})
def test_get_current_config_env_fallback_no_config(fs):
    """With no config file, get_current_config should fall back to env vars."""
    _, config = get_current_config()
    assert config["token"] == "env_token"
    assert config["api_root"] == NOVEM_API_ROOT_TEST


@patch.dict(os.environ, {"NOVEM_TOKEN": "env_token"})
def test_get_current_config_env_fallback_missing_profile_token(fs):
    """When config exists but profile has no token, env var should fill in."""
    setup_fake_config_no_token(fs, API_ROOT)
    _, config = get_current_config()
    assert config["token"] == "env_token"
    assert config["api_root"] == API_ROOT


@patch.dict(os.environ, {"NOVEM_API_ROOT": NOVEM_API_ROOT_TEST})
def test_get_current_config_env_fallback_api_root_only(fs):
    """When config has no api_root, env var should fill in."""
    setup_fake_config_no_api_root(fs, "config_token")
    _, config = get_current_config()
    assert config["token"] == "config_token"
    assert config["api_root"] == NOVEM_API_ROOT_TEST


def test_get_current_config_default_api_root(fs):
    """When no api_root in config or env, should use hardcoded default."""
    setup_fake_config_no_api_root(fs, "config_token")
    _, config = get_current_config()
    assert config["token"] == "config_token"
    assert config["api_root"] == API_ROOT


@patch.dict(os.environ, {"NOVEM_TOKEN": "env_token"})
def test_get_current_config_config_token_over_env(fs):
    """Config file token should take priority over NOVEM_TOKEN env var."""
    setup_fake_config(fs, "config_token", API_ROOT)
    _, config = get_current_config()
    assert config["token"] == "config_token"


@patch.dict(os.environ, {"NOVEM_API_ROOT": "https://wrong.example.com/v1/"})
def test_get_current_config_config_api_root_over_env(fs):
    """Config file api_root should take priority over NOVEM_API_ROOT env var."""
    setup_fake_config(fs, "config_token", NOVEM_API_ROOT_TEST)
    _, config = get_current_config()
    assert config["api_root"] == NOVEM_API_ROOT_TEST


@patch.dict(os.environ, {"NOVEM_TOKEN": "env_token", "NOVEM_API_ROOT": "https://wrong.example.com/v1/"})
def test_get_current_config_kwargs_over_env(fs):
    """Kwargs should take priority over env vars."""
    _, config = get_current_config(token="kwarg_token", api_root=NOVEM_API_ROOT_TEST)
    assert config["token"] == "kwarg_token"
    assert config["api_root"] == NOVEM_API_ROOT_TEST


# ---------------------------------------------------------------------------
# Minimal / malformed config files should be handled gracefully
# ---------------------------------------------------------------------------


@patch.dict(os.environ, {"NOVEM_TOKEN": "env_token"})
def test_get_current_config_no_general_section(fs):
    """A config file without [general] should fall back to env vars and leave
    the file untouched (no normalization runs without a usable profile)."""
    config_dir, config_path = get_config_path()
    fs.create_dir(config_dir)
    contents = "[some_other_section]\nkey = value\n"
    fs.create_file(config_path, contents=contents)

    ok, config = get_current_config()

    assert ok is False
    assert config["token"] == "env_token"
    assert config["api_root"] == API_ROOT
    # file must not be rewritten when there's no [general]
    assert open(config_path).read() == contents


@patch.dict(os.environ, {"NOVEM_TOKEN": "env_token"})
def test_get_current_config_general_without_profile_key(fs):
    """[general] present but missing the profile key — env fallback, no write."""
    config_dir, config_path = get_config_path()
    fs.create_dir(config_dir)
    contents = "[general]\napi_root = https://example.test/v1/\n"
    fs.create_file(config_path, contents=contents)

    ok, config = get_current_config()

    assert ok is False
    assert config["token"] == "env_token"
    assert open(config_path).read() == contents


def test_get_current_config_adds_missing_app_cli_section(fs):
    """When [general] + profile are valid but [app:cli] is missing, the section
    and its defaults should be written back to the file."""
    config_dir, config_path = get_config_path()
    fs.create_dir(config_dir)
    fs.create_file(
        config_path,
        contents="""[general]
api_root = https://example.test/v1/
profile = demo

[profile:demo]
username = sondov
token = tok
""",
    )

    get_current_config()

    written = configparser.ConfigParser()
    written.read(config_path)
    assert written.has_section("app:cli")
    assert written["app:cli"]["striped"] == "false"
    assert written["app:cli"]["prompt_lines"] == "1"


def test_ensure_cli_defaults_creates_section(fs, tmp_path=None):
    """Direct unit test: ensure_cli_defaults adds the section and defaults."""
    path = "novem.conf"
    fs.create_file(path, contents="[general]\nprofile = demo\n")
    cp = configparser.ConfigParser()
    cp.read(path)

    modified = ensure_cli_defaults(path, cp)

    assert modified is True
    assert cp["app:cli"]["striped"] == "false"
    assert cp["app:cli"]["prompt_lines"] == "1"

    # second call should be a no-op
    cp2 = configparser.ConfigParser()
    cp2.read(path)
    assert ensure_cli_defaults(path, cp2) is False


def test_ensure_cli_defaults_preserves_existing_values(fs):
    """Existing values in [app:cli] must not be overwritten."""
    path = "novem.conf"
    fs.create_file(
        path,
        contents="""[general]
profile = demo

[app:cli]
striped = true
prompt_lines = 5
""",
    )
    cp = configparser.ConfigParser()
    cp.read(path)

    modified = ensure_cli_defaults(path, cp)

    assert modified is False
    assert cp["app:cli"]["striped"] == "true"
    assert cp["app:cli"]["prompt_lines"] == "5"
