import configparser
import io
import os
import platform
import select
import sys
import unicodedata
from typing import Any, Dict, List, Tuple, Union

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
    BOLD = "\033[1m"
    UNDERLINE = "\033[4m"
    BGGRAY = "\033[48:5:234m"


def disable_colors() -> None:
    cl.HEADER = ""
    cl.OKBLUE = ""
    cl.OKCYAN = ""
    cl.OKGREEN = ""
    cl.WARNING = ""
    cl.FAIL = ""
    cl.ENDC = ""
    cl.BOLD = ""
    cl.UNDERLINE = ""
    cl.BGGRAY = ""


def colors() -> None:
    # disable colors if not supported
    for handle in [sys.stdout, sys.stderr]:
        if (hasattr(handle, "isatty") and handle.isatty()) or (
            "TERM" in os.environ and os.environ["TERM"] == "ANSI"
        ):
            if platform.system() == "Windows" and not (
                "TERM" in os.environ and os.environ["TERM"] == "ANSI"
            ):
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
) -> Tuple[bool, Dict[str, str]]:
    """
    Resolve and return the current config options

    Contains :
    current user
    current profile
    current token
    current api_root
    """

    # config path can be supplied as an option, if it is use that
    if "config_path" not in kwargs or not kwargs["config_path"]:
        (novem_dir, config_path) = get_config_path()
    else:
        config_path = kwargs["config_path"]

    co: Dict[str, str] = {}

    # in addition, we can be instructed to ignore the config
    # if we are ignoring the config then the api root must be provided
    if "ignore_config" in kwargs:
        co["api_root"] = kwargs["api_root"]

        # return (True:Bool, co:Dict[str, str])
        return (True, co)

    # construct a config object
    config = configparser.ConfigParser()

    # check if novem config file exist
    config.read(config_path)

    # if api_root is present in kwagars it overrides all other options
    co["api_root"] = ""
    if "api_root" in kwargs and kwargs["api_root"]:
        co["api_root"] = kwargs["api_root"]

    # the configuration file has an invalid format
    try:
        general = config["general"]
        profile = general["user"]
        if "api_root" in general:
            co["api_root"] = general["api_root"]
    except KeyError:
        return (False, co)

    # get our config
    try:
        uc = config[f"user:{profile}"]
        if "api_root" in uc:
            co["api_root"] = uc["api_root"]

        co["token"] = uc["token"]
        co["username"] = uc["username"]

    except KeyError:
        return (True, co)

    # kwargs supercedes
    if "api_root" in kwargs and kwargs["api_root"]:
        co["api_root"] = kwargs["api_root"]

    if "token" in kwargs and kwargs["token"]:
        co["token"] = kwargs["token"]

    return (True, co)


def pretty_format(
    values: List[Dict[str, str]], order: List[Dict[str, Any]]
) -> str:
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
            cand = max([ucl(x[k]) for x in values])
        except ValueError:
            cand = 0

        wm[k] = max([cand, len(o["header"])])

    # let's calculate our actual widths
    if sum(wm.values()) + (len(order) - 1) * pw > col:
        # we need to adjust our sizing
        ainst = {}

        nts = 0
        for o in order:
            aos = wm[o["key"]]
            if o["overflow"] == "keep" and nts + aos < col:
                ainst[o["key"]] = "keep"
                nts += aos

        rem = col - nts - ((len(order) - 1) * pw)

        # allocate truncate width
        nks = [x for x in order if x["overflow"] != "keep"]
        for o in nks:
            wm[o["key"]] = int(rem / len(nks))

    # construct output string
    los = f"{cl.BOLD}"
    for o in order:
        w = f':<{wm[o["key"]]}'
        fmt = "{0" + w + "}"
        los += fmt.format(o["header"]) + " " * pw

    los += f"{cl.ENDC}\n"
    # sep
    for o in order:
        w = f':<{wm[o["key"]]}'
        fmt = "{0" + w + "}"
        # los += fmt.format("┄" * wm[o["key"]]) + " " * pw
        los += fmt.format("╌" * wm[o["key"]]) + " " * pw

    los += "\n"

    i = 0
    for p in values:
        for o in order:
            w = f':<{wm[o["key"]]}'
            fmt = "{0" + w + "}"
            vs = wm[o["key"]]
            ov = p[o["key"]]
            if ov is None:
                ov = ""

            if len(ov) > vs:
                val = ov[0 : vs - 3] + "..."
            else:
                val = ov[0:vs]

            if "fmt" in o:
                val = o["fmt"](val)

            val = fmt.format(val)

            if "clr" in o:
                if i % 2 == 0:
                    val = f'{o["clr"]}{val}{cl.ENDC}{cl.BGGRAY}'
                else:
                    val = f'{o["clr"]}{val}{cl.ENDC}'

            if o == order[-1]:
                pad = ""
            else:
                pad = " " * pw

            if i % 2 == 0:
                los += f"{cl.BGGRAY}" + val + pad + f"{cl.ENDC}"
            else:
                los += val + pad

        los += "\n"
        i += 1

    return los


def data_on_stdin() -> Tuple[bool, str]:
    """
    identify if there is data waiting on sys.stdin
    """

    has_data = False

    try:
        # use msvcrt on windows
        import msvcrt

        if msvcrt.kbhit():  # type: ignore
            has_data = True
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
        except io.UnsupportedOperation:
            # We're going to assume that this is the pytest wrapper
            # if sys.stdin is an instance of io.StringIO we are mocking data
            # on stdin, so it should be true. else ignore.
            has_data = isinstance(sys.stdin, io.StringIO)

    ctnt = ""
    if has_data:
        ctnt = "".join([x for x in sys.stdin])
        if ctnt == "":
            ctnt = ""
            has_data = False

    return has_data, ctnt
