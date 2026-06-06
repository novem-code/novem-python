import os
import sys
import urllib.request
from typing import Any, Dict, Optional

import requests

from .config import ConfigManager, config, resolve
from .version import __version__

did_token_warning = False


def get_ua(is_cli: bool) -> Dict[str, str]:
    name = "NovemCli" if is_cli else "NovemLib"
    py_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"

    # Include pandas version if available
    pandas_part = ""
    try:
        import pandas as pd

        pandas_part = f" Pandas/{pd.__version__}"
    except ImportError:
        pass

    return {
        "User-Agent": f"{name}/{__version__} Python/{py_version}{pandas_part}",
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


class Novem409(NovemException):
    pass


class Novem401(NovemException):
    pass


class NovemAPI(object):
    """
    Novem API class

    * Read config file
    * Communicate with API_ROOT
    * Offer utilities for subclasses
    """

    id: Optional[str] = None
    _type: Optional[str] = None
    _qpr: Optional[str] = None

    def __init__(
        self,
        *,
        token: Optional[str] = None,
        api_root: Optional[str] = None,
        config_path: Optional[str] = None,
        profile: Optional[str] = None,
        config_profile: Optional[str] = None,
        ignore_ssl: bool = False,
        ignore_config: bool = False,
        is_cli: bool = False,
        config_manager: Optional[ConfigManager] = None,
        **kwargs: Any,
    ) -> None:
        """Initialise the API client.

        Connection settings are explicit keyword arguments; any explicitly
        supplied value wins over the globally configured defaults
        (``novem.config``).  Extra ``**kwargs`` (content/behaviour options
        consumed by subclasses) are accepted and ignored at this layer.

        ``config_manager`` lets a caller resolve against a specific (bound)
        ConfigManager instead of the process-wide ``novem.config`` default —
        the foundation for per-profile factories. Defaults to the global one.
        """

        # only forward connection options that were actually supplied so the
        # global defaults can fill in the rest
        conn: Dict[str, Any] = {}
        if token is not None:
            conn["token"] = token
        if api_root is not None:
            conn["api_root"] = api_root
        if config_path is not None:
            conn["config_path"] = config_path
        if profile is not None:
            conn["profile"] = profile
        if config_profile is not None:
            conn["config_profile"] = config_profile
        if ignore_ssl:
            conn["ignore_ssl"] = ignore_ssl
        if ignore_config:
            conn["ignore_config"] = ignore_config

        config_status, cfg = resolve(default=config_manager or config, **conn)

        self._config = cfg
        self._session = requests.Session()
        self._session.headers.update(get_ua(is_cli))
        self._session.proxies = urllib.request.getproxies()

        if cfg.ignore_ssl:
            # supress ssl warnings
            self._session.verify = False
            import urllib3

            urllib3.disable_warnings()

        self._api_root = cfg.api_root

        if cfg.token:
            self.token = cfg.token
            self._session.headers["Authorization"] = f"Bearer {self.token}"

            # Warn if NOVEM_TOKEN is set to a different value than the resolved token
            env_token = os.getenv("NOVEM_TOKEN")
            global did_token_warning
            if env_token and env_token != self.token and not did_token_warning:
                did_token_warning = True
                print("WARN: Both NOVEM_TOKEN and config file token are set. Using config file token.", file=sys.stderr)

        elif not config_status:
            print("""\
Novem config file is missing.  Either specify config file location with
the config_path parameter, setup a new token using
$ python -m novem --init
or set the NOVEM_TOKEN environment variable.\
""")
            sys.exit(0)

        if self._api_root[-1] != "/":
            # our code assumes that the api_root ends with a /
            self._api_root = f"{self._api_root}/"

    def _parse_kwargs(self, **kwargs: Any) -> None:
        """Terminator for the cooperative ``_parse_kwargs`` chain.

        Connection settings (including ``api_root``) are resolved once in
        ``__init__``; subclasses override this to apply their own content
        properties.
        """

    def create_token(self, params: Dict[str, str]) -> Dict[str, str]:
        r = requests.post(
            f"{self._api_root}token",
            headers={"User-Agent": self._session.headers["User-Agent"]},
            json=params,
        )

        if not r.ok:
            try:
                resp = r.json()
            except ValueError:
                resp = {}
            message = resp.get("message") or r.text or f"HTTP {r.status_code}"
            if r.status_code == 401:
                raise Novem401(message)
            raise NovemException(message)

        return r.json()

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

    def create(self, path: str, raise_on_conflict: bool = False) -> bool:
        """PUT to create a resource. Returns True if created, False on 409.

        Args:
            path: API path to create.
            raise_on_conflict: If True, raise Novem409 on HTTP 409 instead of
                returning False.
        """

        r = self._session.put(
            f"{self._api_root}{path}",
        )

        if not r.ok:
            resp = r.json()
            if r.status_code == 404:
                raise Novem404(resp["message"])
            elif r.status_code == 409:
                if raise_on_conflict:
                    raise Novem409(resp.get("message", "Resource already exists"))
                return False
            else:
                print(r.json())

        return True
