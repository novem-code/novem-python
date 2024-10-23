import numpy as np
import pandas as pd
import pytest

from novem.table.utils import merge_from_index, merge_from_index_first_rows, merge_from_index_last_rows


@pytest.fixture
def sample_dataframe():
    return pd.DataFrame(index=[["A", "A", "B", "B", "C"], ["X", "Y", "Z", "W", "V"]])


@pytest.fixture
def sample_multiindex():
    return pd.MultiIndex.from_product([["P", "Q"], ["1", "2", "3"]])


def test_dataframe_with_multiindex(sample_dataframe):
    result = merge_from_index(sample_dataframe)
    expected = "1:2 0 lbl1\n3:4 0 lbl2"
    assert result == expected


def test_dataframe_single_level_index():
    df = pd.DataFrame(index=["A", "B", "C"])
    result = merge_from_index(df)
    assert result == ""


def test_multiindex_directly(sample_multiindex):
    result = merge_from_index(sample_multiindex)
    expected = "1:3 0 lbl1\n4:6 0 lbl2"
    assert result == expected


def test_dataframe_custom_offset(sample_dataframe):
    result = merge_from_index(sample_dataframe, io=2)
    expected = "2:3 0 lbl1\n4:5 0 lbl2"
    assert result == expected


def test_single_entry_index():
    index = pd.Index(["Single"])
    result = merge_from_index(index)
    assert result == ""


def test_dataframe_alternating_values():
    df = pd.DataFrame(index=[["A", "B", "A", "B"], ["X", "Y", "Z", "W"]])
    result = merge_from_index(df)
    assert result == ""


def test_dataframe_single_column():
    df = pd.DataFrame({"A": [1, 2, 3]}, index=[["X", "X", "Y"], ["1", "2", "3"]])
    result = merge_from_index(df)
    expected = "1:2 0 lbl1"
    assert result == expected


def test_dataframe_multiple_column_levels():
    df = pd.DataFrame(
        np.random.rand(4, 4),
        columns=pd.MultiIndex.from_product([["A", "B"], ["X", "Y"]]),
        index=pd.MultiIndex.from_product([["P", "Q"], ["1", "2"]]),
    )
    result = merge_from_index(df)
    expected = "2:3 0 lbl1\n4:5 0 lbl2"
    assert result == expected


def test_large_multiindex():
    large_index = pd.MultiIndex.from_product([["A", "B", "C"], ["X", "Y", "Z"], ["1", "2", "3", "4"]])
    result = merge_from_index(large_index)
    expected = (
        "1:12 0 lbl1\n13:24 0 lbl2\n25:36 0 lbl3\n1:4 1 lbl4\n5:8 1 lbl5\n9:12 1 lbl6\n13:16 1 lbl7\n"
        "17:20 1 lbl8\n21:24 1 lbl9\n25:28 1 lbl10\n29:32 1 lbl11\n33:36 1 lbl12"
    )
    assert result == expected


def test_mixed_multiindex():
    mixed_index = pd.MultiIndex.from_tuples(
        [("A", "X", 1), ("A", "X", 2), ("A", "Y", 1), ("B", "X", 1), ("B", "Y", 1), ("B", "Y", 2)]
    )
    result = merge_from_index(mixed_index)
    expected = "1:3 0 lbl1\n4:6 0 lbl2\n1:2 1 lbl3\n5:6 1 lbl4\n3:5 2 lbl5"
    assert result == expected


def test_zero_initial_offset():
    df = pd.DataFrame(index=[["A", "A", "B"], ["X", "Y", "Z"]])
    result = merge_from_index(df, io=0)
    expected = "0:1 0 lbl1"
    assert result == expected


def test_very_large_offset():
    df = pd.DataFrame(index=[["A", "A", "B"], ["X", "Y", "Z"]])
    result = merge_from_index(df, io=1000)
    expected = "1000:1001 0 lbl1"
    assert result == expected


def test_single_level_multiindex_no_merges():
    index = pd.MultiIndex.from_tuples([("A",), ("B",), ("C",)])
    result = merge_from_index(index)
    assert result == ""


def test_all_unique_values_multiindex():
    index = pd.MultiIndex.from_tuples([("A", "X"), ("B", "Y"), ("C", "Z")])
    result = merge_from_index(index)
    assert result == ""


