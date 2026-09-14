"""A repo's commit history must not be expanded by an unqualified walk.

Every entry under ``/commits`` is a directory holding that commit's whole
file tree, so recursing into it re-reads the repo once per commit and grows
without bound as history accumulates.
"""

from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

from novem import Repo
from novem.code import Space

config_file = str(Path(__file__).resolve().parent / "test.conf")

FILE_ACTIONS = ["POST", "GET", "DELETE", "OPTIONS"]


def _dir(*names):
    return ("dir", [{"name": n, "type": t, "permissions": "rw", "actions": FILE_ACTIONS} for n, t in names])


# A repo with two commits, each exposing its full tree under files/.
TREE = {
    "": _dir(("commits", "dir"), ("src", "dir"), ("README", "file")),
    "/README": ("file", "readme"),
    "/src": _dir(("main.py", "file")),
    "/src/main.py": ("file", "print(1)"),
    "/commits": _dir(("sha1", "dir"), ("sha2", "dir")),
    "/commits/sha1": _dir(("message", "file"), ("files", "dir")),
    "/commits/sha1/message": ("file", "first"),
    "/commits/sha1/files": _dir(("a.txt", "file"), ("sub", "dir")),
    "/commits/sha1/files/a.txt": ("file", "a"),
    "/commits/sha1/files/sub": _dir(("b.txt", "file")),
    "/commits/sha1/files/sub/b.txt": ("file", "b"),
    "/commits/sha2": _dir(("message", "file"), ("files", "dir")),
    "/commits/sha2/message": ("file", "second"),
    "/commits/sha2/files": _dir(("a.txt", "file")),
    "/commits/sha2/files/a.txt": ("file", "a"),
}


class FakeResp:
    def __init__(self, status_code=200, text="", headers=None, json_data=None):
        self.status_code = status_code
        self.text = text
        self.headers = headers or {}
        self._json = json_data
        self.ok = 200 <= status_code < 300

    def json(self):
        return self._json


class RecordingSession:
    """Serve the canned tree and record every api path GET touches.

    Walk paths are built by concatenation and arrive with doubled slashes
    (``//commits``), exactly as the real client sends them; the server
    normalises those, so this does too.
    """

    def __init__(self, tree, prefix):
        self.tree = tree
        self.prefix = prefix
        self.gets = []

    def get(self, url, **kwargs):
        raw = url[len(self.prefix) :]
        api_path = "/" + "/".join(p for p in raw.split("/") if p)
        api_path = "" if api_path == "/" else api_path
        self.gets.append(api_path)

        node = self.tree.get(api_path)
        if node is None:
            return FakeResp(status_code=404)
        kind, payload = node
        if kind == "file":
            return FakeResp(text=payload, headers={"X-NVM-Type": "file"})
        return FakeResp(
            headers={"X-NVM-Type": "dir", "X-NVM-Permissions": "r, w"},
            json_data=payload,
        )


def _with_remote(obj):
    session = RecordingSession(TREE, obj._path())
    obj._session = session
    return obj, session


def _repo():
    return _with_remote(Repo(id="test_repo", create=False, config_path=config_file))


def test_root_tree_lists_commits_without_descending():
    repo, session = _repo()
    out = repo.api_tree()

    # the working tree is walked as normal
    assert "/src" in session.gets
    # nothing under the history is ever fetched
    assert not [g for g in session.gets if g.startswith("/commits")]

    # and the collapsed directory says so rather than looking empty
    assert "commits/ (commit history not expanded)" in out
    assert "sha1" not in out
    assert "main.py" in out


def test_tree_rooted_at_commits_lists_the_history_only():
    repo, session = _repo()
    out = repo.api_tree(relpath="/commits")

    assert session.gets == ["/commits"]
    assert "sha1/ (not expanded)" in out
    assert "a.txt" not in out


def test_tree_rooted_at_one_commit_expands_it():
    """The deliberate browse the endpoint exists for still works."""
    repo, session = _repo()
    out = repo.api_tree(relpath="/commits/sha1")

    assert "/commits/sha1/files" in session.gets
    assert "/commits/sha1/files/sub" in session.gets
    assert "not expanded" not in out
    assert "a.txt" in out
    assert "b.txt" in out

    # the sibling commit is not dragged in
    assert not [g for g in session.gets if g.startswith("/commits/sha2")]


def test_dump_skips_commit_history(tmp_path):
    repo, session = _repo()

    out = StringIO()
    with redirect_stdout(out):
        repo.api_dump(outpath=str(tmp_path))

    assert not [g for g in session.gets if g.startswith("/commits")]
    assert "Skipping commit history: /commits" in out.getvalue()

    # the working tree still round-trips to disk
    assert (tmp_path / "src" / "main.py").read_text() == "print(1)"
    assert not (tmp_path / "commits").exists()


def test_skip_is_repo_scoped():
    """A space directory that happens to be named commits is ordinary data."""
    space, session = _with_remote(Space("test_space", create=False, config_path=config_file))
    out = space.api_tree()

    assert "/commits/sha1/files" in session.gets
    assert "not expanded" not in out
