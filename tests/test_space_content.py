"""Library tests for the native space content API (Space.content)."""

import configparser
import json
import os

import pytest

from novem import Space
from novem.exceptions import Novem404, NovemException

BASE = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = f"{BASE}/test.conf"


def _api_root():
    config = configparser.ConfigParser()
    config.read(CONFIG_FILE)
    return config["general"]["api_root"]


def _space(requests_mock):
    api_root = _api_root()
    requests_mock.register_uri("put", f"{api_root}code/spaces/sp", status_code=201)
    return Space("sp", config_path=CONFIG_FILE), f"{api_root}code/spaces/sp/content"


# --- reads -------------------------------------------------------------------


def test_read_str_and_leading_slash(requests_mock):
    s, base = _space(requests_mock)
    requests_mock.register_uri("get", f"{base}/path/to/doc.json", content=b'{"a": 1}')

    assert s.content["path/to/doc.json"] == '{"a": 1}'
    assert s.content["/path/to/doc.json"] == '{"a": 1}'  # leading slash optional


def test_read_bytes(requests_mock):
    s, base = _space(requests_mock)
    payload = bytes(range(256))
    requests_mock.register_uri("get", f"{base}/logo.png", content=payload)

    assert s.content.read_bytes("logo.png") == payload


def test_read_missing_raises_404_and_get_defaults(requests_mock):
    s, base = _space(requests_mock)
    requests_mock.register_uri("get", f"{base}/nope.txt", status_code=404)

    with pytest.raises(Novem404):
        s.content["nope.txt"]
    assert s.content.get("nope.txt") is None
    assert s.content.get("nope.txt", "fallback") == "fallback"


def test_reading_a_folder_without_slash_is_guided(requests_mock):
    s, base = _space(requests_mock)
    requests_mock.register_uri("get", f"{base}/docs", json=[], headers={"X-NVM-Type": "dir"})

    with pytest.raises(NovemException, match="trailing slash"):
        s.content["docs"]


def test_stat_file(requests_mock):
    s, base = _space(requests_mock)

    def on_get(request, context):
        assert request.headers["Accept"] == "application/json"
        context.status_code = 200
        return json.dumps(
            {
                "kind": "file",
                "name": "doc.json",
                "path": "path/doc.json",
                "size": 42,
                "content_type": "application/json",
                "etag": "abc123",
                "created_on": "Thu, 17 Mar 2022 12:19:02 UTC",
                "last_modified": "Thu, 17 Mar 2022 12:20:02 UTC",
            }
        )

    requests_mock.register_uri("get", f"{base}/path/doc.json", text=on_get)

    info = s.content.stat("path/doc.json")
    assert info.kind == "file"
    assert info.size == 42
    assert info.etag == "abc123"
    assert info.content_type == "application/json"


def test_contains(requests_mock):
    s, base = _space(requests_mock)
    requests_mock.register_uri("get", f"{base}/there.txt", json={"kind": "file", "name": "there.txt"})
    requests_mock.register_uri("get", f"{base}/missing.txt", status_code=404)

    assert "there.txt" in s.content
    assert "missing.txt" not in s.content


# --- folders -----------------------------------------------------------------

LISTING = [
    {"name": "raw", "type": "dir", "created_on": "Thu, 17 Mar 2022 12:19:02 UTC"},
    {
        "name": "q3.csv",
        "type": "file",
        "size": 1234,
        "content_type": "text/csv",
        "ETag": "e1",
        "created_on": "Thu, 17 Mar 2022 12:19:02 UTC",
        "last_modified": "Thu, 17 Mar 2022 12:20:02 UTC",
    },
]


def test_dir_view_iteration_and_relative_access(requests_mock):
    s, base = _space(requests_mock)
    requests_mock.register_uri("get", f"{base}/reports", json=LISTING)
    requests_mock.register_uri("get", f"{base}/reports/q3.csv", content=b"a,b\n1,2\n")

    reports = s.content["reports/"]
    names = [(e.name, e.kind) for e in reports]
    assert names == [("raw", "dir"), ("q3.csv", "file")]

    assert [e.name for e in reports.files] == ["q3.csv"]
    assert [e.name for e in reports.dirs] == ["raw"]
    assert reports.files[0].size == 1234
    assert reports.files[0].etag == "e1"
    assert reports.files[0].path == "reports/q3.csv"
    assert reports.dirs[0].path == "reports/raw/"

    # relative indexing from the folder view
    assert reports["q3.csv"] == "a,b\n1,2\n"


def test_root_listing(requests_mock):
    s, base = _space(requests_mock)
    requests_mock.register_uri("get", base, json=LISTING)

    root = s.content["/"]
    assert [e.name for e in root] == ["raw", "q3.csv"]
    assert [e.name for e in s.content.ls()] == ["raw", "q3.csv"]


def test_walk(requests_mock):
    s, base = _space(requests_mock)
    requests_mock.register_uri("get", base, json=[{"name": "docs", "type": "dir"}, {"name": "a.txt", "type": "file"}])
    requests_mock.register_uri(
        "get", f"{base}/docs", json=[{"name": "deep", "type": "dir"}, {"name": "b.txt", "type": "file"}]
    )
    requests_mock.register_uri("get", f"{base}/docs/deep", json=[{"name": "c.txt", "type": "file"}])

    assert list(s.content.walk()) == [
        ("", ["docs"], ["a.txt"]),
        ("docs/", ["deep"], ["b.txt"]),
        ("docs/deep/", [], ["c.txt"]),
    ]


