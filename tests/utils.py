import os

from novem.utils import get_config_path


def file_exists(path):
    # verify that our config is missing
    exist = True
    try:
        os.stat(path)
    except OSError:
        exist = False

    return exist


def print_file(path):
    with open(path, "r") as f:
        print("".join(f.readlines()))


def write_config(obj):
    (cfolder, cpath) = get_config_path()

    ctxt = f"""
[general]
profile = demouser
api_root = https://api.novem.io/v1/

[app:cli]
version = 0.5.0

[app:pylib]

[app:fuse]

[profile:demouser]
username = {obj["username"]}
token_name = {obj["token_name"]}
token = demo_token_abc
"""

    os.makedirs(cfolder, exist_ok=True)

    with open(cpath, "w") as f:
        f.write(ctxt)
