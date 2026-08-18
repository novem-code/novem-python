"""Shared base for the novem "coding" resources.

The coding resources (repos, spaces, computers, images — and jobs, which
predate this module) are siblings under ``code/`` in the API:

    code/{collection}/{id}
    users/{user}/code/{collection}/{id}

They all share the same VDE surface (name/summary/description, url,
shortname, shared, tags) plus a per-resource set of config leaves and
derived reads. ``NovemCodeAPI`` implements that shared surface once;
subclasses set ``_collection``/``_label`` and add their own properties.
"""

import sys
from typing import Any, Callable, Dict, Iterator, List, Optional, Tuple, Union, cast

from novem.exceptions import Novem403, Novem404, NovemException, raise_on_response

from ..api_ref import NovemAPI
from ..shared import NovemShare
from ..sync import NovemTreeSync
from ..tags import NovemTags
from ..utils import cl
from ..utils import colors as clrs
from .compute import (
    ComputeConnection,
    ExecResult,
    NovemComputeError,
    NovemComputeTransportError,
    StdinSource,
    _exec_collect_channel,
    _exec_stream_channel,
    _open_interactive_pty,
    _pty_interactive,
    _run_sync,
    _split_argv,
    _with_retry,
    target_for,
    ws_url,
)
from .space_content import SpaceChange, SpaceContent, SpaceDir, SpaceEntry, SpaceFileInfo, SpacePath, space_changes


class NovemCodeConfig:
    """Proxy dict-style config onto the resource's ``/config/*`` leaves.

    ``set({"type": "x", "cpu": "4"})`` writes each key to ``/config/{key}``,
    so it works for every coding resource without enumerating their
    (different) config surfaces.
    """

    def __init__(self, api: "NovemCodeAPI") -> None:
        self.api: "NovemCodeAPI" = api

    def set(self, config: Dict[str, Any]) -> None:
        for k, v in config.items():
            self.api.api_write(f"/config/{k}", str(v))

    @property
    def type(self) -> str:
        return self.api.api_read("/config/type").strip()

    @type.setter
    def type(self, value: str) -> None:
        return self.api.api_write("/config/type", value)


