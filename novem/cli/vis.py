import datetime
import email.utils as eut
import json
import re
from typing import Any, Dict, List, Optional, Tuple

from novem.exceptions import Novem404

from ..api_ref import NovemAPI
from ..utils import cl, colors, get_current_config, pretty_format
from .filter import apply_filters
from .gql import (
    NovemGQL,
    list_grids_gql,
    list_jobs_gql,
    list_mails_gql,
    list_org_members_gql,
    list_orgs_gql,
    list_plots_gql,
    list_users_gql,
)


def list_vis(args: Dict[str, Any], type: str) -> None:
    colors()
    # get current plot list

    pfx = type[0].lower()

    if "profile" in args:
        args["config_profile"] = args["profile"]

    (config_status, config) = get_current_config(**args)

    plist: List[Dict[str, Any]] = []

    usr = config["username"]
    if "for_user" in args and args["for_user"]:
        usr = args["for_user"]

    # Use GraphQL for listing
    gql = NovemGQL(**args)

    if "group" in args and args["group"]:
        # Group listing not yet supported via GraphQL, fall back to REST
        novem = NovemAPI(**args, is_cli=True)
        group = args["group"]
        org = args.get("org", "")
        fu = args.get("for_user", "")

        if group[0] in ["@", "+"]:
            query = group
        elif fu and group:
            query = f"@{usr}~{group}"
        elif org and group:
            query = f"+{org}~{group}"
        else:
            query = ""

        if query:
            path = f"o/{query}/{pfx}/"
            try:
                plist = json.loads(novem.read(path))
            except Novem404:
                plist = []
    else:
        # Use GraphQL for user's own visualizations
        if pfx == "p":
            plist = list_plots_gql(gql, author=usr)
        elif pfx == "g":
            plist = list_grids_gql(gql, author=usr)
        elif pfx == "m":
            plist = list_mails_gql(gql, author=usr)

    # Apply filters (handles both legacy and new column-based filtering)
    plist = apply_filters(plist, args.get("filter"))

    # Sort by: 1) favs first, 2) likes second, 3) rest last - each group sorted by updated (newest first)
    # Parse date string for proper sorting (format: "Thu, 17 Mar 2022 12:19:02 UTC")
    def parse_date(date_str: str) -> datetime.datetime:
        parsed = eut.parsedate(date_str)
        if parsed:
            return datetime.datetime(*parsed[:6])
        return datetime.datetime.min

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

    def fav_fmt(markers: str, cl: cl) -> str:
        fav_str = f"{cl.WARNING}*{cl.ENDFGC}" if "*" in markers else " "
        like_str = f"{cl.OKBLUE}+{cl.ENDFGC}" if "+" in markers else " "
        return f" {fav_str}{like_str} "

    ppo: List[Dict[str, Any]] = [
        {
            "key": "fav",
            "header": "    ",
            "type": "text",
            "fmt": fav_fmt,
            "overflow": "keep",
            "no_border": True,
            "no_padding": True,
        },
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
        },
        {
            "key": "name",
            "header": "Name",
            "type": "text",
            "overflow": "shrink",
        },
        {
            "key": "uri",
            "header": "Url",
            "type": "url",
            "overflow": "keep",
        },
        {
            "key": "updated",
            "header": "Updated",
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
        nd = datetime.datetime(*eut.parsedate(p["updated"])[:6])
        p["updated"] = nd.strftime("%Y-%m-%d %H:%M")

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
        pds = eut.parsedate(p["created_on"])
        if pds:
            nd = datetime.datetime(*pds[:6])
            p["created_on"] = nd.strftime("%Y-%m-%d %H:%M")

    ppl = pretty_format(plist, ppo, striped=striped)
    print(ppl)


def list_vis_shares(vis_name: str, args: Dict[str, str], type: str) -> None:

    novem = NovemAPI(**args, is_cli=True)
    # see if list flag is set

    pth = type.lower()

    (config_status, config) = get_current_config(**args)

    plist = []

    try:
        plist = json.loads(novem.read(f"vis/{pth}s/{vis_name}/shared"))
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


def list_job_shares(job_name: str, args: Dict[str, str]) -> None:

    novem = NovemAPI(**args, is_cli=True)

    (config_status, config) = get_current_config(**args)

    plist = []

    try:
        plist = json.loads(novem.read(f"jobs/{job_name}/shared"))
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
        pds = eut.parsedate(p.get("created_on", ""))
        if pds:
            nd = datetime.datetime(*pds[:6])
            p["created_on"] = nd.strftime("%Y-%m-%d %H:%M")

    ppl = pretty_format(plist, ppo, striped=striped)
    print(ppl)


def list_vis_tags(vis_name: str, args: Dict[str, str], type: str) -> None:
    """List tags for a visualization."""

    novem = NovemAPI(**args, is_cli=True)

    pth = type.lower()

    (config_status, config) = get_current_config(**args)

    plist = []

    try:
        plist = json.loads(novem.read(f"vis/{pth}s/{vis_name}/tags"))
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


def list_job_tags(job_name: str, args: Dict[str, str]) -> None:
    """List tags for a job."""

    novem = NovemAPI(**args, is_cli=True)

    (config_status, config) = get_current_config(**args)

    plist = []

    try:
        plist = json.loads(novem.read(f"jobs/{job_name}/tags"))
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


def list_users(args: Dict[str, Any]) -> None:
    """List connected users with custom formatting."""
    colors()

    if "profile" in args:
        args["config_profile"] = args["profile"]

    (config_status, config) = get_current_config(**args)

    # Use GraphQL for listing
    gql = NovemGQL(**args)
    plist = list_users_gql(gql)

    # Apply filters
    plist = apply_filters(plist, args.get("filter"))

    # Get current user's username
    current_user = config.get("username", "")

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


def list_jobs(args: Dict[str, Any]) -> None:
    """List jobs with custom formatting."""
    colors()

    if "profile" in args:
        args["config_profile"] = args["profile"]

    (config_status, config) = get_current_config(**args)

    usr = config["username"]
    if "for_user" in args and args["for_user"]:
        usr = args["for_user"]

    # Use GraphQL for listing
    gql = NovemGQL(**args)
    plist = list_jobs_gql(gql, author=usr)

    # Apply filters
    plist = apply_filters(plist, args.get("filter"))

    # Sort by: 1) favs first, 2) likes second, 3) rest last - each group sorted by updated (newest first)
    def parse_date(date_str: str) -> datetime.datetime:
        parsed = eut.parsedate(date_str)
        if parsed:
            return datetime.datetime(*parsed[:6])
        return datetime.datetime.min

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

    def schedule_fmt(schedule: Optional[str], cl: cl) -> str:
        """Format schedule column as cron or dashes, right-aligned fields."""
        if not schedule:
            return " -  -  -  -  -"
        # Pad to consistent width (5 cron fields), each field 2 chars right-aligned
        parts = schedule.split()
        if len(parts) == 5:
            return f"{parts[0]:>2} {parts[1]:>2} {parts[2]:>2} {parts[3]:>2} {parts[4]:>2}"
        return schedule

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

    def fav_fmt(markers: str, cl: cl) -> str:
        fav_str = f"{cl.WARNING}*{cl.ENDFGC}" if "*" in markers else " "
        like_str = f"{cl.OKBLUE}+{cl.ENDFGC}" if "+" in markers else " "
        return f" {fav_str}{like_str} "

    ppo: List[Dict[str, Any]] = [
        {
            "key": "fav",
            "header": "    ",
            "type": "text",
            "fmt": fav_fmt,
            "overflow": "keep",
            "no_border": True,
            "no_padding": True,
        },
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
            "key": "name",
            "header": "Name",
            "type": "text",
            "overflow": "shrink",
        },
        {
            "key": "last_run_status",
            "header": "Status",
            "type": "text",
            "fmt": status_fmt,
            "overflow": "keep",
        },
        {
            "key": "shared",
            "header": "Shared",
            "type": "text",
            "fmt": share_fmt,
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
            "key": "schedule",
            "header": "Schedule",
            "type": "text",
            "fmt": schedule_fmt,
            "overflow": "keep",
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
            "key": "summary",
            "header": "Summary",
            "type": "text",
            "overflow": "truncate",
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


def _format_relative_time(date_str: str) -> str:
    """Format a date string as relative time (e.g., '2 weeks ago')."""
    if not date_str:
        return ""
    try:
        parsed = eut.parsedate(date_str)
        if not parsed:
            return date_str
        dt = datetime.datetime(*parsed[:6])
        now = datetime.datetime.now()
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


def list_orgs(args: Dict[str, Any]) -> None:
    """List organizations with custom formatting."""
    colors()

    if "profile" in args:
        args["config_profile"] = args["profile"]

    (config_status, config) = get_current_config(**args)

    # Use GraphQL for listing
    gql = NovemGQL(**args)
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


def list_org_users(args: Dict[str, Any]) -> None:
    """List org members with roles and content shared with org groups."""
    colors()

    if "profile" in args:
        args["config_profile"] = args["profile"]

    (config_status, config) = get_current_config(**args)

    org_id = args.get("org", "")
    if not org_id:
        print("Error: No org specified")
        return

    current_user = config.get("username", "")

    # Use GraphQL for listing
    gql = NovemGQL(**args)
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
