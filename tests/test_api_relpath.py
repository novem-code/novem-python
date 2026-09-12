"""A resource-relative path is accepted with or without its leading slash.

The path builders concatenate straight onto the resource root, so an
unprefixed relpath used to yield ".../my-plotconfig/type".
"""

import pytest
import requests_mock as rm_mod

from novem import Job
from novem.code import Space
from novem.vis.plot import Plot

API_ROOT = "https://api.novem.io/v1/"


def mk(cls, **kwargs):
    return cls("res", api_root=API_ROOT, ignore_config=True, create=False, token="nbt-toktok", **kwargs)


@pytest.fixture
def plot():
    return mk(Plot)


@pytest.fixture
def job():
    return mk(Job)


@pytest.fixture
def space():
    return mk(Space)


def urls_for(requests_mock, method, call):
    """Return the URL produced with and without a leading slash."""
    requests_mock.register_uri(method, rm_mod.ANY, text="", status_code=200)
    call("config/type")
    without = requests_mock.last_request.url
    call("/config/type")
    with_ = requests_mock.last_request.url
    return without, with_


@pytest.mark.parametrize("res", ["plot", "job", "space"])
@pytest.mark.parametrize(
    "method,attr",
    [("GET", "api_read"), ("DELETE", "api_delete"), ("PUT", "api_create")],
)
def test_relpath_slash_optional(request, requests_mock, res, method, attr):
    obj = request.getfixturevalue(res)
    without, with_ = urls_for(requests_mock, method, getattr(obj, attr))
    assert without == with_
    assert "restconfig" not in without


@pytest.mark.parametrize("res", ["plot", "job", "space"])
def test_relpath_slash_optional_on_write(request, requests_mock, res):
    obj = request.getfixturevalue(res)
    without, with_ = urls_for(requests_mock, "POST", lambda p: obj.api_write(p, "value"))
    assert without == with_
    assert "restconfig" not in without


def test_relpath_slash_optional_on_read_bytes(plot, requests_mock):
    without, with_ = urls_for(requests_mock, "GET", plot.api_read_bytes)
    assert without == with_


def test_empty_relpath_addresses_the_resource_root(job, requests_mock):
    """_path("") is the resource itself and must not gain a trailing slash."""
    assert job._path("") == f"{API_ROOT}code/jobs/res"


def test_vis_user_path_is_get_only(requests_mock):
    """Reads may target another user; writes are refused rather than retargeted."""
    p = mk(Plot, user="other")

    requests_mock.register_uri("GET", rm_mod.ANY, text="", status_code=200)
    p.api_read("config/type")
    assert requests_mock.last_request.url == f"{API_ROOT}users/other/vis/plots/res/config/type"

    before = requests_mock.call_count
    p.api_write("config/type", "value")
    assert requests_mock.call_count == before, "a write against another user must not reach the API"
