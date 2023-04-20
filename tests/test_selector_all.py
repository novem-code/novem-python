import os

import pandas as pd
import pytest

from novem.table import Selector as S  # noqa: F401

from .cases import get_cases_from_path

pfx = "selector_cases"
cases = get_cases_from_path(pfx)


@pytest.mark.parametrize("case", cases)
def test_data_parser(case):
    print("\n--")
    print(case)

    dir_path = os.path.dirname(os.path.realpath(__file__))
    path = f"{dir_path}/{pfx}/{case}/"

    # grab reference data
    df = pd.read_csv(f"{path}/in/data.csv", index_col=0)  # noqa: F841

    # grab selector operations
    isel = ""
    with open(f"{path}/in/selectors.txt", "r") as inf:
        isel = inf.read()

    # grab output matching
    osel = ""
    with open(f"{path}/out/selectors.txt", "r") as of:
        osel = of.read()

    ic = [x for x in isel.split("\n") if x]
    toc = [x for x in osel.split("\n") if x]

    oc = []
    for i, v in enumerate(ic):
        try:
            oc.append(toc[i])
        except IndexError:
            oc.append("MISSING")

    for c in zip(ic, oc):
        tc = c[0]
        rc = c[1]

        # evalutate test case
        fc = str(eval(tc))
        assert fc == rc
