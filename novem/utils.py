import configparser
import datetime
import email.utils as eut
import io
import os
import platform
import re
import select
import shutil
import sys
import unicodedata
from dataclasses import dataclass
from datetime import timezone
from typing import Any, Dict, List, Optional, Tuple, Union, cast

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


def pretty_format(values: List[Dict[str, str]], order: List[Dict[str, Any]], striped: bool = False) -> str:
    """
    Constructs a pretty print table of the values in values
    in the order of List
    """

    colors()

    # lets' get total terminal width (we use 120 as default). shutil honours
    # a COLUMNS override and falls back gracefully when there is no tty.
    col = shutil.get_terminal_size(fallback=(120, 24)).columns

    col = col - 2
    return pretty_format_inner(values, order, col, striped=striped)


def pretty_format_inner(
    values: List[Dict[str, str]], order: List[Dict[str, Any]], col: int, striped: bool = False
) -> str:
    # padding width
    pw = 2

    # the width a flexible (shrink/truncate) column is squeezed to before it is
    # considered unrenderable - shared by the drop test and the shave phases
    min_flex_width = 5

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

    # clip text to a width, with an ellipsis when there is room for one
    def clip(text: str, width: int) -> str:
        if len(text) <= width:
            return text
        if width <= 3:
            return text[:width]
        return text[: width - 3] + "..."

    def padding_for(cols: List[Dict[str, Any]]) -> int:
        # padding follows every column except the last and the no_padding
        # ones (matches the render loops below)
        return sum(pw for o in cols[:-1] if not o.get("no_padding"))

    def min_width(o: Dict[str, Any]) -> int:
        # what a column can be squeezed to before it has to go: flexible
        # columns shave down to the same floor the shave phases use below,
        # "keep" columns only ever hold their natural width
        w = wm[o["key"]]
        if o["overflow"] in ("shrink", "truncate"):
            return min(w, min_flex_width)
        return w

    # When the table does not fit, whole low-value columns are dropped before
    # anything gets mangled. A column opts in with "drop": N — lower N is
    # dropped first (summary=1, name=2, views=3, activity=4 in the listings).
    # The test is against minimum widths, not natural ones, so a wide but
    # truncatable column (a long summary) is squeezed rather than dropped
    # whenever the terminal has room for it at all.
    while sum(min_width(o) for o in order) + padding_for(order) > col:
        droppable = [o for o in order if "drop" in o]
        if not droppable:
            break
        victim = min(droppable, key=lambda o: o["drop"])
        order = [o for o in order if o is not victim]

    if not order:
        return ""

    # forget widths of dropped columns
    wm = {o["key"]: wm[o["key"]] for o in order}

    # let's calculate our actual widths
    total_padding = padding_for(order)
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
                    wm[o["key"]] = max(min_flex_width, int(rem_after_shrink / len(truncate_cols)))
        else:
            # Shrink columns need to be reduced
            # Allocate space proportionally between shrink and truncate
            all_flexible = shrink_cols + truncate_cols
            if all_flexible:
                total_natural = sum(wm[o["key"]] for o in all_flexible)
                for o in all_flexible:
                    # Proportional allocation based on natural width
                    proportion = wm[o["key"]] / total_natural if total_natural > 0 else 1 / len(all_flexible)
                    wm[o["key"]] = max(min_flex_width, int(rem_after_keep * proportion))

    # HARD guarantee: the table never exceeds the terminal width. The
    # allocation above is best-effort — its floors, and "keep" columns on a
    # narrow terminal, can still overflow. Shave the widest column of the
    # least precious class first (truncate, then shrink, then keep), in
    # progressively lower floors, until everything fits. Columns marked
    # "protect" (e.g. the schedule grid) are only touched as a last resort.
    shave_phases = [
        ("truncate", min_flex_width),
        ("shrink", min_flex_width),
        ("truncate", 3),
        ("shrink", 3),
        ("keep", 3),
        ("truncate", 1),
        ("shrink", 1),
        ("keep", 1),
    ]
    for protected_too in (False, True):
        for phase, floor in shave_phases:
            while sum(wm.values()) + total_padding > col:
                cands = [
                    o
                    for o in order
                    if o["overflow"] == phase and wm[o["key"]] > floor and (protected_too or not o.get("protect"))
                ]
                if not cands:
                    break
                widest = max(cands, key=lambda o: wm[o["key"]])
                wm[widest["key"]] -= 1

    # construct output string
    los = f"{cl.BOLD}"
    for o in order:
        w = f":<{wm[o['key']]}"
        fmt = "{0" + w + "}"
        col_pad = "" if o.get("no_padding") else " " * pw
        # headers respect the column width too — an over-long header used to
        # push the whole line past the terminal edge
        los += fmt.format(clip(o["header"], wm[o["key"]])) + col_pad

    los += f"{cl.ENDC}\n"
    # sep
    for o in order:
        w = f":<{wm[o['key']]}"
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
            align = ">" if o.get("align") == "right" else "<"
            w = f":{align}{wm[o['key']]}"
            fmt = "{0" + w + "}"
            try:
                vs = wm[o["key"]]
                ov = p[o["key"]]
            except KeyError:
                vs = 0
                ov = ""

            if ov is None:
                ov = ""

            if "fmt" in o:
                # Call fmt function on the ORIGINAL value (before any string conversion)
                val = o["fmt"](ov, cl)
                # Adjust format width for invisible ANSI characters
                val_str = str(val)
                visual_len = len(strip_ansi(val_str))
                actual_len = len(val_str)
                invisible_chars = actual_len - visual_len
                adjusted_width = wm[o["key"]] + invisible_chars
                w = f":{align}{adjusted_width}"
                fmt = "{0" + w + "}"
                # Truncation on formatted value (loses ANSI codes if truncated)
                if visual_len > vs:
                    val = clip(strip_ansi(val_str), vs)
                    # Reset width since we stripped ANSI
                    w = f":{align}{vs}"
                    fmt = "{0" + w + "}"
            else:
                # Use visual length (stripped of ANSI codes) to determine truncation
                ov_visual = strip_ansi(str(ov))
                if len(ov_visual) > vs:
                    # Truncate based on visual length, keeping ANSI codes intact where possible
                    # For simplicity, strip ANSI first, truncate, then we lose colors on truncated text
                    val = clip(ov_visual, vs)
                else:
                    val = ov

            val = fmt.format(val)

            if "clr" in o:
                if striped and i % 2 == 0:
                    val = f"{o['clr']}{val}{cl.ENDC}{cl.BGGRAY}"
                else:
                    val = f"{o['clr']}{val}{cl.ENDC}"

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


