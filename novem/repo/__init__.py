"""Novem repos — git repositories under ``code/repos/{id}``.

Historically this module talked to the legacy ``repos/{id}`` alias and
carried its own copies of the shared plumbing. It is now a thin subclass
of :class:`novem.code.NovemCodeAPI`, which gives it the canonical
``code/repos/`` paths plus user-scoping, tags, tree sync and ``api_tree``
for free.
"""

from typing import Any

from ..code import NovemCodeAPI
from ..job.chain import RepoRef
from .config import NovemRepoConfig

__all__ = ["NovemRepoAPI", "Repo", "NovemRepoConfig", "RepoRef"]


class NovemRepoAPI(NovemCodeAPI):
    _collection = "repos"
    _label = "repo"

    # Every entry under ``/commits`` is a browsable directory holding that
    # commit's entire file tree, so an unqualified walk re-reads the whole
    # repo once per commit and gets slower with every push. List the history,
    # and leave expanding a commit to an explicit ``--tree /commits/<sha>``.
    _walk_no_recurse = {"/commits": "commit history"}

    def ref(self, ref: str = "latest") -> RepoRef:
        """A reference to one of this repo's images, by label.

        Labels are ``latest``, ``prod``, ``dev``, ``tag:<name>`` and friends.
        The result is the string ``/<user>/<repo>:<label>`` and can be used
        directly as a job chain step.
        """
        return RepoRef(self.user or self.whoami(), self.id, ref)

    def get_chain_ref(self) -> str:
        """This repo's latest image, as a job chain reference."""
        return self.ref().get_chain_ref()


class Repo(NovemRepoAPI):
    def __init__(self, id: str, **kwargs: Any) -> None:
        self.id = id
        super().__init__(**kwargs)
