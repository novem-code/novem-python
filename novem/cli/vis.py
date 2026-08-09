import datetime
import json
import re
from datetime import timezone
from typing import Any, Dict, List, Optional, Tuple

from novem.exceptions import Novem404

from ..api_ref import NovemAPI
from ..utils import cl, colors, format_datetime_local, get_current_config, parse_api_datetime, pretty_format
from .args import CliArgs
from .config import config_from_args
from .filter import apply_filters
from .gql import (
    NovemGQL,
    list_computers_gql,
    list_docs_gql,
    list_grids_gql,
    list_images_gql,
    list_jobs_gql,
    list_mails_gql,
    list_my_computers_gql,
    list_my_docs_gql,
    list_my_grids_gql,
    list_my_images_gql,
    list_my_jobs_gql,
    list_my_mails_gql,
    list_my_plots_gql,
    list_my_repos_gql,
    list_my_spaces_gql,
    list_org_group_members_gql,
    list_org_group_vis_gql,
    list_org_groups_gql,
    list_org_members_gql,
    list_orgs_gql,
    list_plots_gql,
    list_repos_gql,
    list_spaces_gql,
    list_users_gql,
)


def _compact_num(n: int) -> str:
    """Format a number compactly: 0→'-', 1–999 as-is, 1k, 1.2k, 1M, etc."""
    if not n:
        return "-"
    if n < 1000:
        return str(n)
    if n < 100_000:
        v = n / 1000
        return f"{v:.1f}k".replace(".0k", "k")
    if n < 1_000_000:
        return f"{n // 1000}k"
    v = n / 1_000_000
    return f"{v:.1f}M".replace(".0M", "M")


def _format_activity(plist: List[Dict[str, Any]]) -> None:
    """Pre-format the _activity column with right-aligned, evenly-spaced components."""
    # Compute compact strings for each row
    rows = []
    for p in plist:
        c = _compact_num(p.get("_comments", 0))
        lk = _compact_num(p.get("_likes", 0))
        d = _compact_num(p.get("_dislikes", 0))
        rows.append((c, lk, d))

    if not rows:
        return

    # Max width per component
    mc = max(len(r[0]) for r in rows)
    ml = max(len(r[1]) for r in rows)
    md = max(len(r[2]) for r in rows)

    # Total width: at least header "Activity" (8), at least content + 2 gaps
    total = max(8, mc + ml + md + 2)

    # Distribute leftover space evenly across the 2 gaps
    gap_total = total - mc - ml - md
    gap1 = (gap_total + 1) // 2  # first gap gets extra char if odd
    gap2 = gap_total // 2

    s1 = " " * gap1
    s2 = " " * gap2

    for p, (c, lk, d) in zip(plist, rows):
        cs = c.rjust(mc)
        ls = lk.rjust(ml)
        ds = d.rjust(md)
        p["_activity"] = f"{cs}{s1}{cl.OKBLUE}{ls}{cl.ENDFGC}{s2}{cl.FAIL}{ds}{cl.ENDFGC}"


def _format_views(plist: List[Dict[str, Any]]) -> None:
    """Pre-format the _views column as a right-aligned compact number."""
    if not plist:
        return

    rows = [_compact_num(p.get("_views", 0)) for p in plist]
    mw = max(max(len(r) for r in rows), len("Views"))

    for p, r in zip(plist, rows):
        p["_views_fmt"] = r.rjust(mw)


def list_vis(args: CliArgs, type: str) -> None:
    colors()
    # get current plot list

    pfx = type[0].lower()

    config_status, config = get_current_config(**config_from_args(args))

    plist: List[Dict[str, Any]] = []

    # An explicit --for-user lists *that* user's (public) visualizations; an
    # empty value means "my own", which we resolve from the token via `me`
    # rather than trusting the cached config username (stale after a rename).
    for_user = args["for_user"] if ("for_user" in args and args["for_user"]) else ""

    # Use GraphQL for listing
    gql = NovemGQL.from_args(args)

    if "group" in args and args["group"]:
        # Group listing not yet supported via GraphQL, fall back to REST
        novem = NovemAPI(**config_from_args(args), is_cli=True)
        group = args["group"]
        org = args.get("org", "")

        if group[0] in ["@", "+"]:
            query = group
        elif for_user and group:
            query = f"@{for_user}~{group}"
        elif org and group:
            query = f"+{org}~{group}"
        elif group:
            # My own user group — resolve identity from the token.
            owner = gql.current_username
            query = f"@{owner}~{group}" if owner else ""
        else:
            query = ""

        if query:
            path = f"o/{query}/{pfx}/"
            try:
                plist = json.loads(novem.read(path))
            except Novem404:
                plist = []
    elif for_user:
        # Another user's visualizations, filtered by author.
        if pfx == "p":
            plist = list_plots_gql(gql, author=for_user)
        elif pfx == "g":
            plist = list_grids_gql(gql, author=for_user)
        elif pfx == "m":
            plist = list_mails_gql(gql, author=for_user)
        elif pfx == "d":
            plist = list_docs_gql(gql, author=for_user)
    else:
        # My own visualizations, scoped to the token via `me`.
        if pfx == "p":
            plist = list_my_plots_gql(gql)
        elif pfx == "g":
            plist = list_my_grids_gql(gql)
        elif pfx == "m":
            plist = list_my_mails_gql(gql)
        elif pfx == "d":
            plist = list_my_docs_gql(gql)

    # Apply filters (handles both legacy and new column-based filtering)
    plist = apply_filters(plist, args.get("filter"))

    # Sort by: 1) favs first, 2) likes second, 3) rest last - each group sorted by updated (newest first)
    # Parse date string for proper sorting (format: "Thu, 17 Mar 2022 12:19:02 UTC")
    def parse_date(date_str: str) -> datetime.datetime:
        dt = parse_api_datetime(date_str)
        return dt if dt else datetime.datetime.min.replace(tzinfo=timezone.utc)

    def sort_tier(markers: str) -> int:
        """Return sort tier: 0=fav, 1=like only, 2=rest."""
        if "*" in markers:
            return 0
        if "+" in markers:
            return 1
        return 2

    plist = sorted(plist, key=lambda x: (sort_tier(x.get("fav", "")), -parse_date(x["updated"]).timestamp()))

    if args["list"]:

        # print to terminal
        for p in plist:
            print(p["id"])

        return

    def share_fmt(share: str, cl: cl) -> str:
        sl = [x[0] for x in share]
        pub = f"{cl.FAIL}P{cl.ENDFGC}" if "p" in sl else "-"  # public
        chat = f"{cl.WARNING}C{cl.ENDFGC}" if "c" in sl else "-"  # chat claim
        ug = f"{cl.OKGREEN}@{cl.ENDFGC}" if "@" in sl else "-"  # user group
        og = f"{cl.OKGREEN}+{cl.ENDFGC}" if "+" in sl else "-"  # org group
        return f"{pub} {chat} {ug} {og}"

    def summary_fmt(summary: Optional[str], cl: cl) -> str:
        if not summary:
            return ""

        return summary.replace("\n", "")

    has_favs = any("*" in p.get("fav", "") for p in plist)
    has_likes = any("+" in p.get("fav", "") for p in plist)

    def fav_fmt(markers: str, cl: cl) -> str:
        parts = ""
        if has_favs:
            parts += f"{cl.WARNING}*{cl.ENDFGC}" if "*" in markers else " "
        if has_likes:
            parts += f"{cl.OKBLUE}+{cl.ENDFGC}" if "+" in markers else " "
        return f" {parts} " if parts else ""

    fav_header_width = (1 if has_favs else 0) + (1 if has_likes else 0)
    fav_header = (" " * (fav_header_width + 2)) if fav_header_width > 0 else ""

    ppo: List[Dict[str, Any]] = [
        *(
            [
                {
                    "key": "fav",
                    "header": fav_header,
                    "type": "text",
                    "fmt": fav_fmt,
                    "overflow": "keep",
                    "no_border": True,
                    "no_padding": True,
                },
            ]
            if has_favs or has_likes
            else []
        ),
        {
            "key": "id",
            "header": f"{type} ID",
            "type": "text",
            "overflow": "keep",
        },
        {
            "key": "type",
            "header": "Type",
            "type": "text",
            "clr": cl.OKCYAN,
            "overflow": "keep",
        },
        {
            "key": "shared",
            "header": "Shared",
            "type": "text",
            "fmt": share_fmt,
            "overflow": "keep",
            "protect": True,
        },
        {
            "key": "name",
            "header": "Name",
            "type": "text",
            "overflow": "shrink",
            "drop": 2,
        },
        {
            "key": "_activity",
            "header": "Activity",
            "type": "text",
            "overflow": "keep",
            "drop": 4,
        },
        {
            "key": "_views_fmt",
            "header": "Views",
            "type": "text",
            "overflow": "keep",
            "drop": 3,
        },
        {
            "key": "updated",
            "header": "Updated",
            "type": "date",
            "overflow": "keep",
        },
        {
            "key": "uri",
            "header": "Url",
            "type": "url",
            "overflow": "keep",
        },
        {
            "key": "summary",
            "header": "Summary",
            "fmt": summary_fmt,
            "type": "text",
            "overflow": "truncate",
            "drop": 1,
        },
    ]

    for p in plist:
        dt = parse_api_datetime(p["updated"])
        if dt:
            p["updated"] = format_datetime_local(dt)

    _format_activity(plist)
    _format_views(plist)

    striped: bool = config.get("cli_striped", False)
    ppl = pretty_format(plist, ppo, striped=striped)

    print(ppl)

    return


