import argparse as ap
import shutil
from enum import Enum
from typing import Any, List, Optional, Tuple, cast

from .args import CliArgs

width = min(120, shutil.get_terminal_size().columns - 2)


class Share(Enum):
    NOT_GIVEN = 0
    CREATE = 1
    DELETE = 2
    LIST = 3
    # `-s TARGET` with neither -C nor -D: a query, answered by the exit code
    CHECK = 4


class Tag(Enum):
    NOT_GIVEN = 0
    CREATE = 1
    DELETE = 2
    LIST = 3
    # `-t TAG` with neither -C nor -D: a query, answered by the exit code
    CHECK = 4


def formatter(prog: str) -> ap.RawDescriptionHelpFormatter:
    return ap.RawDescriptionHelpFormatter(prog, width=width)


# The overloaded short flags: each doubles as a coding-resource selector when
# nothing else claims the invocation (see promote_code_selectors).
# -c is deliberately absent: it belongs to --computer outright, and the config
# file it used to name now requires --config / --config-path.
_CODE_SELECTOR_MAP = {
    "-s": "--space",
    "-r": "--repo",
    "-i": "--image-select",
    # --image is overloaded on the same first-occurrence rule as the shorts:
    # unclaimed it selects an image, otherwise it sets config/image on the
    # selected resource. It cannot be its own promotion target, so both
    # spellings rewrite to the hidden --image-select.
    "--image": "--image-select",
}

# Flags that claim the invocation for another resource. When any of these is
# present the overloaded short flags keep their legacy meaning everywhere.
# -O/-G are handled separately: they restrict promotion to BARE flags (see
# promote_code_selectors) instead of disabling it, so that
# `novem -O org -G group -s` lists the group's spaces while
# `novem -O org -G group -i ./data ...` keeps reading an input directory.
_PRIMARY_SELECTOR_FLAGS = {
    "-p",
    "-g",
    "-m",
    "-d",
    "-j",
    "-u",
    "-c",
    "--invites",
    "--space",
    "--repo",
    "--computer",
    "--image-select",
}

# Early-exit commands that historically pair with the legacy meanings of the
# overloaded shorts (-i input dir, -r read path, ...) and never combine with
# a resource selector. Their presence disables promotion entirely.
# --gql is special-cased: a VALUED --gql (@file / inline query) runs standalone
# and blocks, while a bare --gql only toggles debug output and does not.
_PROMOTION_BLOCKERS = {
    "--version",
    "--init",
    "--refresh",
    "--info",
    "--add-ssh-key",
    "--events",
    "--get",
    "--post",
    "--put",
    "--delete",
    "--invite",
    "--accept",
    "--reject",
}

# Flags that deliberately do NOT affect promotion: global modifiers (--profile,
# --token, ...), the explicit long forms of the overloaded shorts, and options
# that only qualify a resource already chosen by a selector.
#
# This set exists so every long option the parser knows about is classified
# somewhere; test_cli_selectors.py::test_every_long_flag_is_classified fails
# when a new flag is added without deciding whether it claims the invocation.
_PROMOTION_NEUTRAL = {
    "--api-url",
    "--bcc",
    "--cc",
    "--color",
    "--comments",
    "--config",
    "--config-path",
    "--image",
    "--debug",
    "--dry-run",
    "--dump",
    "--force",
    "--fs",
    "--help",
    "--ignore-ssl",
    "--input",
    "--json",
    "--load",
    "--output",
    "--profile",
    "--qpr",
    "--subject",
    "--to",
    "--token",
    "--token-name",
    "--tree",
    "--type",
}

# Short flags that take a value, for recognising the attached form (-pmyplot).
_VALUED_SHORT_FLAGS = {"-p", "-g", "-m", "-d", "-j", "-u", "-O", "-G", "-s", "-t", "-r", "-c", "-i", "-o", "-e", "-f"}


def split_argv_tail(raw_args: Any) -> Tuple[Any, Optional[List[str]]]:
    """Split a trailing ``-- argv...`` off the command line.

    ``-R`` runs the selected resource's workload, and everything after a
    standalone ``--`` is the invocation to run rather than novem flags::

        novem -c box -R -- ls -la
        novem -j job -R -- python main.py

    The tail is passed through verbatim, so an argument that looks like a
    flag survives. The CLI has no positional arguments, so a bare ``--``
    previously meant nothing at all.
    """
    if not raw_args:
        return raw_args, None
    tokens = list(raw_args)
    for idx, tok in enumerate(tokens):
        if tok == "--":
            return tokens[:idx], tokens[idx + 1 :]
    return tokens, None


