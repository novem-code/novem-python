"""Native content access for novem spaces.

A space is cloud file storage under ``code/spaces/{id}``; files and folders
live under its ``content/`` tree. :class:`SpaceContent` exposes that tree as
a path-indexed mapping on ``Space.content``:

    s = Space("my-space")

    body = s.content["path/to/document.json"]     # read a file (str)
    s.content["reports/q3.csv"] = csv_string       # write (create or replace)
    del s.content["old/tmp.txt"]                   # delete
    "path/to/document.json" in s.content           # existence

    docs = s.content["docs/"]                      # trailing slash: a folder
    for entry in docs:                             # SpaceEntry records
        print(entry.name, entry.kind, entry.size)

Text in, text out by default (UTF-8), matching the rest of the library;
``read_bytes``/``write_bytes`` handle binary content. Explicit methods
expose the API's optimistic-concurrency machinery (``if_match`` /
``no_clobber``) for careful writers — plain dict assignment is
last-write-wins.
"""

import json
import mimetypes
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Dict, Iterator, List, Optional, Tuple, Union
from urllib.parse import quote

from novem.exceptions import Novem403, Novem404, NovemException, raise_on_response

if TYPE_CHECKING:
    from . import NovemCodeAPI


def _norm(path: str) -> str:
    """Normalise a content path: the leading slash is optional."""
    return path.lstrip("/")


@dataclass
class SpaceFileInfo:
    """Metadata for a single content path (no body download)."""

    kind: str  # 'file' | 'dir'
    name: str
    path: str
    size: Optional[int] = None
    content_type: Optional[str] = None
    etag: Optional[str] = None
    created_on: Optional[str] = None
    last_modified: Optional[str] = None


@dataclass
class SpaceEntry:
    """One row of a folder listing."""

    name: str
    kind: str  # 'file' | 'dir'
    path: str  # full path within the space ('' prefixed dirs end with /)
    size: Optional[int] = None
    content_type: Optional[str] = None
    etag: Optional[str] = None
    created_on: Optional[str] = None
    last_modified: Optional[str] = None


@dataclass
class SpaceChange:
    """One entry of the space's change journal."""

    seq: int
    path: str
    change: str  # 'create' | 'update' | 'move' | 'delete'
    type: Optional[str] = None  # 'file' | 'dir'
    old_path: Optional[str] = None  # set for moves (and delete tombstones)
    etag: Optional[str] = None
    size_bytes: Optional[int] = None
    created_on: Optional[str] = None


class SpaceDir:
    """A navigable view over one folder in the space.

    Iterating yields :class:`SpaceEntry` records; indexing resolves paths
    relative to this folder (so ``s.content["docs/"]["report.json"]`` reads
    ``docs/report.json``).
    """

    def __init__(self, content: "SpaceContent", path: str) -> None:
        # '' for the root, otherwise 'some/dir/' (always trailing slash)
        self._content = content
        self._path = path

    def __repr__(self) -> str:
        return f"SpaceDir({self._path or '/'!r})"

    def ls(self) -> List[SpaceEntry]:
        return self._content.ls(self._path or "/")

    def __iter__(self) -> Iterator[SpaceEntry]:
        return iter(self.ls())

    def __contains__(self, rel: str) -> bool:
        return f"{self._path}{_norm(rel)}" in self._content

    def __getitem__(self, rel: str) -> Union[str, "SpaceDir"]:
        return self._content[f"{self._path}{_norm(rel)}"]

    def __setitem__(self, rel: str, value: Union[str, bytes]) -> None:
        self._content[f"{self._path}{_norm(rel)}"] = value

    def __delitem__(self, rel: str) -> None:
        del self._content[f"{self._path}{_norm(rel)}"]

    @property
    def files(self) -> List[SpaceEntry]:
        return [e for e in self.ls() if e.kind == "file"]

    @property
    def dirs(self) -> List[SpaceEntry]:
        return [e for e in self.ls() if e.kind == "dir"]


