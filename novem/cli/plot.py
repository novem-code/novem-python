import datetime
import email.utils as eut
import json
import sys
from typing import Any, Dict, List

from .. import Plot
from ..api import Novem404, NovemAPI
from ..utils import (
    cl,
    colors,
    data_on_stdin,
    get_current_config,
    pretty_format,
)


def list_plots(args: Dict[str, str]) -> None:
    colors()
    # get current plot list

    novem = NovemAPI(**args)
    # see if list flag is set

    (config_status, config) = get_current_config(**args)

    plist = []
    if not args["list"]:

        try:
            plist = json.loads(novem.read("vis/plots/"))
        except Novem404:
            plist = []

        # print to terminal
        for p in plist:
            print(p["name"])

    else:
        try:
            plist = json.loads(novem.read(f'u/{config["username"]}/p/'))
        except Novem404:
            plist = []

        ppo: List[Dict[str, Any]] = [
            {
                "key": "name",
                "header": "Plot Name",
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
                "key": "display_name",
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
                "key": "caption",
                "header": "Caption",
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


def list_shares(plot_name: str, args: Dict[str, str]) -> None:

    novem = NovemAPI(**args)
    # see if list flag is set

    (config_status, config) = get_current_config(**args)

    plist = []
    if not args["list"]:

        try:
            plist = json.loads(novem.read(f"vis/plots/{plot_name}/shared"))
        except Novem404:
            plist = []

        # print to terminal
        for p in plist:
            print(p["name"])

    # TODO implement -l flag support
    return


def plot(args: Dict[str, str]) -> None:

    # we are invoked so plot must exist
    plot_name = args["plot"]

    if plot_name is None:
        # we need to list plots
        list_plots(args)
        return

    # if delete flag is set, we need to delete it
    if args["delete"] and not args["share"]:
        # creating a plot just to delete it seems wasteful
        # We'll just use the raw api
        novem = NovemAPI(**args)

        try:
            novem.delete(f"vis/plots/{plot_name}")
            return
        except Novem404:
            print(f"Plot {plot_name} did not exist")
            sys.exit(1)

    # we are going to modify one of our plots, listing and deletion has
    # already been handled so we can use the plot api without wasting
    # "resources'

    # this will create the plot if it does not exist
    p = Plot(plot_name)

    # TODO: check if we have a type swtich -t
    ptype = args["type"]
    # print(ptype)
    if ptype:
        p.type = ptype

    found_stdin = False
    stdin_has_data, stdin_data = data_on_stdin()

    # check if we have any explicit inputs [-w's]
    if args["input"] and len(args["input"]):
        # we have inputs
        for i in args["input"]:
            path = f"/{i[0]}"

            if len(i) == 1:
                if stdin_has_data and not found_stdin:
                    ctnt = stdin_data

                    p.api_write(path, ctnt)
                    found_stdin = True
                elif found_stdin:
                    print(
                        "stdin can only be sent to a single destination per"
                        " invocation"
                    )
                    sys.exit(1)
                else:
                    print(
                        f'No data found on stdin, "-w {path}" requires data'
                        f" to be supplied on stdin"
                    )
                    sys.exit(1)

            elif len(i) == 2 and i[1][0] == "@":
                try:
                    fn = i[1][1:]
                    with open(fn, "r") as f:
                        ctnt = f.read()
                        p.api_write(path, ctnt)
                except FileNotFoundError:
                    print(
                        f'The supplied input file "{fn}" does not exist.'
                        f" Please review your options"
                    )
                    sys.exit(1)

            else:
                ctnt = i[1]
                p.api_write(path, ctnt)

    # check if we have standard input and not already "used" it
    if not found_stdin and stdin_has_data:
        ctnt = stdin_data
        # got stdin data
        p.data = ctnt

    # check if we are changing any permissions
    share: str = args["share"]

    if share is not None and share != "":
        # add a share to the plot

        p.shared += share  # type: ignore

    if share is not None and share != "" and args["delete"]:
        # remove a share from the plot

        p.shared -= share  # type: ignore

    # check if we should print our shares, we will not provide other outputs
    if share is None:
        list_shares(plot_name, args)

        return

    # Output - we only allow a singular -o or -x and will return as soon as
    # we find one

    # -x takes presedence
    x = args["tc"]
    if x:
        # get file endpoint
        print(p.files.ansi)  # type: ignore

        # exit as we only support one output
        return

    # TODO: check if we are reading any valus from the plot [-o or -x]
    out = args["out"]
    if out:
        outp = p.api_read(f"/{out}")
        print(outp, end="")
