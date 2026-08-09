"""Novem repos — git repositories under ``code/repos/{id}``.

Historically this module talked to the legacy ``repos/{id}`` alias and
carried its own copies of the shared plumbing. It is now a thin subclass
of :class:`novem.code.NovemCodeAPI`, which gives it the canonical
``code/repos/`` paths plus user-scoping, tags, tree sync and ``api_tree``
for free.
"""

from typing import Any

from ..code import NovemCodeAPI
from .config import NovemRepoConfig

__all__ = ["NovemRepoAPI", "Repo", "NovemRepoConfig"]


class NovemRepoAPI(NovemCodeAPI):
    _collection = "repos"
    _label = "repo"


class Repo(NovemRepoAPI):
    def __init__(self, id: str, **kwargs: Any) -> None:
        self.id = id
        super().__init__(**kwargs)