def share_pretty_print(iplist: List[Dict[str, str]], striped: bool = False) -> None:

    # modify our plist
    plist = []
    for p in iplist:
        if p["name"] == "public":
            p["summary"] = "Shared with the entire world"
            p["type"] = "special"
        elif p["name"] == "chat":
            p["summary"] = "Shared with Minerva (the novem AI agent)"
            p["type"] = "minerva"
        elif re.match("^@.+~.+$", p["name"]):
            p["summary"] = "Shared with all members of the given user group"
            p["type"] = "user group"
        elif re.match("^\\+.+~.+$", p["name"]):
            p["summary"] = "Shared with all members of the given organisation group"
            p["type"] = "org group"
        else:
            p["summary"] = "Custom claim"
            p["type"] = "claim"

        plist.append(p)

    def summary_fmt(summary: str, cl: cl) -> str:
        if not summary:
            return ""

        return summary.replace("\n", "")

    ppo: List[Dict[str, Any]] = [
        {
            "key": "name",
            "header": "Share Name",
            "type": "text",
            "overflow": "keep",
        },
        {
            "key": "type",
            "header": "Type",
            "type": "text",
            "clr": cl.OKCYAN,
            "overflow": "keep",
        },
        {
            "key": "created_on",
            "header": "Shared on",
            "type": "date",
            "overflow": "keep",
        },
        {
            "key": "summary",
            "header": "Summary",
            "fmt": summary_fmt,
            "type": "text",
            "overflow": "truncate",
        },
    ]

    for p in plist:
        dt = parse_api_datetime(p["created_on"])
        if dt:
            p["created_on"] = format_datetime_local(dt)

    ppl = pretty_format(plist, ppo, striped=striped)
    print(ppl)


def list_vis_shares(vis_name: str, args: CliArgs, type: str) -> None:

    novem = NovemAPI(**config_from_args(args), is_cli=True)
    # see if list flag is set

    pth = type.lower()

    config_status, config = get_current_config(**config_from_args(args))

    plist = []

    for_user = args.get("for_user")
    if for_user:
        share_path = f"users/{for_user}/vis/{pth}s/{vis_name}/shared"
    else:
        share_path = f"vis/{pth}s/{vis_name}/shared"

    try:
        plist = json.loads(novem.read(share_path))
    except Novem404:
        plist = []

    if args["list"]:
        # print to terminal
        for p in plist:
            print(p["name"])
    else:
        striped: bool = config.get("cli_striped", False)
        share_pretty_print(plist, striped=striped)

    return


def list_job_shares(job_name: str, args: CliArgs) -> None:

    novem = NovemAPI(**config_from_args(args), is_cli=True)

    config_status, config = get_current_config(**config_from_args(args))

    plist = []

    for_user = args.get("for_user")
    if for_user:
        share_path = f"users/{for_user}/code/jobs/{job_name}/shared"
    else:
        share_path = f"code/jobs/{job_name}/shared"

    try:
        plist = json.loads(novem.read(share_path))
    except Novem404:
        plist = []

    if args["list"]:
        # print to terminal
        for p in plist:
            print(p["name"])
    else:
        striped: bool = config.get("cli_striped", False)
        share_pretty_print(plist, striped=striped)

    return


def tag_pretty_print(iplist: List[Dict[str, str]], striped: bool = False) -> None:
    """Pretty print tags list."""

    plist = []
    for p in iplist:
        tag_name = p["name"]
        if tag_name == "fav":
            p["summary"] = "Marked as favorite"
            p["type"] = "system"
        elif tag_name == "like":
            p["summary"] = "Marked as liked"
            p["type"] = "system"
        elif tag_name == "ignore":
            p["summary"] = "Marked as ignored"
            p["type"] = "system"
        elif tag_name == "wip":
            p["summary"] = "Work in progress"
            p["type"] = "system"
        elif tag_name == "archived":
            p["summary"] = "Archived"
            p["type"] = "system"
        elif tag_name.startswith("+"):
            p["summary"] = "User-defined tag"
            p["type"] = "user"
        elif tag_name.startswith("="):
            p["summary"] = "Category tag"
            p["type"] = "category"
        else:
            p["summary"] = "Custom tag"
            p["type"] = "custom"

        plist.append(p)

    def summary_fmt(summary: str, cl: cl) -> str:
        if not summary:
            return ""
        return summary.replace("\n", "")

    ppo: List[Dict[str, Any]] = [
        {
            "key": "name",
            "header": "Tag Name",
            "type": "text",
            "overflow": "keep",
        },
        {
            "key": "type",
            "header": "Type",
            "type": "text",
            "clr": cl.OKCYAN,
            "overflow": "keep",
        },
        {
            "key": "created_on",
            "header": "Added on",
            "type": "date",
            "overflow": "keep",
        },
        {
            "key": "summary",
            "header": "Summary",
            "fmt": summary_fmt,
            "type": "text",
            "overflow": "truncate",
        },
    ]

    for p in plist:
        dt = parse_api_datetime(p.get("created_on", ""))
        if dt:
            p["created_on"] = format_datetime_local(dt)

    ppl = pretty_format(plist, ppo, striped=striped)
    print(ppl)


def list_vis_tags(vis_name: str, args: CliArgs, type: str) -> None:
    """List tags for a visualization."""

    novem = NovemAPI(**config_from_args(args), is_cli=True)

    pth = type.lower()

    config_status, config = get_current_config(**config_from_args(args))

    plist = []

    for_user = args.get("for_user")
    if for_user:
        tag_path = f"users/{for_user}/vis/{pth}s/{vis_name}/tags"
    else:
        tag_path = f"vis/{pth}s/{vis_name}/tags"

    try:
        plist = json.loads(novem.read(tag_path))
    except Novem404:
        plist = []

    if args["list"]:
        # print to terminal
        for p in plist:
            print(p["name"])
    else:
        striped: bool = config.get("cli_striped", False)
        tag_pretty_print(plist, striped=striped)

    return


def list_job_tags(job_name: str, args: CliArgs) -> None:
    """List tags for a job."""

    novem = NovemAPI(**config_from_args(args), is_cli=True)

    config_status, config = get_current_config(**config_from_args(args))

    plist = []

    for_user = args.get("for_user")
    if for_user:
        tag_path = f"users/{for_user}/code/jobs/{job_name}/tags"
    else:
        tag_path = f"code/jobs/{job_name}/tags"

    try:
        plist = json.loads(novem.read(tag_path))
    except Novem404:
        plist = []

    if args["list"]:
        # print to terminal
        for p in plist:
            print(p["name"])
    else:
        striped: bool = config.get("cli_striped", False)
        tag_pretty_print(plist, striped=striped)

    return


def list_code_shares(kind: str, name: str, args: CliArgs) -> None:
    """List shares for a coding resource (space/repo/computer/image)."""

    novem = NovemAPI(**config_from_args(args), is_cli=True)

    config_status, config = get_current_config(**config_from_args(args))

    collection = f"{kind}s"
    plist = []

    for_user = args.get("for_user")
    if for_user:
        share_path = f"users/{for_user}/code/{collection}/{name}/shared"
    else:
        share_path = f"code/{collection}/{name}/shared"

    try:
        plist = json.loads(novem.read(share_path))
    except Novem404:
        plist = []

    if args["list"]:
        # print to terminal
        for p in plist:
            print(p["name"])
    else:
        striped: bool = config.get("cli_striped", False)
        share_pretty_print(plist, striped=striped)

    return


def list_code_tags(kind: str, name: str, args: CliArgs) -> None:
    """List tags for a coding resource (space/repo/computer/image)."""

    novem = NovemAPI(**config_from_args(args), is_cli=True)

    config_status, config = get_current_config(**config_from_args(args))

    collection = f"{kind}s"
    plist = []

    for_user = args.get("for_user")
    if for_user:
        tag_path = f"users/{for_user}/code/{collection}/{name}/tags"
    else:
        tag_path = f"code/{collection}/{name}/tags"

    try:
        plist = json.loads(novem.read(tag_path))
    except Novem404:
        plist = []

    if args["list"]:
        # print to terminal
        for p in plist:
            print(p["name"])
    else:
        striped: bool = config.get("cli_striped", False)
        tag_pretty_print(plist, striped=striped)

    return


