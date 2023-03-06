import configparser
import io
import json
import sys

import pytest

from novem.cli import run_cli
from novem.utils import get_config_path

from .utils import file_exists

# we need to test the different cli aspects
auth_req = {
    "username": "demouser",
    "password": "demopass",
    "token_name": "demotoken",
    "token_description": (
        'cli token created for "{hostname}" '
        'on "{datetime.now():%Y-%m-%d:%H:%M:%S}"'
    ),
}

auth_resp = {
    "status": "Success",
    "token": "demo_token",
    "token_id": "2OMBg",
    "token_name": "demotoken",
    "token_description": (
        'cli token created for "mordaine" on' ' "2022-03-15:13:24:46"'
    ),
    "comment": "New token created, make sure to store the token.",
}

auth_resp_2 = {
    "status": "Success",
    "token": "demo_token_2",
    "token_id": "2OMBg",
    "token_name": "demotoken",
    "token_description": (
        'cli token created for "mordaine" on' ' "2022-03-15:13:24:46"'
    ),
    "comment": "New token created, make sure to store the token.",
}


# Auth endpoint for our token
def auth(request, context):
    # return a valid auth endpoint
    return json.dumps(auth_resp)


# Auth endpoint for our token
def auth2(request, context):
    # return a valid auth endpoint
    return json.dumps(auth_resp_2)


# request mock
# fx mock
# captreus sys
# monekypath stdin
def test_empty_config(requests_mock, fs, capsys, monkeypatch):

    # The default setting is to use the api_root reference for
    # the primary novem api
    api_root = "https://api.novem.no/v1/"

    # register mocks
    # virtualize authentication endpoint
    requests_mock.register_uri("post", f"{api_root}token", text=auth)

    # get default config path
    (cfolder, cpath) = get_config_path()

    # verify that our config is missing
    exist = file_exists(cpath)

    # file is missing
    assert exist is False

    # interactivley supply username and password
    invalues = f'{auth_req["username"]}\n{auth_req["password"]}'
    monkeypatch.setattr("sys.stdin", io.StringIO(invalues))

    # construct cli paramters
    params = ["--init"]

    # launch cli with params
    sys.argv = ["novem"] + params

    run_cli()
    out, err = capsys.readouterr()

    # verify that our config is missing
    exist = file_exists(cpath)

    # file is missing
    assert exist is True

    # check if novem config file exist
    config = configparser.ConfigParser()
    config.read(cpath)

    assert config.has_section("general") is True

    # verify that we have a general section containing
    # a default username and api_url
    assert config["general"]["profile"] == auth_req["username"]
    assert config["general"]["api_root"] == api_root

    # verify that we have empty app sections for
    # cli, pylib, fuse
    assert config.has_section("app:cli") is True
    assert config.has_section("app:pylib") is True
    assert config.has_section("app:fuse") is True

    # verify that we have a user:username section
    profile = f'profile:{auth_req["username"]}'
    assert config.has_section(profile) is True

    # verify that the section contains
    # username, token, token_name
    assert config[profile]["username"] == auth_req["username"]
    assert config[profile]["token"] == auth_resp["token"]
    assert config[profile]["token_name"] == auth_req["token_name"]

    return


# other tests


# confirm that we can create a new user profile with --profile
def test_specify_user(requests_mock, fs, capsys, monkeypatch):

    # The default setting is to use the api_root reference for
    # the primary novem api
    api_root = "https://api.novem.no/v1/"

    # register mocks
    # virtualize authentication endpoint
    requests_mock.register_uri("post", f"{api_root}token", text=auth)

    # get default config path
    (cfolder, cpath) = get_config_path()

    # verify that our config is missing
    exist = file_exists(cpath)

    # file is missing
    assert exist is False

    # interactivley supply username and password
    invalues = f'{auth_req["username"]}\n{auth_req["password"]}'
    monkeypatch.setattr("sys.stdin", io.StringIO(invalues))

    profile_name = "demo_test"
    # construct cli paramters
    params = ["--init", "--profile", profile_name]

    # launch cli with params
    sys.argv = ["novem"] + params

    run_cli()
    out, err = capsys.readouterr()

    # verify that our config is missing
    exist = file_exists(cpath)

    # file is missing
    assert exist is True

    # check if novem config file exist
    config = configparser.ConfigParser()
    config.read(cpath)

    assert config.has_section("general") is True

    # verify that we have a general section containing
    # a default username and api_url
    assert config["general"]["profile"] == profile_name
    assert config["general"]["api_root"] == api_root

    # verify that we have a user:username section
    profile = f"profile:{profile_name}"
    assert config.has_section(profile) is True

    # verify that the section contains
    # username, token, token_name
    assert config[profile]["username"] == auth_req["username"]
    assert config[profile]["token"] == auth_resp["token"]
    assert config[profile]["token_name"] == auth_req["token_name"]


