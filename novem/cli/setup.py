import argparse as ap
import shutil
from enum import Enum
from typing import Any, Dict, Tuple

width = min(120, shutil.get_terminal_size().columns - 2)


class Share(Enum):
    NOT_GIVEN = 0
    CREATE = 1
    DELETE = 2
    LIST = 3


def formatter(prog: str) -> ap.RawDescriptionHelpFormatter:
    return ap.RawDescriptionHelpFormatter(prog, width=width)


def setup(raw_args: Any = None) -> Tuple[Any, Dict[str, str]]:
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
        help="specify configuration file to use",
    )

    parser.add_argument(
        "--profile",
        dest="profile",
        action="store",
        required=False,
        default=None,
        help="which user to use, combine with --init to setup a new profile and --force to override an existing one",
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
        help="authenticate with the novem service and create default configuration",
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

    parser.add_argument(
        "--refresh",
        dest="refresh",
        action="store_true",
        required=False,
        default=False,
        help="refresh the token for the current profile (or the one supplied by --profile), "
        "requires username and password",
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
        help="delete the current visualisation defined by -[pdmgv] or share defined by -s",
    )

    vis.add_argument(
        "-s",
        dest="share",
        action="store",
        required=False,
        default="",
        nargs="?",
        help="select a share group to operate on, no parameter will list all current shares",
    )

    vis.add_argument(
        "-l",
        dest="list",
        action="store_true",
        help="print ids only, no pretty printing",
    )

    vis.add_argument(
        "-f",
        metavar=("REGEX"),
        required=False,
        dest="filter",
        action="store",
        help="filter visualisations by rgex",
    )

    # support multiple inputs
    vis.add_argument(
        "-w",
        dest="input",
        action="append",
        nargs="+",
        metavar=("PATH", "VALUE"),
        help="write the supplied VALUE to the given PATH. PATH is mandatory. VALUE can be an explicit value, "
        "a filename prefixed with @ or data on stdin",
    )

    vis.add_argument(
        "-r",
        dest="out",
        action="store",
        required=False,
        default=None,
        metavar=("PATH"),
        help="read the content of PATH and prints it to stdout",
    )

    vis.add_argument(
        "-e",
        dest="edit",
        action="store",
        required=False,
        default=None,
        metavar=("PATH"),
        help="open the content located at PATH in $EDITOR and update the saved content on editor exit",
    )

    vis.add_argument(
        "-u",
        metavar=("USER"),
        dest="for_user",
        default=ap.SUPPRESS,
        action="store",
        required=False,
        help="specify user to view shared visualisation from",
    )

    vis.add_argument(
        "-o",
        metavar=("SOURCE"),
        dest="for_other",
        action="store",
        required=False,
        default=None,
        help="specify entity to view vis for, @username, +org, @username~usergroup or +org~orggroup are supported",
    )

    vis.add_argument(
        "--tree",
        metavar=("PATH"),
        dest="tree",
        action="store",
        required=False,
        default=-1,
        nargs="?",
        help="print a tree overview of the api structure at the given path, all input/output options are ignored",
    )

    term = parser.add_argument_group("terminal")

    term.add_argument(
        "-x",
        dest="tc",
        action="store_true",
        required=False,
        default=False,
        help="shorthand for requesting a terminal friendly output, identical to doing -r files/plot.ansi",
    )

    term.add_argument(
        "--qpr",
        dest="qpr",
        action="store",
        required=False,
        default=None,
        help="comma separated list of query parameters to include with request such as "
        "cols=$COLUMNS,rows=$(($lines-1))",
    )

    term.add_argument(
        "--fs",
        dest="fs",
        action="store_true",
        required=False,
        default=False,
        help='shorthand for creating a "full screen" version of the terminal vis',
    )

    # Currently not added as it would expand on our dependencies
    # we might consider adding it or providing it as a separate package
    # in the future
    if 0:
        term.add_argument(
            "--watch",
            dest="watch",
            action="store_true",
            required=False,
            default=False,
            help="connect to the server and redraws the visual when new information is available",
        )

    plot = parser.add_argument_group("plot")

    plot.add_argument(
        "-p",
        dest="plot",
        action="store",
        required=False,
        default="",
        nargs="?",
        help="select plot to operate on, no parameter will list all your plots",
    )

    plot.add_argument(
        "-t",
        dest="type",
        action="store",
        required=False,
        default=None,
        help="shorthand for setting the type of the plot, identical to doing -w config/type TYPE",
    )

    mail = parser.add_argument_group("mail")

    mail.add_argument(
        "-m",
        dest="mail",
        action="store",
        required=False,
        default="",
        nargs="?",
        help="select mail to operate on, no parameter will list all your mails",
    )

    mail.add_argument(
        "--to",
        dest="to",
        metavar=("RECIPIENTS"),
        action="store",
        required=False,
        default=None,
        help="shorthand for setting recipient of mail, identical to doing -w recipients/to RECIPIENTS",
    )

    mail.add_argument(
        "--cc",
        dest="cc",
        metavar=("RECIPIENTS"),
        action="store",
        required=False,
        default=None,
        help="shorthand for setting recipient of mail, identical to doing -w recipients/cc RECIPIENTS",
    )

    mail.add_argument(
        "--bcc",
        dest="bcc",
        metavar=("RECIPIENTS"),
        action="store",
        required=False,
        default=None,
        help="shorthand for setting recipient of mail, identical to doing -w recipients/bcc RECIPIENTS",
    )

    mail.add_argument(
        "--subject",
        dest="subject",
        metavar=("SUBJECT"),
        action="store",
        required=False,
        default=None,
        help="shorthand for setting subject of mail, identical to doing -w config/subject SUBJECT",
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

    invite = parser.add_argument_group("invite")

    invite.add_argument(
        "-i",
        dest="invite",
        action="store",
        required=False,
        default="",
        nargs="?",
        help="select invite to operate on, no parameter will list all pending invitations",
    )

    invite.add_argument(
        "--accept",
        dest="accept",
        action="store_true",
        required=False,
        default=False,
        help="accept the invite",
    )

    invite.add_argument(
        "--reject",
        dest="reject",
        action="store_true",
        required=False,
        default=False,
        help="reject the invite",
    )

    group = parser.add_argument_group(
        "group",
        description="""\
Operate on novem groups.

-C, --create - create
-D, --delete - delete the group
--invite      - invite a member to a group
--remove      - manage members

Examples:
  --invite bob -C analysts
""",
    )

    group.add_argument(
        "-O",
        dest="org",
        action="store",
        required=False,
        default=ap.SUPPRESS,
        nargs="?",
        help="select an organisation operate on, no parameter will list all organisations of which you are a member",
    )

    group.add_argument(
        "-G",
        dest="group",
        action="store",
        required=False,
        default=ap.SUPPRESS,
        nargs="?",
        help="""\
select an organisation -O or user -u group operate on.
No parameter will list all organisations groups of which you are a member""",
    )

    group.add_argument(
        "--invite",
        metavar=("USER"),
        dest="invite_user",
        action="store",
        required=False,
        help="invite a USER to the current organisation",
    )

    # group.add_argument(
    #    "--role",
    #    dest="role",
    #    action="store",
    #    required=False,
    #    help="specify role to give invited user, empty means member"
    # )

    args = vars(parser.parse_args(raw_args))

    # fix up the --share option
    share = args.pop("share")
    if share == "":
        args["share"] = (Share.NOT_GIVEN, None)
    elif share is None:
        args["share"] = (Share.LIST, None)
    elif args["create"]:
        args["create"] = None
        args["share"] = (Share.CREATE, share)
    elif args["delete"]:
        args["delete"] = None
        args["share"] = (Share.DELETE, share)
    else:
        args["share"] = None

    return (parser, args)