def list_users(args: CliArgs) -> None:
    """List connected users with custom formatting."""
    colors()

    config_status, config = get_current_config(**config_from_args(args))

    # Use GraphQL for listing
    gql = NovemGQL.from_args(args)
    plist = list_users_gql(gql)

    # Apply filters
    plist = apply_filters(plist, args.get("filter"))

    # Get current user's username (token-resolved, not the cached config label)
    current_user = gql.current_username

    # Sort by relevance: me first > connected > following > follower > groups > orgs > username
    def user_sort_key(u: Dict[str, Any]) -> Tuple[bool, bool, bool, bool, int, int, str]:
        is_me = u.get("username", "") == current_user
        return (
            not is_me,  # Current user first
            not u.get("connected", False),  # Connected second (False sorts before True, so negate)
            not u.get("following", False),  # Following third
            not u.get("follower", False),  # Followers fourth
            -(u.get("groups", 0) or 0),  # More shared groups = higher priority
            -(u.get("orgs", 0) or 0),  # More shared orgs = higher priority
            u.get("username", "").lower(),  # Alphabetically by username
        )

    plist = sorted(plist, key=user_sort_key)

    if args["list"]:
        # print usernames only
        for p in plist:
            print(p["username"])
        return

    def bio_fmt(bio: Optional[str], _cl: Any) -> str:
        """Format bio, stripping newlines."""
        if not bio:
            return ""
        return bio.replace("\n", " ")

    # Helper to format number or dash
    def fmt_num(n: int) -> str:
        return str(n) if n else "-"

    # Calculate max widths for dynamic columns
    max_orgs = max((len(fmt_num(p.get("orgs", 0))) for p in plist), default=1)
    max_groups = max((len(fmt_num(p.get("groups", 0))) for p in plist), default=1)

    max_social_conn = max((len(fmt_num(p.get("social_connections", 0))) for p in plist), default=1)
    max_social_foll = max((len(fmt_num(p.get("social_followers", 0))) for p in plist), default=1)
    max_social_fing = max((len(fmt_num(p.get("social_following", 0))) for p in plist), default=1)

    max_plots = max((len(fmt_num(p.get("plots", 0))) for p in plist), default=1)
    max_grids = max((len(fmt_num(p.get("grids", 0))) for p in plist), default=1)
    max_mails = max((len(fmt_num(p.get("mails", 0))) for p in plist), default=1)
    max_docs = max((len(fmt_num(p.get("docs", 0))) for p in plist), default=1)
    max_repos = max((len(fmt_num(p.get("repos", 0))) for p in plist), default=1)
    max_jobs = max((len(fmt_num(p.get("jobs", 0))) for p in plist), default=1)

    # Build dynamic header for content counts (P G M D R J)
    content_header = " ".join(
        [
            "P".rjust(max_plots),
            "G".rjust(max_grids),
            "M".rjust(max_mails),
            "D".rjust(max_docs),
            "R".rjust(max_repos),
            "J".rjust(max_jobs),
        ]
    )

    ppo: List[Dict[str, Any]] = [
        {
            "key": "_verified",
            "header": "   ",
            "type": "text",
            "overflow": "keep",
            "no_border": True,
            "no_padding": True,
        },
        {
            "key": "username",
            "header": "Username",
            "type": "text",
            "clr": cl.OKCYAN,
            "overflow": "keep",
        },
        {
            "key": "name",
            "header": "Name",
            "type": "text",
            "overflow": "keep",
        },
        {
            "key": "_public",
            "header": "P",
            "type": "text",
            "overflow": "keep",
        },
        {
            "key": "_conn",
            "header": "Relation",
            "type": "text",
            "overflow": "keep",
        },
        {
            "key": "_groups",
            "header": "Groups",
            "type": "text",
            "overflow": "keep",
        },
        {
            "key": "_social",
            "header": "Social",
            "type": "text",
            "overflow": "keep",
        },
        {
            "key": "_content",
            "header": content_header,
            "type": "text",
            "overflow": "keep",
        },
        {
            "key": "bio",
            "header": "Biography",
            "fmt": bio_fmt,
            "type": "text",
            "overflow": "truncate",
        },
    ]

    # Pre-process formatted columns
    for p in plist:
        # Marker: > for current user, * for verified/novem/org users
        user_type = p.get("type", "").upper()
        is_me = p.get("username", "") == current_user

        if is_me:
            # Current user always shows > with color based on type
            if user_type in ("NOVEM", "SYSTEM"):
                p["_verified"] = f" {cl.WARNING}>{cl.ENDFGC} "
            elif user_type == "VERIFIED":
                p["_verified"] = f" {cl.OKBLUE}>{cl.ENDFGC} "
            elif user_type == "ORG":
                p["_verified"] = f" {cl.OKGREEN}>{cl.ENDFGC} "
            else:
                p["_verified"] = " > "
        else:
            # Other users show symbol based on type: ◆ for novem, * for verified, + for org
            if user_type in ("NOVEM", "SYSTEM"):
                p["_verified"] = f" {cl.WARNING}◆{cl.ENDFGC} "
            elif user_type == "VERIFIED":
                p["_verified"] = f" {cl.OKBLUE}*{cl.ENDFGC} "
            elif user_type == "ORG":
                p["_verified"] = f" {cl.OKGREEN}+{cl.ENDFGC} "
            else:
                p["_verified"] = "   "

        # Public profile indicator
        p["_public"] = f"{cl.FAIL}P{cl.ENDFGC}" if p.get("public") else "-"

        # Connection status: C F F I (connected, follower, following, ignoring)
        connected = f"{cl.OKGREEN}C{cl.ENDFGC}" if p.get("connected") else "-"
        follower = f"{cl.OKBLUE}F{cl.ENDFGC}" if p.get("follower") else "-"
        following = f"{cl.OKCYAN}F{cl.ENDFGC}" if p.get("following") else "-"
        ignoring = f"{cl.FAIL}I{cl.ENDFGC}" if p.get("ignoring") else "-"
        p["_conn"] = f"{connected} {follower} {following} {ignoring} "

        # Groups: orgs, org_groups, user_groups
        orgs_str = fmt_num(p.get("orgs", 0))
        groups_str = fmt_num(p.get("groups", 0))
        p["_groups"] = f"{orgs_str:>{max_orgs}} {groups_str:>{max_groups}} -"

        # Social: connections, followers, following
        conn_str = fmt_num(p.get("social_connections", 0))
        followers_str = fmt_num(p.get("social_followers", 0))
        following_str = fmt_num(p.get("social_following", 0))
        p["_social"] = (
            f"{conn_str:>{max_social_conn}} {followers_str:>{max_social_foll}} {following_str:>{max_social_fing}}"
        )

        # Content counts: P G M D R J
        plots_str = fmt_num(p.get("plots", 0))
        grids_str = fmt_num(p.get("grids", 0))
        mails_str = fmt_num(p.get("mails", 0))
        docs_str = fmt_num(p.get("docs", 0))
        repos_str = fmt_num(p.get("repos", 0))
        jobs_str = fmt_num(p.get("jobs", 0))
        p["_content"] = (
            f"{plots_str:>{max_plots}} {grids_str:>{max_grids}} {mails_str:>{max_mails}} "
            f"{docs_str:>{max_docs}} {repos_str:>{max_repos}} {jobs_str:>{max_jobs}}"
        )

    striped: bool = config.get("cli_striped", False)
    ppl = pretty_format(plist, ppo, striped=striped)

    print(ppl)


