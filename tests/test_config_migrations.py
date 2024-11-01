import configparser
from pathlib import Path

from novem.types import Config
from novem.utils import migrate_config_04_to_05


def test_migrate_config_04_to_05(fs):
    config: Config = {}  # type: ignore
    conf_file = Path("novem.conf")
    config["api_root"] = "https://api.novem.no/v1/"

    cp = configparser.ConfigParser()
    cp.read_string(
        """\
[general]
api_root = https://api.novem.no/v1/
profile = demo

[profile:demo]
username = sondov
token_name = test-token-name
token = tok-token

[app:cli]

[app:python]

[app:fuse]"""
    )
    # test that the migration rewrites the api url
    migrate_config_04_to_05(str(conf_file), cp, config)

    assert "https://api.novem.io/v1/" in conf_file.read_text()
    assert "https://api.novem.no/v1/" not in conf_file.read_text()

    assert config["api_root"] == "https://api.novem.io/v1/"
    assert cp["general"]["api_root"] == "https://api.novem.io/v1/"

    # verify that it writes a version
    assert cp["app:cli"]["version"]

    # verify that the migration doesnt run again
    cp["general"]["api_root"] = "https://api.novem.no/v1/"
    migrate_config_04_to_05(str(conf_file), cp, config)

    assert cp["general"]["api_root"] == "https://api.novem.no/v1/"


def test_migrate_config_04_to_05_no_app_cli_section(fs):
    config: Config = {}  # type: ignore
    conf_file = Path("novem.conf")
    config["api_root"] = "https://api.novem.no/v1/"

    cp = configparser.ConfigParser()
    cp.read_string(
        """\
[general]
api_root = https://api.novem.no/v1/
"""
    )

    migrate_config_04_to_05(str(conf_file), cp, config)

    assert cp["app:cli"]["version"]
