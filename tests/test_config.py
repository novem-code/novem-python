import os
from unittest.mock import patch

import pytest

from novem import Plot
from novem.utils import API_ROOT


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