def list_jobs(args: CliArgs) -> None:
    """List jobs with custom formatting."""
    colors()

    config_status, config = get_current_config(**config_from_args(args))

    for_user = args["for_user"] if ("for_user" in args and args["for_user"]) else ""

    # Use GraphQL for listing
    gql = NovemGQL.from_args(args)
    # --for-user lists that user's jobs; otherwise list my own via `me`.
    plist = list_jobs_gql(gql, author=for_user) if for_user else list_my_jobs_gql(gql)

    # Apply filters
    plist = apply_filters(plist, args.get("filter"))

    # Sort by: 1) favs first, 2) likes second, 3) rest last - each group sorted by updated (newest first)
    def parse_date(date_str: str) -> datetime.datetime:
        dt = parse_api_datetime(date_str)
        return dt if dt else datetime.datetime.min.replace(tzinfo=timezone.utc)

    def sort_tier(markers: str) -> int:
        """Return sort tier: 0=fav, 1=like only, 2=rest."""
        if "*" in markers:
            return 0
        if "+" in markers:
            return 1
        return 2

    plist = sorted(plist, key=lambda x: (sort_tier(x.get("fav", "")), -parse_date(x["updated"]).timestamp()))

    if args["list"]:
        # print ids only
        for p in plist:
            print(p["id"])
        return

    def share_fmt(share: List[str], cl: cl) -> str:
        """Format shared column: P C @ + for public, chat, user group, org group."""
        sl = [x[0] for x in share]
        pub = f"{cl.FAIL}P{cl.ENDFGC}" if "p" in sl else "-"  # public
        chat = f"{cl.WARNING}C{cl.ENDFGC}" if "c" in sl else "-"  # chat claim
        ug = f"{cl.OKGREEN}@{cl.ENDFGC}" if "@" in sl else "-"  # user group
        og = f"{cl.OKGREEN}+{cl.ENDFGC}" if "+" in sl else "-"  # org group
        return f"{pub} {chat} {ug} {og}"

    def trigger_fmt(triggers: List[str], cl: cl) -> str:
        """Format triggers column: M S A C for mail, schedule, api, commit."""
        tset = set(t.lower() for t in triggers) if triggers else set()
        mail = f"{cl.OKCYAN}M{cl.ENDFGC}" if "mail" in tset else "-"
        sched = f"{cl.OKBLUE}S{cl.ENDFGC}" if "schedule" in tset else "-"
        api = f"{cl.OKGREEN}A{cl.ENDFGC}" if "api" in tset else "-"
        commit = f"{cl.WARNING}C{cl.ENDFGC}" if "commit" in tset else "-"
        return f"{mail} {sched} {api} {commit}"

    def steps_fmt(item: Dict[str, Any], cl: cl) -> str:
        """Format steps column as current:total."""
        current = item.get("current_step")
        total = item.get("job_steps", 0) or 0
        if current is not None:
            return f"{current}:{total}"
        return f":{total}"

    def status_fmt(status: Optional[str], cl: cl) -> str:
        """Format status with color."""
        if not status:
            return ""
        status_lower = status.lower()
        if status_lower == "success":
            return f"{cl.OKGREEN}{status}{cl.ENDFGC}"
        elif status_lower == "running":
            return f"{cl.OKBLUE}{status}{cl.ENDFGC}"
        elif status_lower == "failure":
            return f"{cl.FAIL}{status}{cl.ENDFGC}"
        elif status_lower == "disable" or status_lower == "disabled":
            return f"{cl.WARNING}{status}{cl.ENDFGC}"
        return status

    has_favs = any("*" in p.get("fav", "") for p in plist)
    has_likes = any("+" in p.get("fav", "") for p in plist)

    def fav_fmt(markers: str, cl: cl) -> str:
        parts = ""
        if has_favs:
            parts += f"{cl.WARNING}*{cl.ENDFGC}" if "*" in markers else " "
        if has_likes:
            parts += f"{cl.OKBLUE}+{cl.ENDFGC}" if "+" in markers else " "
        return f" {parts} " if parts else ""

    fav_header_width = (1 if has_favs else 0) + (1 if has_likes else 0)
    fav_header = (" " * (fav_header_width + 2)) if fav_header_width > 0 else ""

    ppo: List[Dict[str, Any]] = [
        *(
            [
                {
                    "key": "fav",
                    "header": fav_header,
                    "type": "text",
                    "fmt": fav_fmt,
                    "overflow": "keep",
                    "no_border": True,
                    "no_padding": True,
                },
            ]
            if has_favs or has_likes
            else []
        ),
        {
            "key": "id",
            "header": "Job ID",
            "type": "text",
            "overflow": "keep",
        },
        {
            "key": "type",
            "header": "Type",
            "type": "text",
            "clr": cl.OKCYAN,
            "overflow": "keep",
        },
        {
            "key": "shared",
            "header": "Shared",
            "type": "text",
            "fmt": share_fmt,
            "overflow": "keep",
            "protect": True,
        },
        {
            "key": "name",
            "header": "Name",
            "type": "text",
            "overflow": "shrink",
            "drop": 2,
        },
        {
            "key": "last_run_status",
            "header": "Status",
            "type": "text",
            "fmt": status_fmt,
            "overflow": "keep",
        },
        {
            "key": "triggers",
            "header": "Trigger",
            "type": "text",
            "fmt": trigger_fmt,
            "overflow": "keep",
        },
        {
            "key": "_schedule",
            "header": "Schedule",
            "type": "text",
            "overflow": "keep",
            "protect": True,
        },
        {
            "key": "_steps",
            "header": "Steps",
            "type": "text",
            "overflow": "keep",
            "align": "right",
        },
        {
            "key": "run_count",
            "header": "Runs",
            "type": "text",
            "overflow": "keep",
            "align": "right",
        },
        {
            "key": "_activity",
            "header": "Activity",
            "type": "text",
            "overflow": "keep",
            "drop": 4,
        },
        {
            "key": "_views_fmt",
            "header": "Views",
            "type": "text",
            "overflow": "keep",
            "drop": 3,
        },
        {
            "key": "_last_run",
            "header": "Last Run",
            "type": "text",
            "overflow": "keep",
        },
        {
            "key": "summary",
            "header": "Summary",
            "type": "text",
            "overflow": "truncate",
            "drop": 1,
        },
    ]

    # Pre-process columns that need string conversion
    for p in plist:
        # Steps column
        current = p.get("current_step")
        total = p.get("job_steps", 0) or 0
        if current is not None:
            p["_steps"] = f"{current}:{total}"
        else:
            p["_steps"] = f":{total}"

        # Run count - convert to string
        run_count = p.get("run_count")
        p["run_count"] = str(run_count) if run_count is not None else ""

        # Last run - format last_run_time as relative time
        p["_last_run"] = _format_time_ago(p.get("last_run_time", ""))

    # Schedule column: align the five cron fields into per-position columns
    # across every row (right-aligned), so */15 and single-char fields line
    # up. A TZ=<zone> prefix is never displayed — the fields are recomputed
    # into the viewer's configured time zone instead (the raw schedule config
    # stays authoritative). Anything unparseable is left as-is.
    parsed_scheds: List[Tuple[Dict[str, Any], Optional[List[str]], str, str]] = []
    for p in plist:
        raw = (p.get("schedule") or "").strip()
        tz = ""
        fields = raw.split()
        if fields and fields[0].upper().startswith("TZ="):
            tz = fields[0][3:]
            fields = fields[1:]
        if not raw:
            parsed_scheds.append((p, ["-"] * 5, tz, raw))
        elif len(fields) == 5:
            parsed_scheds.append((p, fields, tz, raw))
        else:
            parsed_scheds.append((p, None, tz, raw))

    if any(tz for _, fields, tz, _ in parsed_scheds if fields):
        viewer_tz = _viewer_timezone(gql)
        parsed_scheds = [
            (p, _localize_cron_fields(fields, tz, viewer_tz) if (fields and tz) else fields, tz, raw)
            for p, fields, tz, raw in parsed_scheds
        ]

    field_widths = [1] * 5
    for _, fields, _, _ in parsed_scheds:
        if fields:
            for fi in range(5):
                field_widths[fi] = max(field_widths[fi], len(fields[fi]))

    for p, fields, tz, raw in parsed_scheds:
        if fields is None:
            p["_schedule"] = raw
        else:
            p["_schedule"] = " ".join(f"{fields[fi]:>{field_widths[fi]}}" for fi in range(5))

    _format_activity(plist)
    _format_views(plist)

    # Calculate max widths for right-aligned columns (must be at least header width)
    max_steps = max(max((len(p["_steps"]) for p in plist), default=0), len("Steps"))
    max_runs = max(max((len(p["run_count"]) for p in plist), default=0), len("Runs"))

    # Right-align by padding with spaces to fill full column width
    for p in plist:
        p["_steps"] = p["_steps"].rjust(max_steps)
        p["run_count"] = p["run_count"].rjust(max_runs)

    striped: bool = config.get("cli_striped", False)
    ppl = pretty_format(plist, ppo, striped=striped)

    print(ppl)


def _localize_cron_fields(fields: List[str], from_tz: str, to_tz: Optional[str]) -> List[str]:
    """Convert a cron schedule's minute/hour from ``from_tz`` into the
    viewer's zone (``to_tz``, falling back to the OS-local zone).

    Only pure-numeric minute and hour fields can be shifted safely; anything
    else (ranges, steps, lists) is returned unchanged.

    A shift that crosses midnight also moves the day. A single numeric
    day-of-week can be rotated to compensate, so that is done; a day-of-month
    cannot (month lengths vary) and neither can a compound day-of-week, so
    those schedules are left in their own zone rather than rendered wrong.
    The raw schedule config remains authoritative either way.
    """
    try:
        from zoneinfo import ZoneInfo

        src = ZoneInfo(from_tz)
        dst: Any = ZoneInfo(to_tz) if to_tz else datetime.datetime.now().astimezone().tzinfo
    except Exception:
        return fields

    minute, hour, dom, mon, dow = fields
    if not (minute.isdigit() and hour.isdigit()):
        return fields

    now = datetime.datetime.now(tz=src)
    src_dt = now.replace(hour=int(hour) % 24, minute=int(minute) % 60, second=0, microsecond=0)
    dst_dt = src_dt.astimezone(dst)

    day_delta = (dst_dt.date() - src_dt.date()).days
    if day_delta:
        # the day moves too, and only a plain numeric day-of-week can follow
        # it: "30 23 1 * *" UTC would otherwise render as "30 1 1 * *" in
        # UTC+2 and claim the 1st while actually firing on the 2nd
        if dom != "*" or mon != "*" or not (dow == "*" or dow.isdigit()):
            return fields

    out = [str(dst_dt.minute), str(dst_dt.hour), dom, mon, dow]
    if day_delta and dow.isdigit():
        out[4] = str((int(dow) + day_delta) % 7)
    return out


def _viewer_timezone(gql: NovemGQL) -> Optional[str]:
    """The viewer's configured novem time zone via ``me { timezone }``.

    Returns None when the backend does not expose the field yet or the
    query fails — callers fall back to the OS-local zone.
    """
    try:
        me = gql._query("query { me { timezone } }").get("me") or {}
        tz = me.get("timezone")
        return str(tz) if tz else None
    except SystemExit:
        raise
    except Exception:
        return None


# per-kind (fetch-by-author, fetch-mine) listing functions
_CODE_LIST_FNS = {
    "space": (list_spaces_gql, list_my_spaces_gql),
    "repo": (list_repos_gql, list_my_repos_gql),
    "computer": (list_computers_gql, list_my_computers_gql),
    "image": (list_images_gql, list_my_images_gql),
}


