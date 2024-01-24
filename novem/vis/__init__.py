import os
import sys
import urllib.request
from typing import Any, Dict, List, Optional, Tuple

import requests

from novem.exceptions import Novem403, Novem404

from ..api_ref import NovemAPI
from ..utils import cl
from ..utils import colors as clrs
from ..version import __version__
from .files import NovemFiles
from .shared import NovemShare

s = requests.Session()


class NovemVisAPI(NovemAPI):
    """ """

    _hdr_post: Dict[str, str] = {
        "User-Agent": f"NovemPythonLibrary-{__version__}",
        "Content-type": "text/plain",
    }
    _hdr_put: Dict[str, str] = {
        "User-Agent": f"NovemPythonLibrary-{__version__}",
    }
    _hdr_get: Dict[str, str] = {
        "User-Agent": f"NovemPythonLibrary-{__version__}",
    }
    _hdr_del: Dict[str, str] = {
        "User-Agent": f"NovemPythonLibrary-{__version__}",
    }

    _proxies: Dict[Any, Any] = {}

    shared: Optional[NovemShare] = None
    files: Optional[NovemFiles] = None

    _vispath: Optional[str] = None
    _debug: bool = False

    def __init__(self, **kwargs: Any) -> None:

        self._proxies = urllib.request.getproxies()

        super().__init__(**kwargs)

        self.user = None

        if self._config["ignore_ssl_warn"] or ("ignore_ssl" in kwargs and kwargs["ignore_ssl"]):
            # supress ssl warnings
            s.verify = False
            import urllib3

            urllib3.disable_warnings()

        if "debug" in kwargs and kwargs["debug"]:
            self._debug = True

        if "create" not in kwargs or kwargs["create"]:
            # let's create our plot if -C specified, always
            # create when used as an api unless specifically told not to
            self.api_create("")

        if "user" in kwargs and kwargs["user"]:
            self.user = kwargs["user"]

        if "qpr" in kwargs and kwargs["qpr"]:
            self._qpr = kwargs["qpr"].replace(",", "&")

        self.shared = NovemShare(self)
        self.files = NovemFiles(self)

    def __setattr__(self, name: str, value: Any) -> None:
        if name == "shared" and self.shared:
            self.shared.set(value)
        else:
            super().__setattr__(name, value)

    def api_dump(self, outpath: str) -> None:
        """
        Iterate over current id and dump output to supplied path
        """

        qpath = f"{self._api_root}vis/{self._vispath}/{self.id}/"

        if self.user:
            qpath = f"{self._api_root}users/{self.user}/vis/" f"{self._vispath}/{self.id}/"

        # create util function
        def rec_tree(path: str) -> None:
            qp = f"{qpath}{path}"
            fp = f"{outpath}{path}"
            # print(f"QP: {qp}")
            req = s.get(
                qp,
                auth=("", self.token),
                headers=self._hdr_get,
                proxies=self._proxies,
            )

            if not req.ok:
                return None

            headers = req.headers
            try:
                tp = headers["X-NS-Type"]
            except KeyError:
                tp = "file"

            # if i am a file, write to disc
            if tp == "file":
                with open(fp, "w") as f:
                    f.write(req.text)
                print(f"Writing file:    {fp}")
                return None

            # if I am a folder, make a folder and recurse
            os.makedirs(fp, exist_ok=True)
            print(f"Creating folder: {fp}")

            nodes: List[Dict[str, str]] = req.json()

            # Recurse relevant structure
            for r in [x for x in nodes if x["type"] not in ["system_file", "system_dir"]]:
                rec_tree(f'{path}/{r["name"]}')

        # start recurison
        rec_tree("")

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
            req = s.get(
                qp,
                auth=("", self.token),
                headers=self._hdr_get,
                proxies=self._proxies,
            )

            if not req.ok:
                return ([], "")

            headers = req.headers

            try:
                tp = headers["X-NS-Type"]
            except KeyError:
                tp = "file"

            if tp == "file":
                print("The tree display is only available for `dir` paths")
                sys.exit(-1)

            nodes: List[Dict[str, str]] = req.json()

            hdp = []
            if level == 0:
                try:
                    hdp = headers["X-NS-Permissions"].split(", ")
                except KeyError:
                    hdp = []

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

        r = s.get(
            qpath,
            auth=("", self.token),
            headers=self._hdr_get,
            proxies=self._proxies,
        )

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

        r = s.get(
            qpath,
            auth=("", self.token),
            headers=self._hdr_get,
            proxies=self._proxies,
        )

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
            print(f"you cannot modify another users {self._vispath}")
            return

        path = f"{self._api_root}vis/{self._vispath}/{self.id}{relpath}"

        if self._debug:
            print(f"DELETE: {path}")

        r = s.delete(
            path,
            auth=("", self.token),
            headers=self._hdr_del,
            proxies=self._proxies,
        )

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
            print(f"you cannot modify another users {self._vispath}")
            return

        path = f"{self._api_root}vis/{self._vispath}/{self.id}{relpath}"

        if self._debug:
            print(f"PUT: {path}")

        r = s.put(
            path,
            auth=("", self.token),
            headers=self._hdr_put,
            proxies=self._proxies,
        )

        if r.status_code == 404:
            raise Novem404(path)

        if r.status_code == 403:
            raise Novem403(path)

        if r.status_code == 409:
            # we will ignore 409 errors
            # as creating objects that already exist is not a problem
            return

        # TODO: verify result and raise exception if not ok
        if not r.ok:
            print(r)
            print(f"PUT: {path}")
            print("body")
            print("---")
            print(r.text)
            print("headers")
            print("---")
            print(r.headers)
            print("should raise a general error")

    def api_write(self, relpath: str, value: str) -> None:
        """
        relpath: relative path to the plot baseline /config/type
                 for the type file in the config folder
        value: the value to write to the file
        """
        if self.user:
            print(f"you cannot modify another users {self._vispath}")
            return

        path = f"{self._api_root}vis/{self._vispath}/{self.id}{relpath}"

        if self._debug:
            print(f"POST: {path}")

        r = s.post(
            path,
            auth=("", self.token),
            headers=self._hdr_post,
            data=value.encode("utf-8"),
            proxies=self._proxies,
        )

        if r.status_code == 404:
            raise Novem404(path)

        if r.status_code == 403:
            raise Novem403

        # TODO: verify result and raise exception if not ok
        if not r.ok:
            print(r)
            print(f"POST: {path} {value}")
            print("body")
            print("---")
            print(r.text)
            print(r.status_code)
            print("headers")
            print("---")
            for k, v in r.headers.items():
                print(f"   {k}: {v}")
            print("should raise a general error")

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
