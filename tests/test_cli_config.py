import configparser
import json

import pytest

import novem
from novem.utils import API_ROOT, get_config_path

from .conftest import CliExit
from .utils import file_exists

# we need to test the different cli aspects
auth_req = {
    "username": "demouser",
    "password": "demopass",
    "token_name": "demotoken",
    "token_description": ('cli token created for "{hostname}" ' 'on "{datetime.now():%Y-%m-%d:%H:%M:%S}"'),
}

auth_resp = {
    "status": "Success",
    "token": "demo_token",
    "token_id": "2OMBg",
    "token_name": "demotoken",
    "token_description": ('cli token created for "mordaine" on' ' "2022-03-15:13:24:46"'),
    "comment": "New token created, make sure to store the token.",
}

auth_resp_2 = {
    "status": "Success",
    "token": "demo_token_2",
    "token_id": "2OMBg",
    "token_name": "demotoken",
    "token_description": ('cli token created for "mordaine" on' ' "2022-03-15:13:24:46"'),
    "comment": "New token created, make sure to store the token.",
}


def mk_auth_responder(resp: dict):
    return lambda request, context: json.dumps(resp)


# requests mock
# fs mock


def test_empty_config(requests_mock, fs, cli):
    # register mocks
    # virtualize authentication endpoint
    requests_mock.register_uri("post", f"{API_ROOT}token", text=mk_auth_responder(auth_resp))

    # get default config path
    cfolder, cpath = get_config_path()

    # verify that our config is missing
    assert not file_exists(cpath)

    # interactively supply username and password
    out, err = cli("--init", stdin=f'{auth_req["username"]}\n{auth_req["password"]}')

    # verify that our config is there
    assert file_exists(cpath)

    config = configparser.ConfigParser()
    config.read(cpath)

    assert config.has_section("general")

    # verify that we have a general section containing
    # a default username and api_url
    assert config["general"]["profile"] == auth_req["username"]
    assert config["general"]["api_root"] == API_ROOT

    # verify that we have empty app sections for
    # cli, pylib, fuse
    assert config.has_section("app:cli")
    assert config.has_section("app:pylib")
    assert config.has_section("app:fuse")

    # verify that we have a user:username section
    profile = f'profile:{auth_req["username"]}'
    assert config.has_section(profile)

    # verify that the section contains
    # username, token, token_name
    assert config[profile]["username"] == auth_req["username"]
    assert config[profile]["token"] == auth_resp["token"]
    assert config[profile]["token_name"] == auth_req["token_name"]


def test_specify_user(requests_mock, fs, cli):
    # confirm that we can create a new user profile with --profile

    # register mocks
    # virtualize authentication endpoint
    requests_mock.register_uri("post", f"{API_ROOT}token", text=mk_auth_responder(auth_resp))

    # get default config path
    cfolder, cpath = get_config_path()

    # verify that our config is missing
    assert not file_exists(cpath)

    profile_name = "demo_test"

    out, err = cli("--init", "--profile", profile_name, stdin=f'{auth_req["username"]}\n{auth_req["password"]}')

    # verify that our config is there
    assert file_exists(cpath)

    config = configparser.ConfigParser()
    config.read(cpath)

    assert config.has_section("general")

    # verify that we have a general section containing
    # a default username and api_url
    assert config["general"]["profile"] == profile_name
    assert config["general"]["api_root"] == API_ROOT

    # verify that we have a user:username section
    profile = f"profile:{profile_name}"
    assert config.has_section(profile)

    # verify that the section contains
    # username, token, token_name
    assert config[profile]["username"] == auth_req["username"]
    assert config[profile]["token"] == auth_resp["token"]
    assert config[profile]["token_name"] == auth_req["token_name"]