def list_code_vis(args: CliArgs, kind: str) -> None:
    """List a coding resource collection (space/repo/computer/image)."""
    colors()

    config_status, config = get_current_config(**config_from_args(args))

    for_user = args["for_user"] if ("for_user" in args and args["for_user"]) else ""

    by_author, mine = _CODE_LIST_FNS[kind]

    # Use GraphQL for listing
    gql = NovemGQL.from_args(args)
    plist = by_author(gql, author=for_user) if for_user else mine(gql)

    # Apply filters
    plist = apply_filters(plist, args.get("filter"))

    # Sort by: favs first, likes second, rest last - each by updated (newest first)
    def parse_date(date_str: str) -> datetime.datetime:
        dt = parse_api_datetime(date_str)
        return dt if dt else datetime.datetime.min.replace(tzinfo=timezone.utc)

    def sort_tier(markers: str) -> int:
        if "*" in markers:
            return 0
        if "+" in markers:
            return 1
        return 2

    plist = sorted(plist, key=lambda x: (sort_tier(x.get("fav", "")), -parse_date(x["updated"]).timestamp()))

    if args["list"]:
        # print ids only
        for p in plist:
            print(p["id"])
        return

    def share_fmt(share: List[str], cl: cl) -> str:
        """Format shared column: P C @ + for public, chat, user group, org group."""
        sl = [x[0] for x in share]
        pub = f"{cl.FAIL}P{cl.ENDFGC}" if "p" in sl else "-"  # public
        chat = f"{cl.WARNING}C{cl.ENDFGC}" if "c" in sl else "-"  # chat claim
        ug = f"{cl.OKGREEN}@{cl.ENDFGC}" if "@" in sl else "-"  # user group
        og = f"{cl.OKGREEN}+{cl.ENDFGC}" if "+" in sl else "-"  # org group
        return f"{pub} {chat} {ug} {og}"

    def status_fmt(status: Optional[str], cl: cl) -> str:
        """Format computer/image status with color."""
        if not status:
            return ""
        s = status.lower()
        if s in ("online", "ready"):
            return f"{cl.OKGREEN}{status}{cl.ENDFGC}"
        if s in ("booting", "building"):
            return f"{cl.OKBLUE}{status}{cl.ENDFGC}"
        if s in ("failed", "failure"):
            return f"{cl.FAIL}{status}{cl.ENDFGC}"
        if s.startswith("ready"):  # ready (stale)
            return f"{cl.WARNING}{status}{cl.ENDFGC}"
        return status

    has_favs = any("*" in p.get("fav", "") for p in plist)
    has_likes = any("+" in p.get("fav", "") for p in plist)

    def fav_fmt(markers: str, cl: cl) -> str:
        parts = ""
        if has_favs:
            parts += f"{cl.WARNING}*{cl.ENDFGC}" if "*" in markers else " "
        if has_likes:
            parts += f"{cl.OKBLUE}+{cl.ENDFGC}" if "+" in markers else " "
        return f" {parts} " if parts else ""

    fav_header_width = (1 if has_favs else 0) + (1 if has_likes else 0)
    fav_header = (" " * (fav_header_width + 2)) if fav_header_width > 0 else ""

    fav_col: List[Dict[str, Any]] = (
        [
            {
                "key": "fav",
                "header": fav_header,
                "type": "text",
                "fmt": fav_fmt,
                "overflow": "keep",
                "no_border": True,
                "no_padding": True,
            },
        ]
        if has_favs or has_likes
        else []
    )

    id_col: Dict[str, Any] = {
        "key": "id",
        "header": f"{kind.capitalize()} ID",
        "type": "text",
        "overflow": "keep",
    }
    name_col: Dict[str, Any] = {
        "key": "name",
        "header": "Name",
        "type": "text",
        "overflow": "shrink",
        "drop": 2,
    }
    shared_col: Dict[str, Any] = {
        "key": "shared",
        "header": "Shared",
        "type": "text",
        "fmt": share_fmt,
        "overflow": "keep",
        "protect": True,
    }
    activity_col: Dict[str, Any] = {
        "key": "_activity",
        "header": "Activity",
        "type": "text",
        "overflow": "keep",
        "drop": 4,
    }
    views_col: Dict[str, Any] = {
        "key": "_views_fmt",
        "header": "Views",
        "type": "text",
        "overflow": "keep",
        "drop": 3,
    }
    updated_col: Dict[str, Any] = {
        "key": "_updated",
        "header": "Updated",
        "type": "text",
        "overflow": "keep",
    }
    summary_col: Dict[str, Any] = {
        "key": "summary",
        "header": "Summary",
        "type": "text",
        "overflow": "truncate",
        "drop": 1,
    }
    status_col: Dict[str, Any] = {
        "key": "status",
        "header": "Status",
        "type": "text",
        "fmt": status_fmt,
        "overflow": "keep",
    }
    type_col: Dict[str, Any] = {
        "key": "type",
        "header": "Type",
        "type": "text",
        "clr": cl.OKCYAN,
        "overflow": "keep",
    }

    if kind == "repo":
        url_col: Dict[str, Any] = {
            "key": "uri",
            "header": "Clone URL",
            "type": "url",
            "overflow": "shrink",
        }
        ppo = [*fav_col, id_col, type_col, shared_col, name_col, activity_col, views_col, updated_col, url_col]
    elif kind == "space":
        ppo = [*fav_col, id_col, shared_col, name_col, activity_col, views_col, updated_col, summary_col]
    elif kind == "computer":
        image_col: Dict[str, Any] = {
            "key": "image_ref",
            "header": "Image",
            "type": "text",
            "overflow": "shrink",
        }
        cpu_col: Dict[str, Any] = {
            "key": "_cpu",
            "header": "Cpu",
            "type": "text",
            "overflow": "keep",
            "align": "right",
        }
        mem_col: Dict[str, Any] = {
            "key": "_memory",
            "header": "Mem",
            "type": "text",
            "overflow": "keep",
            "align": "right",
        }
        disk_col: Dict[str, Any] = {
            "key": "_disk",
            "header": "Disk",
            "type": "text",
            "overflow": "keep",
            "align": "right",
        }
        ppo = [
            *fav_col,
            id_col,
            type_col,
            shared_col,
            name_col,
            status_col,
            image_col,
            cpu_col,
            mem_col,
            disk_col,
            updated_col,
        ]
    else:  # image
        repo_col: Dict[str, Any] = {
            "key": "repo",
            "header": "Repo",
            "type": "text",
            "overflow": "keep",
        }
        labels_col: Dict[str, Any] = {
            "key": "_labels",
            "header": "Labels",
            "type": "text",
            "overflow": "shrink",
        }
        ppo = [*fav_col, id_col, shared_col, name_col, repo_col, status_col, labels_col, updated_col]

    # Pre-process derived columns
    for p in plist:
        p["_updated"] = _format_relative_time(p.get("updated", ""))
        if kind == "computer":
            cpu = p.get("cpu")
            p["_cpu"] = f"{cpu:g}" if isinstance(cpu, (int, float)) else (cpu or "-")
            p["_memory"] = p.get("memory") or "-"
            p["_disk"] = p.get("disk") or "-"
        if kind == "image":
            p["_labels"] = ", ".join(p.get("labels", []) or [])

    _format_activity(plist)
    _format_views(plist)

    striped: bool = config.get("cli_striped", False)
    ppl = pretty_format(plist, ppo, striped=striped)

    print(ppl)


def _format_relative_time(date_str: str) -> str:
    """Format a date string as relative time (e.g., '2 weeks ago')."""
    if not date_str:
        return ""
    try:
        dt = parse_api_datetime(date_str)
        if not dt:
            return date_str
        now = datetime.datetime.now(timezone.utc)
        delta = now - dt

        if delta.days < 0:
            return "in the future"
        elif delta.days == 0:
            if delta.seconds < 60:
                return "just now"
            elif delta.seconds < 3600:
                mins = delta.seconds // 60
                return f"{mins} min{'s' if mins != 1 else ''} ago"
            else:
                hours = delta.seconds // 3600
                return f"{hours} hour{'s' if hours != 1 else ''} ago"
        elif delta.days == 1:
            return "yesterday"
        elif delta.days < 7:
            return f"{delta.days} days ago"
        elif delta.days < 14:
            return "1 week ago"
        elif delta.days < 30:
            weeks = delta.days // 7
            return f"{weeks} weeks ago"
        elif delta.days < 60:
            return "1 month ago"
        elif delta.days < 365:
            months = delta.days // 30
            return f"{months} months ago"
        elif delta.days < 730:
            return "1 year ago"
        else:
            years = delta.days // 365
            return f"{years} years ago"
    except Exception:
        return date_str


def _format_time_ago(date_str: str) -> str:
    """Format a date string as compact relative time.

    Uses compact format: "1 min ago", "2 hrs ago", "1 day ago", etc.
    """
    if not date_str:
        return ""
    try:
        dt = parse_api_datetime(date_str)
        if not dt:
            return date_str
        now = datetime.datetime.now(timezone.utc)
        delta = now - dt

        if delta.days < 0:
            return "in the future"
        elif delta.days == 0:
            if delta.seconds < 60:
                return "just now"
            elif delta.seconds < 3600:
                mins = delta.seconds // 60
                return f"{mins} min ago"
            else:
                hours = delta.seconds // 3600
                if hours == 1:
                    return "1 hour ago"
                else:
                    return f"{hours} hrs ago"
        elif delta.days == 1:
            return "1 day ago"
        elif delta.days < 7:
            return f"{delta.days} days ago"
        elif delta.days < 14:
            return "1 week ago"
        elif delta.days < 30:
            weeks = delta.days // 7
            return f"{weeks} weeks ago"
        elif delta.days < 60:
            return "1 month ago"
        elif delta.days < 365:
            months = delta.days // 30
            return f"{months} months ago"
        elif delta.days < 730:
            return "1 year ago"
        else:
            years = delta.days // 365
            return f"{years} years ago"
    except Exception:
        return date_str


