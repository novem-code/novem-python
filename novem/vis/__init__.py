from typing import Any, Dict, Optional

import requests

from ..api import Novem403, Novem404, NovemAPI
from ..version import __version__
from .files import NovemFiles
from .shared import NovemShare


class NovemVisAPI(NovemAPI):
    """ """

    hdr_post: Dict[str, str] = {
        "User-Agent": f"NovemPythonLibrary-{__version__}",
        "Content-type": "text/plain",
    }
    hdr_put: Dict[str, str] = {
        "User-Agent": f"NovemPythonLibrary-{__version__}",
    }
    hdr_get: Dict[str, str] = {
        "User-Agent": f"NovemPythonLibrary-{__version__}",
    }
    hdr_del: Dict[str, str] = {
        "User-Agent": f"NovemPythonLibrary-{__version__}",
    }

    shared: Optional[NovemShare] = None
    files: Optional[NovemFiles] = None

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)

        self.shared = NovemShare(self)
        self.files = NovemFiles(self)

    def __setattr__(self, name: str, value: Any) -> None:
        if name == "shared" and self.shared:
            self.shared.set(value)
        else:
            super().__setattr__(name, value)

    def api_read(self, relpath: str) -> str:
        """
        Read the api value located at realtive path
        """

        r = requests.get(
            f"{self.api_root}vis/plots/{self.id}{relpath}",
            auth=("", self.token),
            headers=self.hdr_get,
        )

        # TODO: verify result and raise exception if not ok
        if r.status_code == 404:
            raise Novem404

        if r.status_code == 403:
            raise Novem403

        return r.text

    def api_delete(self, relpath: str) -> None:
        """
        relpath: relative path to the plot baseline /config/type
                 for the type file in the config folder
        value: the value to write to the file
        """

        r = requests.delete(
            f"{self.api_root}vis/plots/{self.id}{relpath}",
            auth=("", self.token),
            headers=self.hdr_del,
        )

        if r.status_code == 404:
            raise Novem404

        if r.status_code == 403:
            raise Novem403

        # TODO: verify result and raise exception if not ok
        if not r.ok:
            print(r)
            print(r.text)
            print("should raise an error")

    def api_create(self, relpath: str) -> None:
        """
        relpath: relative path to the plot baseline /config/type
                 for the type file in the config folder
        value: the value to write to the file
        """

        path = f"{self.api_root}vis/plots/{self.id}{relpath}"
        r = requests.put(
            path,
            auth=("", self.token),
            headers=self.hdr_put,
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
            print(r.text)
            print("should raise a general error")

    def api_write(self, relpath: str, value: str) -> None:
        """
        relpath: relative path to the plot baseline /config/type
                 for the type file in the config folder
        value: the value to write to the file
        """

        r = requests.post(
            f"{self.api_root}vis/plots/{self.id}{relpath}",
            auth=("", self.token),
            headers=self.hdr_post,
            data=value,
        )
        # TODO: verify result and raise exception if not ok
        if not r.ok:
            print(r)
            print(r.text)
            print("should raise an error")

        if r.status_code == 404:
            raise Novem404

        if r.status_code == 403:
            raise Novem403
