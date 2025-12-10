import datetime
import email.utils as eut
import json
import re
from typing import Any, Dict, List, Optional

from novem.exceptions import Novem404

from ..api_ref import NovemAPI
from ..utils import cl, colors, get_current_config, pretty_format
from .gql import NovemGQL, list_grids_gql, list_mails_gql, list_plots_gql


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

    if "filter" in args and args["filter"]:
        fv = args["filter"]
        if fv[0] != "^":
            fv = f".*{fv}"
        if fv[-1] != "$":
            fv = f"{fv}.*"

        flt = re.compile(fv, re.I)

        plist = [x for x in plist if (flt.match(x["id"]) or flt.match(x["name"]) or flt.match(x["type"]))]

    # Sort by favorites first (fav="*" before fav=""), then by updated date (newest first)
    # Parse date string for proper sorting (format: "Thu, 17 Mar 2022 12:19:02 UTC")
    def parse_date(date_str: str) -> datetime.datetime:
        parsed = eut.parsedate(date_str)
        if parsed:
            return datetime.datetime(*parsed[:6])
        return datetime.datetime.min

    plist = sorted(plist, key=lambda x: (x.get("fav", "") != "*", parse_date(x["updated"])), reverse=True)
    # Re-sort to get favs at top (stable sort preserves updated order within each group)
    plist = sorted(plist, key=lambda x: x.get("fav", "") != "*")

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

    def fav_fmt(fav: str, cl: cl) -> str:
        if fav == "*":
            return f" {cl.OKBLUE}*{cl.ENDFGC} "
        return "   "

    ppo: List[Dict[str, Any]] = [
        {
            "key": "fav",
            "header": "   ",
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
