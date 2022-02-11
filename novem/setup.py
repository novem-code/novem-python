import argparse as ap
import shutil
from typing import Any, Dict

width = min(80, shutil.get_terminal_size().columns - 2)


def formatter(prog: str) -> ap.RawDescriptionHelpFormatter:
    return ap.RawDescriptionHelpFormatter(prog, width=width)


def setup(raw_args: Any = None) -> Dict[str, str]:
    # formatter = lambda prog: ap.RawDescriptionHelpFormatter(prog,
    # width=width)

    parser = ap.ArgumentParser(
        prog="novem",
        description="Novem commandline interface.",
        formatter_class=formatter,
    )

    general = parser.add_argument_group("general")

    general.add_argument(
        "--api-url",
        dest="api-url",
        action="store",
        required=False,
        default="https://api.novem.no/v1",
        help="api url to use, defaul is https://api.novem.no/v1",
    )

    general.add_argument(
        "--profile-name",
        dest="profile-name",
        action="store",
        required=False,
        default="default",
        help=(
            "Which profile to use, combine with --init to setup a"
            " new profile and --force to override an existing token"
        ),
    )

    general.add_argument(
        "--token",
        dest="token",
        action="store",
        required=False,
        default=None,
        help="Use this token instead, overrides profile lookup",
    )

    setup = parser.add_argument_group("setup")

    setup.add_argument(
        "--init",
        dest="init",
        action="store_true",
        help="authenticate with the novem service and create"
        " default configuration",
    )

    setup.add_argument(
        "--force",
        dest="force",
        action="store_true",
        required=False,
        help="force reinit of existing profile",
    )

    setup.add_argument(
        "--token_name",
        dest="token_name",
        action="store",
        required=False,
        default=None,
        help="name of token (lowercase alphanumeric, no whitespace)",
    )

    # Gather the provided arguements as an array.
    args: Dict[str, str] = vars(parser.parse_args(raw_args))

    return args
