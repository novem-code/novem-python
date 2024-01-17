import os

import pandas as pd

from novem.table import Selector as S

# from novem.colors import StaticColor as SC,
# UseDataset as _
# from novem.table import CellAlign, CellBorder, CellFormat,
# CellPadding, CellText, CellWidth, CellMerge


def test_text_selctor():
    # selctors are utility items

    sel_strings = [": :", "1,2,3 :", "1,2 1"]

    for s in sel_strings:
        # if a string is given in it's returned back
        assert S(s, "").get_selector_string() == s


def test_dataframe_selector():
    """
    Test pandas dataframe selector
    """

    cpath = os.path.abspath(os.path.dirname(__file__))

    df = pd.read_csv(f"{cpath}/files/hier.csv")

    flt = [df.level == 3, df.level == 2, df.level == 1]

    # tst rows selectors
    for f in flt:
        ixs = ",".join([str(x + 1) for x in df[f].index.values])
        inst = str(S(df[f], "", df))
        # assert our index instructions match
        assert inst.split(" ")[0] == ixs

    # test our column selectors
    test = [
        [df.loc[:, ["NAV", "YTD"]], "2,7"],
        [df.loc[:, "NAV":], "2,3,4,5,6,7,8"],
        [df.loc[:, :], "1,2,3,4,5,6,7,8"],
    ]

    for t in test:
        inst = str(S(t[0], "", df))
        assert inst.split(" ")[1] == t[1]

    # test our combined selectors
    cmb = [
        [df.loc[df.level == 1, ["NAV", "YTD"]], "2,7"],
        [df.loc[df.level == 2, "NAV":], "2,3,4,5,6,7,8"],
        [df.loc[df.level == 3, :], "1,2,3,4,5,6,7,8"],
    ]

    for c in cmb:
        cf = c[0]
        cxs = c[1]

        inst = str(S(cf, "", df))
        cand = " ".join(inst.split(" ")[:2])

        ixs = ",".join([str(x + 1) for x in cf.index.values])

        # assert combined instructions match
        assert cand == f"{ixs} {cxs}"

    # test our c overrides
    test = [
        [df.loc[:, ["NAV", "YTD"]], ":", ":"],
        [df.loc[:, "NAV":], ":-1", ":-1"],
        [df.loc[:, :], "0", "0"],
    ]

    for t in test:
        inst = str(S(t[0], "", df, c=t[1]))
        assert inst.split(" ")[1] == t[2]

    # test our i overrides
    test = [
        [df.loc[:, ["NAV", "YTD"]], ":", ":"],
        [df.loc[:, "NAV":], ":-1", ":-1"],
        [df.loc[:, :], "0", "0"],
    ]

    for t in test:
        inst = str(S(t[0], "", df, i=t[1]))
        assert inst.split(" ")[0] == t[2]

    # test our c offset
    test = [
        [df.loc[:, ["NAV", "YTD"]], 1, "3,8"],
        [df.loc[:, "NAV":], -1, "1,2,3,4,5,6,7"],
        [df.loc[:, :], -2, "0,1,2,3,4,5,6"],
    ]

    for t in test:
        inst = str(S(t[0], "", df, co=t[1]))
        assert inst.split(" ")[1] == t[2]

    # test our i offset
    test = [
        [df.loc[1:5, ["NAV", "YTD"]], 1, "3,4,5,6,7"],
        [df.loc[5:10, "NAV":], -1, "5,6,7,8,9,10"],
        [df.loc[4:10, :], -2, "3,4,5,6,7,8,9"],
    ]

    for t in test:
        inst = str(S(t[0], "", df, io=t[1]))
        assert inst.split(" ")[0] == t[2]

    # test our c offset range
    test = [
        [df.loc[:, ["NAV", "YTD"]], 1, "2,7,8"],
        [df.loc[:, :"QTD"], -1, "0,1,2,3,4,5,6"],
        [df.loc[:, "WTD":"QTD"], -2, "2,3,4,5,6"],
    ]

    for t in test:
        inst = str(S(t[0], "", df, cor=t[1]))
        assert inst.split(" ")[1] == t[2]

    # test our i offset range
    test = [
        [df.loc[1:5, ["NAV", "YTD"]], 1, "2,3,4,5,6,7"],
        [df.loc[5:10, "NAV":], -1, "5,6,7,8,9,10,11"],
        [df.loc[4:10, :], -2, "3,4,5,6,7,8,9,10,11"],
    ]

    for t in test:
        inst = str(S(t[0], "", df, ior=t[1]))
        assert inst.split(" ")[0] == t[2]


def test_2d_selector():
    data = {
        "Foo": [1, 2, 3, 4],
        "Bar": [5, 6, 7, 8],
        "Baz": [9, 10, 11, 12],
    }

    df = pd.DataFrame(data, index=["AAA", "BBB", "CCC", "DDD"])
    format = S(df.iloc[:, :], ",.1%", r=df).get_selector_string()
    assert format == "1,2,3,4 1,2,3"

    df = df.transpose()
    format = S(df.iloc[:, :], ",.1%", r=df).get_selector_string()
    assert format == "1,2,3 1,2,3,4"
