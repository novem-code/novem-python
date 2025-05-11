import json
from typing import TYPE_CHECKING, Any, Dict, Iterator, List, Union

from novem.exceptions import Novem404

if TYPE_CHECKING:
    from novem.group import NovemGroupAPI


class Roles:
    _role_type: str = "NA"

    def __init__(self, api: "NovemGroupAPI", type: str) -> None:
        """Initialize the Roles object"""
        self.api: "NovemGroupAPI" = api
        self._role_type = type

    def get(self) -> List[str]:
        """Get list of all roles currently active"""
        try:
            s = self.api.api_read(f"/roles/{self._role_type}")
            roles = json.loads(s)
            shared = sorted([x["name"] for x in roles])
        except Novem404:
            shared = []
        return shared

    def set(self, share: Union[str, List[str]]) -> None:
        """Replace all roles with the new set"""
        if isinstance(share, str):
            roles = [share]
        else:
            roles = share

        es = self.get()
        rms = set(es) - set(roles)
        adds = set(roles) - set(es)

        # Delete non-empty items
        for r in filter(None, rms):
            self.api.api_delete(f"/roles/{self._role_type}/{r}")

        # Add non-empty items
        for a in filter(None, adds):
            self.api.api_create(f"/roles/{self._role_type}/{a}")

    def __iadd__(self, share: str) -> "Roles":
        """Add a new share to the plot"""
        if share not in self.get():
            self.api.api_create(f"/roles/{self._role_type}/{share}")
        return self

    def __isub__(self, share: str) -> "Roles":
        """Remove a share from the plot"""
        if share in self.get():
            self.api.api_delete(f"/roles/{self._role_type}/{share}")
        return self

    def __eq__(self, other: object) -> bool:
        if isinstance(other, list):
            return self.get() == other
        return NotImplemented

    def __str__(self) -> str:
        """Return a string representation of roles"""
        es = self.get()
        if es:
            return "\n".join(es)
        else:
            return ""

    def __len__(self) -> int:
        """Return the number of roles"""
        es = self.get()
        return len(es) if es else 0

    def __iter__(self) -> Iterator[str]:
        """Allow iteration over roles"""
        return iter(self.get())

    def __getitem__(self, index: Union[int, slice]) -> Union[str, List[str]]:
        """Allow indexing into roles"""
        return self.get()[index]


class NovemRoles(object):
    """
    Novem share
    """

    def __init__(self, api: "NovemGroupAPI") -> None:
        """Initialize the NovemRoles object"""
        self.api: "NovemGroupAPI" = api

        # Store the actual Roles objects as private attributes
        self._founders = Roles(api, "founders")
        self._admins = Roles(api, "admins")
        self._superusers = Roles(api, "superusers")
        self._members = Roles(api, "members")

    def set(self, profile: Dict[str, Any]) -> None:
        """
        Set role members
        """

        props = [x for x in dir(self) if x in ["founders", "members", "admins", "superusers"]]

        for k in profile:
            if k not in props:
                continue
            v = profile[k]
            setattr(self, k, v)

    @property
    def founders(self) -> Roles:
        """Get the founders roles object"""
        return self._founders

    @founders.setter
    def founders(self, value: Union[str, List[str]]) -> None:
        """Set the founders roles"""
        self._founders.set(value)

    @property
    def admins(self) -> Roles:
        """Get the admins roles object"""
        return self._admins

    @admins.setter
    def admins(self, value: Union[str, List[str]]) -> None:
        """Set the admins roles"""
        self._admins.set(value)

    @property
    def superusers(self) -> Roles:
        """Get the superusers roles object"""
        return self._superusers

    @superusers.setter
    def superusers(self, value: Union[str, List[str]]) -> None:
        """Set the superusers roles"""
        self._superusers.set(value)

    @property
    def members(self) -> Roles:
        """Get the members roles object"""
        return self._members

    @members.setter
    def members(self, value: Union[str, List[str]]) -> None:
        """Set the members roles"""
        self._members.set(value)