# --- writes ------------------------------------------------------------------


def test_write_str_sets_content_type_from_extension(requests_mock):
    s, base = _space(requests_mock)
    seen = {}

    def on_put(request, context):
        seen["body"] = request.body
        seen["ct"] = request.headers.get("Content-Type")
        context.status_code = 201
        return ""

    requests_mock.register_uri("put", f"{base}/doc.json", text=on_put)

    s.content["doc.json"] = '{"a": 1}'
    assert seen["body"] == b'{"a": 1}'
    assert seen["ct"] == "application/json"


def test_write_bytes(requests_mock):
    s, base = _space(requests_mock)
    seen = {}

    def on_put(request, context):
        seen["body"] = request.body
        seen["ct"] = request.headers.get("Content-Type")
        context.status_code = 201
        return ""

    requests_mock.register_uri("put", f"{base}/blob.bin", text=on_put)

    s.content["blob.bin"] = b"\x00\x01\x02"
    assert seen["body"] == b"\x00\x01\x02"
    assert seen["ct"] == "application/octet-stream"


def test_write_conditions(requests_mock):
    s, base = _space(requests_mock)
    seen = {}

    def on_put(request, context):
        seen["if_match"] = request.headers.get("If-Match")
        seen["if_none_match"] = request.headers.get("If-None-Match")
        context.status_code = 200
        return ""

    requests_mock.register_uri("put", f"{base}/state.json", text=on_put)

    s.content.write("state.json", "{}", if_match="abc123")
    assert seen["if_match"] == "abc123"

    s.content.write("state.json", "{}", no_clobber=True)
    assert seen["if_none_match"] == "*"


def test_write_conflict_raises(requests_mock):
    s, base = _space(requests_mock)
    requests_mock.register_uri("put", f"{base}/state.json", status_code=412, json={"message": "precondition failed"})

    with pytest.raises(NovemException, match="precondition failed"):
        s.content.write("state.json", "{}", if_match="stale")


def test_write_rejects_folder_path(requests_mock):
    s, base = _space(requests_mock)
    with pytest.raises(NovemException, match="mkdir"):
        s.content.write("docs/", "nope")


def test_mkdir_uses_trailing_slash(requests_mock):
    s, base = _space(requests_mock)
    seen = {}

    def on_put(request, context):
        seen["url"] = request.url
        context.status_code = 201
        return ""

    requests_mock.register_uri("put", f"{base}/data/raw/", text=on_put)

    s.content.mkdir("data/raw")
    assert seen["url"].endswith("/content/data/raw/")


def test_move(requests_mock):
    s, base = _space(requests_mock)
    seen = {}

    def on_patch(request, context):
        seen["body"] = request.json()
        seen["no_clobber"] = request.headers.get("If-None-Match")
        context.status_code = 200
        return ""

    requests_mock.register_uri("patch", f"{base}/draft.md", text=on_patch)

    s.content.move("draft.md", "published/final.md")
    assert seen["body"] == {"to": "published/final.md"}

    s.content.move("/draft.md", "final.md", no_clobber=True)
    assert seen["no_clobber"] == "*"


def test_remove_and_recursive(requests_mock):
    s, base = _space(requests_mock)
    seen = {}

    def on_delete(request, context):
        seen["qs"] = request.qs
        context.status_code = 200
        return ""

    requests_mock.register_uri("delete", f"{base}/tmp.txt", text=on_delete)
    requests_mock.register_uri("delete", f"{base}/data", text=on_delete)

    del s.content["tmp.txt"]
    assert seen["qs"] == {}

    s.content.remove("data/", recursive=True)
    assert seen["qs"] == {"recursive": ["true"]}


def test_paths_are_url_quoted(requests_mock):
    s, base = _space(requests_mock)
    requests_mock.register_uri("get", f"{base}/with%20space/a%20file.txt", content=b"ok")

    assert s.content["with space/a file.txt"] == "ok"


# --- change journal ------------------------------------------------------------


def test_changes_pages_through_journal(requests_mock):
    api_root = _api_root()
    requests_mock.register_uri("put", f"{api_root}code/spaces/sp", status_code=201)
    s = Space("sp", config_path=CONFIG_FILE)

    pages = {
        "0": {
            "changes": [
                {"seq": 1, "path": "a.txt", "change": "create", "type": "file", "etag": "e1"},
                {"seq": 2, "path": "b.txt", "change": "update", "type": "file", "etag": "e2"},
            ],
            "latest_seq": 2,
            "has_more": True,
        },
        "2": {
            "changes": [
                {"seq": 3, "path": "c.txt", "change": "move", "type": "file", "old_path": "b.txt"},
            ],
            "latest_seq": 3,
            "has_more": False,
        },
    }

    def on_get(request, context):
        context.status_code = 200
        return json.dumps(pages[request.qs["since"][0]])

    requests_mock.register_uri("get", f"{api_root}code/spaces/sp/changes", text=on_get)

    changes = list(s.changes())
    assert [(c.seq, c.change, c.path) for c in changes] == [
        (1, "create", "a.txt"),
        (2, "update", "b.txt"),
        (3, "move", "c.txt"),
    ]
    assert changes[2].old_path == "b.txt"
