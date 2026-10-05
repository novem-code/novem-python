"""Entry point for the ``novem`` command.

Runs the native CLI from ``novem[cli]``, or says how to install it. This lives
outside the novem package so starting the CLI doesn't pay for importing it.
"""

import os
import platform
import sys
from typing import NoReturn, Optional

# copy of novem.__version__, kept in sync by scripts/bump_version.py; importing
# novem (or importlib.metadata) to look it up would cost every invocation
__version__ = "0.7.0"

# platforms novem-cli ships wheels for, keep in sync with the cli extra; elsewhere
# there is no CLI to install
_NATIVE_PLATFORMS = {
    ("linux", "x86_64"),
    ("linux", "aarch64"),
    ("darwin", "arm64"),
    ("darwin", "x86_64"),
    ("win32", "AMD64"),
}


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
    binary = _find_native()
    if binary:
        _run_native(binary)

    if (sys.platform, platform.machine()) in _NATIVE_PLATFORMS:
        print(
            "novem: the novem command needs the native CLI, install it with: pipx install --force 'novem[cli]'",
            file=sys.stderr,
        )
    else:
        print(f"novem: the native CLI isn't available for {sys.platform}/{platform.machine()}", file=sys.stderr)
    sys.exit(1)


if __name__ == "__main__":
    main()