# confirm that we can create a new user profile with --profile
def test_add_two_user(requests_mock, fs, capsys, monkeypatch):

    # The default setting is to use the api_root reference for
    # the primary novem api
    api_root = "https://api.novem.no/v1/"

    # register mocks
    # virtualize authentication endpoint
    requests_mock.register_uri("post", f"{api_root}token", text=auth)

    # get default config path
    (cfolder, cpath) = get_config_path()

    # verify that our config is missing
    exist = file_exists(cpath)

    # file is missing
    assert exist is False

    # interactivley supply username and password
    invalues = f'{auth_req["username"]}\n{auth_req["password"]}'
    monkeypatch.setattr("sys.stdin", io.StringIO(invalues))

    profile_name = "demo_test"
    # construct cli paramters
    params = ["--init", "--profile", profile_name]

    # launch cli with params
    sys.argv = ["novem"] + params

    run_cli()
    out, err = capsys.readouterr()

    # verify that our config is missing
    exist = file_exists(cpath)

    # file is missing
    assert exist is True

    # check if novem config file exist
    config = configparser.ConfigParser()
    config.read(cpath)

    assert config.has_section("general") is True

    # verify that we have a general section containing
    # a default username and api_url
    assert config["general"]["profile"] == profile_name
    assert config["general"]["api_root"] == api_root

    # verify that we have a user:username section
    profile = f"profile:{profile_name}"
    assert config.has_section(profile) is True

    # verify that the section contains
    # username, token, token_name
    assert config[profile]["username"] == auth_req["username"]
    assert config[profile]["token"] == auth_resp["token"]
    assert config[profile]["token_name"] == auth_req["token_name"]

    u2 = "demouser_2"

    # interactivley supply username and password
    invalues = f'{u2}\n{auth_req["password"]}'
    monkeypatch.setattr("sys.stdin", io.StringIO(invalues))

    profile_name = "demo_test_2"
    # construct cli paramters
    params = ["--init", "--profile", profile_name]

    # launch cli with params
    sys.argv = ["novem"] + params

    run_cli()
    out, err = capsys.readouterr()

    # verify that our config is missing
    exist = file_exists(cpath)

    # file is missing
    assert exist is True

    # check if novem config file exist
    config = configparser.ConfigParser()
    config.read(cpath)

    assert config.has_section("general") is True

    # verify that we have a general section containing
    # a default username and api_url

    # verify that we have a user:username section
    profile = f"profile:{profile_name}"
    assert config.has_section(profile) is True

    # verify that the section contains
    # username, token, token_name
    assert config[profile]["username"] == u2
    assert config[profile]["token"] == auth_resp["token"]
    assert config[profile]["token_name"] == auth_req["token_name"]


# confirm that we can create a new user profile with --profile
def test_fail_if_exist(requests_mock, fs, capsys, monkeypatch):

    # The default setting is to use the api_root reference for
    # the primary novem api
    api_root = "https://api.novem.no/v1/"

    # register mocks
    # virtualize authentication endpoint
    requests_mock.register_uri("post", f"{api_root}token", text=auth)

    # get default config path
    (cfolder, cpath) = get_config_path()

    # verify that our config is missing
    exist = file_exists(cpath)

    # file is missing
    assert exist is False

    # interactivley supply username and password
    invalues = f'{auth_req["username"]}\n{auth_req["password"]}'
    monkeypatch.setattr("sys.stdin", io.StringIO(invalues))

    profile_name = auth_req["username"]
    # construct cli paramters
    params = ["--init", "--profile", profile_name]

    # launch cli with params
    sys.argv = ["novem"] + params

    run_cli()
    out, err = capsys.readouterr()

    # verify that our config is missing
    exist = file_exists(cpath)

    # file is missing
    assert exist is True

    # check if novem config file exist
    config = configparser.ConfigParser()
    config.read(cpath)

    assert config.has_section("general") is True

    # verify that we have a general section containing
    # a default username and api_url
    assert config["general"]["profile"] == profile_name
    assert config["general"]["api_root"] == api_root

    # verify that we have a user:username section
    profile = f"profile:{profile_name}"
    assert config.has_section(profile) is True

    # verify that the section contains
    # username, token, token_name
    assert config[profile]["username"] == auth_req["username"]
    assert config[profile]["token"] == auth_resp["token"]
    assert config[profile]["token_name"] == auth_req["token_name"]

    # interactivley supply username and password
    invalues = f'{auth_req["username"]}\n{auth_req["password"]}'
    monkeypatch.setattr("sys.stdin", io.StringIO(invalues))

    # construct cli paramters
    params = ["--init", "--profile", profile_name]

    # launch cli with params
    sys.argv = ["novem"] + params

    # assert that we exit with message

    with pytest.raises(SystemExit) as pytest_wrapped_e:
        run_cli()
    assert pytest_wrapped_e.type == SystemExit
    assert pytest_wrapped_e.value.code == 1
    out, err = capsys.readouterr()
    assert out == (
        ' !  The supplied profile "demouser" already exist,'
        " use --force to override\n"
    )

    # verify that we work with override

    # virtualize authentication endpoint

    requests_mock.reset_mock()
    requests_mock.register_uri("post", f"{api_root}token", text=auth2)

    # interactivley supply username and password
    invalues = f'{auth_req["username"]}\n{auth_req["password"]}'
    monkeypatch.setattr("sys.stdin", io.StringIO(invalues))

    # construct cli kkkkkkkkkkkkaramters
    params = ["--init", "--profile", profile_name, "--force"]

    # launch cli with params
    sys.argv = ["novem"] + params

    # run cli
    run_cli()
    out, err = capsys.readouterr()

    # verify that our config is missing
    exist = file_exists(cpath)

    # file is missing
    assert exist is True

    # check if novem config file exist
    config = configparser.ConfigParser()
    config.read(cpath)

    # print_file(cpath)
    assert config.has_section("general") is True

    # verify that we have a general section containing
    # a default username and api_url

    # verify that we have a user:username section
    profile = f"profile:{profile_name}"
    assert config.has_section(profile) is True

    # verify that the section contains
    # username, token, token_name
    assert config[profile]["username"] == auth_req["username"]
    assert config[profile]["token"] == auth_resp_2["token"]
    assert config[profile]["token_name"] == auth_req["token_name"]