class NovemCodeAPI(NovemTreeSync, NovemAPI):
    _collection: str = ""  # plural path segment, e.g. "spaces"
    _label: str = ""  # singular, for messages, e.g. "space"

    config: Optional[NovemCodeConfig]
    shared: Optional[NovemShare]
    tags: Optional[NovemTags]
    id: str
    user: Optional[str] = None

    _debug: bool = False

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)

        if "debug" in kwargs and kwargs["debug"]:
            self._debug = True

        if "user" in kwargs and kwargs["user"]:
            self.user = kwargs["user"]

        if "create" not in kwargs or kwargs["create"]:
            # create when used as an api unless specifically told not to
            self.api_create("")

        self.config = self._mk_config()
        if self.user:
            base_path = f"users/{self.user}/code/{self._collection}/{self.id}"
        else:
            base_path = f"code/{self._collection}/{self.id}"
        self.shared = NovemShare(self, base_path)
        self.tags = NovemTags(self, base_path)

        if "shared" in kwargs:
            self.shared.set(kwargs["shared"])

        if "config" in kwargs:
            self.config.set(kwargs["config"])

        self._parse_kwargs(**kwargs)

    def _mk_config(self) -> NovemCodeConfig:
        return NovemCodeConfig(self)

    def _parse_kwargs(self, **kwargs: Any) -> None:

        # first let our super do it's thing
        super()._parse_kwargs(**kwargs)

        # get a list of valid properties
        props = [
            x
            for x in dir(self)
            if x[0] != "_" and x not in ["data", "read", "delete", "write", "shared", "config", "create"]
        ]

        for k, v in kwargs.items():
            if k not in props:
                continue

            setattr(self, k, v)

    def __setattr__(self, name: str, value: Any) -> None:
        # nested isinstance checks (rather than a chain) so a type checker does
        # not narrow `value` across branches; see NovemVisAPI.__setattr__
        if name == "config" and hasattr(self, "config") and self.config:
            if isinstance(value, NovemCodeConfig):
                super().__setattr__(name, value)
            else:
                self.config.set(value)
        elif name == "shared" and hasattr(self, "shared") and self.shared is not None:
            if isinstance(value, NovemShare):
                super().__setattr__(name, value)
            else:
                self.shared.set(value)
        elif name == "tags" and hasattr(self, "tags") and self.tags is not None:
            if isinstance(value, NovemTags):
                super().__setattr__(name, value)
            else:
                self.tags.set(value)
        else:
            super().__setattr__(name, value)

    def _path(self, relpath: str = "") -> str:
        if self.user:
            return f"{self._api_root}users/{self.user}/code/{self._collection}/{self.id}{relpath}"
        return f"{self._api_root}code/{self._collection}/{self.id}{relpath}"

    def api_read(self, relpath: str) -> str:
        """
        Read the api value located at relative path
        """

        qpath = self._path(relpath)

        if self._debug:
            print(f"GET: {qpath}")

        r = self._session.get(qpath)

        # verify result and raise exception if not ok
        if r.status_code == 404:
            raise Novem404(qpath)

        if r.status_code == 403:
            raise Novem403

        return r.content.decode("utf-8")

    def api_delete(self, relpath: str) -> None:
        """
        relpath: relative path to the resource baseline, /config/type
                 for the type file in the config folder
        """
        if self.user:
            print(f"You cannot modify another user's {self._label}")
            return

        path = self._path(relpath)

        if self._debug:
            print(f"DELETE: {path}")

        r = self._session.delete(path)

        if r.status_code == 404:
            raise Novem404(path)

        if r.status_code == 403:
            raise Novem403

        if not r.ok:
            raise_on_response(r)

    def api_create(self, relpath: str) -> None:
        """
        relpath: relative path to the resource baseline
        """
        if self.user:
            print(f"You cannot modify another user's {self._label}")
            return

        path = self._path(relpath)

        if self._debug:
            print(f"PUT: {path}")

        r = self._session.put(path)

        if r.status_code == 404:
            raise Novem404(path)

        if r.status_code == 403:
            raise Novem403(path)

        if r.status_code == 409:
            # we will ignore 409 errors
            # as creating objects that already exist is not a problem
            return

        if not r.ok:
            raise_on_response(r)

    def api_write(self, relpath: str, value: str) -> None:
        """
        relpath: relative path to the resource baseline, /config/type
                 for the type file in the config folder
        value: the value to write to the file
        """
        if self.user:
            print(f"You cannot modify another user's {self._label}")
            return

        path = self._path(relpath)

        if self._debug:
            print(f"POST: {path}")

        r = self._session.post(
            path,
            headers={"Content-type": "text/plain"},
            data=value.encode("utf-8"),
        )

        if r.status_code == 404:
            raise Novem404(path)

        if not r.ok:
            raise_on_response(r)

    # chainable utility function for setting values
    def w(self, key: str, value: str) -> Any:
        """
        Set a novem property, if key is a valid class prop then it will set
        that, else it will try to invoke an api call

        (both options results in the same effect)
        """
        props = [x for x in dir(self) if x[0] != "_" and x not in ["data", "read", "delete", "write"]]

        if key in props:
            self.__setattr__(key, value)
        else:
            self.api_write(key, value)

        return self

    def ref(self, ref: str) -> str:
        """
        Return a fully qualified path to given ref

        So input of "tag:v0.0.2" gives "/<user>/<id>:tag:v0.0.2"
        """
        user = self.read("whoami")

        return f"/{user}/{self.id}:{ref}"

    @property
    def log(self) -> None:
        """
        print the current novem logs for the given resource
        """
        print(self.api_read("/log"))

        return None

    @property
    def type(self) -> str:
        return self.api_read("/config/type").strip()

    @type.setter
    def type(self, value: str) -> None:
        return self.api_write("/config/type", value)

    @property
    def name(self) -> str:
        return self.api_read("/name").strip()

    @name.setter
    def name(self, value: str) -> None:
        return self.api_write("/name", value)

    @property
    def description(self) -> str:
        return self.api_read("/description")

    @description.setter
    def description(self, value: str) -> None:
        return self.api_write("/description", value)

    @property
    def summary(self) -> str:
        return self.api_read("/summary")

    @summary.setter
    def summary(self, value: str) -> None:
        return self.api_write("/summary", value)

    @property
    def url(self) -> str:
        return self.api_read("/url").strip()

    @property
    def shortname(self) -> str:
        return self.api_read("/shortname").strip()

    def _sync_base(self, user_aware: bool) -> str:
        # _path() is already user-aware
        return self._path()

    def _sync_label(self) -> str:
        return self._label

    def api_tree(self, colors: bool = False, relpath: str = "/") -> str:
        """
        Iterate over the current resource and print a "pretty" ascii tree
        """
        if relpath[0] != "/":
            relpath = f"/{relpath}"

        clrs()

        # Base path without trailing slash - we'll add paths in rec_tree
        qpath = self._path()

        # some display options
        c = "├"
        b = "└"
        v = "│"
        h = "─"

        # create util function
        def rec_tree(path: str, level: int = 0, last: List[bool] = [False]) -> Tuple[List[str], str]:
            qp = f"{qpath}{path}"
            req = self._session.get(qp)

            if not req.ok:
                if level == 0:
                    # Top level failure - show error to user
                    if req.status_code == 404:
                        print(f"{self._label.capitalize()} '{self.id}' not found")
                    else:
                        print(f"Failed to fetch {self._label} tree: {req.status_code}")
                    sys.exit(1)
                return ([], "")

            headers = req.headers
            tp = headers.get("X-NVM-Type", headers.get("X-NS-Type", "file"))

            if tp == "file":
                print("The tree display is only available for `dir` paths")
                sys.exit(-1)

            nodes: List[Dict[str, str]] = req.json()

            hdp: List[str] = []
            if level == 0:
                hdp = headers.get("X-NVM-Permissions", headers.get("X-NS-Permissions", "")).split(", ")

            pfx = ""
            for il in last:
                if il:
                    pfx += "    "
                else:
                    pfx += f"{v}   "

            # drop system stuff
            nodes = [x for x in nodes if x["type"] not in ["system_file", "system_dir"]]

            resp = ""
            # convert element into a tree structure
            nodes = sorted(nodes, key=lambda k: (k["type"], k["name"]))
            for r in nodes:
                rd = "r" if "r" in r["permissions"] else "-"
                w = "w" if "w" in r["permissions"] else "-"
                d = "d" if "d" in r["permissions"] else "-"
                if colors:
                    a = f"{cl.FGGRAY}[{rd}{w}{d}]{cl.ENDC}"
                else:
                    a = f"[{rd}{w}{d}]"

                if r["name"] == nodes[-1]["name"]:
                    mc = last + [True]
                    co = f"{b}"
                else:
                    mc = last + [False]
                    co = f"{c}"

                if r["type"] == "dir":
                    if colors:
                        resp += f"{pfx}{co}{h}{h} {a} {cl.OKBLUE}{r['name']}/{cl.ENDC}\n"
                    else:
                        resp += f"{pfx}{co}{h}{h} {a} {r['name']}/\n"

                    resp += rec_tree(f"{path}/{r['name']}", level + 1, mc)[1]
                else:
                    resp += f"{pfx}{co}{h}{h} {a} {r['name']}\n"

            # order by dir, files, alphabetically
            return (hdp, resp)

        hdp, tr = rec_tree(relpath, 0, [True])

        sf = f"{self.id}{relpath}"
        if sf[-1] != "/":
            sf = f"{sf}/"

        if colors:
            sf = f"{cl.OKBLUE}{sf}{cl.ENDC}"

        rd = "r" if "r" in hdp else "-"
        w = "w" if "w" in hdp else "-"
        d = "d" if "d" in hdp else "-"
        if colors:
            a = f"{cl.FGGRAY}[{rd}{w}{d}]{cl.ENDC}"
        else:
            a = f"[{rd}{w}{d}]"
        tr = f"{a} {sf}\n{tr}"

        return tr[:-1]  # strip trailing newline


