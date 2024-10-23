from typing import List, Optional, Tuple, Union

try:
    import pandas as pd
except ImportError:
    pd = None  # type: ignore


def merge_from_index(src: Union[pd.DataFrame, pd.Index], io: Optional[int] = None) -> str:
    """
    Create novem merge instructions based on a supplied pandas DataFrame or Index object.

    This function analyzes the structure of the input DataFrame or Index and generates
    a set of merge instructions. These instructions describe how to merge cells to
    replicate the hierarchical structure of the input in a tabular format.
    Single cell merges are skipped.

    Args:
        src (Union[pd.DataFrame, pd.Index]): The source DataFrame or Index object to analyze.
        io (Optional[int]): Initial offset. If provided, overrides the calculated offset.
            Use this to account for additional header rows.

    Returns:
        str: A string of newline-separated merge instructions. Each instruction has the format:
             "start:end column label"
             where:
             - start:end is the range of rows to merge
             - column is the column index
             - label is a unique identifier for the merged cell

    Raises:
        TypeError: If src is not a pandas DataFrame or Index object.

    Example:
        >>> import pandas as pd
        >>> df = pd.DataFrame(index=[['A', 'A', 'B', 'B', 'C'],
        ...                          ['X', 'Y', 'Z', 'W', 'V']])
        >>> print(merge_from_index(df))
        1:2 0 lbl1
        3:4 0 lbl2
        >>>
        >>> # Using a MultiIndex directly
        >>> idx = pd.MultiIndex.from_product([['P', 'Q'], ['1', '2', '3']])
        >>> print(merge_from_index(idx))
        1:3 0 lbl1
        4:6 0 lbl2
        >>>
        >>> # Using a custom initial offset
        >>> print(merge_from_index(df, io=2))
        2:3 0 lbl1
        4:5 0 lbl2
    """
    if not isinstance(src, (pd.DataFrame, pd.Index)):
        raise TypeError("Input must be a pandas DataFrame or Index object")

    if isinstance(src, pd.DataFrame):
        index = src.index
        aio = src.columns.nlevels
    else:
        index = src
        aio = 1

    if io is not None:
        aio = io

    if not isinstance(index, pd.MultiIndex):
        index = pd.MultiIndex.from_arrays([index])

    if len(index) == 0:
        return ""  # Return empty string for empty index

    merge_instructions: List[str] = []
    for level in range(index.nlevels):
        current_label = None
        start_row = 0

        for row, label in enumerate(index.get_level_values(level)):
            if label == current_label:
                continue
            if current_label is not None and start_row < row - 1:
                merge_instructions.append(f"{start_row + aio}:{row + aio - 1} {level} lbl{len(merge_instructions) + 1}")
            current_label = label
            start_row = row

        if start_row < row:
            merge_instructions.append(f"{start_row + aio}:{row + aio} {level} lbl{len(merge_instructions) + 1}")

    return "\n".join(merge_instructions)


def find_index_breaks(
    src: Union[pd.DataFrame, pd.Index], io: Optional[int] = None, level: Optional[int] = None
) -> Tuple[List[int], int, int]:
    """
    Find the points where groups change in an index and calculate relevant metadata.

    Args:
        src (Union[pd.DataFrame, pd.Index]): The source DataFrame or Index object to analyze.
        io (Optional[int]): Initial offset. If provided, overrides the calculated offset.
        level (Optional[int]): The level of the MultiIndex to analyze. If None, uses the
            innermost (most granular) level.

    Returns:
        Tuple[List[int], int, int]: A tuple containing:
            - List of row indices where groups begin (break points)
            - The calculated offset value
            - Total length of the source data
    """
    if not isinstance(src, (pd.DataFrame, pd.Index)):
        raise TypeError("Input must be a pandas DataFrame or Index object")

    if isinstance(src, pd.DataFrame):
        index = src.index
        aio = src.columns.nlevels
    else:
        index = src
        aio = 1

    offset = io if io is not None else aio

    if not isinstance(index, pd.MultiIndex):
        index = pd.MultiIndex.from_arrays([index])

    total_length = len(index)
    if total_length == 0:
        return [], offset, 0

    if level is None:
        actual_level = index.nlevels - 1
    else:
        actual_level = level if level >= 0 else index.nlevels + level

    if not 0 <= actual_level < index.nlevels:
        raise ValueError(f"Level {level} out of range for index with {index.nlevels} levels")

    break_points: List[int] = []
    current_label = None

    for row, label in enumerate(index.get_level_values(actual_level)):
        if label != current_label:
            break_points.append(row)
            current_label = label

    return break_points, offset, total_length


def merge_from_index_first_rows(
    src: Union[pd.DataFrame, pd.Index], io: Optional[int] = None, level: Optional[int] = None
) -> str:
    """
    Get comma-separated list of first rows from each merge group at specified level.

    Args:
        src (Union[pd.DataFrame, pd.Index]): The source DataFrame or Index object to analyze.
        io (Optional[int]): Initial offset. If provided, overrides the calculated offset.
        level (Optional[int]): The level of the MultiIndex to analyze. If None, uses the
            innermost (most granular) level.

    Returns:
        str: Comma-separated list of row numbers representing first rows of merged sections
    """
    break_points, offset, _ = find_index_breaks(src, io, level)
    if not break_points:
        return ""
    return ",".join(str(point + offset) for point in break_points)


def merge_from_index_last_rows(
    src: Union[pd.DataFrame, pd.Index], io: Optional[int] = None, level: Optional[int] = None
) -> str:
    """
    Get comma-separated list of last rows from each merge group at specified level.

    Args:
        src (Union[pd.DataFrame, pd.Index]): The source DataFrame or Index object to analyze.
        io (Optional[int]): Initial offset. If provided, overrides the calculated offset.
        level (Optional[int]): The level of the MultiIndex to analyze. If None, uses the
            innermost (most granular) level.

    Returns:
        str: Comma-separated list of row numbers representing last rows of merged sections
    """
    break_points, offset, total_length = find_index_breaks(src, io, level)
    if not break_points:
        return ""

    last_rows: List[int] = []

    # Handle groups before the last one
    for i in range(len(break_points) - 1):
        last_rows.append(break_points[i + 1] - 1)

    # Handle the last group
    last_rows.append(total_length - 1)

    return ",".join(str(row + offset) for row in last_rows)