class SpaceContent:
    """The ``content/`` tree of a space as a path-indexed mapping."""

    def __init__(self, api: "NovemCodeAPI") -> None:
        self._api = api

    # -- transport ---------------------------------------------------------

    def _url(self, path: str) -> str:
        path = _norm(path)
        return self._api._path("/content" + (f"/{quote(path, safe='/')}" if path else ""))

    def _request(
        self,
        method: str,
        path: str,
        headers: Optional[Dict[str, str]] = None,
        data: Optional[bytes] = None,
        params: Optional[Dict[str, str]] = None,
    ) -> Any:
        url = self._url(path)

        if self._api._debug:
            print(f"{method}: {url}")

        r = self._api._session.request(method, url, headers=headers, data=data, params=params)

        if r.status_code == 404:
            raise Novem404(f"{path or '/'}")
        if r.status_code == 403:
            raise Novem403(f"{path or '/'}")
        if not r.ok:
            raise_on_response(r)

        return r

    # -- mapping interface ---------------------------------------------------

    def __getitem__(self, path: str) -> Union[str, SpaceDir]:
        npath = _norm(path)
        if npath == "" or npath.endswith("/"):
            return SpaceDir(self, npath)
        return self.read(npath)

    def __setitem__(self, path: str, value: Union[str, bytes]) -> None:
        if isinstance(value, bytes):
            self.write_bytes(path, value)
        else:
            self.write(path, value)

    def __delitem__(self, path: str) -> None:
        self.remove(path)

    def __contains__(self, path: str) -> bool:
        try:
            self.stat(path)
            return True
        except Novem404:
            return False

    def get(self, path: str, default: Optional[str] = None) -> Union[str, SpaceDir, None]:
        """Like ``[]`` but returns ``default`` instead of raising Novem404."""
        try:
            return self[path]
        except Novem404:
            return default

    # -- reads ---------------------------------------------------------------

    def read(self, path: str) -> str:
        """Read a file's content as text (UTF-8)."""
        return self.read_bytes(path).decode("utf-8")

    def read_bytes(self, path: str) -> bytes:
        """Read a file's content as raw bytes."""
        r = self._request("GET", path)
        # a folder listing is JSON, not file content — nudge towards the
        # trailing-slash convention instead of returning it as a body
        if r.headers.get("X-NVM-Type") == "dir":
            raise NovemException(f'"{_norm(path)}" is a folder — index it with a trailing slash: "{_norm(path)}/"')
        return r.content

    def stat(self, path: str) -> SpaceFileInfo:
        """Metadata for a path without downloading the body."""
        npath = _norm(path).rstrip("/")
        r = self._request("GET", npath, headers={"Accept": "application/json"})
        meta = r.json()
        if isinstance(meta, list):
            # folders answer with their listing
            name = npath.rsplit("/", 1)[-1] if npath else "/"
            return SpaceFileInfo(kind="dir", name=name, path=npath)
        return SpaceFileInfo(
            kind=meta.get("kind", "file"),
            name=meta.get("name", ""),
            path=meta.get("path", npath),
            size=meta.get("size"),
            content_type=meta.get("content_type"),
            etag=meta.get("etag"),
            created_on=meta.get("created_on"),
            last_modified=meta.get("last_modified"),
        )

    def ls(self, path: str = "/") -> List[SpaceEntry]:
        """List a folder (default: the content root)."""
        npath = _norm(path).rstrip("/")
        r = self._request("GET", npath)
        rows = r.json()
        if not isinstance(rows, list):
            raise NovemException(f'"{npath}" is a file, not a folder')

        prefix = f"{npath}/" if npath else ""
        out = []
        for row in rows:
            kind = "dir" if row.get("type") == "dir" else "file"
            out.append(
                SpaceEntry(
                    name=row.get("name", ""),
                    kind=kind,
                    path=f'{prefix}{row.get("name", "")}' + ("/" if kind == "dir" else ""),
                    size=row.get("size"),
                    content_type=row.get("content_type"),
                    etag=row.get("ETag") or row.get("etag"),
                    created_on=row.get("created_on"),
                    last_modified=row.get("last_modified"),
                )
            )
        return out

    def walk(self, top: str = "/") -> Iterator[Tuple[str, List[str], List[str]]]:
        """Walk the tree like ``os.walk``: yields (path, dirnames, filenames).

        ``path`` is '' for the root, otherwise 'some/dir/'.
        """
        npath = _norm(top).rstrip("/")
        prefix = f"{npath}/" if npath else ""
        entries = self.ls(npath or "/")
        dirs = [e.name for e in entries if e.kind == "dir"]
        files = [e.name for e in entries if e.kind == "file"]
        yield (prefix, dirs, files)
        for d in dirs:
            yield from self.walk(f"{prefix}{d}")

    # -- writes ---------------------------------------------------------------

    def write(
        self,
        path: str,
        data: Union[str, bytes],
        if_match: Optional[str] = None,
        no_clobber: bool = False,
        content_type: Optional[str] = None,
    ) -> None:
        """Write a file (create or replace); parent folders are auto-created.

        ``if_match`` writes only when the file's current ETag matches;
        ``no_clobber`` refuses to replace an existing file. Both surface a
        412 as a NovemException when the condition fails.
        """
        npath = _norm(path)
        if npath.endswith("/"):
            raise NovemException("write() takes a file path — use mkdir() for folders")

        body = data.encode("utf-8") if isinstance(data, str) else data
        headers: Dict[str, str] = {
            "Content-Type": content_type
            or mimetypes.guess_type(npath)[0]
            or ("text/plain" if isinstance(data, str) else "application/octet-stream")
        }
        if if_match:
            headers["If-Match"] = if_match
        if no_clobber:
            headers["If-None-Match"] = "*"

        self._request("PUT", npath, headers=headers, data=body)

    def write_bytes(
        self,
        path: str,
        data: bytes,
        if_match: Optional[str] = None,
        no_clobber: bool = False,
        content_type: Optional[str] = None,
    ) -> None:
        """Write raw bytes to a file (see :meth:`write`)."""
        self.write(path, data, if_match=if_match, no_clobber=no_clobber, content_type=content_type)

    def mkdir(self, path: str) -> None:
        """Create a folder (idempotent; parents are auto-created)."""
        npath = _norm(path).rstrip("/")
        if not npath:
            return
        # PUT with a trailing slash is the folder-create form
        url = self._api._path(f"/content/{quote(npath, safe='/')}/")
        r = self._api._session.put(url)
        if r.status_code == 404:
            raise Novem404(npath)
        if r.status_code == 403:
            raise Novem403(npath)
        if not r.ok:
            raise_on_response(r)

    def move(
        self,
        src: str,
        dst: str,
        if_match: Optional[str] = None,
        no_clobber: bool = False,
    ) -> None:
        """Rename or move a file or folder tree (atomic, metadata-only).

        Matches POSIX ``mv``: an existing file destination is replaced,
        a folder destination is never replaced. ``no_clobber`` refuses to
        replace anything; ``if_match`` guards the source's ETag.
        """
        headers = {"Content-Type": "application/json"}
        if if_match:
            headers["If-Match"] = if_match
        if no_clobber:
            headers["If-None-Match"] = "*"

        self._request("PATCH", _norm(src), headers=headers, data=json.dumps({"to": _norm(dst)}).encode("utf-8"))

    def remove(self, path: str, recursive: bool = False) -> None:
        """Delete a file or folder; non-empty folders need ``recursive``."""
        params = {"recursive": "true"} if recursive else None
        self._request("DELETE", _norm(path).rstrip("/"), params=params)


def space_changes(
    api: "NovemCodeAPI",
    since: int = 0,
    batch: int = 1000,
) -> Iterator[SpaceChange]:
    """Iterate the space's change journal, oldest first, auto-paging.

    Resume by passing the highest ``seq`` you have processed as ``since``.
    """
    while True:
        url = api._path("/changes")
        r = api._session.get(url, params={"since": str(since), "limit": str(batch)})
        if r.status_code == 404:
            raise Novem404("changes")
        if r.status_code == 403:
            raise Novem403("changes")
        if not r.ok:
            raise_on_response(r)

        payload = r.json()
        for row in payload.get("changes", []):
            yield SpaceChange(
                seq=row.get("seq", 0),
                path=row.get("path", ""),
                change=row.get("change", ""),
                type=row.get("type"),
                old_path=row.get("old_path"),
                etag=row.get("etag"),
                size_bytes=row.get("size_bytes"),
                created_on=row.get("created_on"),
            )
            since = max(since, row.get("seq", 0))

        if not payload.get("has_more"):
            return


__all__ = [
    "SpaceContent",
    "SpaceDir",
    "SpaceEntry",
    "SpaceFileInfo",
    "SpaceChange",
    "space_changes",
]