class Space(NovemCodeAPI):
    """A novem space — cloud file storage under ``code/spaces/{id}``.

    File content is exposed as a path-indexed mapping on :attr:`content`::

        s = Space("my-space")
        body = s.content["path/to/document.json"]   # read (str)
        s.content["reports/q3.csv"] = csv_string     # write
        for entry in s.content["docs/"]:             # navigate folders
            ...

        path = s / "path/to/document.json"           # pathlib-style view
        path.content = "new content"
        print(path.size)

    See :mod:`novem.code.space_content` for the full surface (bytes,
    stat, mkdir, move, remove, walk) and :meth:`changes` for the journal.
    """

    _collection = "spaces"
    _label = "space"

    content: "SpaceContent"

    def __init__(self, id: str, **kwargs: Any) -> None:
        self.id = id
        super().__init__(**kwargs)
        self.content = SpaceContent(self)

    def __truediv__(self, path: str) -> "SpacePath":
        """Return a pathlib-inspired view of ``path`` in this space."""
        return SpacePath(self.content, path)

    def changes(self, since: int = 0) -> Iterator["SpaceChange"]:
        """Iterate the space's change journal, oldest first, auto-paging.

        Each :class:`SpaceChange` carries ``seq``, ``path``, ``change``
        (create/update/move/delete), ``old_path`` for moves, ``etag`` and
        ``size_bytes``. Resume by passing the highest ``seq`` processed.
        """
        return space_changes(self, since=since)


