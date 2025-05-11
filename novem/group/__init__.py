import os
from typing import Any, Dict, List, Optional

from novem.exceptions import Novem403, Novem404

from ..api_ref import NovemAPI
from .profile import NovemGroupProfile
from .roles import NovemRoles


class NovemGroupAPI(NovemAPI):
    """
    Novem group api, provides utility for the sub types
    """

    roles: Optional[NovemRoles] = None
    profile: Optional[NovemGroupProfile] = None

    id: str

    _type: str = "NA"
    _vispath: Optional[str] = None
    _debug: bool = False

    # path for admin functionality /v1/admin
    _admin_path: Optional[str] = None

    # path for group info         /v1/groups, /v1/org/group etc
    _group_path: Optional[str] = None

    _permissions: str = "r"

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)

        if "debug" in kwargs and kwargs["debug"]:
            self._debug = True

        if "create" not in kwargs or kwargs["create"]:
            # create when used as an api unless specifically told not to
            self.api_create("")

        self.roles = NovemRoles(self)
        self.profile = NovemGroupProfile(self, type=self._type)

        if "profile" in kwargs:
            self.profile.set(kwargs["profile"])

        if "roles" in kwargs:
            self.roles.set(kwargs["roles"])

        self._parse_kwargs(**kwargs)

    def _parse_kwargs(self, **kwargs: Any) -> None:

        # first let our super do it's thing
        super()._parse_kwargs(**kwargs)

        # get a list of valid properties
        # exclude data as it needs to be run lastj
        props = [
            x for x in dir(self) if x[0] != "_" and x not in ["data", "read", "delete", "write", "roles", "profile"]
        ]

        for k, v in kwargs.items():

            if k not in props:
                continue

            setattr(self, k, v)

    def __setattr__(self, name: str, value: Any) -> None:
        if name == "roles" and self.roles:
            self.roles.set(value)
        if name == "profile" and self.profile:
            self.profile.set(value)
        else:
            super().__setattr__(name, value)

    def api_dump(self, outpath: str) -> None:
        """
        Iterate over current id and dump output to supplied path
        """

        qpath = f"{self._api_root}vis/{self._vispath}/{self.id}/"

        # create util function
        def rec_tree(path: str) -> None:
            qp = f"{qpath}{path}"
            fp = f"{outpath}{path}"
            # print(f"QP: {qp}")
            req = self._session.get(qp)

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

    def api_read(self, relpath: str) -> str:
        """
        Read the api value located at realtive path
        """

        qpath = f"{self._api_root}{self._admin_path}/{self.id}{relpath}"

        # We can read information from other users, but not perform any
        # other actions so only the GET method supports the custom user
        # pathing
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
        qpath = f"{self._api_root}{self._admin_path}/{self.id}{relpath}"
        # We can read information from other users, but not perform any
        # other actions so only the GET method supports the custom user
        # pathing

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

        path = f"{self._api_root}{self._admin_path}/{self.id}{relpath}"

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

        path = f"{self._api_root}{self._admin_path}/{self.id}{relpath}"

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

        path = f"{self._api_root}{self._admin_path}/{self.id}{relpath}"

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
    def log(self) -> None:
        """
        print the current novem logs for the given vis
        """
        print(self.api_read("/log"))

        return None

    @property
    def permissions(self) -> str:
        """
        print the current novem logs for the given vis
        """

        return self._permissions

    @permissions.setter
    def permissions(self, value: str) -> None:
        """
        print the current novem logs for the given vis
        """

        self._permissions = value

    # chainable utility function for setting values
    def w(self, key: str, value: str) -> Any:
        """
        Set a novem group property, if key is a valid
        class prop then it will set that, else it will
        try to invoke an api call

        (both options results in the same effect)
        """
        props = [x for x in dir(self) if x[0] != "_" and x not in ["data", "read", "delete", "write"]]

        if key in props:
            self.__setattr__(key, value)
        else:
            self.api_write(key, value)

        return self
