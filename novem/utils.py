import configparser
import io
import os
import platform
import re
import select
import sys
import unicodedata
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple, Union, cast

from packaging.version import InvalidVersion, Version

from novem.types import Config

API_ROOT = "https://api.novem.io/v1/"
NOVEM_PATH = "novem"
NOVEM_NAME = "novem.conf"


# find ansi escape sequences in string
ansi_escape = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")


def strip_ansi(text: str) -> str:
    return ansi_escape.sub("", text)


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
            "api_root": kwargs.get("api_root", None),
            "ignore_ssl_warn": kwargs.get("ignore_ssl", False),
        }
    )

    if kwargs.get("token", False) or "ignore_config" in kwargs:
        return True, co

    # config path can be supplied as an option, if it is use that
    if "config_path" not in kwargs or not kwargs["config_path"]:
        (novem_dir, config_path) = get_config_path()
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
        return (False, co)

    else:
        migrate_config_04_to_05(config_path, config, co)
        ensure_cli_defaults(config_path, config)

    # override profile
    profile = kwargs.get("config_profile") or profile

    # get our config
    try:
        uc = config[f"profile:{profile}"]
        if "api_root" in uc:
            co["api_root"] = uc["api_root"]

        co["token"] = uc["token"]
        co["username"] = uc["username"]

        if "ignore_ssl_warn" in uc:
            co["ignore_ssl_warn"] = uc.getboolean("ignore_ssl_warn")

    except KeyError:
        return (True, co)

    # kwargs supercedes
    if kwargs.get("api_root", False):
        co["api_root"] = kwargs["api_root"]

    if kwargs.get("token", False):
        co["token"] = kwargs["token"]

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


def pretty_format(values: List[Dict[str, str]], order: List[Dict[str, Any]], striped: bool = False) -> str:
    """
    Constructs a pretty print table of the values in values
    in the order of List
    """

    colors()

    # lets' get total terminal width (we use 120 as default)
    try:
        (col, row) = os.get_terminal_size()
    except OSError:
        col = 120

    col = col - 2
    return pretty_format_inner(values, order, col, striped=striped)


def pretty_format_inner(
    values: List[Dict[str, str]], order: List[Dict[str, Any]], col: int, striped: bool = False
) -> str:
    # padding width
    pw = 2

    # unicode aware string length https://stackoverflow.com/questions/33351599/
    def ucl(word: str) -> int:
        if not word:
            return 0
        return sum(1 for ch in word if unicodedata.combining(ch) == 0)

    # construct width map
    wm = {}
    for o in order:
        k = o["key"]
        try:
            cs = []
            for x in values:
                if "fmt" in o:
                    fs = strip_ansi(o["fmt"](x[k], cl))
                    c = ucl(fs)
                else:
                    # Always strip ANSI codes to get visual width
                    c = ucl(strip_ansi(str(x[k]) if x[k] is not None else ""))
                cs.append(c)

            cand = max(cs)
            # cand = max([ucl(x[k]) for x in values])
        except ValueError:
            cand = 0
        except KeyError:
            if "fmt" in o:
                fs = strip_ansi(o["fmt"]("", cl))
                cand = ucl(fs)
            else:
                cand = 0

        wm[k] = max([cand, len(o["header"])])

    # let's calculate our actual widths
    total_padding = (len(order) - 1) * pw
    if sum(wm.values()) + total_padding > col:
        # we need to adjust our sizing
        # Priority: keep > shrink > truncate

        # 1. Reserve space for "keep" columns first
        keep_total = 0
        for o in order:
            if o["overflow"] == "keep":
                keep_total += wm[o["key"]]

        rem_after_keep = col - keep_total - total_padding

        # 2. Handle "shrink" columns - use natural width if fits, otherwise reduce
        shrink_cols = [x for x in order if x["overflow"] == "shrink"]
        shrink_natural_total = sum(wm[o["key"]] for o in shrink_cols)

        # 3. Handle "truncate" columns - they share remaining space
        truncate_cols = [x for x in order if x["overflow"] == "truncate"]

        if shrink_natural_total <= rem_after_keep:
            # Shrink columns fit at natural width
            rem_after_shrink = rem_after_keep - shrink_natural_total
            # Truncate columns share the rest
            if truncate_cols:
                for o in truncate_cols:
                    wm[o["key"]] = max(5, int(rem_after_shrink / len(truncate_cols)))
        else:
            # Shrink columns need to be reduced
            # Allocate space proportionally between shrink and truncate
            all_flexible = shrink_cols + truncate_cols
            if all_flexible:
                total_natural = sum(wm[o["key"]] for o in all_flexible)
                for o in all_flexible:
                    # Proportional allocation based on natural width
                    proportion = wm[o["key"]] / total_natural if total_natural > 0 else 1 / len(all_flexible)
                    wm[o["key"]] = max(5, int(rem_after_keep * proportion))

    # construct output string
    los = f"{cl.BOLD}"
    for o in order:
        w = f':<{wm[o["key"]]}'
        fmt = "{0" + w + "}"
        col_pad = "" if o.get("no_padding") else " " * pw
        los += fmt.format(o["header"]) + col_pad

    los += f"{cl.ENDC}\n"
    # sep
    for o in order:
        w = f':<{wm[o["key"]]}'
        fmt = "{0" + w + "}"
        col_pad = "" if o.get("no_padding") else " " * pw
        if o.get("no_border"):
            los += fmt.format(" " * wm[o["key"]]) + col_pad
        else:
            los += fmt.format("╌" * wm[o["key"]]) + col_pad

    los += "\n"

    i = 0
    for p in values:
        for o in order:
            w = f':<{wm[o["key"]]}'
            fmt = "{0" + w + "}"
            try:
                vs = wm[o["key"]]
                ov = p[o["key"]]
            except KeyError:
                vs = 0
                ov = ""

            if ov is None:
                ov = ""

            # Use visual length (stripped of ANSI codes) to determine truncation
            ov_visual = strip_ansi(str(ov))
            if len(ov_visual) > vs:
                # Truncate based on visual length, keeping ANSI codes intact where possible
                # For simplicity, strip ANSI first, truncate, then we lose colors on truncated text
                val = ov_visual[0 : vs - 3] + "..."
            else:
                val = ov

            if "fmt" in o:
                val = o["fmt"](val, cl)

            val = fmt.format(val)

            if "clr" in o:
                if striped and i % 2 == 0:
                    val = f'{o["clr"]}{val}{cl.ENDC}{cl.BGGRAY}'
                else:
                    val = f'{o["clr"]}{val}{cl.ENDC}'

            if o == order[-1]:
                pad = ""
            elif o.get("no_padding"):
                pad = ""
            else:
                pad = " " * pw

            if striped and i % 2 == 0:
                los += f"{cl.BGGRAY}" + val + pad + f"{cl.ENDC}"
            else:
                los += val + pad

        los += "\n"
        i += 1

    return los


