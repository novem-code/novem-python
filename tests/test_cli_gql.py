import json

import pytest

from novem.cli.gql import _get_gql_endpoint
from novem.utils import API_ROOT

from .conftest import CliExit
from .utils import write_config

gql_endpoint = _get_gql_endpoint(API_ROOT)

auth_req = {
    "username": "demouser",
    "password": "demopass",
    "token_name": "demotoken",
    "token_description": "test token",
}


def test_gql_from_file(cli, requests_mock, fs):
    """Test --gql @filename reads query from file."""
    write_config(auth_req)

    gql_response = {"data": {"me": {"username": "demouser"}}}

    captured_query = None

    def capture_gql(request, context):
        nonlocal captured_query
        captured_query = request.json().get("query")
        return json.dumps(gql_response)

    requests_mock.register_uri("POST", gql_endpoint, text=capture_gql)

    # Write a query file
    query = "{ me { username } }"
    with open("query.txt", "w") as f:
        f.write(query)

    out, err = cli("--gql", "@query.txt")

    assert captured_query == query
    assert "demouser" in out


def test_gql_from_stdin(cli, requests_mock, fs):
    """Test --gql with no argument reads from stdin."""
    write_config(auth_req)

    gql_response = {"data": {"me": {"username": "demouser"}}}

    captured_query = None

    def capture_gql(request, context):
        nonlocal captured_query
        captured_query = request.json().get("query")
        return json.dumps(gql_response)

    requests_mock.register_uri("POST", gql_endpoint, text=capture_gql)

    query = "{ me { username email } }"
    out, err = cli("--gql", stdin=query)

    assert captured_query == query
    assert "demouser" in out


def test_gql_inline_query(cli, requests_mock, fs):
    """Test --gql with inline query string."""
    write_config(auth_req)

    gql_response = {"data": {"me": {"username": "demouser"}}}

    captured_query = None

    def capture_gql(request, context):
        nonlocal captured_query
        captured_query = request.json().get("query")
        return json.dumps(gql_response)

    requests_mock.register_uri("POST", gql_endpoint, text=capture_gql)

    query = "{ me { username } }"
    out, err = cli("--gql", query)

    assert captured_query == query
    assert "demouser" in out


def test_gql_respects_profile(cli, requests_mock, fs):
    """Test --gql respects --profile option."""
    # Write config with two profiles
    conf = """\
[general]
profile = user1

[app:cli]
version = 0.5.0

[profile:user1]
username = user1
api_root = https://api1.test/v1
token = token1

[profile:user2]
username = user2
api_root = https://api2.test/v1
token = token2
"""

    import os

    from novem.utils import get_config_path

    cfolder, cpath = get_config_path()
    os.makedirs(cfolder, exist_ok=True)
    with open(cpath, "w") as f:
        f.write(conf)

    captured_tokens = []

    def capture_gql(request, context):
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            captured_tokens.append(auth_header[7:])
        return json.dumps({"data": {"me": {"username": "test"}}})

    requests_mock.register_uri("POST", "https://api1.test/gql", text=capture_gql)
    requests_mock.register_uri("POST", "https://api2.test/gql", text=capture_gql)

    query = "{ me { username } }"

    # Default profile (user1)
    cli("--gql", query)
    assert captured_tokens[-1] == "token1"

    # Explicit profile user1
    cli("--profile", "user1", "--gql", query)
    assert captured_tokens[-1] == "token1"

    # Explicit profile user2
    cli("--profile", "user2", "--gql", query)
    assert captured_tokens[-1] == "token2"


def test_gql_debug_mode_with_other_commands(cli, requests_mock, fs):
    """Test --gql with other commands enables debug mode instead of stdin."""
    write_config(auth_req)

    gql_response = {"data": {"plots": []}}

    def return_gql(request, context):
        return json.dumps(gql_response)

    requests_mock.register_uri("POST", gql_endpoint, text=return_gql)

    # When --gql is used with -p, it should enable debug mode
    # and show the GQL response, then exit
    with pytest.raises(CliExit) as e:
        cli("-p", "--gql")

    out, err = e.value.args
    assert e.value.code == 0
    # Debug mode prints the response
    assert "plots" in out