# confirm that we can create a new user profile with --profile
def test_misisng_user(requests_mock, fs, capsys, monkeypatch):
    # The default setting is to use the api_root reference for
    # the primary novem api
    api_root = "https://api.novem.no/v1/"

    # register mocks
    # virtualize authentication endpoint
    requests_mock.register_uri("post", f"{api_root}token", text=auth)

    # get default config path
    (cfolder, cpath) = get_config_path()

    # verify that our config is missing
    exist = file_exists(cpath)

    # file is missing
    assert exist is False

    # interactivley supply username and password
    invalues = f'{auth_req["username"]}\n{auth_req["password"]}'
    monkeypatch.setattr("sys.stdin", io.StringIO(invalues))

    profile_name = auth_req["username"]
    # construct cli paramters
    params = ["--profile", profile_name]

    # launch cli with params
    sys.argv = ["novem"] + params

    with pytest.raises(SystemExit) as pytest_wrapped_e:
        run_cli()
    assert pytest_wrapped_e.type == SystemExit
    assert pytest_wrapped_e.value.code == 1
    out, err = capsys.readouterr()
    assert out == (
        f'Profile "{profile_name}" doens\'t exist in your config. '
        f"Please add it using:\nnovem --init --profile {profile_name}\n"
    )


# confirm that we can create a new user profile with --profile
def test_config_param(requests_mock, fs, capsys, monkeypatch):

    # write sample config to location 1
    # write different config to location 2
    # verify that you can use -c swtich to read them

    f1n = "c1.conf"
    f1 = """
[general]
profile = demouser
api_root = https://1.api.novem.no/v1/
"""

    f2n = "c2.conf"
    f2 = """
[general]
profile = demouser
api_root = https://2.api.novem.no/v1/
"""

    url_1 = "https://1.api.novem.no/v1/token"
    url_2 = "https://2.api.novem.no/v1/token"

    def a1(request, context):  # return a valid auth endpoint
        ar = auth_resp
        ar["token"] = "path1-token"
        return json.dumps(ar)

    requests_mock.register_uri("post", f"{url_1}", text=a1)

    def a2(request, context):  # return a valid auth endpoint
        ar = auth_resp
        ar["token"] = "path2-token"
        return json.dumps(ar)

    requests_mock.register_uri("post", f"{url_2}", text=a2)

    # write config file #1
    with open(f1n, "w") as f:
        f.write(f1)

    # write config file #1
    with open(f2n, "w") as f:
        f.write(f2)

    # it should read the supplied config file, but also operate on it
    invalues = f'{auth_req["username"]}\n{auth_req["password"]}'
    monkeypatch.setattr("sys.stdin", io.StringIO(invalues))

    # construct cli kkkkkkkkkkkkaramters
    # params = ["--init", '-c',f1n]
    params = ["--init", "-c", f1n]

    # launch cli with params
    sys.argv = ["novem"] + params

    # run cli
    run_cli()
    out, err = capsys.readouterr()

    # it should read the supplied config file, but also operate on it
    invalues = f'{auth_req["username"]}\n{auth_req["password"]}'
    monkeypatch.setattr("sys.stdin", io.StringIO(invalues))

    # construct cli kkkkkkkkkkkkaramters
    # params = ["--init", '-c',f1n]
    params = ["--init", "-c", f2n]

    # launch cli with params
    sys.argv = ["novem"] + params

    # run cli
    run_cli()
    out, err = capsys.readouterr()
    # print(out)

    # check if novem config file exist
    c1 = configparser.ConfigParser()
    c1.read(f1n)

    c2 = configparser.ConfigParser()
    c2.read(f2n)

    profile_name = auth_req["username"]
    profile = f"profile:{profile_name}"
    assert c1.has_section(profile) is True

    # verify that the section contains
    # username, token, token_name
    assert c1[profile]["username"] == auth_req["username"]
    assert c1[profile]["token"] == "path1-token"
    assert c1[profile]["token_name"] == auth_req["token_name"]

    assert c2.has_section(profile) is True

    # verify that the section contains
    # username, token, token_name
    assert c2[profile]["username"] == auth_req["username"]
    assert c2[profile]["token"] == "path2-token"
    assert c2[profile]["token_name"] == auth_req["token_name"]
