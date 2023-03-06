from __future__ import annotations

from typing import Optional, Union

from novem.table import Selector

from ..api_ref import NovemAPI

# from novem.table import CellAlign, CellBorder, CellFormat,
# CellPadding, CellText, CellWidth, CellMerge


class IProxy(str):

    p: Optional[NovemCellConfig] = None
    path: str = ""

    # TODO figure out how we can return a new string on demand
    # def __init__(self, parent: Any, path: str) -> None:
    #    self.p = parent
    #    self.path = path

    def __iadd__(self, val: Union[str, Selector]) -> str:
        if not self.p:
            return ""
        cur = self.p.read(self.path)
        es = format(f"{cur}\n{str(val)}")
        return es

    def __str__(self) -> str:
        if not self.p:
            return ""
        return self.p.read(self.path)

    def __repr__(self) -> str:
        if not self.p:
            return ""
        return self.p.read(self.path)


class NovemCellConfig(object):
    def __init__(self, api: NovemAPI) -> None:
        """ """
        self.api: NovemAPI = api
        super().__init__()

    def read(self, path: str) -> str:
        """
        Get list of all shares currently active
        """
        return self.api._read(path)

    def write(self, path: str, value: Union[str, Selector]) -> None:
        """
        replace all shares with the new set
        """

        vls: str = ""
        if isinstance(value, str):
            vls = value
        if isinstance(value, Selector):
            vls = str(value)
        else:
            vls = str(value)

        return self.api._write(path, vls)

    def _proxy(self, path: str) -> str:
        ip = IProxy()
        ip.p = self
        ip.path = path
        return ip

    @property
    def align(self) -> str:
        return self._proxy("/config/table/cell/align")

    @align.setter
    def align(self, style: Union[str, Selector]) -> None:
        return self.write("/config/table/cell/align", style)

    @property
    def border(self) -> str:
        return self._proxy("/config/table/cell/border")

    @border.setter
    def border(self, style: Union[str, Selector]) -> None:
        return self.write("/config/table/cell/border", style)

    @property
    def format(self) -> str:
        return self._proxy("/config/table/cell/format")

    @format.setter
    def format(self, style: Union[str, Selector]) -> None:
        return self.write("/config/table/cell/format", style)

    @property
    def padding(self) -> str:
        return self._proxy("/config/table/cell/padding")

    @padding.setter
    def padding(self, style: Union[str, Selector]) -> None:
        return self.write("/config/table/cell/padding", style)

    @property
    def text(self) -> str:
        return self._proxy("/config/table/cell/text")

    @text.setter
    def text(self, style: Union[str, Selector]) -> None:
        return self.write("/config/table/cell/text", style)

    @property
    def width(self) -> str:
        return self._proxy("/config/table/cell/width")

    @width.setter
    def width(self, style: Union[str, Selector]) -> None:
        return self.write("/config/table/cell/width", style)

    @property
    def merge(self) -> str:
        return self._proxy("/config/table/cell/merge")

    @merge.setter
    def merge(self, style: Union[str, Selector]) -> None:
        return self.write("/config/table/cell/merge", style)