# confirm that we can create a new user profile with --profile
def test_add_two_user(requests_mock, fs, cli):

    # register mocks
    # virtualize authentication endpoint
    requests_mock.register_uri("post", f"{API_ROOT}token", text=mk_auth_responder(auth_resp))

    # get default config path
    cfolder, cpath = get_config_path()

    # verify that our config is missing
    assert not file_exists(cpath)

    # interactively supply username and password
    profile_name = "demo_test"
    out, err = cli("--init", "--profile", profile_name, stdin=f'{auth_req["username"]}\n{auth_req["password"]}')

    # verify that our config is there
    assert file_exists(cpath)

    config = configparser.ConfigParser()
    config.read(cpath)

    assert config.has_section("general")

    # verify that we have a general section containing
    # a default username and api_url
    assert config["general"]["profile"] == profile_name
    assert config["general"]["api_root"] == API_ROOT

    # verify that we have a user:username section
    profile = f"profile:{profile_name}"
    assert config.has_section(profile)

    # verify that the section contains
    # username, token, token_name
    assert config[profile]["username"] == auth_req["username"]
    assert config[profile]["token"] == auth_resp["token"]
    assert config[profile]["token_name"] == auth_req["token_name"]

    u2 = "demouser_2"

    # interactively supply username and password
    profile_name = "demo_test_2"
    out, err = cli("--init", "--profile", profile_name, stdin=f'{u2}\n{auth_req["password"]}')

    # verify that our config is there
    assert file_exists(cpath)

    config = configparser.ConfigParser()
    config.read(cpath)

    assert config.has_section("general")

    # verify that we have a general section containing
    # a default username and api_url

    # verify that we have a user:username section
    profile = f"profile:{profile_name}"
    assert config.has_section(profile)

    # verify that the section contains
    # username, token, token_name
    assert config[profile]["username"] == u2
    assert config[profile]["token"] == auth_resp["token"]
    assert config[profile]["token_name"] == auth_req["token_name"]


# confirm that we can create a new user profile with --profile
def test_fail_if_exist(requests_mock, fs, cli):

    # register mocks
    # virtualize authentication endpoint
    requests_mock.register_uri("post", f"{API_ROOT}token", text=mk_auth_responder(auth_resp))

    # get default config path
    cfolder, cpath = get_config_path()

    # verify that our config is missing
    assert not file_exists(cpath)

    # interactively supply username and password
    profile_name = auth_req["username"]
    out, err = cli("--init", "--profile", profile_name, stdin=f'{auth_req["username"]}\n{auth_req["password"]}')

    # verify that our config is there
    assert file_exists(cpath)

    config = configparser.ConfigParser()
    config.read(cpath)

    assert config.has_section("general")

    # verify that we have a general section containing
    # a default username and api_url
    assert config["general"]["profile"] == profile_name
    assert config["general"]["api_root"] == API_ROOT

    # verify that we have a user:username section
    profile = f"profile:{profile_name}"
    assert config.has_section(profile)

    # verify that the section contains
    # username, token, token_name
    assert config[profile]["username"] == auth_req["username"]
    assert config[profile]["token"] == auth_resp["token"]
    assert config[profile]["token_name"] == auth_req["token_name"]

    # assert that we exit with message
    with pytest.raises(CliExit) as e:
        cli("--init", "--profile", profile_name, stdin=f'{auth_req["username"]}\n{auth_req["password"]}')

    out, err = e.value.args
    assert e.value.code == 1
    assert out == (' !  The supplied profile "demouser" already exist,' " use --force to override\n")

    # verify that we work with override
    requests_mock.reset_mock()
    requests_mock.register_uri("post", f"{API_ROOT}token", text=mk_auth_responder(auth_resp_2))

    # interactively supply username and password
    out, err = cli(
        "--init", "--profile", profile_name, "--force", stdin=f'{auth_req["username"]}\n{auth_req["password"]}'
    )

    # verify that our config is there
    assert file_exists(cpath)

    config = configparser.ConfigParser()
    config.read(cpath)

    assert config.has_section("general")

    # verify that we have a general section containing
    # a default username and api_url

    # verify that we have a user:username section
    profile = f"profile:{profile_name}"
    assert config.has_section(profile)

    # verify that the section contains
    # username, token, token_name
    assert config[profile]["username"] == auth_req["username"]
    assert config[profile]["token"] == auth_resp_2["token"]
    assert config[profile]["token_name"] == auth_req["token_name"]


