import json
from typing import TYPE_CHECKING, Iterator, List, Union

from typing_extensions import Protocol, runtime_checkable

from novem.exceptions import Novem404

if TYPE_CHECKING:
    from ..api_ref import NovemAPI


@runtime_checkable
class HasShareString(Protocol):
    def get_share_string(self) -> str: ...


def get_share_value(share_item: Union[str, HasShareString]) -> str:
    """
    Extract the share string from a share item

    - If string, return as is
    - If object with get_share_string() method, return that result
    """
    if isinstance(share_item, str):
        return share_item
    return share_item.get_share_string()


class NovemShare:
    """
    Novem share

    Novem shares are exposed at:
      f"{api._api_root}{share_path}/shared"
    """

    def __init__(self, api: "NovemAPI", share_path: str) -> None:
        """Initialize the Share object"""
        self.api: "NovemAPI" = api
        self.share_path = share_path

    def get(self) -> List[str]:
        """
        Get list of all shares currently active
        """
        try:
            path = f"{self.share_path}/shared"
            s = self.api.read(path)
            shares = json.loads(s)
            shared = sorted([x["name"] for x in shares])
        except Novem404:
            shared = []

        return shared

    def set(self, share: Union[str, HasShareString, List[Union[str, HasShareString]]]) -> None:
        """
        replace all shares with the new set

        Args:
            share: A string, a shareable object with get_share_string() method,
                  or a list of either strings or shareable objects
        """
        # Convert to a list of share strings
        if isinstance(share, (str, HasShareString)):
            share_value = get_share_value(share)
            shares = [share_value] if share_value else []
        else:
            # Process list items to convert objects to their share strings
            shares = [get_share_value(s) for s in share if s]
            # Filter out empty strings
            shares = [s for s in shares if s]

        # If the list was non-empty but all items resulted in empty strings,
        # don't change the existing shares
        if isinstance(share, list) and share and not shares:
            return

        es = self.get()
        rms = set(es) - set(shares)
        adds = set(shares) - set(es)

        # Delete non-empty items
        for r in filter(None, rms):
            path = f"{self.share_path}/shared/{r}"
            self.api.delete(path)

        # Add non-empty items
        for a in filter(None, adds):
            path = f"{self.share_path}/shared/{a}"
            self.api.create(path)

    def __iadd__(self, share: Union[str, HasShareString]) -> "NovemShare":
        """
        Add a new share to the collection

        Args:
            share: A string or an object with get_share_string() method
        """
        share_value = get_share_value(share)
        if share_value and share_value not in self.get():
            path = f"{self.share_path}/shared/{share_value}"
            self.api.create(path)
        return self

    def __isub__(self, share: Union[str, HasShareString]) -> "NovemShare":
        """
        Remove a share from the collection

        Args:
            share: A string or an object with get_share_string() method
        """
        share_value = get_share_value(share)
        if share_value and share_value in self.get():
            path = f"{self.share_path}/shared/{share_value}"
            self.api.delete(path)
        return self

    def __eq__(self, other: object) -> bool:
        """
        Check if the shares are equal to the given object

        Supports comparison with:
        - List of strings
        - List of shareable objects
        - Mixed list of strings and shareable objects
        """
        if isinstance(other, list):
            # Convert all items in the other list to share strings
            other_shares = []
            for item in other:
                if isinstance(item, str):
                    other_shares.append(item)
                elif hasattr(item, "get_share_string"):
                    other_shares.append(item.get_share_string())
                else:
                    # If we get something we don't understand, return False
                    return False

            # Compare the string representations
            return set(self.get()) == set(other_shares)
        return NotImplemented

    def __str__(self) -> str:
        """
        Return a string representation of shares
        """
        es = self.get()
        if es:
            return "\n".join(es)
        else:
            return ""

    def __len__(self) -> int:
        """Return the number of shares"""
        es = self.get()
        return len(es) if es else 0

    def __iter__(self) -> Iterator[str]:
        """Allow iteration over shares"""
        return iter(self.get())

    def __getitem__(self, index: Union[int, slice]) -> Union[str, List[str]]:
        """Allow indexing into shares"""
        return self.get()[index]
