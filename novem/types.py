from typing import Optional, TypedDict

from typing_extensions import NotRequired

Config = TypedDict(
    "Config",
    {
        "username": NotRequired[str],
        "token": Optional[str],
        "api_root": str,
        "ignore_ssl_warn": bool,
        "profile": NotRequired[str],
        "cli_striped": NotRequired[bool],
        "cli_prompt_lines": NotRequired[int],
    },
)
