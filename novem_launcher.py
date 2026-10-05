"""Entry point for the ``novem`` command.

Runs the native CLI when ``novem[cli]`` is installed, otherwise the Python
CLI in novem.cli. This lives outside the novem package so the native path
doesn't pay for importing it.
"""

import os
import sys
from typing import NoReturn, Optional

# copy of novem.__version__, kept in sync by scripts/bump_version.py; importing
# novem (or importlib.metadata) to look it up would cost every invocation
__version__ = "0.6.3"


def _find_native() -> Optional[str]:
    try:
        from novem_cli import find_binary  # type: ignore[import-not-found,unused-ignore]
    except ImportError:
        return None
    try:
        return find_binary()
    except FileNotFoundError:
        return None


def _run_native(binary: str) -> NoReturn:
    args = [binary, *sys.argv[1:]]
    # lets the binary report which python package launched it in --version
    os.environ["NOVEM_PYTHON_VERSION"] = __version__
    if sys.platform == "win32":
        # no real exec on windows, so wait for the child and forward its exit code
        import subprocess

        try:
            sys.exit(subprocess.call(args))
        except KeyboardInterrupt:
            sys.exit(130)
    os.execv(binary, args)


def main() -> None:
    if not os.environ.get("NOVEM_PYTHON_CLI"):
        binary = _find_native()
        if binary:
            _run_native(binary)

    from novem.cli import run_cli

    run_cli()


if __name__ == "__main__":
    main()
