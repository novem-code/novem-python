import sys
import warnings
from typing import Any, Dict, List, Optional, Tuple

from novem.exceptions import Novem403, Novem404, raise_on_response

from ..api_ref import NovemAPI
from ..shared import NovemShare
from ..sync import NovemTreeSync
from ..tags import NovemTags
from ..utils import cl
from ..utils import colors as clrs
from .files import NovemFiles

# keyword arguments consumed by the connection/behaviour layers
# (NovemAPI + NovemVisAPI); anything else passed to a vis constructor that is
# not a declared content property is treated as an unknown extra.
_RECOGNISED_KWARGS = frozenset(
    {
        # connection (NovemAPI)
        "token",
        "api_root",
        "config_path",
        "profile",
        "config_profile",
        "ignore_ssl",
        "ignore_config",
        "is_cli",
        "config_manager",
        # behaviour (NovemVisAPI)
        "user",
        "create",
        "qpr",
        "debug",
    }
)

# settable properties common to every vis (applied via __setattr__ intercept),
# accepted by all vis constructors regardless of their declared content props
_COMMON_VIS_PROPS = frozenset({"shared", "tags"})


def _warn_unknown_kwarg(owner: str, key: str) -> None:
    """Warn (once) about an unrecognised keyword argument, then ignore it.

    Unknown kwargs are non-fatal for backwards compatibility — a typo or a
    stale option should not break a caller — but we surface it so it does not
    pass silently.
    """
    warnings.warn(
        f"{owner}: unknown keyword argument '{key}' ignored",
        UserWarning,
        stacklevel=3,
    )


