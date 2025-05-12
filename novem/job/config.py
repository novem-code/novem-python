from typing import TYPE_CHECKING, Any, Dict

if TYPE_CHECKING:
    from novem.job import NovemJobAPI


class NovemJobConfig:
    """
    Provide utility objects for novem jobs
    """

    def __init__(self, api: "NovemJobAPI") -> None:
        """Initialize the Job object"""
        self.api: "NovemJobAPI" = api

    def set(self, config: Dict[str, Any]) -> None:
        """
        Set config options
        """

        props = [x for x in dir(self) if x in ["type"]]

        for k in config.keys():
            if k not in props:
                continue
            v = config[k]
            setattr(self, k, v)

    @property
    def type(self) -> str:
        return self.api.api_read("/config/type").strip()

    @type.setter
    def type(self, value: str) -> None:
        return self.api.api_write("/config/type", value)

    @property
    def extract(self) -> str:
        return self.api.api_read("/config/extract").strip()

    @extract.setter
    def extract(self, value: str) -> None:
        return self.api.api_write("/config/extract", value)

    @property
    def render(self) -> str:
        return self.api.api_read("/config/render").strip()

    @render.setter
    def render(self, value: str) -> None:
        return self.api.api_write("/config/render", value)
