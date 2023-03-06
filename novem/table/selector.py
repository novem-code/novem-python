from typing import Any, Optional

from novem.exceptions import NovemException


class NovemSelectorException(NovemException):
    def __init__(self, message: str):

        message = f"Invalid selector format {message}."

        super().__init__(message)


class Selector(object):
    """
    A novem selector is used for selecting a subset of a table plot
    and applying a style to it
    """

    def __init__(
        self,
        selector: Any,
        applicator: Any,
        r: Any = None,
        c: Optional[str] = None,
        i: Optional[str] = None,
        co: Optional[int] = None,
        io: Optional[int] = None,
    ) -> None:
        """ """

        # TODO: verify that it's a valid novem selector before
        # storing it and throw an error if not
        self.selector = selector
        self.applicator = applicator
        self.ref = r
        self.c = c
        self.i = i
        self.co = co
        self.io = io

    def get_selector_string(self) -> str:
        """ """
        if isinstance(self.selector, str):
            return self.selector

        cols: str = ""
        rows: str = ""

        # if we don't have a columns attribute assume we're a series
        columns: Any = getattr(self.selector, "columns", None)
        index: Any = getattr(self.selector, "index", None)

        if self.ref is None:
            # TODO: Raise exception
            raise NovemSelectorException(
                "We need a reference to correctly infer pandas selections"
            )

        if index is None:
            raise NovemSelectorException(
                "There is no data in our dataframe, we need at "
                "least one value."
            )

        cola = 1
        if self.co:
            cola = cola + self.co

        if columns is None:
            # grab column index of our series name
            try:
                cols = self.ref.columns.get_loc(self.selector.name) + cola
            except KeyError:
                cols = ":"
        else:

            if list(self.selector.columns.values) == list(
                self.ref.columns.values
            ):
                # cols = ":"
                cols = ",".join(
                    [
                        str(self.ref.columns.get_loc(x) + cola)
                        for x in self.selector.columns.values
                    ]
                )
            else:
                cols = ",".join(
                    [
                        str(self.ref.columns.get_loc(x) + cola)
                        for x in self.selector.columns.values
                    ]
                )

        ila = 1
        if self.io:
            ila = ila + self.io

        if list(self.selector.index.values) == list(self.ref.index.values):
            rows = ":"
        else:
            try:
                rows = ",".join(
                    [
                        str(self.ref.index.get_loc(x) + ila)
                        for x in self.selector.index.values
                    ]
                )
            except KeyError:
                rows = self.ref.index.get_loc(self.selector.name) + ila

        if self.c:
            cols = self.c

        if self.i:
            rows = self.i

        return f"{rows} {cols}"

    def __str__(self) -> str:
        """
        return a string representaion of our selector
        """

        return f"{self.get_selector_string()} {self.applicator}"
