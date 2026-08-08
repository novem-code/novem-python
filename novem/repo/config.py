"""Backwards-compatible alias for the shared coding-resource config.

``NovemRepoConfig`` used to be a standalone class with its own (buggy)
``set`` implementation; the generic :class:`novem.code.NovemCodeConfig`
supersedes it.
"""

from ..code import NovemCodeConfig

NovemRepoConfig = NovemCodeConfig

__all__ = ["NovemRepoConfig"]
