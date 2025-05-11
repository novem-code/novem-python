from typing import Any

from novem.group import NovemGroupAPI

from .org_group import OrgGroup


class Org(NovemGroupAPI):
    """
    A novem org group
    """

    def __init__(self, id: str, **kwargs: Any) -> None:
        """
        :id org id, duplicate entry will update the org

        """

        self._type = "org"

        # set our config
        self._admin_path = "admin/orgs"
        self._group_path = "orgs"

        self.id = id

        super().__init__(**kwargs)

    def Group(self, group_id: str, **kwargs: Any) -> OrgGroup:
        """
        Return a org-group linked to this organisation
        """
        return OrgGroup(group_id, self.id, **kwargs)

    def get_share_string(self) -> str:
        """get our share string"""
        # TODO: we should really throw an error here, as orgs have no "share string"
        return f"+{self.id}"

    def __str__(self) -> str:
        """Return a string representation of roles"""
        return f"+{self.id}"