class NovemVisAPI(NovemTreeSync, NovemAPI):
    shared: NovemShare
    tags: NovemTags
    files: Optional[NovemFiles] = None

    _vispath: Optional[str] = None
    _debug: bool = False

    # declared content properties applied from constructor / call kwargs.
    # `_content_props` is the full set; `_content_deferred` lists the subset
    # that must be applied last, in order (they trigger renders / sends).
    _content_props: Tuple[str, ...] = ()
    _content_deferred: Tuple[str, ...] = ()

    def __init__(
        self,
        *,
        user: Optional[str] = None,
        create: bool = True,
        qpr: Optional[str] = None,
        debug: bool = False,
        **kwargs: Any,
    ) -> None:
        # connection + content kwargs are resolved by the super chain; the
        # behaviour flags below are the vis layer's own concern
        super().__init__(**kwargs)

        self.user = user or None

        if debug:
            self._debug = True

        if create:
            # always create when used as an api unless specifically told not
            # to (the CLI passes create=False to avoid spurious creation)
            self.api_create("")

        if qpr:
            self._qpr = qpr.replace(",", "&")

        if self.user:
            base_path = f"users/{self.user}/vis/{self._vispath}/{self.id}"
        else:
            base_path = f"vis/{self._vispath}/{self.id}"
        self.shared = NovemShare(self, base_path)
        self.tags = NovemTags(self, base_path)
        self.files = NovemFiles(self)

    def _parse_kwargs(self, **kwargs: Any) -> None:
        """Apply declared content properties from constructor / call kwargs.

        Connection/behaviour kwargs are consumed by the super chain and
        skipped here. Declared content properties are applied via their
        setters (deferred ones last, in order). Anything else is an unknown
        extra: warned about and ignored (non-fatal for backwards compat).
        """
        deferred: Dict[str, Any] = {}
        for key, value in kwargs.items():
            if value is None or key in _RECOGNISED_KWARGS:
                continue
            if key not in self._content_props and key not in _COMMON_VIS_PROPS:
                _warn_unknown_kwarg(type(self).__name__, key)
                continue
            if key in self._content_deferred:
                deferred[key] = value
                continue
            setattr(self, key, value)

        # apply deferred properties last, in declared order
        for key in self._content_deferred:
            if key in deferred:
                setattr(self, key, deferred[key])

    def __setattr__(self, name: str, value: Any) -> None:
        # Assigning a bare value to `shared`/`tags` is sugar for `.set(value)`;
        # assigning the wrapper object itself (as __init__ does) is a real set.
        # The isinstance checks are nested rather than chained so a type
        # checker does not narrow `value` across the branches (pyright would
        # otherwise widen it to `Any | NovemShare` in the tags branch).
        if name == "shared" and hasattr(self, "shared"):
            if isinstance(value, NovemShare):
                super().__setattr__(name, value)
            else:
                self.shared.set(value)
        elif name == "tags" and hasattr(self, "tags"):
            if isinstance(value, NovemTags):
                super().__setattr__(name, value)
            else:
                self.tags.set(value)
        else:
            super().__setattr__(name, value)

    def _sync_base(self, user_aware: bool) -> str:
        if user_aware and self.user:
            return f"{self._api_root}users/{self.user}/vis/{self._vispath}/{self.id}"
        return f"{self._api_root}vis/{self._vispath}/{self.id}"

    def _sync_label(self) -> str:
        return self._vispath or "vis"

    def api_tree(self, colors: bool = False, relpath: str = "/") -> str:
        """
        Iterate over the current id and print a "pretty" ascii tree
        """
        if relpath[0] != "/":
            relpath = f"/{relpath}"

        clrs()

        qpath = f"{self._api_root}vis/{self._vispath}/{self.id}{relpath}"

        if self.user:
            qpath = f"{self._api_root}users/{self.user}/vis/" f"{self._vispath}/{self.id}{relpath}"

        # TODO: we're using some hard coded unicode symbols and colors here
        # probably better to make this configurable by the user and perhaps
        # even move it to cli

        # this is an ugly hack, and mostly here to help users familiarize
        # themselves with the api structure

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
                return ([], "")

            headers = req.headers
            tp = headers.get("X-NVM-Type", headers.get("X-NS-Type", "file"))

            if tp == "file":
                print("The tree display is only available for `dir` paths")
                sys.exit(-1)

            nodes: List[Dict[str, str]] = req.json()

            hdp = []
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
                        resp += f"{pfx}{co}{h}{h} {a} {cl.OKBLUE}" f'{r["name"]}/{cl.ENDC}\n'
                    else:
                        resp += f'{pfx}{co}{h}{h} {a} {r["name"]}/\n'

                    resp += rec_tree(f'{path}/{r["name"]}', level + 1, mc)[1]
                else:
                    resp += f'{pfx}{co}{h}{h} {a} {r["name"]}\n'

            # order by dir, files, alphabetically
            return (hdp, resp)

        hdp, tr = rec_tree("/", 0, [True])

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

    def api_read(self, relpath: str) -> str:
        """
        Read the api value located at realtive path
        """

        qpath = f"{self._api_root}vis/{self._vispath}/{self.id}{relpath}"

        # We can read information from other users, but not perform any
        # other actions so only the GET method supports the custom user
        # pathing
        if self.user:
            qpath = f"{self._api_root}users/{self.user}/vis/" f"{self._vispath}/{self.id}{relpath}"

        if self._qpr and len(self._qpr):
            qpath = f"{qpath}?{self._qpr}"

        if self._debug:
            print(f"GET: {qpath}")

        r = self._session.get(qpath)

        # TODO: verify result and raise exception if not ok
        if r.status_code == 404:
            raise Novem404(qpath)

        if r.status_code == 403:
            raise Novem403

        return r.content.decode("utf-8")

    def api_read_bytes(self, relpath: str) -> bytes:
        qpath = f"{self._api_root}vis/{self._vispath}/{self.id}{relpath}"

        # We can read information from other users, but not perform any
        # other actions so only the GET method supports the custom user
        # pathing
        if self.user:
            qpath = f"{self._api_root}users/{self.user}/vis/" f"{self._vispath}/{self.id}{relpath}"

        if self._qpr and len(self._qpr):
            qpath = f"{qpath}?{self._qpr}"

        if self._debug:
            print(f"GET: {qpath}")

        r = self._session.get(qpath)

        # TODO: verify result and raise exception if not ok
        if r.status_code == 404:
            raise Novem404(qpath)

        if r.status_code == 403:
            raise Novem403

        return r.content

    def api_delete(self, relpath: str) -> None:
        """
        relpath: relative path to the plot baseline /config/type
                 for the type file in the config folder
        value: the value to write to the file
        """
        if self.user:
            print(f"You cannot modify another user's {self._vispath}")
            return

        path = f"{self._api_root}vis/{self._vispath}/{self.id}{relpath}"

        if self._debug:
            print(f"DELETE: {path}")

        r = self._session.delete(path)

        if r.status_code == 404:
            raise Novem404(path)

        if r.status_code == 403:
            raise Novem403

        # TODO: verify result and raise exception if not ok
        if not r.ok:
            print(r)
            print(f"DELETE: {path}")
            print("body")
            print("---")
            print(r.text)
            print("headers")
            print("---")
            print(r.headers)
            print("should raise an error")

    def api_create(self, relpath: str) -> None:
        """
        relpath: relative path to the plot baseline /config/type
                 for the type file in the config folder
        value: the value to write to the file
        """
        if self.user:
            print(f"You cannot modify another user's {self._vispath}")
            return

        path = f"{self._api_root}vis/{self._vispath}/{self.id}{relpath}"

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
        relpath: relative path to the plot baseline /config/type
                 for the type file in the config folder
        value: the value to write to the file
        """
        if self.user:
            print(f"You cannot modify another user's {self._vispath}")
            return

        path = f"{self._api_root}vis/{self._vispath}/{self.id}{relpath}"

        if self._debug:
            print(f"POST: {path}")

        r = self._session.post(
            path,
            headers={"Content-type": "text/plain"},
            data=value.encode("utf-8"),
        )

        if r.status_code == 404:
            raise Novem404(path)

        if r.status_code == 403:
            raise Novem403

        if not r.ok:
            raise_on_response(r)

    @property
    def log(self) -> None:
        """
        print the current novem logs for the given vis
        """
        print(self.api_read("/log"))

        return None

    @property
    def qpr(self) -> str:
        if self._qpr:
            return self._qpr.replace("&", ",")
        else:
            return ""

    @qpr.setter
    def qpr(self, value: str) -> None:
        if value:
            self._qpr = value.replace(",", "&")
