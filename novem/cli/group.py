import datetime
import email.utils as eut
import json
import re
from typing import Any, Dict, List

from novem.exceptions import Novem404

from ..api_ref import NovemAPI
from ..utils import cl, pretty_format


def list_orgs(args: Dict[str, Any], novem: NovemAPI, path: str) -> None:
    ilist = []

    try:
        ilist = json.loads(novem.read(path))
    except Novem404:
        ilist = []

    ilist = sorted(ilist, key=lambda x: x["name"])

    if "filter" in args and args["filter"]:
        fv = args["filter"]
        if fv[0] != "^":
            fv = f".*{fv}"
        if fv[-1] != "$":
            fv = f"{fv}.*"

        flt = re.compile(fv, re.I)

        ilist = [x for x in ilist if (flt.match(x["name"]))]

    flist = []

    if args["list"]:

        # print to terminal
        for p in ilist:
            print(p["name"])

        return

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
        gt = "organisation"

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
            "header": "Group ID",
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
        # {
        #    "key": "group",
        #    "header": "Group",
        #    "type": "text",
        #    "overflow": "truncate",
        # },
        # {
        #    "key": "org_user",
        #    "header": "Org / User",
        #    "type": "text",
        #    "overflow": "truncate",
        # },
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


def list_groups(args: Dict[str, Any], novem: NovemAPI, path: str) -> None:
    """
    List pending invites
    """

    # see if list flag is set

    ilist = []

    try:
        ilist = json.loads(novem.read(path))
    except Novem404:
        ilist = []

    ilist = sorted(ilist, key=lambda x: x["name"])

    if "filter" in args and args["filter"]:
        fv = args["filter"]
        if fv[0] != "^":
            fv = f".*{fv}"
        if fv[-1] != "$":
            fv = f"{fv}.*"

        flt = re.compile(fv, re.I)

        ilist = [x for x in ilist if (flt.match(x["name"]))]

    if args["list"]:

        # print to terminal
        for p in ilist:
            print(p["name"])

        return

    flist = []

    orgo = ""
    if "org" in args and args["org"]:
        orgo = args["org"]

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

        if orgo:
            res["type"] = "organisation group"
            res["org_user"] = f"+{orgo}"
            res["group"] = nm
            res["id"] = f"+{orgo}~{nm}"

        flist.append(res)

    ppo: List[Dict[str, Any]] = [
        {
            "key": "id",
            "header": "Group ID",
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


# TODO: shift this logic to a group class
# and make it available from python as well
def group(args: Dict[str, Any]) -> None:
    novem = NovemAPI(**args)

    has_org = "org" in args and args["org"] != ""
    has_group = "group" in args and args["group"] != ""
    has_user = "for_user" in args and args["for_user"] != ""

    # we are invoked so plot must exist
    group_name = args["group"] if "group" in args else None
    org_name = args["org"] if "org" in args else None
    # user_name = args["for_user"] if "for_user" in args else None

    # print(f"{has_group} - {has_org} - {has_user}")
    # print(f"{group_name} - {org_name} - {user_name}")

    # check if we should create a group
    if has_group and group_name and args["create"] and not has_org:
        # create usergroup
        path = f"/admin/groups/{group_name}/"
        novem.create(path)
        return

    # check if we should create a group
    if has_group and group_name and args["create"] and has_org and org_name:
        # create usergroup
        path = f"/admin/orgs/{org_name}/groups/{group_name}/"
        novem.create(path)
        return

    # check if we should create a group
    if has_group and group_name and args["delete"] and not has_org:
        # create usergroup
        path = f"/admin/groups/{group_name}/"
        novem.delete(path)
        return

    # check if we should create a group
    if has_group and group_name and args["delete"] and has_org and org_name:
        # create usergroup
        path = f"/admin/orgs/{org_name}/groups/{group_name}/"
        novem.delete(path)
        return

    # check if we should invite a user
    if "invite_user" in args and args["invite_user"] and has_group and has_org:
        iu = args["invite_user"]
        path = f"/admin/orgs/{org_name}/groups/{group_name}/roles/members/{iu}"
        novem.create(path)
        return

    if "invite_user" in args and args["invite_user"] and has_group and group_name and not has_org:
        iu = args["invite_user"]
        path = f"/admin/groups/{group_name}/roles/members/{iu}"
        novem.create(path)
        return

    if has_group and has_org and not has_user and org_name and not group_name:
        list_groups(args, novem, f'/orgs/{args["org"]}/groups/')
        return

    if not has_group and not has_user and has_org and not org_name:
        list_orgs(args, novem, "/orgs/")
        return

    if has_group and not has_user and not has_org and not group_name:
        list_groups(args, novem, "/groups/")
        return

    # print("no condition")
