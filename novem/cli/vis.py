import datetime
import email.utils as eut
import json
import re
from typing import Any, Dict, List, Optional

from novem.exceptions import Novem404

from ..api_ref import NovemAPI
from ..utils import cl, colors, get_current_config, pretty_format
from .filter import apply_filters
from .gql import NovemGQL, list_grids_gql, list_jobs_gql, list_mails_gql, list_plots_gql


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
            "overflow": "truncate",
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