def list_orgs(args: CliArgs) -> None:
    """List organizations with custom formatting."""
    colors()

    config_status, config = get_current_config(**config_from_args(args))

    # Use GraphQL for listing
    gql = NovemGQL.from_args(args)
    plist = list_orgs_gql(gql)

    # Apply filters
    plist = apply_filters(plist, args.get("filter"))

    # Sort by role priority, then name
    role_order = {"founder": 0, "admin": 1, "superuser": 2, "member": 3}
    plist = sorted(plist, key=lambda x: (role_order.get(x.get("role", "member"), 3), x.get("name", "").lower()))

    if args.get("list"):
        # print org ids only
        for p in plist:
            print(p["id"])
        return

    def state_fmt(item: Dict[str, Any], _cl: Any) -> str:
        """Format state column: P O S (public, open, subdomain)."""
        pub = f"{cl.FAIL}P{cl.ENDFGC}" if item.get("public") else "-"
        opn = f"{cl.FAIL}O{cl.ENDFGC}" if item.get("is_open") else "-"
        sub = f"{cl.WARNING}S{cl.ENDFGC}" if item.get("enable_subdomain") else "-"
        return f"{pub} {opn} {sub}"

    def role_fmt(role: str, _cl: Any) -> str:
        """Format role with color."""
        if role == "founder":
            return f"{cl.WARNING}{role}{cl.ENDFGC}"
        elif role == "admin":
            return f"{cl.FAIL}{role}{cl.ENDFGC}"
        elif role == "superuser":
            return f"{cl.OKCYAN}{role}{cl.ENDFGC}"
        return role

    # Helper to format number or dash
    def fmt_num(n: int) -> str:
        return str(n) if n else "-"

    # Calculate max widths for dynamic columns
    max_plots = max((len(fmt_num(p.get("plots", 0))) for p in plist), default=1)
    max_grids = max((len(fmt_num(p.get("grids", 0))) for p in plist), default=1)
    max_mails = max((len(fmt_num(p.get("mails", 0))) for p in plist), default=1)
    max_docs = max((len(fmt_num(p.get("docs", 0))) for p in plist), default=1)
    max_repos = max((len(fmt_num(p.get("repos", 0))) for p in plist), default=1)
    max_jobs = max((len(fmt_num(p.get("jobs", 0))) for p in plist), default=1)

    # Build dynamic header for content counts (P G M D R J)
    content_header = " ".join(
        [
            "P".rjust(max_plots),
            "G".rjust(max_grids),
            "M".rjust(max_mails),
            "D".rjust(max_docs),
            "R".rjust(max_repos),
            "J".rjust(max_jobs),
        ]
    )

    ppo: List[Dict[str, Any]] = [
        {
            "key": "id",
            "header": "Org ID",
            "type": "text",
            "clr": cl.OKCYAN,
            "overflow": "keep",
        },
        {
            "key": "name",
            "header": "Name",
            "type": "text",
            "overflow": "shrink",
        },
        {
            "key": "role",
            "header": "Role",
            "type": "text",
            "fmt": role_fmt,
            "overflow": "keep",
        },
        {
            "key": "groups_count",
            "header": "Grp",
            "type": "text",
            "overflow": "keep",
            "align": "right",
        },
        {
            "key": "members_count",
            "header": "Mem",
            "type": "text",
            "overflow": "keep",
            "align": "right",
        },
        {
            "key": "_state",
            "header": "State",
            "type": "text",
            "overflow": "keep",
        },
        {
            "key": "_content",
            "header": content_header,
            "type": "text",
            "overflow": "keep",
        },
        {
            "key": "_joined",
            "header": "Joined",
            "type": "text",
            "overflow": "keep",
        },
    ]

    # Pre-process columns
    for p in plist:
        # State column
        p["_state"] = state_fmt(p, cl)

        # Joined column (relative time)
        p["_joined"] = _format_relative_time(p.get("created", ""))

        # Content counts: P G M D R J
        plots_str = fmt_num(p.get("plots", 0))
        grids_str = fmt_num(p.get("grids", 0))
        mails_str = fmt_num(p.get("mails", 0))
        docs_str = fmt_num(p.get("docs", 0))
        repos_str = fmt_num(p.get("repos", 0))
        jobs_str = fmt_num(p.get("jobs", 0))
        p["_content"] = (
            f"{plots_str:>{max_plots}} {grids_str:>{max_grids}} {mails_str:>{max_mails}} "
            f"{docs_str:>{max_docs}} {repos_str:>{max_repos}} {jobs_str:>{max_jobs}}"
        )

        # Convert counts to strings
        p["groups_count"] = str(p.get("groups_count", 0))
        p["members_count"] = str(p.get("members_count", 0))

    striped: bool = config.get("cli_striped", False)
    ppl = pretty_format(plist, ppo, striped=striped)

    print(ppl)


def list_org_users(args: CliArgs) -> None:
    """List org members with roles and content shared with org groups."""
    colors()

    config_status, config = get_current_config(**config_from_args(args))

    org_id = args.get("org", "")
    if not org_id:
        print("Error: No org specified")
        return

    # Use GraphQL for listing
    gql = NovemGQL.from_args(args)
    current_user = gql.current_username
    plist = list_org_members_gql(gql, org_id, current_user)

    # Apply filters
    plist = apply_filters(plist, args.get("filter"))

    # Role priority map for sorting
    role_order = {"founder": 0, "admin": 1, "superuser": 2, "member": 3}

    # Sort by: me first > role priority > connected > alphabetically
    def user_sort_key(u: Dict[str, Any]) -> Tuple[bool, int, bool, str]:
        is_me = u.get("is_me", False)
        return (
            not is_me,  # Current user first
            role_order.get(u.get("role", "member"), 3),  # Role priority
            not u.get("connected", False),  # Connected users next
            u.get("username", "").lower(),  # Alphabetically by username
        )

    plist = sorted(plist, key=user_sort_key)

    if args.get("list"):
        # print usernames only
        for p in plist:
            print(p["username"])
        return

    # Helper to format number or dash
    def fmt_num(n: int) -> str:
        return str(n) if n else "-"

    # Calculate max widths for dynamic columns
    max_plots = max((len(fmt_num(p.get("plots", 0))) for p in plist), default=1)
    max_grids = max((len(fmt_num(p.get("grids", 0))) for p in plist), default=1)
    max_mails = max((len(fmt_num(p.get("mails", 0))) for p in plist), default=1)
    max_docs = max((len(fmt_num(p.get("docs", 0))) for p in plist), default=1)
    max_repos = max((len(fmt_num(p.get("repos", 0))) for p in plist), default=1)
    max_jobs = max((len(fmt_num(p.get("jobs", 0))) for p in plist), default=1)

    # Build dynamic header for content counts (P G M D R J)
    content_header = " ".join(
        [
            "P".rjust(max_plots),
            "G".rjust(max_grids),
            "M".rjust(max_mails),
            "D".rjust(max_docs),
            "R".rjust(max_repos),
            "J".rjust(max_jobs),
        ]
    )

    def role_fmt(role: str, _cl: Any) -> str:
        """Format role with color."""
        if role == "founder":
            return f"{cl.WARNING}{role}{cl.ENDFGC}"
        elif role == "admin":
            return f"{cl.FAIL}{role}{cl.ENDFGC}"
        elif role == "superuser":
            return f"{cl.OKCYAN}{role}{cl.ENDFGC}"
        return role

    ppo: List[Dict[str, Any]] = [
        {
            "key": "_verified",
            "header": "   ",
            "type": "text",
            "overflow": "keep",
            "no_border": True,
            "no_padding": True,
        },
        {
            "key": "username",
            "header": "Username",
            "type": "text",
            "clr": cl.OKCYAN,
            "overflow": "keep",
        },
        {
            "key": "name",
            "header": "Name",
            "type": "text",
            "overflow": "shrink",
        },
        {
            "key": "role",
            "header": "Role",
            "type": "text",
            "fmt": role_fmt,
            "overflow": "keep",
        },
        {
            "key": "_public",
            "header": "P",
            "type": "text",
            "overflow": "keep",
        },
        {
            "key": "_conn",
            "header": "Relation",
            "type": "text",
            "overflow": "keep",
        },
        {
            "key": "_content",
            "header": content_header,
            "type": "text",
            "overflow": "keep",
        },
    ]

    # Pre-process formatted columns
    for p in plist:
        # Marker: > for current user, * for verified/novem/org users
        user_type = p.get("type", "").upper()
        is_me = p.get("is_me", False)

        if is_me:
            # Current user always shows > with color based on type
            if user_type in ("NOVEM", "SYSTEM"):
                p["_verified"] = f" {cl.WARNING}>{cl.ENDFGC} "
            elif user_type == "VERIFIED":
                p["_verified"] = f" {cl.OKBLUE}>{cl.ENDFGC} "
            elif user_type == "ORG":
                p["_verified"] = f" {cl.OKGREEN}>{cl.ENDFGC} "
            else:
                p["_verified"] = " > "
        else:
            # Other users show symbol based on type: ◆ for novem, * for verified, + for org
            if user_type in ("NOVEM", "SYSTEM"):
                p["_verified"] = f" {cl.WARNING}◆{cl.ENDFGC} "
            elif user_type == "VERIFIED":
                p["_verified"] = f" {cl.OKBLUE}*{cl.ENDFGC} "
            elif user_type == "ORG":
                p["_verified"] = f" {cl.OKGREEN}+{cl.ENDFGC} "
            else:
                p["_verified"] = "   "

        # Public profile indicator
        p["_public"] = f"{cl.FAIL}P{cl.ENDFGC}" if p.get("public") else "-"

        # Connection status: C F F I (connected, follower, following, ignoring)
        connected = f"{cl.OKGREEN}C{cl.ENDFGC}" if p.get("connected") else "-"
        follower = f"{cl.OKBLUE}F{cl.ENDFGC}" if p.get("follower") else "-"
        following = f"{cl.OKCYAN}F{cl.ENDFGC}" if p.get("following") else "-"
        ignoring = f"{cl.FAIL}I{cl.ENDFGC}" if p.get("ignoring") else "-"
        p["_conn"] = f"{connected} {follower} {following} {ignoring} "

        # Content counts: P G M D R J
        plots_str = fmt_num(p.get("plots", 0))
        grids_str = fmt_num(p.get("grids", 0))
        mails_str = fmt_num(p.get("mails", 0))
        docs_str = fmt_num(p.get("docs", 0))
        repos_str = fmt_num(p.get("repos", 0))
        jobs_str = fmt_num(p.get("jobs", 0))
        p["_content"] = (
            f"{plots_str:>{max_plots}} {grids_str:>{max_grids}} {mails_str:>{max_mails}} "
            f"{docs_str:>{max_docs}} {repos_str:>{max_repos}} {jobs_str:>{max_jobs}}"
        )

    striped: bool = config.get("cli_striped", False)
    ppl = pretty_format(plist, ppo, striped=striped)

    print(ppl)


