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
        "--ignore-ssl",
        dest="ignore_ssl",
        action="store_true",
        required=False,
        default=False,
        help=ap.SUPPRESS,
    )

    parser.add_argument(
        "--debug",
        dest="debug",
        action="store_true",
        required=False,
        default=False,
        help=ap.SUPPRESS,
    )

    parser.add_argument(
        "--dump",
        metavar=("OUT_PATH"),
        dest="dump",
        action="store",
        required=False,
        default=None,
        help=ap.SUPPRESS,
    )

    parser.add_argument(
        "--version",
        dest="version",
        action="store_true",
        required=False,
        default=False,
        help="print the current version and terminate",
    )

    parser.add_argument(
        "--color",
        dest="color",
        action="store_true",
        required=False,
        default=False,
        help="preserve colors when redirecting to pipe or file",
    )

    parser.add_argument(
        "--api-url",
        dest="api-url",
        action="store",
        required=False,
        default=None,
        help="api url to use, defaul is https://api.novem.no/v1/",
    )

    parser.add_argument(
        "--config-path",
        "-c",
        dest="config_path",
        action="store",
        required=False,
        default=None,
        help=("specify configuration file to use"),
    )

    parser.add_argument(
        "--profile",
        dest="profile",
        action="store",
        required=False,
        default=None,
        help=(
            "which user to use, combine with --init to setup a"
            " new profile and --force to override an existing one"
        ),
    )

    parser.add_argument(
        "--token",
        dest="token",
        action="store",
        required=False,
        default=None,
        help="use this token instead, overrides profile lookup",
    )

    parser.add_argument(
        "--info",
        dest="info",
        action="store_true",
        required=False,
        help="print info about the current user",
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

    vis = parser.add_argument_group("common visualisation arguments")

    vis.add_argument(
        "-C",
        dest="create",
        action="store_true",
        required=False,
        help="create the visualisation if it doesn't exist",
    )

    vis.add_argument(
        "-D",
        dest="delete",
        action="store_true",
        help="delete the current visualisation defined by -[pdmgv] or "
        "share defined by -s",
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
        "-l",
        dest="list",
        action="store_true",
        help="print ids only, no pretty printing",
    )

    # support multiple inputs
    vis.add_argument(
        "-w",
        dest="input",
        action="append",
        nargs="+",
        metavar=("PATH", "VALUE"),
        help="write the suppied VALUE to the given PATH. PATH is mandatory "
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
        help="reads the content of PATH and prints it to standard out",
    )

    vis.add_argument(
        "-e",
        dest="edit",
        action="store",
        required=False,
        default=None,
        metavar=("PATH"),
        help="opens the content located at PATH in your default $EDITOR "
        " and updates the saved content on editor exit",
    )

    vis.add_argument(
        "-u",
        metavar=("USER"),
        dest="for_user",
        action="store",
        required=False,
        default=None,
        help="specify user to view shared visualisation from",
    )

    vis.add_argument(
        "-o",
        metavar=("SOURCE"),
        dest="for_other",
        action="store",
        required=False,
        default=None,
        help="specify entity to view vis for, @username, "
        "+org, @username~usergroup or +org~orggroup are supported",
    )

    vis.add_argument(
        "--tree",
        metavar=("PATH"),
        dest="tree",
        action="store",
        required=False,
        default=-1,
        nargs="?",
        help="print a tree overview of the api structure at the "
        "given path, all input/output options are ignored",
    )

    term = parser.add_argument_group("terminal")

    term.add_argument(
        "-x",
        dest="tc",
        action="store_true",
        required=False,
        default=False,
        help="shorthand for requesting a terminal friendly output, "
        "identical to doing -r files/plot.ansi",
    )

    term.add_argument(
        "--qpr",
        dest="qpr",
        action="store",
        required=False,
        default=False,
        help="comma separated list of query paramters to include "
        "with request such as cols=$COLUMNS,rows=$(($lines-1))",
    )

    term.add_argument(
        "--fs",
        dest="fs",
        action="store_true",
        required=False,
        default=False,
        help='shorthand for creating a "full screen" version of '
        "the terminal vis",
    )

    # Currently not added as it would expand on our dependencies
    # we might consider adding it or providing it as a separate package
    # in the future
    # term.add_argument(
    #     "--watch",
    #     dest="watch",
    #     action="store_true",
    #     required=False,
    #     default=False,
    #     help="connects to the server and redraws the visual when "
    #     "new information is available",
    # )

    plot = parser.add_argument_group("plot")

    plot.add_argument(
        "-p",
        dest="plot",
        action="store",
        required=False,
        default="",
        nargs="?",
        help="select plot to operate on, no paramter will list"
        " all your plots",
    )

    plot.add_argument(
        "-t",
        dest="type",
        action="store",
        required=False,
        default=None,
        help="shorthand for setting the type of the plot, "
        "identical to doing -w config/type TYPE",
    )

    mail = parser.add_argument_group("mail")

    mail.add_argument(
        "-m",
        dest="mail",
        action="store",
        required=False,
        default="",
        nargs="?",
        help="select mail to operate on, no paramter will list"
        " all your mails",
    )

    mail.add_argument(
        "--to",
        dest="to",
        metavar=("RECIPIENTS"),
        action="store",
        required=False,
        default=None,
        help="shorthand for setting recipient of mail, "
        "identical to doing -w recipients/to RECIPIENTS",
    )

    mail.add_argument(
        "--cc",
        dest="cc",
        metavar=("RECIPIENTS"),
        action="store",
        required=False,
        default=None,
        help="shorthand for setting recipient of mail, "
        "identical to doing -w recipients/cc RECIPIENTS",
    )

    mail.add_argument(
        "--bcc",
        dest="bcc",
        metavar=("RECIPIENTS"),
        action="store",
        required=False,
        default=None,
        help="shorthand for setting recipient of mail, "
        "identical to doing -w recipients/bcc RECIPIENTS",
    )

    mail.add_argument(
        "--subject",
        dest="subject",
        metavar=("SUBJECT"),
        action="store",
        required=False,
        default=None,
        help="shorthand for setting subject of mail, "
        "identical to doing -w config/subject SUBJECT",
    )

    mail.add_argument(
        "-S",
        dest="send",
        action="store_true",
        required=False,
        help="send the e-mail to recipients",
    )

    mail.add_argument(
        "-T",
        dest="test",
        action="store_true",
        required=False,
        help="send a test e-mail to your registered address",
    )

    # Gather the provided arguements as an array.
    args: Dict[str, str] = vars(parser.parse_args(raw_args))

    return (parser, args)
