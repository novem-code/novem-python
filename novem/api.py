import sys
from typing import Any, Dict, Optional

import requests

from .utils import get_current_config


class NovemException(Exception):
    pass


class Novem404(NovemException):
    pass


class Novem403(NovemException):
    pass


class Novem401(NovemException):
    pass


class NovemAPI(object):
    """
    Novem API class

    * Read config file
    * Communicate with api.novem.no
    * Offer utilities for subclasses
    """

    id: Optional[str] = None

    def __init__(self, **kwargs: Any) -> None:
        """ """

        (config_status, config) = get_current_config(**kwargs)

        # api root should alwasy be supplied in the result
        self.api_root = config["api_root"]

        if "token" in config:
            self.token = config["token"]
        elif not config_status:
            print("Novem config file is missing.")
            print(
                "Either specify config file location with "
                "the config_path parameter."
            )
            print("or setup a new token using python -m novem --init")
            sys.exit(0)

        if self.api_root[-1] != "/":
            # our code assumes that the api_root ends with a /
            self.api_root = f"{self.api_root}/"

    def parse_kwargs(self, **kwargs: Any) -> None:
        """
        Parse the arguments and invoke the novem api
        """

        if "type" in kwargs:
            self.type = kwargs["type"]
        if "api_root" in kwargs:
            self.api_root = kwargs["api_root"]

    def create_token(self, params: Dict[str, str]) -> Dict[str, str]:

        r = requests.post(
            f"{self.api_root}token",
            json=params,
        )

        if not r.ok:
            resp = r.json()
            if r.status_code == 401:
                raise Novem401(resp["message"])

        res = r.json()

        return res

    def delete(self, path: str) -> bool:

        r = requests.delete(
            f"{self.api_root}{path}",
            auth=("", self.token),
        )

        if not r.ok:
            resp = r.json()
            if r.status_code == 404:
                raise Novem404(resp["message"])

        return r.ok

    def read(self, path: str) -> str:

        r = requests.get(
            f"{self.api_root}{path}",
            auth=("", self.token),
        )

        if not r.ok:
            resp = r.json()
            if r.status_code == 404:
                raise Novem404(resp["message"])

        return r.text

    def api_read(self, relpath: str) -> str:
        """
        Read the api value located at realtive path
        """
        pass

    def api_delete(self, relpath: str) -> None:
        """
        relpath: relative path to the plot baseline /config/type
                 for the type file in the config folder
        value: the value to write to the file
        """
        pass

    def api_create(self, relpath: str) -> None:
        """
        relpath: relative path to the plot baseline /config/type
                 for the type file in the config folder
        value: the value to write to the file
        """
        pass

    def api_write(self, relpath: str, value: str) -> None:
        """
        relpath: relative path to the plot baseline /config/type
                 for the type file in the config folder
        value: the value to write to the file
        """
        pass