def promote_code_selectors(raw_args: Any) -> Any:
    """Rewrite a leading ``-s``/``-r``/``-i`` into its selector form.

    Three coding resources reuse short flags that already have a job:

        -s  spaces     (legacy: share group)
        -r  repos      (legacy: read path to stdout)
        -i  images     (legacy: --input upload dir)

    ``-c`` is not among them: it selects a computer and nothing else, and the
    config file it used to name needs ``--config`` / ``--config-path``. That is
    the one overload where both meanings could legitimately appear in the same
    invocation, and guessing wrong there picks the wrong credentials.

    When no other resource selector (``-p``/``-g``/``-m``/``-d``/``-j``/``-c``/…)
    and no early-exit command (``--init``/``--info``/…) is present, the FIRST
    occurrence of one of these shorts is the resource selector and is
    rewritten to its long form (``-s`` → ``--space``, …). Every later
    occurrence keeps its legacy meaning, so

        novem -r my-repo -r url        # read my-repo's clone url
        novem -s my-space -s public -C # share my-space with public

    both do what you'd expect, while ``novem -p my-plot -r url`` and
    ``novem -j my-job -R -i data/`` are untouched.
    """
    if not raw_args:
        return raw_args

    tokens = list(raw_args)

    def short_base(tok: str) -> str:
        """The flag part of a short token: '-pmyplot' -> '-p'."""
        if tok.startswith("-") and not tok.startswith("--") and len(tok) > 2 and tok[:2] in _VALUED_SHORT_FLAGS:
            return tok[:2]
        return tok

    def is_bare(idx: int) -> bool:
        """True when the flag at idx has no value (separate or attached)."""
        if short_base(tokens[idx]) != tokens[idx]:
            return False  # attached value
        nxt = tokens[idx + 1] if idx + 1 < len(tokens) else None
        return nxt is None or nxt.startswith("-")

    # in these contexts only BARE code-selector flags promote; valued ones
    # keep their legacy meaning (-i ./data stays the input directory):
    #  - group management (-O/-G): a bare selector lists the group's resources
    #  - bare --gql (debug output): a bare selector is the listing to debug
    bare_only = False

    for idx, tok in enumerate(tokens):
        if tok == "--":
            break
        if not tok.startswith("-"):
            continue
        base = tok.split("=", 1)[0] if tok.startswith("--") else short_base(tok)
        if base == "-u":
            # `-u USER` only scopes another selector to that user; it is the
            # bare `-u` (list connections) that claims the invocation
            if not is_bare(idx):
                continue
        if base in ("-O", "-G"):
            bare_only = True
            continue
        if base == "--gql":
            # a valued --gql runs a standalone query: legacy meanings hold
            if tok != "--gql" or not is_bare(idx):
                return tokens
            bare_only = True
            continue
        if base in _PRIMARY_SELECTOR_FLAGS or base in _PROMOTION_BLOCKERS:
            return tokens

    for idx, tok in enumerate(tokens):
        if tok == "--":
            break
        if tok.startswith("--"):
            base, _, attached = tok.partition("=")
        else:
            base = short_base(tok)
            attached = tok[2:] if base != tok else ""
        if base in _CODE_SELECTOR_MAP:
            if bare_only and (attached or not is_bare(idx)):
                break
            target = _CODE_SELECTOR_MAP[base]
            tokens[idx] = f"{target}={attached}" if attached else target
            break

    return tokens


