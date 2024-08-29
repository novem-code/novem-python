from typing import TYPE_CHECKING

from novem.exceptions import Novem404

if TYPE_CHECKING:
    from novem.vis import NovemVisAPI


class NovemFiles(object):

    def __init__(self, api: "NovemVisAPI") -> None:
        """ """
        self.api: "NovemVisAPI" = api

    def get(self, fn: str) -> str:
        try:
            ctnt = self.api.api_read(f"/files/{fn}")
        except Novem404:
            ctnt = ""

        return ctnt

    @property
    def txt(self) -> str:
        """
        return novem text file
        """
        return self.get(f"{self.api._type}.txt")

    @property
    def ansi(self) -> str:
        """
        return novem ansi representation file
        """
        return self.get(f"{self.api._type}.ansi")

    @property
    def img(self) -> bytes:
        """
        return novem png representation file
        """
        return self.api.api_read_bytes(f"/files/{self.api._type}.png")
