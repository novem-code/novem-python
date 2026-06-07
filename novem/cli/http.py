import mimetypes
import os
import sys
from typing import Any, Dict, List, Optional, Tuple

from ..api_ref import NovemAPI
from .args import CliArgs
from .config import config_from_args


def active_http_flags(args: CliArgs) -> List[str]:
    """Return the http flag names (e.g. ['--get']) that the user supplied."""
    return [
        name
        for name, val in (
            ("--get", args.get("http_get")),
            ("--post", args.get("http_post")),
            ("--put", args.get("http_put")),
            ("--delete", args.get("http_delete")),
        )
        if val is not None
    ]


def _has_other_primary_command(args: CliArgs) -> bool:
    """True when any non-http primary command/dispatch flag is set."""
    if args.get("init"):
        return True
    if args.get("refresh"):
        return True
    if args.get("info"):
        return True
    if args.get("events") is not None:
        return True
    # add_ssh_key and gql default to False; True or a string means set
    if args.get("add_ssh_key") is not False:
        return True
    if args.get("gql") is not False:
        return True
    # plot/mail/grid/doc/job/invite/for_user default to "" (unset)
    for key in ("plot", "mail", "grid", "doc", "job", "invite", "for_user"):
        if args.get(key) != "":
            return True
    # org/group use SUPPRESS — present in args dict means -O / -G was given
    if "org" in args or "group" in args:
        return True
    return False


def validate_isolation(args: CliArgs) -> None:
    """Reject combining http flags with each other or with other commands."""
    active = active_http_flags(args)
    if not active:
        return
    if len(active) > 1:
        print(
            f"Error: {', '.join(active)} cannot be combined; use only one at a time",
            file=sys.stderr,
        )
        sys.exit(1)
    if _has_other_primary_command(args):
        print(
            f"Error: {active[0]} must be used in isolation (no other -p/-g/-m/-j/-d/-u/-O/-G/--gql/etc.)",
            file=sys.stderr,
        )
        sys.exit(1)


def _resolve_data(value: str) -> Tuple[bytes, Optional[str]]:
    """`@filename` reads the file as bytes; otherwise treat as a literal string.

    Returns (body, filename) — filename is set only for the `@filename` form
    so the caller can guess a content-type from the extension.
    """
    if value.startswith("@"):
        filename = os.path.expanduser(value[1:])
        try:
            with open(filename, "rb") as f:
                return f.read(), filename
        except FileNotFoundError:
            print(f'The supplied input file "{filename}" does not exist.', file=sys.stderr)
            sys.exit(1)
    return value.encode("utf-8"), None


def _resolve_content_type(explicit: Optional[str], filename: Optional[str]) -> str:
    """Pick content-type: explicit --type wins, else guess from filename, else text/plain."""
    if explicit:
        return explicit
    if filename:
        guessed, _ = mimetypes.guess_type(filename)
        if guessed:
            return guessed
    return "text/plain"


def _normalize_path(path: str) -> str:
    """api_root ends with `/`, so a leading `/` on path would double it."""
    return path.lstrip("/")


def _read_stdin() -> Optional[bytes]:
    """Return piped stdin bytes, or None when stdin is a TTY (no piped input)."""
    if sys.stdin.isatty():
        return None
    return sys.stdin.read().encode("utf-8")


def _emit(r: Any) -> None:
    if r.text:
        sys.stdout.write(r.text)
        if not r.text.endswith("\n"):
            sys.stdout.write("\n")
    if not r.ok:
        sys.exit(1)


def http_request(
    args: CliArgs,
    method: str,
    path: str,
    data: Optional[str] = None,
) -> None:

    body: Optional[bytes] = None
    filename: Optional[str] = None
    if data is not None:
        body, filename = _resolve_data(data)
    elif method in ("POST", "PUT"):
        body = _read_stdin()

    if method == "POST" and body is None:
        print(
            "Error: --post requires DATA (inline string, @filename, or piped via stdin)",
            file=sys.stderr,
        )
        sys.exit(1)

    novem = NovemAPI(**config_from_args(args), is_cli=True)
    url = f"{novem._api_root}{_normalize_path(path)}"

    request_kwargs: Dict[str, Any] = {}
    if body is not None:
        content_type = _resolve_content_type(args.get("type"), filename)
        request_kwargs["headers"] = {"Content-type": content_type}
        request_kwargs["data"] = body

    r = novem._session.request(method, url, **request_kwargs)
    _emit(r)
