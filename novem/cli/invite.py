import json
from typing import Any, Dict, List

from novem.exceptions import Novem404

from ..api_ref import NovemAPI
from ..utils import cl, format_datetime_local, parse_api_datetime, pretty_format
from .args import CliArgs
from .config import config_from_args


def list_invites(args: CliArgs, novem: NovemAPI) -> None:
    """
    List pending invites.

    /admin/invites is the whole pending picture: inbound group and
    organisation invitations, inbound connection requests, your own pending
    personal invites and your active invite URLs. (/admin/social/invites is
    the history of personal invites that have already been accepted, so it
    has no place in a list of things awaiting an answer.)
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
        email = ""
        handle = ""
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
        elif nm[0] == "@" and "~" not in nm:
            gt = "connection"
            user = nm[1:]
        elif nm.startswith("I-"):
            # a personal invite you sent that is still pending; revoked with
            # DELETE rather than answered
            gt = "personal invite"
            email = nm[2:]
        else:
            # an active invite URL handle of yours
            gt = "invite url"
            handle = nm

        res["group"] = group
        if org:
            res["org_user"] = f"+{org}"
        elif user:
            res["org_user"] = f"@{user}"
        elif email:
            res["org_user"] = email
        else:
            res["org_user"] = handle

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
            "header": "Updated",
            "type": "date",
            "overflow": "keep",
        },
    ]

    for p in flist:
        dt = parse_api_datetime(p["created"])
        if dt:
            p["created"] = format_datetime_local(dt)

    ppl = pretty_format(flist, ppo)

    print(ppl)


def invite(args: CliArgs) -> None:
    novem = NovemAPI(**config_from_args(args), is_cli=True)

    # we are invoked so plot must exist
    invite_name = args["invite"]

    if invite_name is None:
        # we need to list plots
        list_invites(args, novem)
        return

    # one endpoint answers every pending invite, connection requests
    # included: a bare "@user" is recognised as a connection there
    path = f"/admin/invites/{invite_name}/accept"

    # check if
    if "accept" in args and args["accept"]:
        novem.write(path, "yes")

    elif "reject" in args and args["reject"]:
        novem.write(path, "no")
