import pytest

from novem.cli.gql import _get_gql_endpoint
from novem.utils import API_ROOT
from tests.conftest import CliExit

from .utils import write_config

gql_endpoint = _get_gql_endpoint(API_ROOT)
whoami_url = f"{API_ROOT.rstrip('/')}/whoami"

auth_req = {
    "username": "demouser",
    "token_name": "demotoken",
}


def test_dead_token_aborts_with_message(cli, requests_mock, fs):
    """A configured-but-rejected token exits with a clear re-auth message."""
    write_config(auth_req)

    requests_mock.register_uri(
        "get",
        whoami_url,
        json={"message": "Resource not found"},
        status_code=401,
    )

    with pytest.raises(CliExit) as ei:
        cli("-p", "-l")

    assert ei.value.code == 1
    _out, err = ei.value.args
    assert "invalid or has expired" in err
    assert "novem --init" in err


def test_dead_token_does_not_reach_listing(cli, requests_mock, fs):
    """The guard aborts before the listing query runs (no GQL leak)."""
    write_config(auth_req)

    requests_mock.register_uri("get", whoami_url, status_code=401, json={})
    gql = requests_mock.register_uri("post", gql_endpoint, json={"data": {"me": None}})

    with pytest.raises(CliExit):
        cli("-p", "-l")

    assert gql.call_count == 0


def test_valid_token_whoami_does_double_duty(cli, requests_mock, fs):
    """A single whoami at startup validates the token *and* seeds identity.

    Listing users needs the current user (for is_me highlighting); with the
    shared cache the startup check is the only /whoami request made.
    """
    write_config(auth_req)

    requests_mock.register_uri("get", whoami_url, text="demouser", status_code=200)
    requests_mock.register_uri(
        "post",
        gql_endpoint,
        json={"data": {"users": []}},
        status_code=200,
    )

    out, _ = cli("-u")

    whoami_calls = [r for r in requests_mock.request_history if r.path.rstrip("/").endswith("whoami")]
    assert len(whoami_calls) == 1


def test_no_token_is_not_treated_as_dead(cli, requests_mock, fs):
    """With no token at all we don't abort; the command runs (anonymous)."""
    write_config({"username": "", "token_name": ""})
    # Blank out the token so the guard's "no token" branch is taken.
    import configparser

    from novem.utils import get_config_path

    _, cpath = get_config_path()
    cfg = configparser.ConfigParser()
    cfg.read(cpath)
    cfg["profile:demouser"]["token"] = ""
    with open(cpath, "w") as f:
        cfg.write(f)

    whoami = requests_mock.register_uri("get", whoami_url, status_code=401)
    requests_mock.register_uri("post", gql_endpoint, json={"data": {"me": {"username": "", "plots": []}}})

    # Should not raise / abort on a dead-token message.
    cli("-p", "-l")
    assert whoami.call_count == 0
