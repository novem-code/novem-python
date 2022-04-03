import getpass
import random
import readline
import socket
import string
import sys
from datetime import datetime
from signal import SIG_DFL, SIGPIPE, signal
from typing import Any, Dict, Union

from ..api import Novem401, NovemAPI
from ..utils import cl, colors, get_current_config
from ..version import __version__
from .config import check_if_profile_exists, update_config
from .plot import plot
from .setup import setup


def input_with_prefill(prompt: str, text: str) -> Any:
    def hook() -> Any:
        readline.insert_text(text)
        readline.redisplay()

    readline.set_pre_input_hook(hook)
    result = input(prompt)
    readline.set_pre_input_hook()
    return result


def do_update_config(
    profile: str,
    username: str,
    api_root: str,
    token_name: str,
    token: str,
    path: str,
) -> None:
    (status, path) = update_config(
        profile, username, api_root, token_name, token, path
    )

    print(
        f"{cl.OKGREEN} \u2713 {cl.ENDC}new token "
        f'{cl.OKCYAN}"{token_name}"{cl.ENDC} created and'
        f" saved to {path}"
    )

    # save file


def init_config(args: Dict[str, str] = None) -> None:
    """
    Initialize user and config

    the --init flag has been supplied, this means we are going to update the
    configuration file. There are several different scenarios we have to adapt
    to in this case:

    * a simple --init with no options and missing config file
      * request username and password from user
      * authenticate against service
      * create config file and store credentials if successful

    * a simple --init with no options and existing config file
      * check if config has a default user
      * if default user exist in config, inform user that config
      * already exist and terminate

    * a simple --init with --profile <username> and missing config file
      * request username and password from user
        * with username prefilled as --profile
      * authenticate against service
      * create config file and store credentials if successful

      --init

      --profile
      --token
      --api-url
      --force

      user in config

      config exist



      if --token not supplied, request username and password
      if --profile specified, prefill username

      if token supplied request token info, if username password

    """

    if not args:
        # make mypy happy, return if no argument supplied
        return

    token: Union[str, None] = None

    if "token" in args:
        token = args["token"]

    api_root: str = args["api-url"]
    profile: str = args["profile"]
    force: str = args["force"]
    config_path: str = args["config_path"]

    # first check if we have a valid config
    profile_exists: bool = check_if_profile_exists(profile, config_path)
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

    token_name: Union[str, None] = None
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
            "The supplied token name contained invalid charracters,"
            f' token changed to "{cl.OKCYAN}{new_token_name}{cl.ENDC}"'
        )
        token_name = new_token_name

    # get novem username
    prefill = ""
    if "profile" in args:
        prefill = args["profile"]

    username = input_with_prefill(" \u2022 novem.no username: ", prefill)
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

    if not api_root:
        (hasconf, curconf) = get_current_config(**args)
        # if our config exist, try to read it from there
        if not hasconf:
            api_root = "https://api.novem.no/v1/"
        else:
            api_root = curconf["api_root"]

    # let's grab our token
    novem = NovemAPI(
        api_root=api_root,
        ignore_config=True,
    )

    try:
        res = novem.create_token(req)
        token = res["token"]
        token_name = res["token_name"]

    except Novem401:
        print("Invalid username and/or password")
        sys.exit(1)

    # default profile to username if not supplied
    if not profile:
        profile = username

    # let's write our config
    do_update_config(
        profile, username, api_root, token_name, token, config_path
    )


def print_short(parser: Any) -> None:
    parser.print_usage()

    print()
    print("Novem commandline interface - no options supplied")
    print()
    print("  novem -h, --help      print a concise help")
    print("  novem --guide         print the comprehensive novem cli guide")
    print()
    print(
        "  novem --init          if you already have an account and want"
        " to get started"
    )
    print()
    print("  novem -p              list your plots")


def run_cli_wrapped() -> None:
    colors()

    raw_args = sys.argv[1:]

    #    return

    # Gather the provided arguements as an array.
    # (parser:Any, args:Dict[str, str]) = setup(raw_args)
    (parser, args) = setup(raw_args)

    if len(raw_args) == 0:
        print_short(parser)
        return

    if args and args["version"]:
        print(f"novem {__version__}")
        return

    # verify profile
    if args and args["profile"]:
        config_path: str = args["config_path"]
        profile_exists: bool = check_if_profile_exists(
            args["profile"], config_path
        )
        if not profile_exists:
            print(
                f'Profile "{args["profile"]}" doens\'t exist in your config. '
                "Please add it using:"
            )
            print(f'novem --init --profile {args["profile"]}')

    # we are getting an init instruction
    if args and args["init"]:
        init_config(args)
        return

    # operate on plot
    if args and args["plot"] != "":
        plot(args)
        pass


def run_cli() -> None:
    signal(SIGPIPE, SIG_DFL)  # supress broken pipe error
    run_cli_wrapped()


__all__ = ["run_cli"]
