from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

from novem import Plot

config_file = str(Path(__file__).resolve().parent / "test.conf")


class FakeResp:
    def __init__(self, status_code=200, text="", headers=None, json_data=None):
        self.status_code = status_code
        self.text = text
        self.headers = headers or {}
        self._json = json_data
        self.ok = 200 <= status_code < 300

    def json(self):
        return self._json


class FakeSession:
    """
    Minimal session that serves a canned remote tree for GET and records
    every state-changing call so the sync behaviour can be asserted.

    `tree` is keyed by api path ("" for root, "/config/type" for a file) and
    maps to either ("file", content) or ("dir", [node, ...]).
    """

    def __init__(self, tree, read_prefix, write_prefix, fail_paths=None):
        self.tree = tree
        self.read_prefix = read_prefix
        self.write_prefix = write_prefix
        # api paths whose POST/DELETE should return a non-ok status
        self.fail_paths = set(fail_paths or [])
        self.puts = []
        self.posts = []
        self.deletes = []

    def get(self, url, **kwargs):
        api_path = url[len(self.read_prefix) :]
        node = self.tree.get(api_path)
        if node is None:
            return FakeResp(status_code=404)
        kind, payload = node
        if kind == "file":
            return FakeResp(text=payload, headers={"X-NVM-Type": "file"})
        return FakeResp(headers={"X-NVM-Type": "dir"}, json_data=payload)

    def put(self, url, **kwargs):
        self.puts.append(url[len(self.write_prefix) :])
        return FakeResp(status_code=201)

    def post(self, url, **kwargs):
        path = url[len(self.write_prefix) :]
        self.posts.append(path)
        return FakeResp(status_code=500 if path in self.fail_paths else 200)

    def delete(self, url, **kwargs):
        path = url[len(self.write_prefix) :]
        self.deletes.append(path)
        return FakeResp(status_code=404 if path in self.fail_paths else 200)


def _make_plot_with_remote(tree, fail_paths=None):
    p = Plot(id="test_plot", create=False, config_path=config_file)
    read_prefix = f"{p._api_root}vis/plots/{p.id}/"
    write_prefix = f"{p._api_root}vis/plots/{p.id}"
    session = FakeSession(tree, read_prefix, write_prefix, fail_paths=fail_paths)
    p._session = session
    return p, session


def _write_local(root, files):
    for rel, content in files.items():
        full = Path(root) / rel
        full.parent.mkdir(parents=True, exist_ok=True)
        full.write_text(content)


# Verbs as the directory listing reports them. A real file_content-backed
# file carries DELETE; virtual/computed files (e.g. `notifications`) accept
# POST but no DELETE; read-only files only GET.
FILE_ACTIONS = ["POST", "GET", "DELETE", "OPTIONS"]
VIRTUAL_ACTIONS = ["POST", "GET", "OPTIONS"]
RO_ACTIONS = ["GET", "OPTIONS"]

REMOTE_TREE = {
    "": (
        "dir",
        [
            {"name": "config", "type": "dir", "permissions": "r", "actions": RO_ACTIONS},
            {"name": "name", "type": "file", "permissions": "rw", "actions": FILE_ACTIONS},
            {"name": "stale", "type": "file", "permissions": "rw", "actions": FILE_ACTIONS},
            # virtual file: writable (POST) but no DELETE -> must be ignored
            {"name": "notifications", "type": "file", "permissions": "rw", "actions": VIRTUAL_ACTIONS},
            # read-only file: no DELETE -> must be ignored
            {"name": "url", "type": "file", "permissions": "r", "actions": RO_ACTIONS},
        ],
    ),
    "/config": ("dir", [{"name": "type", "type": "file", "permissions": "rw", "actions": FILE_ACTIONS}]),
    "/config/type": ("file", "bar"),
    "/name": ("file", "old name"),
    "/stale": ("file", "remove me"),
    # present remotely, but never reached because the walk skips them above
    "/notifications": ("file", "info"),
    "/url": ("file", "https://example/x"),
}


def test_load_sync_creates_overwrites_and_deletes(tmp_path):
    p, session = _make_plot_with_remote(REMOTE_TREE)

    _write_local(
        str(tmp_path),
        {
            "config/type": "bar",  # unchanged
            "name": "new name",  # changed -> overwrite
            "fresh": "brand new",  # new -> create
            # "stale" absent -> delete
        },
    )

    out = StringIO()
    with redirect_stdout(out):
        p.api_load(inpath=str(tmp_path))

    assert session.puts == ["/fresh"]
    assert sorted(session.posts) == ["/fresh", "/name"]
    assert session.deletes == ["/stale"]

    # virtual (notifications) and read-only (url) files are never managed:
    # not created, overwritten, deleted, nor counted as unchanged
    all_calls = session.puts + session.posts + session.deletes
    assert not any("notifications" in c for c in all_calls)
    assert not any("url" in c for c in all_calls)

    summary = out.getvalue()
    assert "1 created, 1 overwritten, 1 deleted, 1 unchanged" in summary
    # single-line values log the actual change rather than a byte count
    assert 'overwrite: /name ("old name" -> "new name")' in summary


