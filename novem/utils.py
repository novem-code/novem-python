import configparser
import datetime
import email.utils as eut
import os
import platform
import sys
from datetime import timezone
from typing import Any, Optional, Tuple, Union, cast

from novem.types import Config

API_ROOT = "https://api.novem.io/v1/"
NOVEM_PATH = "novem"
NOVEM_NAME = "novem.conf"


class cl:
    HEADER = "\033[95m"
    OKBLUE = "\033[94m"
    OKCYAN = "\033[96m"
    OKGREEN = "\033[92m"
    WARNING = "\033[93m"
    FAIL = "\033[91m"
    ENDC = "\033[0m"
    ENDFGC = "\033[39m"
    BOLD = "\033[1m"
    UNDERLINE = "\033[4m"
    FGGRAY = "\033[38;5;246m"
    BGGRAY = "\033[48;5;234m"


def disable_colors() -> None:
    c = cast(Any, cl)
    c.HEADER = ""
    c.OKBLUE = ""
    c.OKCYAN = ""
    c.OKGREEN = ""
    c.WARNING = ""
    c.FAIL = ""
    c.ENDC = ""
    c.ENDFGC = ""
    c.BOLD = ""
    c.UNDERLINE = ""
    c.FGGRAY = ""
    c.BGGRAY = ""


def colors() -> None:
    # ignore color disable if --colors in argv
    for a in sys.argv:
        if os.name == "nt":
            from colorama import just_fix_windows_console  # type: ignore

            just_fix_windows_console()
        if a == "--color":
            return

    if os.name == "nt":
        # TODO: do some proper color detection on nt
        from colorama import just_fix_windows_console

        just_fix_windows_console()
        return

    # disable colors if not supported
    for handle in [sys.stdout, sys.stderr]:
        if (hasattr(handle, "isatty") and handle.isatty()) or ("TERM" in os.environ and os.environ["TERM"] == "ANSI"):
            if platform.system() == "Windows" and not ("TERM" in os.environ and os.environ["TERM"] == "ANSI"):
                disable_colors()
        else:
            disable_colors()


def get_user_config_directory() -> Union[str, None]:
    """Returns a platform-specific root directory for user config settings."""
    # On Windows, prefer %LOCALAPPDATA%, then %APPDATA%, since we can expect
    # the AppData directories to be ACLed to be visible only to the user and
    # admin users (https://stackoverflow.com/a/7617601/1179226). If neither is
    # set, return None instead of falling back to something that may be
    # world-readable.
    if os.name == "nt":
        appdata = os.getenv("LOCALAPPDATA")
        if appdata:
            return appdata
        appdata = os.getenv("APPDATA")
        if appdata:
            return appdata
        return None
    # On non-windows, use XDG_CONFIG_HOME if set, else default to ~/.config.
    xdg_config_home = os.getenv("XDG_CONFIG_HOME")
    if xdg_config_home:
        return xdg_config_home
    return os.path.join(os.path.expanduser("~"), ".config")


def get_config_path() -> Tuple[str, str]:
    """
    Get default configuration path
    """

    config_path: Union[str, None] = get_user_config_directory()
    novem_dir = f"{config_path}/{NOVEM_PATH}"
    novem_config = f"{config_path}/{NOVEM_PATH}/{NOVEM_NAME}"

    return (novem_dir, novem_config)


def _apply_env_fallbacks(co: "Config") -> None:
    """Apply environment variable fallbacks for token and api_root."""
    if not co.get("token"):
        co["token"] = os.getenv("NOVEM_TOKEN")
    if not co.get("api_root"):
        co["api_root"] = os.getenv("NOVEM_API_ROOT") or API_ROOT


def get_current_config(
    **kwargs: Any,
) -> Tuple[bool, Config]:
    """
    Resolve and return the current config options

    Contains :
    current user
    current profile
    current token
    current api_root
    """

    co = Config(
        {
            "token": kwargs.get("token", None),
            "api_root": kwargs.get("api_root") or "",
            "ignore_ssl_warn": bool(kwargs.get("ignore_ssl", False)),
        }
    )

    if kwargs.get("token", False) or "ignore_config" in kwargs:
        _apply_env_fallbacks(co)
        return True, co

    # config path can be supplied as an option, if it is use that
    if "config_path" not in kwargs or not kwargs["config_path"]:
        novem_dir, config_path = get_config_path()
    else:
        config_path = kwargs["config_path"]

    config = configparser.ConfigParser()
    config.read(config_path)

    # the configuration file has an invalid format
    try:
        general = config["general"]
        profile = general["profile"]

        if "api_root" in general:
            co["api_root"] = general["api_root"]

    except KeyError:
        _apply_env_fallbacks(co)
        return (False, co)

    else:
        ensure_cli_defaults(config_path, config)

    # override profile; `profile` is the public-facing alias for the internal
    # `config_profile` selector
    profile = kwargs.get("config_profile") or kwargs.get("profile") or profile

    # get our config
    try:
        uc = config[f"profile:{profile}"]
        if "api_root" in uc:
            co["api_root"] = uc["api_root"]

        co["token"] = uc["token"]
        co["username"] = uc["username"]

        if "ignore_ssl_warn" in uc:
            co["ignore_ssl_warn"] = uc.getboolean("ignore_ssl_warn", False)

    except KeyError:
        _apply_env_fallbacks(co)
        return (True, co)

    # kwargs supercedes
    if kwargs.get("api_root", False):
        co["api_root"] = kwargs["api_root"]

    if kwargs.get("token", False):
        co["token"] = kwargs["token"]

    _apply_env_fallbacks(co)

    co["profile"] = profile

    # Read app:cli settings
    if config.has_section("app:cli"):
        cli_config = config["app:cli"]
        co["cli_striped"] = cli_config.getboolean("striped", fallback=False)
        co["cli_prompt_lines"] = cli_config.getint("prompt_lines", fallback=1)
    else:
        co["cli_striped"] = False
        co["cli_prompt_lines"] = 1

    return (True, co)


def ensure_cli_defaults(path: str, config: configparser.ConfigParser) -> bool:
    """Ensure default CLI settings exist in config."""
    modified = False

    if not config.has_section("app:cli"):
        config.add_section("app:cli")
        modified = True

    if "striped" not in config["app:cli"]:
        config["app:cli"]["striped"] = "false"
        modified = True

    if "prompt_lines" not in config["app:cli"]:
        config["app:cli"]["prompt_lines"] = "1"
        modified = True

    if modified:
        with open(path, "w") as configfile:
            config.write(configfile)

    return modified


def parse_api_datetime(date_str: str) -> Optional[datetime.datetime]:
    """
    Parse an API date string into a timezone-aware datetime.

    The API returns dates in RFC 2822 format with "UTC" suffix, e.g.:
    "Mon, 05 Jan 2026 23:40:13 UTC"

    email.utils.parsedate doesn't recognize "UTC" as a timezone, only numeric
    offsets like "+0000". We normalize the string before parsing.

    Returns a timezone-aware datetime in UTC, or None if parsing fails.
    """
    if not date_str:
        return None
    try:
        # Normalize "UTC" to "+0000" for email.utils parsing
        normalized = date_str.replace(" UTC", " +0000").replace(" GMT", " +0000")
        return eut.parsedate_to_datetime(normalized)
    except Exception:
        # Fallback: try parsing without timezone, assume UTC
        try:
            parsed = eut.parsedate(date_str)
            if parsed:
                dt = datetime.datetime(*parsed[:6])
                return dt.replace(tzinfo=timezone.utc)
        except Exception:
            pass
        return None
