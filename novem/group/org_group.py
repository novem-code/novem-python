from typing import Any

from novem.group import NovemGroupAPI


class OrgGroup(NovemGroupAPI):
    """
    A novem org group
    """

    parent_id: str

    def __init__(self, id: str, parent_id: str, **kwargs: Any) -> None:
        """
        :id org id, duplicate entry will update the org

        """

        self._type = "org_group"

        # set our config
        self._admin_path = f"admin/orgs/{parent_id}/groups"
        self._group_path = "orgs/{$parent_id}/groups"

        self.id = id
        self.parent_id = parent_id

        super().__init__(**kwargs)

    def get_share_string(self) -> str:
        """get our share string"""
        return f"+{self.parent_id}~{self.id}~{self.permissions}"

    def __str__(self) -> str:
        """Return a string representation of roles"""
        return self.get_share_string()
