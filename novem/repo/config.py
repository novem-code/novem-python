from typing import TYPE_CHECKING, Any, Dict

if TYPE_CHECKING:
    from novem.repo import NovemRepoAPI


class NovemRepoConfig:
    """
    Provide utility objects for novem repos
    """

    def __init__(self, api: "NovemRepoAPI") -> None:
        """Initialize the Repo object"""
        self.api: "NovemRepoAPI" = api

    def set(self, config: Dict[str, Any]) -> None:
        """
        Set config options
        """

        props = [x for x in dir(self) if x in ["type"]]

        for k in props:
            v = config[k]
            setattr(self, k, v)

    @property
    def type(self) -> str:
        return self.api.api_read("/config/type").strip()

    @type.setter
    def type(self, value: str) -> None:
        return self.api.api_write("/config/type", value)