def data_on_stdin() -> Optional[str]:
    """
    identify if there is data waiting on sys.stdin
    """

    @dataclass
    class Result:
        has_data: bool
        is_test: bool

    def _data_ready() -> Result:
        try:
            # use msvcrt on windows
            import msvcrt

            r = msvcrt.kbhit()  # type: ignore
            return Result(has_data=r, is_test=False)

        except ImportError:
            try:
                # use select on linux
                has_data = bool(
                    select.select(
                        [
                            sys.stdin,
                        ],
                        [],
                        [],
                        0.0,
                    )[0]
                )

                return Result(has_data=has_data, is_test=False)
            except io.UnsupportedOperation:
                # We're going to assume that this is the pytest wrapper
                # if sys.stdin is an instance of io.StringIO we are mocking data
                # on stdin, so it should be true. else ignore.
                has_data = isinstance(sys.stdin, io.StringIO)
                return Result(has_data=has_data, is_test=True)

    r = _data_ready()

    is_noninteractive = not sys.stdin.isatty()
    has_data = r.has_data or (is_noninteractive and not r.is_test)

    ctnt = "".join(sys.stdin.readlines()) if has_data else ""
    return ctnt if ctnt else None


def migrate_config_04_to_05(path: str, config: configparser.ConfigParser, co: Config) -> bool:
    # before: there is no `version` key in the [app:cli] section, or the version is less than 0.5
    # action: insert version, and rewrite all `api.novem.no` URLs to `api.novem.io'

    try:
        version = Version(config["app:cli"]["version"])
    except (KeyError, InvalidVersion):
        version = Version("0.4")

    if version >= Version("0.5"):
        # we're good!
        return False

    # set this to 0.5 instead of the actual version to allow for stacked migrations in the future
    if not config.has_section("app:cli"):
        config.add_section("app:cli")

    config["app:cli"]["version"] = "0.5"

    for section in config.sections():
        if "api_root" in config[section]:
            config[section]["api_root"] = config[section]["api_root"].replace("api.novem.no", "api.novem.io")

    co["api_root"] = co["api_root"].replace("api.novem.no", "api.novem.io")

    with open(path, "w") as configfile:
        config.write(configfile)

    print("Migrating to 0.5 complete. API url updated from api.novem.no to api.novem.io")
    return True


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
