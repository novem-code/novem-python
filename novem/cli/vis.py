import datetime
import email.utils as eut
import json
import re
from typing import Any, Dict, List

from novem.exceptions import Novem404

from ..api_ref import NovemAPI
from ..utils import cl, colors, get_current_config, pretty_format


def list_vis(args: Dict[str, Any], type: str) -> None:
    colors()
    # get current plot list

    pfx = type[0].lower()

    novem = NovemAPI(**args)
    # see if list flag is set

    (config_status, config) = get_current_config(**args)

    plist = []

    usr = config["username"]
    if "for_user" in args and args["for_user"]:
        usr = args["for_user"]

    path = f"u/{usr}/{pfx}/"

    if "group" in args:
        # we're listing vis for a group
        query = ""
        group = args["group"]
        org = ""
        fu = ""

        if "for_user" in args and args["for_user"]:
            fu = args["for_user"]

        if "org" in args:
            org = args["org"]

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

    if "filter" in args and args["filter"]:
        fv = args["filter"]
        if fv[0] != "^":
            fv = f".*{fv}"
        if fv[-1] != "$":
            fv = f"{fv}.*"

        flt = re.compile(fv, re.I)

        plist = [x for x in plist if (flt.match(x["id"]) or flt.match(x["name"]) or flt.match(x["type"]))]

    plist = sorted(plist, key=lambda x: x["id"])

    if args["list"]:

        # print to terminal
        for p in plist:
            print(p["id"])

        return

    ppo: List[Dict[str, Any]] = [
        {
            "key": "id",
            "header": f"{type} ID",
            "type": "text",
            "overflow": "keep",
        },
        # {
        #    "key": "id",
        #    "header": "ID",
        #    "type": "text",
        #    "overflow": "keep",
        # },
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
            "overflow": "truncate",
        },
        {
            "key": "uri",
            "header": "Url",
            "type": "url",
            "overflow": "keep",
        },
        {
            "key": "created",
            "header": "Created",
            "type": "date",
            "overflow": "keep",
        },
        {
            "key": "summary",
            "header": "Summary",
            "fmt": lambda x: x.replace("\n", ""),
            "type": "text",
            "overflow": "truncate",
        },
    ]

    for p in plist:
        nd = datetime.datetime(*eut.parsedate(p["created"])[:6])
        p["created"] = nd.strftime("%Y-%m-%d %H:%M")

    ppl = pretty_format(plist, ppo)

    print(ppl)

    return


def share_pretty_print(iplist: List[Dict[str, str]]) -> None:

    # modify our plist
    plist = []
    for p in iplist:
        if p["name"] == "public":
            p["summary"] = "Shared with the entire world"
            p["type"] = "special"
        if re.match("^@.+~.+$", p["name"]):
            p["summary"] = "Shared with all members of the given user group"
            p["type"] = "user group"
        if re.match("^\\+.+~.+$", p["name"]):
            p["summary"] = "Shared with all members of the given organisation group"
            p["type"] = "org group"

        plist.append(p)

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
            "fmt": lambda x: x.replace("\n", ""),
            "type": "text",
            "overflow": "truncate",
        },
    ]

    for p in plist:
        pds = eut.parsedate(p["created_on"])
        if pds:
            nd = datetime.datetime(*pds[:6])
            p["created_on"] = nd.strftime("%Y-%m-%d %H:%M")

    ppl = pretty_format(plist, ppo)
    print(ppl)


def list_vis_shares(vis_name: str, args: Dict[str, str], type: str) -> None:

    novem = NovemAPI(**args)
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
        share_pretty_print(plist)

    return
