import numpy as np
import pandas as pd
import pytest

from novem.table.utils import merge_from_index


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


def test_empty_dataframe():
    df = pd.DataFrame()
    result = merge_from_index(df)
    assert result == ""


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


def test_invalid_input():
    with pytest.raises(TypeError):
        merge_from_index([1, 2, 3])


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


if __name__ == "__main__":
    pytest.main([__file__])
