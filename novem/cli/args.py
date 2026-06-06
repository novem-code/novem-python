"""Typed view of the parsed CLI argument namespace.

``setup()`` returns ``vars(parser.parse_args(...))`` — a plain dict that is
threaded through every command handler. ``CliArgs`` gives that dict a static
type so key typos and value-type mistakes are caught by mypy, without any
runtime change (it is still an ordinary dict). A few flags use hyphenated
keys (``api-url``, ``token-name``), so the functional TypedDict form is
required.
"""

from typing import Any, List, Optional, Tuple, TypedDict, Union

# Share/Tag are (action_enum, value) tuples, where value may be a string or a
# list of strings; typed loosely here to avoid importing from .setup (which
# imports this module). setup() always replaces the raw value with a tuple
# before the dict reaches a handler, and every consumer unpacks unconditionally.
_ShareTag = Tuple[Any, Any]

CliArgs = TypedDict(
    "CliArgs",
    {
        # primary resource selectors (empty string = "not given")
        "plot": str,
        "mail": str,
        "grid": str,
        "doc": str,
        "job": str,
        "invite": str,
        # group subcommand (only present for `novem group ...`)
        "org": Optional[str],
        "group": Optional[str],
        # connection
        "token": Optional[str],
        "token-name": Optional[str],
        "api-url": Optional[str],
        "config_path": Optional[str],
        "profile": Optional[str],
        "ignore_ssl": bool,
        # behaviour / output
        "create": bool,
        "delete": bool,
        "debug": bool,
        "force": bool,
        "list": bool,
        "info": bool,
        "send": bool,
        "color": bool,
        "comments": bool,
        "json_output": bool,
        "dry_run": bool,
        "fs": bool,
        "tc": bool,
        "test": bool,
        "version": bool,
        "refresh": bool,
        "accept": bool,
        "reject": bool,
        "add_ssh_key": bool,
        "qpr": Optional[str],
        "for_user": str,
        "tree": Union[int, str, None],  # -1 sentinel, or a path (nargs="?")
        "gql": Union[bool, str],
        # vis content / mail fields
        "to": Optional[str],
        "cc": Optional[str],
        "bcc": Optional[str],
        "subject": Optional[str],
        "type": Optional[str],
        # io / tree dump-load
        "dump": Optional[str],
        "load": Optional[str],
        "input": Optional[str],
        "input_dir": Optional[str],
        "output_dir": Optional[str],
        "out": Optional[str],
        "edit": Optional[str],
        "filter": Optional[List[str]],  # action="append"
        # subcommands / actions
        "init": Optional[str],
        "invite_user": Optional[str],
        "run_job": Optional[List[str]],  # nargs="*"
        "events": Optional[List[str]],  # nargs="+"
        # raw http (post/put take PATH [DATA] -> nargs="+")
        "http_get": Optional[str],
        "http_post": Optional[List[str]],
        "http_put": Optional[List[str]],
        "http_delete": Optional[str],
        # share/tag actions
        "share": _ShareTag,
        "tag": _ShareTag,
    },
)
