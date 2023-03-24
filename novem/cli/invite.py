import datetime
import email.utils as eut
import json
from typing import Any, Dict, List

from novem.exceptions import Novem404

from ..api_ref import NovemAPI
from ..utils import cl, pretty_format


def list_invites(args: Dict[str, Any], novem: NovemAPI) -> None:
    """
    List pending invites
    """

    # see if list flag is set

    ilist = []

    try:
        ilist = json.loads(novem.read("/admin/invites/"))
    except Novem404:
        ilist = []

    ilist = sorted(ilist, key=lambda x: x["name"])

    if args["list"]:

        # print to terminal
        for p in ilist:
            print(p["name"])

        return

    flist = []

    for i in ilist:
        res = {}
        nm = i["name"]
        # let's populate our final list with info
        res["name"] = nm
        res["id"] = nm

        gt = "unkown"
        user = ""
        group = ""
        org = ""
        if nm[0] == "+" and "~" in nm:
            gt = "organisation group"
            spl = nm[1:].split("~")
            org = spl[0]
            group = spl[1]
        elif nm[0] == "@" and "~" in nm:
            gt = "user group"
            spl = nm[1:].split("~")
            user = spl[0]
            group = spl[1]
        elif nm[0] == "+" and "~" not in nm:
            gt = "organisation"
            org = nm[1:]
        else:
            gt = "unkown"

        res["group"] = group
        if org:
            res["org_user"] = f"+{org}"
        else:
            res["org_user"] = f"@{user}"

        res["type"] = gt
        res["created"] = i["created_on"]

        flist.append(res)

    ppo: List[Dict[str, Any]] = [
        {
            "key": "id",
            "header": "Invitation ID",
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
            "key": "group",
            "header": "Group",
            "type": "text",
            "overflow": "truncate",
        },
        {
            "key": "org_user",
            "header": "Org / User",
            "type": "text",
            "overflow": "truncate",
        },
        {
            "key": "created",
            "header": "Created",
            "type": "date",
            "overflow": "keep",
        },
    ]

    for p in flist:
        nd = datetime.datetime(*eut.parsedate(p["created"])[:6])
        p["created"] = nd.strftime("%Y-%m-%d %H:%M")

    ppl = pretty_format(flist, ppo)

    print(ppl)


def invite(args: Dict[str, Any]) -> None:

    novem = NovemAPI(**args)

    # we are invoked so plot must exist
    invite_name = args["invite"]

    if invite_name is None:
        # we need to list plots
        list_invites(args, novem)
        return

    # check if
    if "accept" in args and args["accept"]:
        novem.write(f"/admin/invites/{invite_name}/accept", "yes")

    elif "reject" in args and args["reject"]:
        novem.write(f"/admin/invites/{invite_name}/accept", "no")
