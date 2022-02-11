import configparser
import os
import stat
from os import path
from pathlib import Path
from typing import Tuple, Union

NOVEM_PATH = "novem"
NOVEM_NAME = "novem.conf"


def get_user_config_directory() -> Union[str, None]:
    """Returns a platform-specific root directory for user config settings."""
    # On Windows, prefer %LOCALAPPDATA%, then %APPDATA%, since we can expect
    # the AppData directories to be ACLed to be visible only to the user and
    # admin users (https://stackoverflow.com/a/7617601/1179226). If neither is
    # set, return None instead of falling back to something that may be
    # world-readable.
    if os.name == "nt":
        appdata = os.getenv("LOCALAPPDATA")
        if appdata:
            return appdata
        appdata = os.getenv("APPDATA")
        if appdata:
            return appdata
        return None
    # On non-windows, use XDG_CONFIG_HOME if set, else default to ~/.config.
    xdg_config_home = os.getenv("XDG_CONFIG_HOME")
    if xdg_config_home:
        return xdg_config_home
    return os.path.join(os.path.expanduser("~"), ".config")


def get_config_path() -> Tuple[str, str]:
    """
    Get default configuration path
    """

    config_path: Union[str, None] = get_user_config_directory()
    novem_dir = f"{config_path}/{NOVEM_PATH}"
    novem_config = f"{config_path}/{NOVEM_PATH}/{NOVEM_NAME}"

    return (novem_dir, novem_config)


def update_config(
    profile: str, username: str, api_root: str, token_name: str, token: str
) -> Tuple[bool, str]:
    """
    Write configuration to file
    """

    (novem_dir, novem_config) = get_config_path()

    # create path and file if not exist
    Path(novem_dir).mkdir(parents=True, exist_ok=True)
    Path(novem_config).touch(mode=stat.S_IRUSR | stat.S_IWUSR, exist_ok=True)
    os.chmod(
        novem_config, stat.S_IRUSR | stat.S_IWUSR
    )  # ensure file is not world readable

    config = configparser.ConfigParser()

    # read our config object
    config.read(novem_config)

    # add/update our section
    if not config.has_section(profile):
        config.add_section(profile)

    config.set(profile, "username", username)
    config.set(profile, "api_root", api_root)
    config.set(profile, "token_name", token_name)
    config.set(profile, "token", token)

    with open(novem_config, "w+") as configfile:
        config.write(configfile)

    return (True, novem_config)


def check_if_profile_exists(profile: str) -> bool:
    """
    Check if config dir already contains a valid token for the profile
    """

    (novem_dir, novem_config) = get_config_path()

    # check if path exists
    if not path.exists(novem_config):
        # profile don't exist

        return False

    config = configparser.ConfigParser()

    # read our config object
    config.read(novem_config)

    # add/update our section
    if config.has_section(profile):
        return True

    return False