@dataclass
class _StdinReadiness:
    has_data: bool
    is_test: bool


def _stdin_readiness() -> _StdinReadiness:
    try:
        # use msvcrt on windows
        import msvcrt

        return _StdinReadiness(has_data=msvcrt.kbhit(), is_test=False)  # type: ignore
    except ImportError:
        try:
            # use select on linux
            has_data = bool(select.select([sys.stdin], [], [], 0.0)[0])
            return _StdinReadiness(has_data=has_data, is_test=False)
        except io.UnsupportedOperation:
            # Pytest replaces stdin with a stream that must not be read. A
            # StringIO, on the other hand, is an intentional test input.
            has_data = isinstance(sys.stdin, io.StringIO)
            return _StdinReadiness(has_data=has_data, is_test=True)


def stream_on_stdin() -> Optional[Any]:
    """Return stdin without consuming it when input should be forwarded.

    Real redirected stdin may not have bytes available at the instant the
    command starts, so every non-interactive stream is returned. Callers that
    need binary-safe incremental input can consume the returned buffer while
    doing their other work concurrently.
    """

    readiness = _stdin_readiness()
    is_noninteractive = not sys.stdin.isatty()
    has_data = readiness.has_data or (is_noninteractive and not readiness.is_test)
    if not has_data:
        return None
    return getattr(sys.stdin, "buffer", sys.stdin)


def data_on_stdin() -> Optional[str]:
    """Read text waiting on stdin, preserving the legacy buffered behavior."""

    ctnt = "".join(sys.stdin.readlines()) if stream_on_stdin() is not None else ""
    return ctnt if ctnt else None


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


def format_datetime_local(dt: datetime.datetime) -> str:
    """Format a datetime as local time in YYYY-MM-DD HH:MM format."""
    local_dt = dt.astimezone()  # Convert to system local timezone
    return local_dt.strftime("%Y-%m-%d %H:%M")
