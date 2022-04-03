import argparse as ap
import shutil
from typing import Any, Dict, Tuple

width = min(80, shutil.get_terminal_size().columns - 2)


def formatter(prog: str) -> ap.RawDescriptionHelpFormatter:
    return ap.RawDescriptionHelpFormatter(prog, width=width)


def setup(raw_args: Any = None) -> Tuple[Any, Dict[str, str]]:
    # formatter = lambda prog: ap.RawDescriptionHelpFormatter(prog,
    # width=width)

    parser = ap.ArgumentParser(
        prog="novem",
        description="Novem commandline interface.",
        formatter_class=formatter,
    )

    parser.add_argument(
        "--version",
        dest="version",
        action="store_true",
        required=False,
        default=False,
        help="Print the current version and terminate",
    )

    parser.add_argument(
        "--api-url",
        dest="api-url",
        action="store",
        required=False,
        default=None,
        help="api url to use, defaul is https://api.novem.no/v1",
    )

    parser.add_argument(
        "--config-path",
        "-c",
        dest="config_path",
        action="store",
        required=False,
        default=None,
        help=("Specify configuration file to use"),
    )

    parser.add_argument(
        "--profile",
        dest="profile",
        action="store",
        required=False,
        default=None,
        help=(
            "Which user to use, combine with --init to setup a"
            " new profile and --force to override an existing one"
        ),
    )

    parser.add_argument(
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
        "--token-name",
        dest="token-name",
        action="store",
        required=False,
        default=None,
        help="name of token (lowercase alphanumeric, no whitespace)",
    )

    vis = parser.add_argument_group("visualisations")

    vis.add_argument(
        "-p",
        dest="plot",
        action="store",
        required=False,
        default="",
        nargs="?",
        help="select plot to operate on, no paramter will list"
        " all your plots",
    )

    vis.add_argument(
        "-s",
        dest="share",
        action="store",
        required=False,
        default="",
        nargs="?",
        help="select a share group to operate on, no paramter will list"
        " all current shares",
    )

    vis.add_argument(
        "-t",
        dest="type",
        action="store",
        required=False,
        default=None,
        help="Shorthand for setting the type of the plot",
    )

    vis.add_argument(
        "-x",
        dest="tc",
        action="store_true",
        required=False,
        default=False,
        help="Shorthand for requesting a terminal friendly output. "
        "Identical to doing -o files/plot.ansi",
    )

    vis.add_argument(
        "-D",
        dest="delete",
        action="store_true",
        help="Delete the current plot defined by -p or share defined by -s",
    )

    vis.add_argument(
        "-l",
        dest="list",
        action="store_true",
        help="Pretty print the plot or share listing",
    )

    # support multiple inputs
    vis.add_argument(
        "-w",
        dest="input",
        action="append",
        nargs="+",
        metavar=("PATH", "VALUE"),
        help="Write the suppied VALUE to the given PATH. PATH is mandatory "
        "but value can be an explicit value, an @prefixed filename or the "
        "input from standard in ",
    )

    vis.add_argument(
        "-r",
        dest="out",
        action="store",
        required=False,
        default=None,
        metavar=("PATH"),
        help="Reads the content of PATH and prints it to standard out",
    )

    # add -p  with one optional paramter

    # add -i with one mandatory and one optional paramters
    # add -o with one mandatory paramter

    # add -s with one optional paramter
    # add +s with one optional paramter

    # add -l as a toggle

    # add -D as toggle

    # Gather the provided arguements as an array.
    args: Dict[str, str] = vars(parser.parse_args(raw_args))

    return (parser, args)
