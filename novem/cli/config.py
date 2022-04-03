import configparser
import os
import stat
from os import path
from pathlib import Path
from typing import Tuple

from ..utils import get_config_path


def update_config(
    profile: str,
    username: str,
    api_root: str,
    token_name: str,
    token: str,
    path: str,
) -> Tuple[bool, str]:
    """
    Write configuration to file
    """

    novem_config: str = ""
    if not path:
        (novem_dir, novem_config) = get_config_path()

        # create path and file if not exist
        Path(novem_dir).mkdir(parents=True, exist_ok=True)
        Path(novem_config).touch(
            mode=stat.S_IRUSR | stat.S_IWUSR, exist_ok=True
        )
        os.chmod(
            novem_config, stat.S_IRUSR | stat.S_IWUSR
        )  # ensure file is not world readable
    else:
        novem_config = path

    print(novem_config)

    config = configparser.ConfigParser()

    # read our config object
    config.read(novem_config)

    add_api_root = True

    # check if config has general section
    if not config.has_section("general"):
        config.add_section("general")
        config.set("general", "user", profile)
        config.set("general", "api_root", api_root)
        add_api_root = False
    else:
        gar = config["general"]["api_root"]
        if gar == api_root:
            # don't add api_root to user config if it's the same as general api
            # root. If the user want's to modify the global api_url then this
            # let's them not have to update all users.
            # the user can still add individual api_roots if they want when
            # creating users

            add_api_root = False
        if "user" not in config["general"]:
            # incomplete config, set our user to be default
            config.set("general", "user", username)

    # TODO: Expand default app configs here when needed
    if not config.has_section("app:cli"):
        config.add_section("app:cli")

    if not config.has_section("app:pylib"):
        config.add_section("app:pylib")

    if not config.has_section("app:fuse"):
        config.add_section("app:fuse")

    profile_name = f"user:{profile}"

    # add/update our section
    if not config.has_section(profile_name):
        config.add_section(profile_name)

    config.set(profile_name, "username", username)
    if add_api_root:
        config.set(profile_name, "api_root", api_root)

    config.set(profile_name, "token_name", token_name)
    config.set(profile_name, "token", token)

    with open(novem_config, "w+") as configfile:
        config.write(configfile)

    return (True, novem_config)


def check_if_profile_exists(profile: str, config_path: str) -> bool:
    """
    Check if config dir already contains a valid token for the profile
    """

    if not config_path:
        (novem_dir, novem_config) = get_config_path()
    else:
        novem_config = config_path

    # check if path exists
    if not path.exists(novem_config):
        # profile don't exist

        return False

    config = configparser.ConfigParser()

    # read our config object
    config.read(novem_config)

    profile_name = f"user:{profile}"

    # add/update our section
    if config.has_section(profile_name):
        return True

    return False