def setup(raw_args: Any = None) -> Tuple[Any, CliArgs]:
    raw_args, argv_tail = split_argv_tail(raw_args)
    raw_args = promote_code_selectors(raw_args)

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
        "--gql",
        dest="gql",
        action="store",
        required=False,
        nargs="?",
        const=True,
        default=False,
        help="Run a GraphQL query. Use @filename to read from file, no argument to read from stdin, "
        "or combine with -p/-g/-m/-j/-u to show debug output",
    )

    parser.add_argument(
        "--add-ssh-key",
        dest="add_ssh_key",
        action="store",
        required=False,
        nargs="?",
        const=True,
        default=False,
        help="Add an SSH key for git access. Reads key from stdin. "
        "Optional argument specifies key ID (defaults to lowercase hostname)",
    )

    parser.add_argument(
        "--events",
        dest="events",
        nargs="+",
        required=False,
        default=None,
        metavar="FQNP",
        help="subscribe to real-time events using FQNP patterns. "
        "Example: --events /u/sondov/p/tst_plot/e/update /u/trt/p/markets/*",
    )

    parser.add_argument(
        "--json",
        dest="json_output",
        action="store_true",
        required=False,
        default=False,
        help="output events as JSON lines (default is human-readable)",
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
        "--load",
        metavar=("IN_PATH"),
        dest="load",
        action="store",
        required=False,
        default=None,
        help=ap.SUPPRESS,
    )

    parser.add_argument(
        "--dry-run",
        dest="dry_run",
        action="store_true",
        required=False,
        default=False,
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
        help="api url to use, default is https://api.novem.io/v1/",
    )

    parser.add_argument(
        "--config-path",
        "--config",
        dest="config_path",
        action="store",
        required=False,
        default=None,
        help="specify configuration file to use (-c selects a computer)",
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
        nargs="?",
        const=True,
        default=None,
        help="use this token instead, overrides profile lookup. "
        "With --init token, supplies the token value directly",
    )

    parser.add_argument(
        "--info",
        dest="info",
        action="store_true",
        required=False,
        help="print info about the current user",
    )

    http = parser.add_argument_group(
        "raw http",
        description="""\
Issue a raw HTTP request against the novem api. PATH is everything after the
api root (the part following /v1/), e.g. /vis/plots/my-plot/data. DATA can be
an inline string, @filename to read from a file, or piped via stdin.""",
    )

    http.add_argument(
        "--get",
        dest="http_get",
        action="store",
        required=False,
        default=None,
        metavar="PATH",
        help="GET the resource at PATH and print the response body",
    )

    http.add_argument(
        "--post",
        dest="http_post",
        action="store",
        required=False,
        default=None,
        nargs="+",
        metavar=("PATH", "DATA"),
        help="POST DATA to PATH. DATA is an inline string, @filename, or piped via stdin. "
        "Content-type is taken from --type when set, otherwise guessed from the @filename "
        "extension, falling back to text/plain",
    )

    http.add_argument(
        "--put",
        dest="http_put",
        action="store",
        required=False,
        default=None,
        nargs="+",
        metavar=("PATH", "DATA"),
        help="PUT to PATH with optional DATA. DATA is an inline string, @filename, or piped "
        "via stdin. Content-type is taken from --type when set, otherwise guessed from the "
        "@filename extension, falling back to text/plain",
    )

    http.add_argument(
        "--delete",
        dest="http_delete",
        action="store",
        required=False,
        default=None,
        metavar="PATH",
        help="DELETE the resource at PATH",
    )

    setup = parser.add_argument_group("setup")

    setup.add_argument(
        "--init",
        dest="init",
        action="store",
        nargs="?",
        const="credentials",
        default=None,
        help="authenticate with the novem service and create default configuration. "
        "Optional type: credentials (default, username+password), oauth (browser-based), "
        "or token (paste an existing token)",
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
        action="count",
        default=0,
        required=False,
        help="create the visualisation if it doesn't exist. Each -C covers one action, so "
        '"-s my-space -C -s public -C" creates the space AND adds the share',
    )

    vis.add_argument(
        "-D",
        dest="delete",
        action="count",
        default=0,
        help="delete the current visualisation defined by -[pdmgv] or share defined by -s. "
        "Like -C, each -D covers one action",
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
        "-t",
        dest="tag",
        action="store",
        required=False,
        default="",
        nargs="?",
        help="select a tag to operate on (fav, like, ignore, wip, archived, +usertag, or =categorytag), "
        "no parameter will list all current tags",
    )

    vis.add_argument(
        "-l",
        dest="list",
        action="store_true",
        help="print ids only, no pretty printing",
    )

    vis.add_argument(
        "-f",
        metavar="FILTER",
        required=False,
        dest="filter",
        action="append",
        help="filter visualisations. Syntax: column=value (exact) or column~regex. "
        "Multiple -f flags use AND logic. Without column, matches id/name/type.",
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
        default="",
        action="store",
        required=False,
        nargs="?",
        help="specify user to view shared visualisation from, no parameter will list users you are connected to",
    )

    vis.add_argument(
        "--comments",
        dest="comments",
        action="store_true",
        required=False,
        default=False,
        help="show topics and comments for the visualisation",
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
        "--type",
        dest="type",
        action="store",
        required=False,
        default=None,
        help="shorthand for setting the type of the plot, identical to doing -w config/type TYPE. "
        "When combined with --post or --put, sets the request Content-type instead",
    )

    grid = parser.add_argument_group("grid")

    grid.add_argument(
        "-g",
        dest="grid",
        action="store",
        required=False,
        default="",
        nargs="?",
        help="select grid to operate on, no parameter will list all your grids",
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

    doc = parser.add_argument_group("doc")

    doc.add_argument(
        "-d",
        dest="doc",
        action="store",
        required=False,
        default="",
        nargs="?",
        help="select doc to operate on, no parameter will list all your docs",
    )

    job = parser.add_argument_group("job")

    job.add_argument(
        "-j",
        dest="job",
        action="store",
        required=False,
        default="",
        nargs="?",
        help="select job to operate on, no parameter will list all your jobs",
    )

    job.add_argument(
        "-R",
        dest="run_job",
        nargs="*",
        default=None,
        metavar="ARG",
        help="run the job. Input and output files are -i and -o; run arguments " "are coming in a future release",
    )

    job.add_argument(
        "-i",
        "--input",
        dest="input_dir",
        action="append",
        default=None,
        metavar="PATH",
        help="send input with -R. @file.ext sends one file, a bare path sends every "
        "file in that directory (subdirectories preserved). Repeatable",
    )

    job.add_argument(
        "-o",
        "--output",
        dest="output_dir",
        action="append",
        default=None,
        metavar="PATH",
        help="save job output. @file.ext writes it to that file, a bare path writes "
        "into that directory (created if needed)",
    )

    code = parser.add_argument_group(
        "coding resources",
        description="""\
Spaces, repos, computers and images. The short flags -s/-r/-c/-i select these
resources when they are the first selector on the command line; once a
resource is selected they keep their usual meaning:

  novem -r my-repo -r url          read the clone url of my-repo
  novem -s my-space -s public -C   share my-space with public
  novem -c my-box -w status reboot reboot computer my-box
""",
    )

    code.add_argument(
        "--space",
        dest="space",
        action="store",
        required=False,
        default="",
        nargs="?",
        help="select space to operate on (also: -s as first selector), no parameter will list all your spaces",
    )

    code.add_argument(
        "--repo",
        dest="repo",
        action="store",
        required=False,
        default="",
        nargs="?",
        help="select repo to operate on (also: -r as first selector), no parameter will list all your repos",
    )

    code.add_argument(
        "--computer",
        "-c",
        dest="computer",
        action="store",
        required=False,
        default="",
        nargs="?",
        help="select computer to operate on, no parameter will list all your computers",
    )

    code.add_argument(
        "--image-select",
        dest="image",
        action="store",
        required=False,
        default="",
        nargs="?",
        help=ap.SUPPRESS,
    )

    code.add_argument(
        "--image",
        dest="image_ref",
        action="store",
        required=False,
        default="",
        nargs="?",
        metavar="REF",
        help="as the first selector, select an image to operate on (same as -i); "
        "otherwise set the selected resource's image, e.g. -c my-box --image @novem/base",
    )

    code.add_argument(
        "-A",
        dest="attach",
        action="store_true",
        required=False,
        default=False,
        help="attach an interactive shell to the selected computer",
    )

    invite = parser.add_argument_group("invite")

    invite.add_argument(
        "--invites",
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

    # -c used to name a config file. A path-shaped computer name is almost
    # certainly that muscle memory, and silently treating it as a computer
    # would run against the default profile's credentials.
    computer = args.get("computer")
    if computer and ("/" in computer or computer.startswith("~")):
        parser.error(f'-c "{computer}" looks like a path - the config file is now --config / --config-path')

    # -C and -D are counted: each occurrence covers one action. The share and
    # tag fixups below each consume one; whatever remains covers the resource
    # itself ("-s my-space -C -s public -C" creates the space AND the share).

    # fix up the --share option
    share = args.pop("share")
    if share == "":
        args["share"] = (Share.NOT_GIVEN, None)
    elif share is None:
        args["share"] = (Share.LIST, None)
    elif args["create"]:
        args["create"] -= 1
        args["share"] = (Share.CREATE, share)
    elif args["delete"]:
        args["delete"] -= 1
        args["share"] = (Share.DELETE, share)
    else:
        # `-s TARGET` with neither -C nor -D asks whether the share is already
        # there; the exit code is the answer. (It previously stored a non-tuple
        # None that crashed every consumer.)
        args["share"] = (Share.CHECK, share)

    # fix up the --tag option (supports comma-separated tags like -t fav,+demo,+test)
    tag = args.pop("tag")
    if tag == "":
        args["tag"] = (Tag.NOT_GIVEN, None)
    elif tag is None:
        args["tag"] = (Tag.LIST, None)
    elif args["create"]:
        args["create"] -= 1
        # Split by comma to support multiple tags
        tags = [t.strip() for t in tag.split(",") if t.strip()]
        args["tag"] = (Tag.CREATE, tags)
    elif args["delete"]:
        args["delete"] -= 1
        # Split by comma to support multiple tags
        tags = [t.strip() for t in tag.split(",") if t.strip()]
        args["tag"] = (Tag.DELETE, tags)
    else:
        # `-t TAG` with neither -C nor -D asks whether the tags are already
        # there; the exit code is the answer. (It previously stored a non-tuple
        # None that crashed every consumer.)
        tags = [t.strip() for t in tag.split(",") if t.strip()]
        args["tag"] = (Tag.CHECK, tags)

    # the invocation after `--`, if any (see split_argv_tail)
    args["argv"] = argv_tail

    # everything downstream treats create/delete as booleans
    args["create"] = args["create"] > 0
    args["delete"] = args["delete"] > 0

    return (parser, cast(CliArgs, args))