def test_load_sync_overwrite_multiline_shows_byte_count(tmp_path):
    # a multi-line body has no useful one-line diff, so fall back to size
    tree = {
        "": ("dir", [{"name": "data", "type": "file", "permissions": "rw", "actions": FILE_ACTIONS}]),
        "/data": ("file", "a,b\n1,2\n"),
    }
    p, session = _make_plot_with_remote(tree)
    _write_local(str(tmp_path), {"data": "a,b\n9,9\n"})

    out = StringIO()
    with redirect_stdout(out):
        p.api_load(inpath=str(tmp_path))

    text = out.getvalue()
    assert "overwrite: /data (8 bytes)" in text
    assert "->" not in text


def test_load_sync_dry_run_sends_nothing(tmp_path):
    p, session = _make_plot_with_remote(REMOTE_TREE)

    _write_local(
        str(tmp_path),
        {
            "config/type": "bar",
            "name": "new name",
            "fresh": "brand new",
        },
    )

    out = StringIO()
    with redirect_stdout(out):
        p.api_load(inpath=str(tmp_path), dry_run=True)

    assert session.puts == []
    assert session.posts == []
    assert session.deletes == []

    text = out.getvalue()
    assert "[dry-run] create:    /fresh" in text
    assert "[dry-run] overwrite: /name" in text
    assert "[dry-run] delete:    /stale" in text
    assert "[dry-run] 1 created, 1 overwritten, 1 deleted, 1 unchanged" in text


def test_load_sync_reports_failed_operations(tmp_path):
    # the server rejects the DELETE of /stale (e.g. no DELETE route) -> the
    # sync must report it as failed, not silently count it as deleted
    p, session = _make_plot_with_remote(REMOTE_TREE, fail_paths={"/stale"})

    _write_local(
        str(tmp_path),
        {
            "config/type": "bar",
            "name": "new name",
            "fresh": "brand new",
        },
    )

    out = StringIO()
    with redirect_stdout(out):
        p.api_load(inpath=str(tmp_path))

    assert session.deletes == ["/stale"]  # the attempt was made

    text = out.getvalue()
    assert "FAILED delete:    /stale (HTTP 404)" in text
    # /stale is counted as failed, not deleted
    assert "1 created, 1 overwritten, 0 deleted, 1 unchanged, 1 failed" in text


def test_load_sync_ignores_local_virtual_file(tmp_path):
    # a stale dump may still contain a `notifications` file on disk; since the
    # remote walk reports it as skipped (virtual, no DELETE), load must ignore
    # the local copy rather than "creating" it on every run
    tree = {
        "": (
            "dir",
            [
                {"name": "name", "type": "file", "permissions": "rw", "actions": FILE_ACTIONS},
                {"name": "notifications", "type": "file", "permissions": "rw", "actions": VIRTUAL_ACTIONS},
            ],
        ),
        "/name": ("file", "hi"),
        "/notifications": ("file", "info"),
    }
    p, session = _make_plot_with_remote(tree)
    _write_local(str(tmp_path), {"name": "hi", "notifications": "info"})

    out = StringIO()
    with redirect_stdout(out):
        p.api_load(inpath=str(tmp_path))

    # notifications is never touched, and there are no phantom actions
    all_calls = session.puts + session.posts + session.deletes
    assert all_calls == []
    assert "0 created, 0 overwritten, 0 deleted, 1 unchanged" in out.getvalue()


def test_load_sync_creates_shares_via_put(tmp_path):
    # shares are links created via PUT (no body); POST 405s. A new share must
    # be created with PUT alone and reported as a success, not a failed POST.
    tree = {
        "": ("dir", [{"name": "shared", "type": "dir", "permissions": "r", "actions": RO_ACTIONS}]),
        "/shared": ("dir", []),  # no shares yet
    }
    p, session = _make_plot_with_remote(tree)
    _write_local(str(tmp_path), {"shared/public": ""})

    out = StringIO()
    with redirect_stdout(out):
        p.api_load(inpath=str(tmp_path))

    assert session.puts == ["/shared/public"]
    assert session.posts == []  # never POST to a share
    text = out.getvalue()
    assert "FAILED" not in text
    assert "1 created, 0 overwritten, 0 deleted, 0 unchanged" in text


def test_load_sync_ignores_tags(tmp_path):
    # tags are managed via the -t flag; the sync must ignore /tags entirely,
    # both remotely (not fetched) and locally (stale dump entries dropped)
    tree = {
        "": (
            "dir",
            [
                {"name": "tags", "type": "dir", "permissions": "rw", "actions": FILE_ACTIONS},
                {"name": "name", "type": "file", "permissions": "rw", "actions": FILE_ACTIONS},
            ],
        ),
        "/name": ("file", "x"),
    }
    p, session = _make_plot_with_remote(tree)
    _write_local(str(tmp_path), {"name": "x", "tags/mytag": ""})

    out = StringIO()
    with redirect_stdout(out):
        p.api_load(inpath=str(tmp_path))

    all_calls = session.puts + session.posts + session.deletes
    assert not any("tags" in c for c in all_calls)
    assert all_calls == []
    assert "0 created, 0 overwritten, 0 deleted, 1 unchanged" in out.getvalue()
