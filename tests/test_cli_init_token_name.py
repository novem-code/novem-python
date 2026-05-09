import json
import re

import pytest

from novem.api_ref import Novem401, NovemAPI, NovemException
from novem.cli import _default_token_name, _sanitize_token_name
from novem.utils import API_ROOT

from .conftest import CliExit

# Server-enforced rule from gaia/db/functions/token_create.sql
SERVER_TOKEN_NAME_REGEX = re.compile(r"^[a-z][a-z0-9\-\._]*$")
SERVER_TOKEN_NAME_MAX = 128


# ---------------------------------------------------------------------------
# Helper unit tests
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("simple", "simple"),
        ("Already-Mixed_Case.1", "already-mixed_case.1"),
        ("123leading-digit", "leading-digit"),  # leading digits stripped
        ("---dashes-only", "dashes-only"),  # leading dashes stripped
        ("..._punct-leading", "punct-leading"),
        ("123", ""),  # nothing valid remains
        ("name with spaces!", "namewithspaces"),  # invalid chars dropped
    ],
)
def test_sanitize_token_name(raw, expected):
    assert _sanitize_token_name(raw) == expected
    if expected:
        assert SERVER_TOKEN_NAME_REGEX.match(expected)


def test_sanitize_token_name_clamps_length():
    name = "a" + "b" * 200
    sanitized = _sanitize_token_name(name)
    assert len(sanitized) == SERVER_TOKEN_NAME_MAX
    assert SERVER_TOKEN_NAME_REGEX.match(sanitized)


@pytest.mark.parametrize(
    "hostname",
    [
        "host",
        "HOST.example.com",
        "users-laptop-2024-something-very-long-name-here",
        "12345-numeric-prefix",
        "....",  # entirely invalid hostname
        "",
    ],
)
def test_default_token_name_satisfies_server_rules(hostname):
    name = _default_token_name(hostname)
    assert SERVER_TOKEN_NAME_REGEX.match(name), f"invalid token name {name!r}"
    assert len(name) <= 32
    assert name.startswith("np-")


def test_default_token_name_includes_nonce():
    # Two calls should differ (nonce randomness).
    a = _default_token_name("host")
    b = _default_token_name("host")
    # Could collide once in 36**8, but practically never.
    assert a != b


# ---------------------------------------------------------------------------
# CLI integration: API-level errors must not crash with KeyError
# ---------------------------------------------------------------------------


auth_req = {
    "username": "demouser",
    "password": "demopass",
}


def test_init_handles_409_token_name_conflict(requests_mock, fs, cli):
    """A non-401 failure (e.g. duplicate token name) used to crash with
    KeyError: 'token'. It should now exit cleanly with the API message."""

    requests_mock.register_uri(
        "post",
        f"{API_ROOT}token",
        status_code=409,
        text=json.dumps({"message": "Token name already exists"}),
    )

    with pytest.raises(CliExit) as exc:
        cli("--init", stdin=f'{auth_req["username"]}\n{auth_req["password"]}')

    out, _ = exc.value.args
    assert exc.value.code == 1
    assert "Token name already exists" in out
    assert "KeyError" not in out


def test_init_handles_500_with_no_message(requests_mock, fs, cli):
    requests_mock.register_uri(
        "post",
        f"{API_ROOT}token",
        status_code=500,
        text="",
    )

    with pytest.raises(CliExit) as exc:
        cli("--init", stdin=f'{auth_req["username"]}\n{auth_req["password"]}')

    out, _ = exc.value.args
    assert exc.value.code == 1
    assert "Failed to create token" in out


def test_create_token_raises_novem_exception_on_non_401(requests_mock, fs):
    requests_mock.register_uri(
        "post",
        f"{API_ROOT}token",
        status_code=409,
        text=json.dumps({"message": "duplicate"}),
    )

    api = NovemAPI(api_root=API_ROOT, ignore_config=True, is_cli=True)
    with pytest.raises(NovemException) as exc:
        api.create_token({"username": "u", "password": "p", "token_name": "t"})
    assert "duplicate" in str(exc.value)


def test_create_token_still_raises_novem_401(requests_mock, fs):
    requests_mock.register_uri(
        "post",
        f"{API_ROOT}token",
        status_code=401,
        text=json.dumps({"message": "bad creds"}),
    )

    api = NovemAPI(api_root=API_ROOT, ignore_config=True, is_cli=True)
    with pytest.raises(Novem401):
        api.create_token({"username": "u", "password": "p", "token_name": "t"})