class Computer(NovemCodeAPI):
    """A novem computer — a permanent or ephemeral VM under
    ``code/computers/{id}``.

    Config leaves: ``config/{type,image,cpu,memory,disk,idle,ttl}``.
    ``status`` accepts the verbs ``online``, ``offline`` and ``reboot``.
    """

    _collection = "computers"
    _label = "computer"

    _compute_owner: Optional[str] = None

    def __init__(self, id: str, **kwargs: Any) -> None:
        self.id = id
        super().__init__(**kwargs)

    @property
    def status(self) -> str:
        return self.api_read("/status").strip()

    @status.setter
    def status(self, value: str) -> None:
        return self.api_write("/status", value)

    @property
    def info(self) -> str:
        return self.api_read("/info")

    # ── live connections (novem.compute.v1 over /ws-cu) ──────────────────

    def _compute_target(self) -> str:
        """The canonical target for this computer.

        The owner is always spelled out — the short ``/v1/code/...`` form is
        not accepted here. Resolved from the token when not scoped to
        another user, and cached for the object's lifetime.
        """
        owner = self.user
        if not owner:
            if self._compute_owner is None:
                self._compute_owner = self.read("whoami").strip()
            owner = self._compute_owner
        return target_for(owner, self.id)

    def connect(self) -> "ComputeConnection":
        """An unopened :class:`ComputeConnection` for this computer's platform.

        For async callers::

            async with computer.connect() as conn:
                ch = await conn.open_exec(computer.compute_target, "ls")
        """
        try:
            url = ws_url(self._api_root)
        except ValueError as e:
            raise NovemComputeTransportError(str(e)) from e
        return ComputeConnection(
            url,
            self.token or "",
            ignore_ssl=self._config.ignore_ssl,
            debug=self._debug,
        )

    @property
    def compute_target(self) -> str:
        return self._compute_target()

    def run(
        self,
        argv: Union[str, List[str]],
        mode: str = "argv",
        cwd: str = "",
        stdin: Optional[StdinSource] = None,
        timeout: int = 600,
        retry_seconds: float = 0.0,
        on_retry: Optional[Callable[[NovemException], None]] = None,
    ) -> "ExecResult":
        """Run one command and return its buffered output and exit status.

        ``argv`` is a list in argv mode (no shell re-parsing) or a command
        string in shell mode. ``stdin`` accepts text, bytes, or a readable
        file-like object; file input is forwarded incrementally while output
        is collected. ``retry_seconds`` retries the open while the computer
        reports a retryable state.
        """
        command, args = _split_argv(argv, mode)
        target = self._compute_target()
        return _run_sync(
            _with_retry(
                lambda conn: conn.open_exec(
                    target,
                    command,
                    args,
                    mode=mode,
                    cwd=cwd,
                    timeout_seconds=timeout,
                ),
                lambda channel: _exec_collect_channel(channel, stdin),
                self.connect,
                retry_seconds,
                on_retry,
            )
        )

    def stream(
        self,
        argv: Union[str, List[str]],
        mode: str = "argv",
        cwd: str = "",
        stdin: Optional[StdinSource] = None,
        timeout: int = 600,
        retry_seconds: float = 0.0,
        on_retry: Optional[Callable[[NovemException], None]] = None,
        forward_signals: bool = False,
    ) -> Tuple[int, Optional[str]]:
        """Run one command, writing its output straight to stdout/stderr.

        ``stdin`` accepts text, bytes, or a readable file-like object. File
        input and command output are handled concurrently. Returns ``(code,
        signal)``; the code is the workload's own, so a non-zero value is a
        successful call reporting a failed command.
        """
        command, args = _split_argv(argv, mode)
        target = self._compute_target()
        return cast(
            Tuple[int, Optional[str]],
            _run_sync(
                _with_retry(
                    lambda conn: conn.open_exec(
                        target,
                        command,
                        args,
                        mode=mode,
                        cwd=cwd,
                        timeout_seconds=timeout,
                    ),
                    lambda channel: _exec_stream_channel(channel, stdin, forward_signals=forward_signals),
                    self.connect,
                    retry_seconds,
                    on_retry,
                )
            ),
        )

    def shell(
        self,
        retry_seconds: float = 0.0,
        on_retry: Optional[Callable[[NovemException], None]] = None,
    ) -> Tuple[int, Optional[str]]:
        """Attach an interactive shell, taking over the local terminal."""
        target = self._compute_target()
        return cast(
            Tuple[int, Optional[str]],
            _run_sync(
                _with_retry(
                    lambda conn: _open_interactive_pty(conn, target),
                    _pty_interactive,
                    self.connect,
                    retry_seconds,
                    on_retry,
                )
            ),
        )