def test_first_rows_basic(sample_dataframe):
    """Test basic functionality of first_rows with default level"""
    assert merge_from_index_first_rows(sample_dataframe) == "1,2,3,4,5"


def test_last_rows_basic(sample_dataframe):
    """Test basic functionality of last_rows with default level"""
    assert merge_from_index_last_rows(sample_dataframe) == "1,2,3,4,5"


def test_first_rows_level_0(sample_dataframe):
    """Test first_rows with explicit level 0"""
    assert merge_from_index_first_rows(sample_dataframe, level=0) == "1,3,5"


def test_last_rows_level_0(sample_dataframe):
    """Test last_rows with explicit level 0"""
    assert merge_from_index_last_rows(sample_dataframe, level=0) == "2,4,5"


def test_first_rows_with_offset(sample_dataframe):
    """Test first_rows with custom offset"""
    assert merge_from_index_first_rows(sample_dataframe, io=2, level=0) == "2,4,6"


def test_last_rows_with_offset(sample_dataframe):
    """Test last_rows with custom offset"""
    assert merge_from_index_last_rows(sample_dataframe, io=2, level=0) == "3,5,6"


def test_first_rows_multiindex(sample_multiindex):
    """Test first_rows with MultiIndex"""
    assert merge_from_index_first_rows(sample_multiindex, level=0) == "1,4"


def test_last_rows_multiindex(sample_multiindex):
    """Test last_rows with MultiIndex"""
    assert merge_from_index_last_rows(sample_multiindex, level=0) == "3,6"


def test_negative_level(sample_dataframe):
    """Test behavior with negative level indexing"""
    assert merge_from_index_first_rows(sample_dataframe, level=-1) == "1,2,3,4,5"
    assert merge_from_index_last_rows(sample_dataframe, level=-1) == "1,2,3,4,5"


def test_empty_dataframe():
    """Test behavior with empty DataFrame"""
    df = pd.DataFrame(index=pd.MultiIndex.from_arrays([[], []]))
    assert merge_from_index_first_rows(df) == ""
    assert merge_from_index_last_rows(df) == ""


def test_single_level_index():
    """Test behavior with single-level index"""
    df = pd.DataFrame(index=["A", "B", "C"])
    assert merge_from_index_first_rows(df) == "1,2,3"
    assert merge_from_index_last_rows(df) == "1,2,3"


def test_invalid_level(sample_dataframe):
    """Test error handling for invalid level"""
    with pytest.raises(ValueError, match="Level .* out of range"):
        merge_from_index_first_rows(sample_dataframe, level=5)
    with pytest.raises(ValueError, match="Level .* out of range"):
        merge_from_index_last_rows(sample_dataframe, level=5)


def test_invalid_input():
    """Test error handling for invalid input type"""
    with pytest.raises(TypeError, match="Input must be a pandas DataFrame or Index object"):
        merge_from_index_first_rows([1, 2, 3])
    with pytest.raises(TypeError, match="Input must be a pandas DataFrame or Index object"):
        merge_from_index_last_rows([1, 2, 3])


@pytest.fixture
def complex_multiindex():
    """Fixture for testing more complex hierarchical structures"""
    arrays = [["A", "A", "A", "B", "B", "C"], ["X", "X", "Y", "Z", "Z", "W"], ["1", "2", "3", "4", "5", "6"]]
    return pd.MultiIndex.from_arrays(arrays)


def test_complex_hierarchy_first_rows(complex_multiindex):
    """Test first_rows with complex hierarchical index at different levels"""
    df = pd.DataFrame(index=complex_multiindex)
    assert merge_from_index_first_rows(df, level=0) == "1,4,6"  # A, B, C groups
    assert merge_from_index_first_rows(df, level=1) == "1,3,4,6"  # X, Y, Z, W groups


def test_complex_hierarchy_last_rows(complex_multiindex):
    """Test last_rows with complex hierarchical index at different levels"""
    df = pd.DataFrame(index=complex_multiindex)
    assert merge_from_index_last_rows(df, level=0) == "3,5,6"  # A, B, C groups
    assert merge_from_index_last_rows(df, level=1) == "2,3,5,6"  # X, Y, Z, W groups


