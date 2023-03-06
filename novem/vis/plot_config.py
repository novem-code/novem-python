"""
Config object for the standard plot structure
exposes the tree hierarchy with easy getters and setters
"""

from ..api_ref import NovemAPI


class NovemConfigBase(object):
    def __init__(self, api: NovemAPI) -> None:
        """ """
        self.api: NovemAPI = api

    def set(self, path: str, value: str) -> None:
        return self.api._write(path, value)

    def get(self, path: str) -> str:
        return self.api._read(path)


class NovemConfigLegend(NovemConfigBase):
    @property
    def format(self) -> str:
        return self.get("/config/legend/format")

    @format.setter
    def format(self, val: str) -> None:
        return self.set("/config/legend/format", val)

    @property
    def layout(self) -> str:
        return self.get("/config/legend/layout")

    @layout.setter
    def layout(self, val: str) -> None:
        return self.set("/config/legend/layout", val)

    @property
    def position(self) -> str:
        return self.get("/config/legend/position")

    @position.setter
    def position(self, val: str) -> None:
        return self.set("/config/legend/position", val)

    @property
    def type(self) -> str:
        return self.get("/config/legend/type")

    @type.setter
    def type(self, val: str) -> None:
        return self.set("/config/legend/type", val)


class NovemPlotConfig(object):
    def __init__(self, api: NovemAPI) -> None:
        """ """
        self.api: NovemAPI = api

        self.legend = NovemConfigLegend(api)