def test_info_respects_profile(cli, requests_mock, fs):
    """Test --info respects --profile option."""
    # Write config with two profiles
    conf = """\
[general]
profile = user1

[app:cli]
version = 0.5.0

[profile:user1]
username = user1
api_root = https://api1.test/v1
token = token1

[profile:user2]
username = user2
api_root = https://api2.test/v1
token = token2
"""

    import os

    from novem.utils import get_config_path

    cfolder, cpath = get_config_path()
    os.makedirs(cfolder, exist_ok=True)
    with open(cpath, "w") as f:
        f.write(conf)

    captured_tokens = []

    def capture_request(request, context):
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            captured_tokens.append(auth_header[7:])
        return "user1 profile info"

    def capture_request2(request, context):
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            captured_tokens.append(auth_header[7:])
        return "user2 profile info"

    # Note: NovemAPI appends paths with leading slash, so URL becomes /v1//admin/...
    requests_mock.register_uri("GET", "https://api1.test/v1//admin/profile/overview", text=capture_request)
    requests_mock.register_uri("GET", "https://api2.test/v1//admin/profile/overview", text=capture_request2)

    # Default profile (user1)
    out, err = cli("--info")
    assert captured_tokens[-1] == "token1"
    assert "user1 profile info" in out

    # Explicit profile user1
    out, err = cli("--profile", "user1", "--info")
    assert captured_tokens[-1] == "token1"

    # Explicit profile user2
    out, err = cli("--profile", "user2", "--info")
    assert captured_tokens[-1] == "token2"
    assert "user2 profile info" in out


def test_gql_file_with_tilde_expansion(cli, requests_mock, fs, monkeypatch):
    """Test --gql @~/path expands tilde to home directory."""
    write_config(auth_req)

    gql_response = {"data": {"me": {"username": "demouser"}}}

    captured_query = None

    def capture_gql(request, context):
        nonlocal captured_query
        captured_query = request.json().get("query")
        return json.dumps(gql_response)

    requests_mock.register_uri("POST", gql_endpoint, text=capture_gql)

    # Create a file in a fake home directory
    import os

    fake_home = "/fakehome"
    os.makedirs(fake_home, exist_ok=True)
    monkeypatch.setenv("HOME", fake_home)

    query = "{ me { username } }"
    with open(f"{fake_home}/query.txt", "w") as f:
        f.write(query)

    out, err = cli("--gql", "@~/query.txt")

    assert captured_query == query
    assert "demouser" in out


def test_gql_file_not_found(cli, requests_mock, fs):
    """Test --gql @nonexistent raises FileNotFoundError."""
    write_config(auth_req)

    with pytest.raises(FileNotFoundError):
        cli("--gql", "@nonexistent.txt")


def test_gql_output_is_valid_json(cli, requests_mock, fs):
    """Test --gql outputs valid JSON."""
    write_config(auth_req)

    gql_response = {"data": {"me": {"username": "demouser", "email": "test@example.com"}}}

    requests_mock.register_uri("POST", gql_endpoint, text=lambda r, c: json.dumps(gql_response))

    out, err = cli("--gql", "{ me { username email } }")

    # Output should be valid JSON
    parsed = json.loads(out)
    assert parsed == gql_response


def test_gql_returns_errors_from_api(cli, requests_mock, fs):
    """Test --gql returns GQL errors from API."""
    write_config(auth_req)

    gql_response = {"errors": [{"message": "Field 'invalid' not found"}]}

    requests_mock.register_uri("POST", gql_endpoint, text=lambda r, c: json.dumps(gql_response))

    out, err = cli("--gql", "{ invalid }")

    # Should output the error response as JSON
    parsed = json.loads(out)
    assert "errors" in parsed
    assert "invalid" in parsed["errors"][0]["message"]


def test_gql_debug_mode_with_user_command(cli, requests_mock, fs):
    """Test --gql with -u enables debug mode."""
    write_config(auth_req)

    gql_response = {"data": {"users": []}}

    requests_mock.register_uri("POST", gql_endpoint, text=lambda r, c: json.dumps(gql_response))

    # When --gql is used with -u, it should enable debug mode
    with pytest.raises(CliExit) as e:
        cli("-u", "--gql")

    out, err = e.value.args
    assert e.value.code == 0
    assert "users" in out


def test_gql_debug_mode_with_grid_command(cli, requests_mock, fs):
    """Test --gql with -g enables debug mode."""
    write_config(auth_req)

    gql_response = {"data": {"grids": []}}

    requests_mock.register_uri("POST", gql_endpoint, text=lambda r, c: json.dumps(gql_response))

    with pytest.raises(CliExit) as e:
        cli("-g", "--gql")

    out, err = e.value.args
    assert e.value.code == 0
    assert "grids" in out
