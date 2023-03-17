import os
import sys
from typing import Any, Dict

from novem.exceptions import Novem404

from .. import Plot
from ..api_ref import NovemAPI
from ..utils import data_on_stdin
from .editor import edit
from .vis import list_vis, list_vis_shares


def plot(args: Dict[str, Any]) -> None:

    # we are invoked so plot must exist
    plot_name = args["plot"]

    if plot_name is None:
        # we need to list plots
        list_vis(args, "Plot")
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

    usr = None
    if "for_user" in args and args["for_user"]:
        usr = args["for_user"]

    # we are going to modify one of our plots, listing and deletion has
    # already been handled so we can use the plot api without wasting
    # "resources'

    # this will create the plot if it does not exist
    ignore_ssl = False
    if "ignore_ssl" in args:
        ignore_ssl = args["ignore_ssl"]

    create = args["create"]

    p = Plot(
        plot_name,
        user=usr,
        ignore_ssl=ignore_ssl,
        create=create,
        config_path=args["config_path"],
        qpr=args["qpr"],
        debug=args["debug"],
    )

    # this is a data dump instruction, we'll ignore everything else
    if "dump" in args and args["dump"]:
        path = args["dump"]

        print(f'Dumping api tree structure to "{path}"')
        p.api_dump(outpath=path)
        return

    # if we detect a tree query then we'll discard all other IO
    if "tree" in args and args["tree"] != -1:
        path = args["tree"]
        if not path:
            path = "/"

        ts = p.api_tree(colors=True, relpath=path)
        print(ts)
        return

    # if we have the -e or edit flag then this takes presedence over all other
    # inputs
    if "edit" in args and args["edit"]:
        path = args["edit"]

        # fetch our target and warn if it doens't exist
        ctnt = p.api_read(f"/{path}")

        # get new content
        nctnt = edit(contents=ctnt, use_tty=True)

        if ctnt != nctnt:
            # update content
            p.api_write(f"/{path}", nctnt)

    else:

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
                            "stdin can only be sent to a single destination"
                            " per invocation"
                        )
                        sys.exit(1)
                    else:
                        print(
                            f'No data found on stdin, "-w {path}" requires'
                            f" data to be supplied on stdin"
                        )
                        sys.exit(1)

                elif len(i) == 2 and i[1][0] == "@":
                    try:
                        fn = os.path.expanduser(i[1][1:])
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

    if share is not None and share != "" and args["create"]:
        # add a share to the plot

        p.shared += share  # type: ignore

    if share is not None and share != "" and args["delete"]:
        # remove a share from the plot

        p.shared -= share  # type: ignore

    # check if we should print our shares, we will not provide other outputs
    if share is None:
        list_vis_shares(plot_name, args, "Plot")

        return

    # Output - we only allow a singular -o or -x and will return as soon as
    # we find one

    # -x takes presedence
    x = args["tc"]
    if x:
        # get file endpoint
        if os.name == "nt":
            from colorama import just_fix_windows_console

            just_fix_windows_console()
        print(p.files.ansi, end="")  # type: ignore

        # exit as we only support one output
        return

    # TODO: check if we are reading any valus from the plot [-r or -x]
    out = args["out"]
    if out:
        outp = p.api_read(f"/{out}")
        print(outp, end="")
