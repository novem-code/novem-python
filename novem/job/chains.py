from typing import TYPE_CHECKING, Any, Iterator

from ..api_ref import Novem404, NovemChainError
from .chain import Chain, Step

if TYPE_CHECKING:
    from novem.job import NovemJobAPI


class NovemJobChains:
    """A job's chain, exposed at ``config/chains``.

    Assigning replaces the chain with one write::

        job.chains = {"fetch": fetch_repo, "render": render_repo.ref("prod")}

    Item assignment, ``+=`` and ``del`` read the stored chain, edit it and
    write it back.
    """

    def __init__(self, api: "NovemJobAPI") -> None:
        self.api: "NovemJobAPI" = api

    @property
    def text(self) -> str:
        """The chain as stored, or an empty string when there is none."""
        try:
            return self.api.api_read("/config/chains").strip()
        except Novem404:
            return ""

    def get(self) -> Chain:
        """The stored chain, parsed."""
        return Chain(self.text)

    def set(self, chain: Any) -> None:
        """Validate ``chain`` and write it, replacing the current one."""
        if self.api._legacy_runtime():
            raise NovemChainError(
                f"Job '{self.api.id}' was given type '{self.api._runtime}', which has no chain; use type='chains'"
            )
        text = str(Chain(chain).validate())
        if self.api._runtime is None:
            # a chain only runs on a job of the chains type; older jobs may
            # still be of another type, and writing the same type is a no-op
            self.api.type = "chains"
        self.api.api_write("/config/chains", text)

    def clear(self) -> None:
        """Remove the chain."""
        try:
            self.api.api_delete("/config/chains")
        except Novem404:
            pass

    def __getitem__(self, name: str) -> Step:
        return self.get()[name]

    def __setitem__(self, name: str, value: Any) -> None:
        chain = self.get()
        chain[name] = value
        self.set(chain)

    def __delitem__(self, name: str) -> None:
        chain = self.get()
        del chain[name]
        self.set(chain)

    def __iadd__(self, other: Any) -> "NovemJobChains":
        chain = self.get()
        chain += other
        self.set(chain)
        return self

    def __eq__(self, other: object) -> bool:
        owner = self.api.user or self.api.whoami()
        try:
            return Chain(self.text, owner=owner) == Chain(other, owner=owner)
        except NovemChainError:
            return NotImplemented

    __hash__ = None  # type: ignore[assignment]

    def __contains__(self, name: object) -> bool:
        return name in self.get()

    def __iter__(self) -> Iterator[Step]:
        return iter(self.get())

    def __len__(self) -> int:
        return len(self.get())

    def __str__(self) -> str:
        return self.text
