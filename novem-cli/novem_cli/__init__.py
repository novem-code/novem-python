"""Carrier package for the native novem CLI binary.

Installed via ``pip install 'novem[cli]'``; the ``novem`` command from the
novem package finds the binary through :func:`find_binary`.
"""

import os
import sys


def find_binary() -> str:
    name = "novem.exe" if sys.platform == "win32" else "novem"
    path = os.path.join(os.path.dirname(__file__), "bin", name)
    if not os.path.isfile(path):
        raise FileNotFoundError(path)
    return path
