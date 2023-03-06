from typing import Union

from novem.table import Selector

from ..api_ref import NovemAPI


class NovemColors(object):
    def __init__(self, api: NovemAPI) -> None:
        """ """
        self.api: NovemAPI = api
        super().__init__()

    def get(self) -> str:
        """
        Get list of all shares currently active
        """

        return self.api._read("/config/colors/colors")

    def set(self, colors: Union[str, Selector]) -> None:
        """
        replace all shares with the new set
        """

        cls: str = ""
        if isinstance(colors, str):
            cls = colors
        if isinstance(colors, Selector):
            cls = str(colors)
        else:
            cls = str(colors)

        return self.api._write("/config/colors/colors", cls)

    @property
    def type(self) -> str:
        """
        get the color type
        """
        return self.api._read("/config/colors/type")

    @type.setter
    def type(self, value: str) -> None:
        """
        Set the color type
        """
        return self.api._write("/config/colors/type", value)

    def __iadd__(self, style: Union[str, Selector]) -> str:
        """
        Add more styles to the plot
        """
        es = format(f"{self.get()}\n{str(style)}")
        return es

    def __repr__(self) -> str:
        return self.get()

    def __str__(self) -> str:
        return self.get()
