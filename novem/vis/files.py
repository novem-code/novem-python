from novem.exceptions import Novem404

from ..api_ref import NovemAPI


class NovemFiles(object):
    """
    Novem Files
    """

    # api: NovemAPI = None

    def __init__(self, api: NovemAPI) -> None:
        """ """
        self.api: NovemAPI = api

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
