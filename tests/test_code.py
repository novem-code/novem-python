"""Library tests for the coding resource classes (Space, Computer, Image).

Path construction and property plumbing against code/{collection}/{id};
follows the shape of test_repo.py.
"""

import configparser
import io
import os
from contextlib import redirect_stdout

from novem import Computer, Image, Space

BASE = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = f"{BASE}/test.conf"


def _api_root():
    config = configparser.ConfigParser()
    config.read(CONFIG_FILE)
    return config["general"]["api_root"]


def test_space_create_and_properties(requests_mock):
    api_root = _api_root()
    gcheck = {}

    def verify_write(key, request, context):
        gcheck[key] = request.text
        context.status_code = 200
        return ""

    def created(request, context):
        gcheck["create"] = True
        context.status_code = 201
        return ""

    requests_mock.register_uri("put", f"{api_root}code/spaces/sp1", text=created)
    for key in ("name", "summary", "description"):
        requests_mock.register_uri(
            "post",
            f"{api_root}code/spaces/sp1/{key}",
            text=lambda request, context, key=key: verify_write(key, request, context),
        )
    requests_mock.register_uri("get", f"{api_root}code/spaces/sp1/url", text="https://novem.no/s/abc")

    s = Space("sp1", config_path=CONFIG_FILE)
    assert gcheck.get("create")

    s.name = "My space"
    s.summary = "A space"
    s.description = "Longer text"
    assert gcheck["name"] == "My space"
    assert gcheck["summary"] == "A space"
    assert gcheck["description"] == "Longer text"
    assert s.url == "https://novem.no/s/abc"


def test_space_user_scoped_reads(requests_mock):
    api_root = _api_root()

    requests_mock.register_uri(
        "get",
        f"{api_root}users/other/code/spaces/team/name",
        text="Team space",
    )

    s = Space("team", user="other", create=False, config_path=CONFIG_FILE)
    assert s.name == "Team space"

    # writes to another user's resource are refused client-side
    f = io.StringIO()
    with redirect_stdout(f):
        s.name = "nope"
    assert "another user's space" in f.getvalue()


def test_computer_status_and_config(requests_mock):
    api_root = _api_root()
    gcheck = {}

    def verify_write(key, request, context):
        gcheck[key] = request.text
        context.status_code = 200
        return ""

    requests_mock.register_uri("put", f"{api_root}code/computers/box", status_code=201)
    requests_mock.register_uri("get", f"{api_root}code/computers/box/status", text="offline\n")
    for key in ("status",):
        requests_mock.register_uri(
            "post",
            f"{api_root}code/computers/box/{key}",
            text=lambda request, context, key=key: verify_write(key, request, context),
        )
    for key in ("type", "cpu", "memory"):
        requests_mock.register_uri(
            "post",
            f"{api_root}code/computers/box/config/{key}",
            text=lambda request, context, key=key: verify_write(f"config/{key}", request, context),
        )
    requests_mock.register_uri("get", f"{api_root}code/computers/box/info", text="state: offline\n")

    c = Computer("box", config_path=CONFIG_FILE)
    assert c.status == "offline"
    assert c.info == "state: offline\n"

    c.status = "online"
    assert gcheck["status"] == "online"

    c.type = "ephemeral"
    assert gcheck["config/type"] == "ephemeral"

    # dict-style config writes each key to /config/{key}
    c.config = {"cpu": 4, "memory": "4Gi"}
    assert gcheck["config/cpu"] == "4"
    assert gcheck["config/memory"] == "4Gi"


def test_computer_compute_connection_uses_resolved_ssl_setting():
    computer = Computer("box", config_path=CONFIG_FILE, ignore_ssl=True, create=False)
    connection = computer.connect()

    assert connection._ignore_ssl is True


def test_image_read_only(requests_mock):
    api_root = _api_root()
    gcheck = {"create": False}

    # no PUT registered: constructing an Image must not attempt a create
    requests_mock.register_uri("get", f"{api_root}code/images/tools/status", text="ready\n")
    requests_mock.register_uri("get", f"{api_root}code/images/tools/config/repo", text="@demo/tools\n")

    def verify_write(request, context):
        gcheck["name"] = request.text
        context.status_code = 200
        return ""

    requests_mock.register_uri("post", f"{api_root}code/images/tools/name", text=verify_write)

    img = Image("tools", config_path=CONFIG_FILE)
    assert img.status == "ready"
    assert img.repo == "@demo/tools"

    # metadata stays writable
    img.name = "Tools image"
    assert gcheck["name"] == "Tools image"

    # create/delete of the image itself are refused client-side
    f = io.StringIO()
    with redirect_stdout(f):
        img.api_create("")
        img.api_delete("")
    assert f.getvalue().count("derived from their source repo") == 2
