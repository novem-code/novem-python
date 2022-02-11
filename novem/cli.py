import getpass
import os
import platform
import random
import socket
import string
import sys
from datetime import datetime
from typing import Any, Dict, Union

from .api import Novem401, NovemAPI
from .setup import setup
from .utils import check_if_profile_exists, update_config


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


def do_update_config(
    profile: str, username: str, api_root: str, token_name: str, token: str
) -> None:
    (status, path) = update_config(
        profile, username, api_root, token_name, token
    )

    print(
        f"{cl.OKGREEN} \u2713 {cl.ENDC}new token "
        f'{cl.OKCYAN}"{token_name}"{cl.ENDC} created and'
        f" saved to {path}"
    )

    # save file


def init_config(args: Dict[str, str] = None) -> None:
    """
    Initialize the novem config and write to file.
    """

    if not args:
        # make mypy happy, return if no argument supplied
        return

    token_name: Union[str, None] = None

    if "token" in args:
        token_name = args["token"]

    api_root: str = args["api-url"]
    profile: str = args["profile-name"]
    force: str = args["force"]

    # first check if we have a valid config
    profile_exists: bool = check_if_profile_exists(profile)
    if profile_exists and not force:
        print(
            f"{cl.WARNING} ! {cl.ENDC}"
            f' The supplied profile "{cl.OKCYAN}{profile}{cl.ENDC}" already '
            f"exist, use --force to override"
        )
        sys.exit(1)

    valid_char_sm = string.ascii_lowercase + string.digits
    valid_char = valid_char_sm + "-_"
    hostname: str = socket.gethostname()

    if not token_name:
        token_hostname: str = "".join(
            [x for x in hostname.lower() if x in valid_char]
        )
        nounce: str = "".join(random.choice(valid_char_sm) for _ in range(8))
        token_name = f"novem-python-{token_hostname}-{nounce}"

    new_token_name = "".join([x for x in token_name if x in valid_char])

    if token_name != new_token_name:
        print(
            f"{cl.WARNING} ! {cl.ENDC}"
            "The supplied token contained invalid charracters,"
            f' token changed to "{cl.OKCYAN}{new_token_name}{cl.ENDC}"'
        )
        token_name = new_token_name

    # get novem username
    username = input(" \u2022 novem.no username: ")
    # username = "abc"

    # get novem password
    password = getpass.getpass(" \u2022 novem.no password: ")

    # authenticate and request token by name
    req = {
        "username": username,
        "password": password,
        "token_name": token_name,
        "token_description": (
            f'cli token created for "{hostname}" '
            f'on "{datetime.now():%Y-%m-%d:%H:%M:%S}"'
        ),
    }

    # let's grab our token
    novem = NovemAPI(
        api_root=api_root,
        ignore_config=True,
    )

    try:
        token = novem.create_token(req)
    except Novem401:
        print("Invalid username and/or password")
        sys.exit(1)

    # let's write our config
    do_update_config(profile, username, api_root, token_name, token)


def run_cli(raw_args: Any = None) -> None:
    colors()

    # Gather the provided arguements as an array.
    args: Dict[str, str] = setup(raw_args)

    if args and args["init"]:
        # init_config(args["token"], args["api"])
        init_config(args)


__all__ = ["run_cli"]