def list_org_groups(args: CliArgs) -> None:
    """List groups within an org."""
    colors()

    config_status, config = get_current_config(**config_from_args(args))

    org_id = args.get("org", "")
    if not org_id:
        print("Error: No org specified")
        return

    # Use GraphQL for listing
    gql = NovemGQL.from_args(args)
    current_user = gql.current_username
    plist = list_org_groups_gql(gql, org_id, current_user)

    # Apply filters
    plist = apply_filters(plist, args.get("filter"))

    # Sort by name
    plist = sorted(plist, key=lambda x: x.get("name", "").lower())

    if args.get("list"):
        # print group ids only
        for p in plist:
            print(p["id"])
        return

    def state_fmt(item: Dict[str, Any], _cl: Any) -> str:
        """Format state column: P O (public, open)."""
        pub = f"{cl.FAIL}P{cl.ENDFGC}" if item.get("public") else "-"
        opn = f"{cl.FAIL}O{cl.ENDFGC}" if item.get("is_open") else "-"
        return f"{pub} {opn}"

    def mail_fmt(item: Dict[str, Any], _cl: Any) -> str:
        """Format mail column: M S D (inbound, spf, dkim)."""
        inb = f"{cl.WARNING}M{cl.ENDFGC}" if item.get("allow_inbound_mail") else "-"
        spf = f"{cl.OKGREEN}S{cl.ENDFGC}" if item.get("mail_verify_spf") else "-"
        dkim = f"{cl.OKGREEN}D{cl.ENDFGC}" if item.get("mail_verify_dkim") else "-"
        return f"{inb} {spf} {dkim}"

    def role_fmt(role: str, _cl: Any) -> str:
        """Format role with color."""
        if role == "founder":
            return f"{cl.WARNING}{role}{cl.ENDFGC}"
        elif role == "admin":
            return f"{cl.FAIL}{role}{cl.ENDFGC}"
        elif role == "superuser":
            return f"{cl.OKCYAN}{role}{cl.ENDFGC}"
        return role

    # Helper to format number or dash
    def fmt_num(n: int) -> str:
        return str(n) if n else "-"

    # Calculate max widths for dynamic columns
    max_plots = max((len(fmt_num(p.get("plots", 0))) for p in plist), default=1)
    max_grids = max((len(fmt_num(p.get("grids", 0))) for p in plist), default=1)
    max_mails = max((len(fmt_num(p.get("mails", 0))) for p in plist), default=1)
    max_docs = max((len(fmt_num(p.get("docs", 0))) for p in plist), default=1)
    max_repos = max((len(fmt_num(p.get("repos", 0))) for p in plist), default=1)
    max_jobs = max((len(fmt_num(p.get("jobs", 0))) for p in plist), default=1)

    # Build dynamic header for content counts (P G M D R J)
    content_header = " ".join(
        [
            "P".rjust(max_plots),
            "G".rjust(max_grids),
            "M".rjust(max_mails),
            "D".rjust(max_docs),
            "R".rjust(max_repos),
            "J".rjust(max_jobs),
        ]
    )

    ppo: List[Dict[str, Any]] = [
        {
            "key": "id",
            "header": "Group ID",
            "type": "text",
            "clr": cl.OKCYAN,
            "overflow": "keep",
        },
        {
            "key": "name",
            "header": "Name",
            "type": "text",
            "overflow": "shrink",
        },
        {
            "key": "role",
            "header": "Role",
            "type": "text",
            "fmt": role_fmt,
            "overflow": "keep",
        },
        {
            "key": "members_count",
            "header": "Mem",
            "type": "text",
            "overflow": "keep",
            "align": "right",
        },
        {
            "key": "_state",
            "header": "State",
            "type": "text",
            "overflow": "keep",
        },
        {
            "key": "_mail",
            "header": "Mail",
            "type": "text",
            "overflow": "keep",
        },
        {
            "key": "_content",
            "header": content_header,
            "type": "text",
            "overflow": "keep",
        },
        {
            "key": "_joined",
            "header": "Created",
            "type": "text",
            "overflow": "keep",
        },
    ]

    # Pre-process columns
    for p in plist:
        # State column
        p["_state"] = state_fmt(p, cl)

        # Mail column
        p["_mail"] = mail_fmt(p, cl)

        # Created column (relative time)
        p["_joined"] = _format_relative_time(p.get("created", ""))

        # Content counts: P G M D R J
        plots_str = fmt_num(p.get("plots", 0))
        grids_str = fmt_num(p.get("grids", 0))
        mails_str = fmt_num(p.get("mails", 0))
        docs_str = fmt_num(p.get("docs", 0))
        repos_str = fmt_num(p.get("repos", 0))
        jobs_str = fmt_num(p.get("jobs", 0))
        p["_content"] = (
            f"{plots_str:>{max_plots}} {grids_str:>{max_grids}} {mails_str:>{max_mails}} "
            f"{docs_str:>{max_docs}} {repos_str:>{max_repos}} {jobs_str:>{max_jobs}}"
        )

        # Convert counts to strings
        p["members_count"] = str(p.get("members_count", 0))

    striped: bool = config.get("cli_striped", False)
    ppl = pretty_format(plist, ppo, striped=striped)

    print(ppl)


