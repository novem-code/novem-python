import json
from typing import TYPE_CHECKING, List, Union

from novem.exceptions import Novem404

if TYPE_CHECKING:
    from novem.vis import NovemVisAPI


class NovemShare(object):
    """
    Novem share
    """

    def __init__(self, api: "NovemVisAPI") -> None:
        """ """
        self.api: "NovemVisAPI" = api

    def get(self) -> List[str]:
        """
        Get list of all shares currently active
        """

        try:
            s = self.api.api_read("/shared")
            shares = json.loads(s)
            shared = [x["name"] for x in shares]

        except Novem404:
            shared = []

        return shared

    def set(self, share: Union[str, List[str]]) -> None:
        """
        replace all shares with the new set
        """

        if isinstance(share, str):
            shares = [share]
        else:
            shares = share

        es = self.get()

        rms = set(es) - set(shares)
        adds = set(shares) - set(es)

        for r in rms:
            self.api.api_delete(f"/shared/{r}")

        for a in adds:
            self.api.api_create(f"/shared/{a}")

    def __iadd__(self, share: str) -> List[str]:
        """
        Add a new share to the plot
        """
        es = self.get()
        es.append(share)

        return es

    def __isub__(self, share: str) -> List[str]:
        """
        Remove a share from the plot
        """
        es = self.get()
        ns = set(es) - set([share])

        return list(ns)
