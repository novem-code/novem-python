from typing import Final, Optional, Union

from novem.exceptions import NovemException

from ..applicator import Applicator

USEDATA: Final = "_"


# create color exception
class NovemColorException(NovemException):
    def __init__(self, message: str):

        message = f"Invalid color {message}"

        super().__init__(message)


class StaticColor(Applicator):
    def __init__(self, plane: str, color: str, dark: Optional[str] = None) -> None:

        # todo: validate colors and plane
        if plane not in ["bg", "fg"]:
            # TODO: Raise error
            plane = "bg"

        ref = f"{plane} {color}"

        if dark:
            ref = f"{ref} {dark}"

        # construct string
        super().__init__(ref)


class DynamicColor(Applicator):
    def __init__(
        self,
        plane: str,
        min: str = "bad",
        mid: Optional[str] = None,
        max: str = "good",
        vmin: Optional[Union[str, float, int]] = USEDATA,
        vmid: Optional[Union[str, float, int]] = USEDATA,
        vmax: Optional[Union[str, float, int]] = USEDATA,
        dmin: Optional[str] = None,
        dmid: Optional[str] = None,
        dmax: Optional[str] = None,
        interp: str = "lin",
    ) -> None:

        if plane not in ["bg", "fg"]:
            # TODO: Raise error
            plane = "bg"

        ccol = ""
        dcol = ""
        vr = ""

        nc = 3

        if not mid:
            nc = 2
            ccol = f"{min},{max}"
        else:
            ccol = f"{min},{mid},{max}"

        if nc == 2:
            vr = f"{vmin},{vmax}"
        else:
            vr = f"{vmin},{vmid},{vmax}"

        exp = interp
        if interp not in ["lin", "pow", "exp"]:
            exp = "lin"

        vr = f"({vr})^{exp}"

        if dmin:
            if nc == 2:
                dcol = f" {dmin},{dmax}{vr}"
            else:
                dcol = f" {dmin},{dmid},{dmax}{vr}"

        ref = f"{plane} {ccol}{vr}{dcol}"

        # construct string
        super().__init__(ref)