@pytest.fixture
def sparse_multiindex():
    """Fixture for testing sparse/irregular hierarchical structures"""
    arrays = [
        ["A", "A", "A", "B", "B", "B", "C"],
        ["X", "X", None, "Y", None, "Y", "Z"],
        ["1", "2", "3", "4", "5", "6", "7"],
    ]
    return pd.MultiIndex.from_arrays(arrays)


@pytest.fixture
def duplicate_values_multiindex():
    """Fixture for testing repeated values across different levels"""
    arrays = [["A", "A", "A", "A", "B", "B"], ["X", "X", "X", "Y", "X", "X"], ["1", "1", "2", "3", "1", "2"]]
    return pd.MultiIndex.from_arrays(arrays)


def test_sparse_hierarchy_first_rows(sparse_multiindex):
    """Test first_rows with sparse hierarchical index containing None values"""
    df = pd.DataFrame(index=sparse_multiindex)
    # None is treated as a distinct value in pandas grouping
    assert merge_from_index_first_rows(df, level=1) == "1,3,4,5,6,7"  # X, None, Y, None, Y, Z groups
    assert merge_from_index_first_rows(df, level=0) == "1,4,7"  # A, B, C groups


def test_sparse_hierarchy_last_rows(sparse_multiindex):
    """Test last_rows with sparse hierarchical index containing None values"""
    df = pd.DataFrame(index=sparse_multiindex)
    # None is treated as a distinct value in pandas grouping
    assert merge_from_index_last_rows(df, level=1) == "2,3,4,5,6,7"  # X, None, Y, None, Y, Z groups
    assert merge_from_index_last_rows(df, level=0) == "3,6,7"  # A, B, C groups


def test_duplicate_values_first_rows(duplicate_values_multiindex):
    """Test first_rows with duplicate values across different levels"""
    df = pd.DataFrame(index=duplicate_values_multiindex)
    assert merge_from_index_first_rows(df, level=0) == "1,5"  # A, B groups
    assert merge_from_index_first_rows(df, level=1) == "1,4,5"  # X, Y, X groups


def test_duplicate_values_last_rows(duplicate_values_multiindex):
    """Test last_rows with duplicate values across different levels"""
    df = pd.DataFrame(index=duplicate_values_multiindex)
    assert merge_from_index_last_rows(df, level=0) == "4,6"  # A, B groups
    assert merge_from_index_last_rows(df, level=1) == "3,4,6"  # X, Y, X groups


def test_cross_level_interactions():
    """Test interactions between levels with overlapping values"""
    arrays = [["A", "A", "B", "B", "B"], ["B", "C", "A", "A", "C"]]
    index = pd.MultiIndex.from_arrays(arrays)
    df = pd.DataFrame(index=index)

    assert merge_from_index_first_rows(df, level=0) == "1,3"  # A, B groups
    assert merge_from_index_first_rows(df, level=1) == "1,2,3,5"  # B, C, A, C groups

    assert merge_from_index_last_rows(df, level=0) == "2,5"  # A, B groups
    assert merge_from_index_last_rows(df, level=1) == "1,2,4,5"  # B, C, A, C groups


def test_single_item_groups():
    """Test behavior with single-item groups at different levels"""
    arrays = [["A", "A", "B", "C", "D"], ["X", "X", "Y", "Y", "Z"]]
    index = pd.MultiIndex.from_arrays(arrays)
    df = pd.DataFrame(index=index)

    assert merge_from_index_first_rows(df, level=0) == "1,3,4,5"  # A, B, C, D groups
    assert merge_from_index_last_rows(df, level=0) == "2,3,4,5"  # A, B, C, D groups


def test_level_boundary_conditions():
    """Test boundary conditions for level parameter"""
    df = pd.DataFrame(index=pd.MultiIndex.from_arrays([["A", "B"], ["X", "Y"]]))

    # Test with exact level boundaries
    assert merge_from_index_first_rows(df, level=0) == "1,2"
    assert merge_from_index_first_rows(df, level=1) == "1,2"
    assert merge_from_index_first_rows(df, level=-1) == "1,2"
    assert merge_from_index_first_rows(df, level=-2) == "1,2"

    # Test invalid boundaries
    with pytest.raises(ValueError):
        merge_from_index_first_rows(df, level=2)
    with pytest.raises(ValueError):
        merge_from_index_first_rows(df, level=-3)


