"""Connection configuration for the novem client.

This module separates *connection* config (how to reach and authenticate to
the API) from the *content* kwargs that flow through the visualisation
classes.  It exposes:

* :class:`NovemConfig` -- a resolved, immutable view of a connection.
* :func:`resolve` -- the single entry point that turns explicit arguments and
  the global defaults into a :class:`NovemConfig`.  Precedence and the actual
  file/env reading still live in :func:`novem.utils.get_current_config`; this
  layer only injects the globally configured overrides on top.
* :data:`config` -- a process-wide :class:`ConfigManager` singleton so callers
  can do ``novem.config.set_token(...)`` once and then construct plots, mails,
  etc. without repeating credentials.

The split lets a user write either::

    import novem
    novem.config.set_token("...")
    p = novem.Plot("my-plot")          # uses the global default

or override per call (explicit always wins over the global default)::

    p = novem.Plot("my-plot", token="...")
"""

from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

from .types import Config
from .utils import API_ROOT, get_current_config

__all__ = ["NovemConfig", "ConfigManager", "resolve", "config"]


@dataclass(frozen=True)
class NovemConfig:
    """A fully resolved connection configuration."""

    token: Optional[str]
    api_root: str
    username: Optional[str] = None
    profile: Optional[str] = None
    ignore_ssl: bool = False

    @classmethod
    def _from_legacy(cls, co: "Config") -> "NovemConfig":
        """Build from the legacy ``Config`` dict returned by utils."""
        return cls(
            token=co.get("token"),
            api_root=co.get("api_root") or API_ROOT,
            username=co.get("username"),
            profile=co.get("profile"),
            ignore_ssl=co.get("ignore_ssl_warn", False),
        )


class ConfigManager:
    """Process-wide mutable connection defaults.

    Records only the fields the caller explicitly sets; resolution still
    merges these on top of the config file, environment and built-in defaults
    via :func:`resolve`.  Setting a field to ``None`` clears that override.
    """

    def __init__(self) -> None:
        self._overrides: Dict[str, Any] = {}

    def _set(self, key: str, value: Any) -> None:
        if value is None:
            self._overrides.pop(key, None)
        else:
            self._overrides[key] = value

    # -- explicit setters -------------------------------------------------
    def set_token(self, token: Optional[str]) -> None:
        """Set the API token used for subsequent connections."""
        self._set("token", token)

    def set_api_root(self, api_root: Optional[str]) -> None:
        """Set the API root URL used for subsequent connections."""
        self._set("api_root", api_root)

    def use_profile(self, profile: Optional[str]) -> None:
        """Select which ``[profile:...]`` from the config file to use."""
        self._set("config_profile", profile)

    def set_config_path(self, path: Optional[str]) -> None:
        """Override the path the config file is read from."""
        self._set("config_path", path)

    def set_ignore_ssl(self, ignore_ssl: bool) -> None:
        """Disable SSL certificate verification for subsequent connections."""
        # only True is meaningful; absence == verify
        self._set("ignore_ssl", ignore_ssl or None)

    def reset(self) -> None:
        """Clear all programmatically set overrides."""
        self._overrides.clear()

    # -- internal ---------------------------------------------------------
    def merge(self, explicit: Dict[str, Any]) -> Dict[str, Any]:
        """Merge explicit kwargs over the stored overrides.

        Explicit (per-call) values win over global defaults.  ``None`` values
        in ``explicit`` mean "not supplied" and never clobber an override.
        """
        merged = dict(self._overrides)
        for key, value in explicit.items():
            if value is not None:
                merged[key] = value
        return merged


# process-wide singleton
config = ConfigManager()


def resolve(
    *,
    default: Optional[ConfigManager] = None,
    **kwargs: Any,
) -> Tuple[bool, NovemConfig]:
    """Resolve a :class:`NovemConfig` from explicit kwargs + global defaults.

    Returns ``(found, cfg)`` mirroring :func:`get_current_config`, where
    ``found`` is ``False`` when no usable config source could be located (the
    caller decides whether that is fatal).
    """
    if default is None:
        default = config

    # `profile` is the public-facing alias for the internal `config_profile`
    # selector; normalise before merging so an explicit profile still wins
    # over a globally configured one.
    if "profile" in kwargs:
        kwargs.setdefault("config_profile", kwargs.pop("profile"))

    merged = default.merge(kwargs)
    found, co = get_current_config(**merged)
    return found, NovemConfig._from_legacy(co)
