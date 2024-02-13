from typing import Any, List, Optional

import numpy as np
import pandas as pd

from novem.exceptions import NovemException


class NovemSelectorException(NovemException):
    def __init__(self, message: str):

        message = f"Invalid selector format {message}."

        super().__init__(message)


def enhance_positions(positions: List[int], ior: int) -> List[int]:
    if not positions or not isinstance(ior, int):
        return positions
    if ior == 0:
        return positions
    elif ior < 0:
        return list(range(min(positions) + ior, min(positions))) + positions
    else:  # ior > 0
        return positions + list(range(max(positions) + 1, max(positions) + 1 + ior))


class Selector(object):
    """
    The novem Selector is a convenience function for carving out parts of a
    dataframe for styling

    The purpose of a novem selector is to supply it with a sliced dataframe
    along with the original and the selector will figure out the correct novem
    selector syntax to replicate the sliced dataframe.

    However, due to some idiosyncracies of pandas data frames it's important
    to know the following:

    Novem selectors doesn't have an index or column concept, all rows and
    columns supplied to the api is considered when applying styling, this
    is different from pandas where index and columns are not part of the
    slicing result.

    This means that by default loc and iloc results are offset by 1 in the
    novem output relative to what you would expect from a pandas dataframe

    Similarly, a .loc[:,:] or .iloc[:,:] will produce 1: 1: not : :

    To override this behavior you have the c (column) and i (index) options
    you can manually specify to override the derived values

    There also cannot be duplicate row or index values when using the slicer

    If you have duplicate values we recommend you reset_index and supply
    a co or ci of -1
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
        cor: Optional[int] = None,
        ior: Optional[int] = None,
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
        self.cor = cor
        self.ior = ior

    def _pd_ix_lookup(self) -> str:

        filter = self.selector
        frame = self.ref

        if frame is None:
            # TODO: Raise exception
            raise NovemSelectorException("We need a reference to correctly infer pandas selections")

        if filter is None:
            raise NovemSelectorException("There is no data in our dataframe, we need at " "least one value.")

        # Grab levels
        cl = filter.index.nlevels
        rl = 1

        co = 0
        io = 0
        if self.co:
            co = self.co
        if self.io:
            io = self.io

        cor = 0
        ior = 0
        if self.cor:
            cor = self.cor
        if self.ior:
            ior = self.ior

        # Check if the filter is a DataFrame or a Series
        if isinstance(filter, pd.DataFrame):
            row_indices = filter.index
            col_indices = filter.columns
            rl = filter.columns.nlevels
        else:
            row_indices = filter.index
            col_indices = pd.Index([filter.name])

            # a series can indicate both a single column
            # and a single slicer, we'll have to check key membership
            # on our original frame to be sure, this is not perfect
            # as if all the values are in both the columns and index we
            # have to just guess
            if all(value in frame.columns for value in row_indices):
                row_indices = pd.Index([filter.name])
                col_indices = filter.index
                rl = filter.index.nlevels
                cl = 1

        # TODO: We need to check against values in the frame for our
        # filtered dataset, else we are still failing to account for
        # duplicate values outside of filter

        # Find the row and column positions in the original dataframe
        row_positions = []
        used_positions = set()
        for row_label in row_indices:
            position = frame.index.get_loc(row_label)
            if isinstance(position, np.ndarray):
                position = np.flatnonzero(position)
                position = [pos for pos in position if pos not in used_positions]
                used_positions.update(position[:1])
                row_positions.append(position[0])
            else:
                if position not in used_positions:
                    used_positions.add(position)
                    row_positions.append(position)

        col_positions = []
        used_col_positions = set()
        for col_label in col_indices:
            position = frame.columns.get_loc(col_label)
            if isinstance(position, np.ndarray):
                position = np.flatnonzero(position)
                position = [pos for pos in position if pos not in used_col_positions]
                used_col_positions.update(position[:1])
                col_positions.append(position[0])
            else:
                if position not in used_col_positions:
                    used_col_positions.add(position)
                    col_positions.append(position)

        # convert to novem 0 based index and drop negative offset results
        height = len(frame)
        width = len(frame.columns)
        row_positions = [x + rl + io for x in row_positions if x < height]
        row_positions = enhance_positions(row_positions, ior)
        row_positions = [x for x in row_positions if x >= 0 and x <= height]

        col_positions = [x + cl + co for x in col_positions if x < width]
        col_positions = enhance_positions(col_positions, cor)
        col_positions = [x for x in col_positions if x >= 0 and x <= width]

        # Create a comma-separated list of row and column positions
        row_str = ",".join(map(str, row_positions))
        col_str = ",".join(map(str, col_positions))

        if self.i:
            row_str = self.i

        if self.c:
            col_str = self.c

        # Combine the row and column positions with the provided text
        result = f"{row_str} {col_str}"
        return result

    def get_selector_string(self) -> str:
        """ """
        if isinstance(self.selector, str):
            return self.selector

        return self._pd_ix_lookup()

    def __str__(self) -> str:
        """
        return a string representaion of our selector
        """

        return f"{self.get_selector_string()} {self.applicator}"