def test_dataframe_with_columns():
    """Test behavior when DataFrame has multiple column levels"""
    df = pd.DataFrame(
        columns=pd.MultiIndex.from_arrays([["A", "A", "B"], ["X", "Y", "Z"]]),
        index=pd.MultiIndex.from_arrays([["P", "P", "Q"], ["1", "2", "3"]]),
    )

    # Offset should be number of column levels (2)
    assert merge_from_index_first_rows(df, level=0) == "2,4"  # P, Q groups
    assert merge_from_index_last_rows(df, level=0) == "3,4"  # P, Q groups


def test_single_row_groups():
    """Test behavior with single-row groups mixed with multi-row groups"""
    arrays = [
        ["A", "A", "B", "C", "D", "D"],  # Mix of single and multi-row groups
        ["X", "X", "Y", "Z", "W", "W"],  # Same pattern in second level
    ]
    index = pd.MultiIndex.from_arrays(arrays)
    df = pd.DataFrame(index=index)

    # Test level 0 (A=2 rows, B=1 row, C=1 row, D=2 rows)
    assert merge_from_index_first_rows(df, level=0) == "1,3,4,5"  # First row of each group
    assert merge_from_index_last_rows(df, level=0) == "2,3,4,6"  # Last row of each group

    # Test level 1 (X=2 rows, Y=1 row, Z=1 row, W=2 rows)
    assert merge_from_index_first_rows(df, level=1) == "1,3,4,5"
    assert merge_from_index_last_rows(df, level=1) == "2,3,4,6"


def test_all_single_row_groups():
    """Test behavior when all groups contain exactly one row"""
    arrays = [["A", "B", "C", "D"], ["W", "X", "Y", "Z"]]  # All single-row groups  # All single-row groups
    index = pd.MultiIndex.from_arrays(arrays)
    df = pd.DataFrame(index=index)

    # For level 0, each letter is its own group
    assert merge_from_index_first_rows(df, level=0) == "1,2,3,4"
    assert merge_from_index_last_rows(df, level=0) == "1,2,3,4"

    # For level 1, same result as each letter is its own group
    assert merge_from_index_first_rows(df, level=1) == "1,2,3,4"
    assert merge_from_index_last_rows(df, level=1) == "1,2,3,4"


def test_mixed_single_and_multi_row_groups():
    """Test with a more complex mix of single and multi-row groups"""
    arrays = [
        ["A", "A", "A", "B", "C", "D", "D", "E"],  # Mix of 1- and 3-row groups
        ["X", "X", "Y", "Z", "W", "V", "V", "U"],  # Various patterns
    ]
    index = pd.MultiIndex.from_arrays(arrays)
    df = pd.DataFrame(index=index)

    # Level 0: A=3 rows, B=1 row, C=1 row, D=2 rows, E=1 row
    assert merge_from_index_first_rows(df, level=0) == "1,4,5,6,8"
    assert merge_from_index_last_rows(df, level=0) == "3,4,5,7,8"

    # Level 1: X=2 rows, Y=1 row, Z=1 row, W=1 row, V=2 rows, U=1 row
    assert merge_from_index_first_rows(df, level=1) == "1,3,4,5,6,8"
    assert merge_from_index_last_rows(df, level=1) == "2,3,4,5,7,8"


def test_single_row_with_offset():
    """Test single-row groups with different offsets"""
    arrays = [["A", "B", "C"], ["X", "Y", "Z"]]  # All single-row groups
    index = pd.MultiIndex.from_arrays(arrays)
    df = pd.DataFrame(index=index, columns=pd.MultiIndex.from_arrays([["P", "Q"], ["1", "2"]]))  # 2 levels of columns

    # With 2 column levels, offset should be 2
    assert merge_from_index_first_rows(df, level=0) == "2,3,4"
    assert merge_from_index_last_rows(df, level=0) == "2,3,4"

    # Test with explicit offset
    assert merge_from_index_first_rows(df, io=3, level=0) == "3,4,5"
    assert merge_from_index_last_rows(df, io=3, level=0) == "3,4,5"


if __name__ == "__main__":
    pytest.main([__file__])
