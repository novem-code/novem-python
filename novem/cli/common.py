import os
import sys
from typing import Any, Dict, Literal, Optional

from novem import Mail, Plot
from novem.api_ref import Novem404, NovemAPI
from novem.cli.editor import edit
from novem.cli.setup import Share
from novem.cli.vis import list_vis, list_vis_shares
from novem.utils import data_on_stdin
from novem.vis import NovemVisAPI


class VisBase:
    def __init__(self, type: Literal["mail", "plot"]) -> None:
        self.type = type

    @property
    def title(self) -> str:
        return self.type.capitalize()

    @property
    def fragment(self) -> str:
        return f"{self.type}s"

    def set_data(self, nva: NovemVisAPI, data: str) -> None:
        if self.type == "mail":
            nva.content = data
        else:
            nva.data = data

    def mk(self, name: str, user: Optional[str], ignore_ssl: bool, create: bool, args: Dict[str, Any]) -> NovemVisAPI:
        if self.type == "mail":
            return Mail(
                name,
                user=user,
                ignore_ssl=ignore_ssl,
                create=create,
                config_path=args["config_path"],
                to=args["to"],
                cc=args["cc"],
                bcc=args["bcc"],
                subject=args["subject"],
                qpr=args["qpr"],
                debug=args["debug"],
                profile=args["profile"],
            )

        elif self.type == "plot":
            return Plot(
                name,
                user=user,
                ignore_ssl=ignore_ssl,
                create=create,
                config_path=args["config_path"],
                qpr=args["qpr"],
                debug=args["debug"],
                profile=args["profile"],
            )
        else:
            assert False, "Invalid type"

    def __call__(self, args: Dict[str, Any]) -> None:
        # we are invoked so vis must exist
        name = args[self.type]

        if name is None:
            # we need to list plots
            list_vis(args, self.title)
            return

        # if delete flag is set, we need to delete it
        if args["delete"]:
            # creating a plot just to delete it seems wasteful
            # We'll just use the raw api
            novem = NovemAPI(**args)

            try:
                novem.delete(f"vis/{self.fragment}/{name}")
                return
            except Novem404:
                print(f"{self.title} {name} did not exist")
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

        vis = self.mk(name=name, user=usr, ignore_ssl=ignore_ssl, create=create, args=args)

        # this is a data dump instruction, we'll ignore everything else
        if "dump" in args and args["dump"]:
            path = args["dump"]

            print(f'Dumping api tree structure to "{path}"')
            vis.api_dump(outpath=path)
            return

        # if we detect a tree query then we'll discard all other IO
        if "tree" in args and args["tree"] != -1:
            path = args["tree"]
            if not path:
                path = "/"

            ts = vis.api_tree(colors=True, relpath=path)
            print(ts)
            return

        # if we have the -e or edit flag then this takes presedence over all other
        # inputs
        if "edit" in args and args["edit"]:
            path = args["edit"]

            # fetch our target and warn if it doesn't exist
            ctnt = vis.api_read(f"/{path}")

            # get new content
            nctnt = edit(contents=ctnt, use_tty=True)

            if ctnt != nctnt:
                # update content
                vis.api_write(f"/{path}", nctnt)

        else:

            ptype = args["type"]
            # print(ptype)
            if ptype:
                vis.type = ptype

            found_stdin = False
            stdin_data = data_on_stdin()
            stdin_has_data = bool(stdin_data)

            # check if we have any explicit inputs [-w's]
            if args["input"] and len(args["input"]):
                # we have inputs
                for i in args["input"]:
                    path = f"/{i[0]}"

                    if len(i) == 1:
                        if stdin_has_data and not found_stdin:
                            assert stdin_data
                            ctnt = stdin_data

                            vis.api_write(path, ctnt)
                            found_stdin = True
                        elif found_stdin:
                            print("stdin can only be sent to a single destination per invocation")
                            sys.exit(1)
                        else:
                            print(f'No data found on stdin, "-w {path}" requires data to be supplied on stdin')
                            sys.exit(1)

                    elif len(i) == 2 and i[1][0] == "@":
                        fn = os.path.expanduser(i[1][1:])
                        try:
                            with open(fn, "r") as f:
                                ctnt = f.read()
                                vis.api_write(path, ctnt)
                        except FileNotFoundError:
                            print(f'The supplied input file "{fn}" does not exist. Please review your options')
                            sys.exit(1)

                    else:
                        ctnt = i[1]
                        vis.api_write(path, ctnt)

            # check if we have standard input and not already "used" it
            if not found_stdin and stdin_has_data:
                assert stdin_data
                ctnt = stdin_data
                # got stdin data
                self.set_data(vis, ctnt)

        # check if we are changing any permissions
        share_op, share_target = args["share"]
        if share_op is Share.CREATE:
            # add a share to the vis
            vis.shared += share_target  # type: ignore

        if share_op is Share.DELETE:
            # remove a share from the vis
            vis.shared -= share_target  # type: ignore

        if share_op is Share.LIST:
            # check if we should print our shares, we will not provide other outputs
            list_vis_shares(name, args, self.title)
            return

        # Output - we only allow a singular -o or -x and will return as soon as
        # we find one

        # -x takes presedence
        x = args["tc"]
        if x:
            # get file endpoint
            if os.name == "nt":
                from colorama import just_fix_windows_console  # type: ignore

                just_fix_windows_console()
            print(vis.files.ansi, end="")  # type: ignore

            # exit as we only support one output
            return

        # TODO: check if we are reading any valus from the plot [-r or -x]
        out = args["out"]
        if out:
            outp = vis.api_read(f"/{out}")
            print(outp, end="")


def mail(args: Dict[str, Any]) -> None:
    mail = VisBase("mail")
    mail(args)


def plot(args: Dict[str, Any]) -> None:
    plot = VisBase("plot")
    plot(args)