def list_org_group_vis(args: CliArgs, vis_type: str) -> None:
    """List visualizations shared with a specific org group."""
    colors()

    config_status, config = get_current_config(**config_from_args(args))

    org_id = args.get("org", "")
    group_id = args.get("group", "")
    if not org_id:
        print("Error: No org specified")
        return
    if not group_id:
        print("Error: No group specified")
        return

    # Map vis_type to GraphQL field name (plural)
    vis_type_map = {
        "Plot": "plots",
        "Grid": "grids",
        "Mail": "mails",
        "Doc": "docs",
        "Repo": "repos",
        "Job": "jobs",
        "Space": "spaces",
        "Computer": "computers",
        "Image": "images",
    }
    gql_vis_type = vis_type_map.get(vis_type, vis_type.lower() + "s")

    # Use GraphQL for listing
    gql = NovemGQL.from_args(args)
    plist = list_org_group_vis_gql(gql, org_id, group_id, gql_vis_type)

    # Apply filters
    plist = apply_filters(plist, args.get("filter"))

    # Sort by: 1) favs first, 2) likes second, 3) rest last - each group sorted by updated (newest first)
    def parse_date(date_str: str) -> datetime.datetime:
        dt = parse_api_datetime(date_str)
        return dt if dt else datetime.datetime.min.replace(tzinfo=timezone.utc)

    def sort_tier(markers: str) -> int:
        """Return sort tier: 0=fav, 1=like only, 2=rest."""
        if "*" in markers:
            return 0
        if "+" in markers:
            return 1
        return 2

    plist = sorted(plist, key=lambda x: (sort_tier(x.get("fav", "")), -parse_date(x.get("updated", "")).timestamp()))

    if args.get("list"):
        # print to terminal (username/id format for easy use)
        for p in plist:
            print(f"{p['username']}/{p['id']}")
        return

    def share_fmt(share: str, _cl: Any) -> str:
        sl = [x[0] for x in share]
        pub = f"{cl.FAIL}P{cl.ENDFGC}" if "p" in sl else "-"  # public
        chat = f"{cl.WARNING}C{cl.ENDFGC}" if "c" in sl else "-"  # chat claim
        ug = f"{cl.OKGREEN}@{cl.ENDFGC}" if "@" in sl else "-"  # user group
        og = f"{cl.OKGREEN}+{cl.ENDFGC}" if "+" in sl else "-"  # org group
        return f"{pub} {chat} {ug} {og}"

    def summary_fmt(summary: Optional[str], _cl: Any) -> str:
        if not summary:
            return ""
        return summary.replace("\n", "")

    has_favs = any("*" in p.get("fav", "") for p in plist)
    has_likes = any("+" in p.get("fav", "") for p in plist)

    def fav_fmt(markers: str, _cl: Any) -> str:
        parts = ""
        if has_favs:
            parts += f"{cl.WARNING}*{cl.ENDFGC}" if "*" in markers else " "
        if has_likes:
            parts += f"{cl.OKBLUE}+{cl.ENDFGC}" if "+" in markers else " "
        return f" {parts} " if parts else ""

    fav_header_width = (1 if has_favs else 0) + (1 if has_likes else 0)
    fav_header = (" " * (fav_header_width + 2)) if fav_header_width > 0 else ""

    ppo: List[Dict[str, Any]] = [
        *(
            [
                {
                    "key": "fav",
                    "header": fav_header,
                    "type": "text",
                    "fmt": fav_fmt,
                    "overflow": "keep",
                    "no_border": True,
                    "no_padding": True,
                },
            ]
            if has_favs or has_likes
            else []
        ),
        {
            "key": "username",
            "header": "Username",
            "type": "text",
            "clr": cl.OKCYAN,
            "overflow": "keep",
        },
        {
            "key": "id",
            "header": f"{vis_type} ID",
            "type": "text",
            "clr": cl.OKCYAN,
            "overflow": "keep",
        },
        {
            "key": "type",
            "header": "Type",
            "type": "text",
            "clr": cl.OKCYAN,
            "overflow": "keep",
        },
        {
            "key": "shared",
            "header": "Shared",
            "type": "text",
            "fmt": share_fmt,
            "overflow": "keep",
            "protect": True,
        },
        {
            "key": "name",
            "header": "Name",
            "type": "text",
            "overflow": "shrink",
            "drop": 2,
        },
        {
            "key": "updated",
            "header": "Updated",
            "type": "date",
            "overflow": "keep",
        },
        {
            "key": "uri",
            "header": "Url",
            "type": "url",
            "overflow": "keep",
        },
        {
            "key": "summary",
            "header": "Summary",
            "fmt": summary_fmt,
            "type": "text",
            "overflow": "truncate",
        },
    ]

    # Add Last Run column for jobs only (after Type column)
    if vis_type == "Job":
        # Find Type column index and insert after it
        type_idx = next((i for i, col in enumerate(ppo) if col.get("key") == "type"), -1)
        ppo.insert(
            type_idx + 1,
            {
                "key": "_last_run",
                "header": "Last Run",
                "type": "text",
                "overflow": "keep",
            },
        )

    for p in plist:
        # Format last_run for jobs
        if vis_type == "Job":
            p["_last_run"] = _format_time_ago(p.get("last_run_time", ""))

        if p.get("updated"):
            dt = parse_api_datetime(p["updated"])
            if dt:
                p["updated"] = format_datetime_local(dt)

    striped: bool = config.get("cli_striped", False)
    ppl = pretty_format(plist, ppo, striped=striped)

    print(ppl)


def list_org_group_users(args: CliArgs) -> None:
    """List members of a specific org group with roles and content shared with that group."""
    # Called from: novem -O <org> -G <group> -u
    colors()

    config_status, config = get_current_config(**config_from_args(args))

    org_id = args.get("org", "")
    group_id = args.get("group", "")
    if not org_id:
        print("Error: No org specified")
        return
    if not group_id:
        print("Error: No group specified")
        return

    # Use GraphQL for listing
    gql = NovemGQL.from_args(args)
    current_user = gql.current_username
    plist = list_org_group_members_gql(gql, org_id, group_id, current_user)

    # Apply filters
    plist = apply_filters(plist, args.get("filter"))

    # Role priority map for sorting
    role_order = {"founder": 0, "admin": 1, "superuser": 2, "member": 3}

    # Sort by: me first > role priority > connected > alphabetically
    def user_sort_key(u: Dict[str, Any]) -> Tuple[bool, int, bool, str]:
        is_me = u.get("is_me", False)
        return (
            not is_me,  # Current user first
            role_order.get(u.get("role", "member"), 3),  # Role priority
            not u.get("connected", False),  # Connected users next
            u.get("username", "").lower(),  # Alphabetically by username
        )

    plist = sorted(plist, key=user_sort_key)

    if args.get("list"):
        # print usernames only
        for p in plist:
            print(p["username"])
        return

    # Helper to format number or dash
    def fmt_num(n: int) -> str:
        return str(n) if n else "-"

    # Calculate max widths for dynamic columns
    max_plots = max((len(fmt_num(p.get("plots", 0))) for p in plist), default=1)
    max_grids = max((len(fmt_num(p.get("grids", 0))) for p in plist), default=1)
    max_mails = max((len(fmt_num(p.get("mails", 0))) for p in plist), default=1)
    max_docs = max((len(fmt_num(p.get("docs", 0))) for p in plist), default=1)
    max_repos = max((len(fmt_num(p.get("repos", 0))) for p in plist), default=1)
    max_jobs = max((len(fmt_num(p.get("jobs", 0))) for p in plist), default=1)

    # Build dynamic header for content counts (P G M D R J)
    content_header = " ".join(
        [
            "P".rjust(max_plots),
            "G".rjust(max_grids),
            "M".rjust(max_mails),
            "D".rjust(max_docs),
            "R".rjust(max_repos),
            "J".rjust(max_jobs),
        ]
    )

    def role_fmt(role: str, _cl: Any) -> str:
        """Format role with color."""
        if role == "founder":
            return f"{cl.WARNING}{role}{cl.ENDFGC}"
        elif role == "admin":
            return f"{cl.FAIL}{role}{cl.ENDFGC}"
        elif role == "superuser":
            return f"{cl.OKCYAN}{role}{cl.ENDFGC}"
        return role

    ppo: List[Dict[str, Any]] = [
        {
            "key": "_verified",
            "header": "   ",
            "type": "text",
            "overflow": "keep",
            "no_border": True,
            "no_padding": True,
        },
        {
            "key": "username",
            "header": "Username",
            "type": "text",
            "clr": cl.OKCYAN,
            "overflow": "keep",
        },
        {
            "key": "name",
            "header": "Name",
            "type": "text",
            "overflow": "shrink",
        },
        {
            "key": "role",
            "header": "Role",
            "type": "text",
            "fmt": role_fmt,
            "overflow": "keep",
        },
        {
            "key": "_public",
            "header": "P",
            "type": "text",
            "overflow": "keep",
        },
        {
            "key": "_conn",
            "header": "Relation",
            "type": "text",
            "overflow": "keep",
        },
        {
            "key": "_content",
            "header": content_header,
            "type": "text",
            "overflow": "keep",
        },
    ]

    # Pre-process formatted columns
    for p in plist:
        # Marker: > for current user, * for verified/novem/org users
        user_type = p.get("type", "").upper()
        is_me = p.get("is_me", False)

        if is_me:
            # Current user always shows > with color based on type
            if user_type in ("NOVEM", "SYSTEM"):
                p["_verified"] = f" {cl.WARNING}>{cl.ENDFGC} "
            elif user_type == "VERIFIED":
                p["_verified"] = f" {cl.OKBLUE}>{cl.ENDFGC} "
            elif user_type == "ORG":
                p["_verified"] = f" {cl.OKGREEN}>{cl.ENDFGC} "
            else:
                p["_verified"] = " > "
        else:
            # Other users show symbol based on type: ◆ for novem, * for verified, + for org
            if user_type in ("NOVEM", "SYSTEM"):
                p["_verified"] = f" {cl.WARNING}◆{cl.ENDFGC} "
            elif user_type == "VERIFIED":
                p["_verified"] = f" {cl.OKBLUE}*{cl.ENDFGC} "
            elif user_type == "ORG":
                p["_verified"] = f" {cl.OKGREEN}+{cl.ENDFGC} "
            else:
                p["_verified"] = "   "

        # Public profile indicator
        p["_public"] = f"{cl.FAIL}P{cl.ENDFGC}" if p.get("public") else "-"

        # Connection status: C F F I (connected, follower, following, ignoring)
        connected = f"{cl.OKGREEN}C{cl.ENDFGC}" if p.get("connected") else "-"
        follower = f"{cl.OKBLUE}F{cl.ENDFGC}" if p.get("follower") else "-"
        following = f"{cl.OKCYAN}F{cl.ENDFGC}" if p.get("following") else "-"
        ignoring = f"{cl.FAIL}I{cl.ENDFGC}" if p.get("ignoring") else "-"
        p["_conn"] = f"{connected} {follower} {following} {ignoring} "

        # Content counts: P G M D R J
        plots_str = fmt_num(p.get("plots", 0))
        grids_str = fmt_num(p.get("grids", 0))
        mails_str = fmt_num(p.get("mails", 0))
        docs_str = fmt_num(p.get("docs", 0))
        repos_str = fmt_num(p.get("repos", 0))
        jobs_str = fmt_num(p.get("jobs", 0))
        p["_content"] = (
            f"{plots_str:>{max_plots}} {grids_str:>{max_grids}} {mails_str:>{max_mails}} "
            f"{docs_str:>{max_docs}} {repos_str:>{max_repos}} {jobs_str:>{max_jobs}}"
        )

    striped: bool = config.get("cli_striped", False)
    ppl = pretty_format(plist, ppo, striped=striped)

    print(ppl)