class Image(NovemCodeAPI):
    """A novem image — the derived, read-only build artifact of a repo,
    under ``code/images/{id}``.

    Images cannot be created or deleted over the API: they appear and
    disappear with builds of their source repo. Metadata
    (name/summary/description) is writable by the owner.
    """

    _collection = "images"
    _label = "image"

    def __init__(self, id: str, **kwargs: Any) -> None:
        self.id = id
        # never attempt the implicit create — images are derived
        kwargs["create"] = False
        super().__init__(**kwargs)

    def api_create(self, relpath: str) -> None:
        print("Images are derived from their source repo and cannot be created directly")
        return

    def api_delete(self, relpath: str) -> None:
        if relpath in ("", "/"):
            print("Images are derived from their source repo and cannot be deleted directly")
            return
        super().api_delete(relpath)

    @property
    def status(self) -> str:
        return self.api_read("/status").strip()

    @property
    def repo(self) -> str:
        """The source repo as ``@owner/name``."""
        return self.api_read("/config/repo").strip()


__all__ = [
    "NovemCodeAPI",
    "NovemCodeConfig",
    "Space",
    "Computer",
    "Image",
    "SpaceContent",
    "SpacePath",
    "SpaceDir",
    "SpaceEntry",
    "SpaceFileInfo",
    "SpaceChange",
    "ComputeConnection",
    "ExecResult",
    "NovemComputeError",
    "NovemComputeTransportError",
]