# confirm that we can create a new user profile with --profile
def test_missing_user(requests_mock, fs, cli):
    # register mocks
    # virtualize authentication endpoint
    requests_mock.register_uri("post", f"{API_ROOT}token", text=mk_auth_responder(auth_resp))

    # get default config path
    cfolder, cpath = get_config_path()

    # file is missing
    assert not file_exists(cpath)

    profile_name = auth_req["username"]

    # interactively supply username and password
    with pytest.raises(CliExit) as e:
        cli("--profile", profile_name, stdin=f'{auth_req["username"]}\n{auth_req["password"]}')

    out, err = e.value.args
    assert e.value.code == 1
    assert out == (
        f'Profile "{profile_name}" doesn\'t exist in your config. '
        f"Please add it using:\nnovem --init --profile {profile_name}\n"
    )


# confirm that we can create a new user profile with --profile
def test_config_param(requests_mock, fs, cli):

    # write sample config to location 1
    # write different config to location 2
    # verify that you can use -c swtich to read them

    f1n = "c1.conf"
    f1 = """
[general]
profile = demouser
api_root = https://1.api.novem.io/v1/

[app:cli]
version = 0.5.0
"""

    f2n = "c2.conf"
    f2 = """
[general]
profile = demouser
api_root = https://2.api.novem.io/v1/

[app:cli]
version = 0.5.0
"""

    url_1 = "https://1.api.novem.io/v1/token"
    url_2 = "https://2.api.novem.io/v1/token"

    def a1(request, context):  # return a valid auth endpoint
        ar = {**auth_resp, "token": "path1-token"}
        return json.dumps(ar)

    requests_mock.register_uri("post", f"{url_1}", text=a1)

    def a2(request, context):  # return a valid auth endpoint
        ar = {**auth_resp, "token": "path2-token"}
        return json.dumps(ar)

    requests_mock.register_uri("post", f"{url_2}", text=a2)

    # write config file #1
    with open(f1n, "w") as f:
        f.write(f1)

    # write config file #1
    with open(f2n, "w") as f:
        f.write(f2)

    # it should read the supplied config file, but also operate on it
    cli("--init", "-c", f1n, stdin=f'{auth_req["username"]}\n{auth_req["password"]}')

    cli("--init", "-c", f2n, stdin=f'{auth_req["username"]}\n{auth_req["password"]}')

    c1 = configparser.ConfigParser()
    c1.read(f1n)

    c2 = configparser.ConfigParser()
    c2.read(f2n)

    profile_name = auth_req["username"]
    profile = f"profile:{profile_name}"
    assert c1.has_section(profile)

    # verify that the section contains
    # username, token, token_name
    assert c1[profile]["username"] == auth_req["username"]
    assert c1[profile]["token"] == "path1-token"
    assert c1[profile]["token_name"] == auth_req["token_name"]

    assert c2.has_section(profile)

    # verify that the section contains
    # username, token, token_name
    assert c2[profile]["username"] == auth_req["username"]
    assert c2[profile]["token"] == "path2-token"
    assert c2[profile]["token_name"] == auth_req["token_name"]


def test_can_start_lib_without_config_file(requests_mock, fs):
    requests_mock.register_uri("put", f"{API_ROOT}vis/plots/myplot")

    novem.Plot("myplot", token="foobar")


def test_can_override_profile_for_plot(requests_mock, fs, cli):
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

    captured_token = None

    def mk_gql_response(r, context):
        nonlocal captured_token
        auth_header = r.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            captured_token = auth_header[7:]  # Remove "Bearer " prefix
        return json.dumps({"data": {"plots": []}})

    # Mock both GQL endpoints for the two profiles
    requests_mock.register_uri("POST", "https://api1.test/gql", text=mk_gql_response)
    requests_mock.register_uri("POST", "https://api2.test/gql", text=mk_gql_response)

    # write config file #1
    with open("conf", "w") as f:
        f.write(conf)

    cli("--conf", "conf", "-p")
    assert captured_token == "token1"

    cli("--conf", "conf", "--profile", "user1", "-p")
    assert captured_token == "token1"

    cli("--conf", "conf", "--profile", "user2", "-p")
    assert captured_token == "token2"
