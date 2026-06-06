"""Connection-bound resource factory.

A :class:`Session` captures connection overrides (profile, token, api_root,
config_path) and constructs novem resources bound to them — without touching
the process-wide ``novem.config`` defaults. This lets several differently
authenticated contexts coexist in one process::

    prod = novem.Session(profile="production")
    staging = novem.Session(profile="staging")

    prod.Plot("earnings").data = staging.Plot("earnings").data

Each factory method mirrors the corresponding top-level class and simply
threads this session's bound config into the constructor.
"""

from typing import TYPE_CHECKING, Any, Optional

from .config import ConfigManager

if TYPE_CHECKING:
    from .job import Job as _Job
    from .repo import Repo as _Repo
    from .vis.doc import Doc as _Doc
    from .vis.grid import Grid as _Grid
    from .vis.mail import Mail as _Mail
    from .vis.plot import Plot as _Plot

__all__ = ["Session"]


class Session:
    """A connection-bound factory for novem resources."""

    def __init__(
        self,
        *,
        profile: Optional[str] = None,
        token: Optional[str] = None,
        api_root: Optional[str] = None,
        config_path: Optional[str] = None,
        _config_manager: Optional[ConfigManager] = None,
    ) -> None:
        cm = _config_manager or ConfigManager()
        if profile is not None:
            cm.use_profile(profile)
        if token is not None:
            cm.set_token(token)
        if api_root is not None:
            cm.set_api_root(api_root)
        if config_path is not None:
            cm.set_config_path(config_path)
        self._config_manager = cm

    # -- resource factories ------------------------------------------------
    def Plot(self, *args: Any, **kwargs: Any) -> "_Plot":
        from .vis.plot import Plot

        return Plot(*args, config_manager=self._config_manager, **kwargs)

    def Mail(self, *args: Any, **kwargs: Any) -> "_Mail":
        from .vis.mail import Mail

        return Mail(*args, config_manager=self._config_manager, **kwargs)

    def Grid(self, *args: Any, **kwargs: Any) -> "_Grid":
        from .vis.grid import Grid

        return Grid(*args, config_manager=self._config_manager, **kwargs)

    def Doc(self, *args: Any, **kwargs: Any) -> "_Doc":
        from .vis.doc import Doc

        return Doc(*args, config_manager=self._config_manager, **kwargs)

    def Job(self, *args: Any, **kwargs: Any) -> "_Job":
        from .job import Job

        return Job(*args, config_manager=self._config_manager, **kwargs)

    def Repo(self, *args: Any, **kwargs: Any) -> "_Repo":
        from .repo import Repo

        return Repo(*args, config_manager=self._config_manager, **kwargs)
