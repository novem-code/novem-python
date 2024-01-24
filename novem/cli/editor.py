from __future__ import print_function

import os.path
import subprocess
import sys
import tempfile
from shutil import which
from typing import List, Optional

"""
This is utility code taken directly from https://github.com/fmoo/python-editor
on the 28th of February 2023. The below code is licensed Apache-2.0

Slight modification for integration with the novem cli
"""


__all__ = [
    "edit",
    "get_editor",
    "EditorError",
]

__version__ = "1.0.5"


class EditorError(RuntimeError):
    pass


def get_default_editors() -> List[str]:
    # TODO: Make platform-specific
    return [
        "editor",
        "vim",
        "emacs",
        "nano",
    ]


def get_editor_args(editor: str) -> List[str]:
    if editor in ["vim", "gvim", "vim.basic", "vim.tiny"]:
        return ["-f", "-o"]

    elif editor == "emacs":
        return ["-nw"]

    elif editor == "gedit":
        return ["-w", "--new-window"]

    elif editor == "nano":
        return ["-R"]

    elif editor == "code":
        return ["-w", "-n"]

    else:
        return []


def get_editor() -> str:
    # Get the editor from the environment.  Prefer VISUAL to EDITOR
    editor = os.environ.get("VISUAL") or os.environ.get("EDITOR")
    if editor:
        return editor

    # None found in the environment.  Fallback to platform-specific defaults.
    for ed in get_default_editors():
        path = which(ed)
        if path is not None:
            return path

    raise EditorError("Unable to find a viable editor on this system. Please consider setting your $EDITOR variable")


def get_tty_filename() -> str:
    if sys.platform == "win32":
        return "CON:"
    return "/dev/tty"


def edit(
    filename: Optional[str] = None,
    contents: Optional[str] = None,
    use_tty: Optional[bool] = None,
    suffix: str = "",
) -> str:
    editor = get_editor()
    args = [editor] + get_editor_args(os.path.basename(os.path.realpath(editor)))

    if use_tty is None:
        use_tty = sys.stdin.isatty() and not sys.stdout.isatty()

    if filename is None:
        tmp = tempfile.NamedTemporaryFile(suffix=suffix)
        filename = tmp.name

    if contents is not None:
        # For python3 only.  If str is passed instead of bytes, encode default
        wc = contents.encode()

        with open(filename, mode="wb") as f:
            f.write(wc)

    args += [filename]

    stdout = None
    if use_tty:
        stdout = open(get_tty_filename(), "wb")

    proc = subprocess.Popen(args, close_fds=True, stdout=stdout)
    proc.communicate()

    with open(filename, mode="rb") as f:
        return f.read().decode("utf-8")
