import os
from unittest.mock import patch

import pytest

from novem import Plot
from novem.utils import API_ROOT, get_config_path


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

[app:python]

[app:fuse]"""

    fs.create_file(config_path, contents=config_content)

    return config_path


def test_fails_without_token(requests_mock, fs):
    with pytest.raises(SystemExit):
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
