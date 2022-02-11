import configparser
import sys
from typing import Any, Dict, Optional

import requests

from .utils import get_config_path


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
        """"""

        if "config_path" not in kwargs:
            (novem_dir, config_path) = get_config_path()
        else:
            config_path = kwargs["config_path"]

        ignore_config = False
        if "ignore_config" in kwargs:
            ignore_config = kwargs["ignore_config"]

        config = configparser.ConfigParser()

        # check if novem config file exist
        config.read(config_path)

        try:
            self.token = config["default"]["token"]
            self.api_root = config["default"]["api_root"]
        except KeyError:
            if not ignore_config:
                print("Novem config file is missing.")
                print(
                    "Either specify config file location with "
                    "the config_path parameter."
                )
                print("or setup a new token using python -m novem --init")
                sys.exit(0)
            else:
                if "default" not in config:
                    self.api_root = kwargs["api_root"]
                pass

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

    def create_token(self, params: Dict[str, str]) -> str:

        r = requests.post(
            f"{self.api_root}/token",
            json=params,
        )

        if not r.ok:
            resp = r.json()
            if r.status_code == 401:
                raise Novem401(resp["message"])

        res = r.json()

        return res["token"]

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
