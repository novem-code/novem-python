import sys
import urllib.request
from typing import Any, Dict, Optional

import requests

from .utils import get_current_config
from .version import __version__


def get_ua(is_cli: bool) -> Dict[str, str]:
    name = "NovemCli" if is_cli else "NovemLib"
    py_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    return {
        "User-Agent": f"{name}/{__version__} Python/{py_version}",
    }


class NovemException(Exception):
    pass


class Novem404(NovemException):
    def __init__(self, message: str):

        # 404 errors can occur if users are not authenticated, let them know
        # future improvement: consider requesting a fixed endpoint (like
        # whoami) and notify if not authenticated
        message = f"Resource not found: {message} (Are you authenticated?)"

        super().__init__(message)


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
    _type: Optional[str] = None
    _qpr: Optional[str] = None

    def __init__(self, **kwargs: Any) -> None:
        """ """

        config_status, config = get_current_config(**kwargs)

        self._config = config
        self._session = requests.Session()
        self._session.headers.update(get_ua(kwargs.get("is_cli", False)))
        self._session.proxies = urllib.request.getproxies()

        if self._config["ignore_ssl_warn"]:
            # supress ssl warnings
            self._session.verify = False
            import urllib3

            urllib3.disable_warnings()

        # api root should always be supplied in the result
        self._api_root = config["api_root"]

        if config.get("token", None):
            assert config["token"]
            self.token = config["token"]
            self._session.auth = ("", self.token)

        elif not config_status:
            print(
                """\
Novem config file is missing.  Either specify config file location with
the config_path parameter, or setup a new token using
$ python -m novem --init
"""
            )
            sys.exit(0)

        if self._api_root[-1] != "/":
            # our code assumes that the api_root ends with a /
            self._api_root = f"{self._api_root}/"

    def _parse_kwargs(self, **kwargs: Any) -> None:
        """
        Parse the arguments and invoke the novem api
        """

        if "api_root" in kwargs:
            self._api_root = kwargs["api_root"]

    def create_token(self, params: Dict[str, str]) -> Dict[str, str]:

        r = self._session.post(
            f"{self._api_root}token",
            auth=None,
            json=params,
        )

        if not r.ok:
            resp = r.json()
            if r.status_code == 401:
                raise Novem401(resp["message"])

        res = r.json()

        return res

    def delete(self, path: str) -> bool:

        r = self._session.delete(
            f"{self._api_root}{path}",
        )

        if not r.ok:
            resp = r.json()
            if r.status_code == 404:
                raise Novem404(resp["message"])
            else:
                print(r.json())

        return r.ok

    def read(self, path: str) -> str:

        r = self._session.get(
            f"{self._api_root}{path}",
        )

        if not r.ok:
            resp = r.json()
            if r.status_code == 404:
                raise Novem404(resp["message"])

        return r.text

    def write(self, path: str, value: str) -> None:

        r = self._session.post(
            f"{self._api_root}{path}",
            headers={
                "Content-type": "text/plain",
            },
            data=value.encode("utf-8"),
        )

        if not r.ok:
            resp = r.json()
            if r.status_code == 404:
                raise Novem404(resp["message"])
            else:
                print(r.json())

    def create(self, path: str) -> None:

        r = self._session.put(
            f"{self._api_root}{path}",
        )

        if not r.ok:
            resp = r.json()
            if r.status_code == 404:
                raise Novem404(resp["message"])
            else:
                print(r.json())

#
#    @abstractmethod
#    def _read(self, relpath: str) -> str:
#        """
#        Read the api value located at realtive path
#        """
#        pass
#
#    @abstractmethod
#    def _write(self, relpath: str, value: str) -> None:
#        """
#        relpath: relative path to the plot baseline /config/type
#                 for the type file in the config folder
#        value: the value to write to the file
#        """
#        pass
#
#    @abstractmethod
#    def api_read(self, relpath: str) -> str:
#        """
#        Read the api value located at realtive path
#        """
#        pass
#
#    @abstractmethod
#    def api_read_bytes(self, relpath: str) -> bytes:
#        """
#        Read the api value located at realtive path
#        """
#        pass
#
#    @abstractmethod
#    def api_delete(self, relpath: str) -> None:
#        """
#        relpath: relative path to the plot baseline /config/type
#                 for the type file in the config folder
#        value: the value to write to the file
#        """
#        pass
#
#    @abstractmethod
#    def api_create(self, relpath: str) -> None:
#        """
#        relpath: relative path to the plot baseline /config/type
#                 for the type file in the config folder
#        value: the value to write to the file
#        """
#        pass
#
#    @abstractmethod
#    def api_write(self, relpath: str, value: str) -> None:
#        """
#        relpath: relative path to the plot baseline /config/type
#                 for the type file in the config folder
#        value: the value to write to the file
#        """
#        pass
