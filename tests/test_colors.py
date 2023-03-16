import configparser
import os
from functools import partial

import pandas as pd

from novem import Plot
from novem.colors import USEDATA as _
from novem.colors import DynamicColor as DC
from novem.colors import StaticColor as SC
from novem.table import Selector as S

# test novem colors
color_type = ""
color_values = ""


def test_ix_color_constructors():

    # test static colors
    assert str(SC("bg", "gray-300")) == "bg gray-300"
    assert str(SC("fg", "gray-300")) == "fg gray-300"
    assert str(SC("xx", "gray-300")) == "bg gray-300"
    assert str(SC(None, "gray-300")) == "bg gray-300"

    assert str(SC("bg", "gray-300", dark="pink-500")) == "bg gray-300 pink-500"
    assert str(SC("bg", "gray-300", "pink-500")) == "bg gray-300 pink-500"

    # test dynamic colors
    assert str(DC("bg", "red", None, "green")) == "bg red,green(_,_)^lin"
    assert str(DC("fg", "red", None, "green")) == "fg red,green(_,_)^lin"
    assert str(DC("xx", "red", None, "green")) == "bg red,green(_,_)^lin"
    assert str(DC(None, "red", None, "green")) == "bg red,green(_,_)^lin"
    assert str(DC("bg", min="red", max="green")) == "bg red,green(_,_)^lin"

    assert (
        str(DC("bg", "red", "neutral", "green"))
        == "bg red,neutral,green(_,_,_)^lin"
    )
    assert (
        str(DC("bg", "red", "neutral", "green", vmid=0))
        == "bg red,neutral,green(_,0,_)^lin"
    )
    assert (
        str(DC("bg", "bad", "neutral", "good", vmid=0))
        == "bg bad,neutral,good(_,0,_)^lin"
    )

    assert (
        str(DC("bg", min="red", max="green", vmin=-100, vmax=100))
        == "bg red,green(-100,100)^lin"
    )
    assert (
        str(DC("bg", min="red", max="green", vmin=_, vmax=100))
        == "bg red,green(_,100)^lin"
    )
    assert (
        str(DC("bg", min="red", max="green", vmin=-100, vmax=_))
        == "bg red,green(-100,_)^lin"
    )

    assert (
        str(DC("bg", "red", "neutral", "green", vmin=10))
        == "bg red,neutral,green(10,_,_)^lin"
    )
    assert (
        str(DC("bg", "red", "neutral", "green", vmin=10, vmax=100))
        == "bg red,neutral,green(10,_,100)^lin"
    )

    assert (
        str(
            DC(
                "bg",
                min="red",
                max="green",
                dmin="blue",
                dmax="purple",
                vmin=_,
                vmax=_,
            )
        )
        == "bg red,green(_,_)^lin blue,purple(_,_)^lin"
    )


def test_color_assign(requests_mock):
    plot_type = "mtable"
    plot_id = "test_plot"
    global color_type
    global color_values
    color_type = ""
    color_values = ""

    # grab our base path so we can use it for our test config
    base = os.path.dirname(os.path.abspath(__file__))
    config_file = f"{base}/test.conf"

    # read our config file as well
    config = configparser.ConfigParser()

    # check if novem config file exist
    config.read(config_file)
    api_root = config["general"]["api_root"]

    def verify(val, request, context):
        assert request.text == val

    def verify_put(val, request, context):
        assert request.url == f"{api_root}vis/plots/{plot_id}"

    requests_mock.register_uri(
        "put",
        f"{api_root}vis/plots/{plot_id}",
        text=partial(verify_put, plot_type),
    )

    requests_mock.register_uri(
        "post",
        f"{api_root}vis/plots/{plot_id}/config/type",
        text=partial(verify, plot_type),
    )

    def post_colors(request, context):
        global color_values
        color_values = request.body.decode("utf-8")

    def get_colors(request, context):
        return color_values

    def post_color_type(request, context):
        global color_type
        color_type = request.body.decode("utf-8")

    def get_color_type(request, context):
        return color_type

    requests_mock.register_uri(
        "get",
        f"{api_root}vis/plots/{plot_id}/config/colors/colors",
        text=get_colors,
    )

    requests_mock.register_uri(
        "post",
        f"{api_root}vis/plots/{plot_id}/config/colors/colors",
        text=post_colors,
    )

    requests_mock.register_uri(
        "get",
        f"{api_root}vis/plots/{plot_id}/config/colors/type",
        text=get_color_type,
    )

    requests_mock.register_uri(
        "post",
        f"{api_root}vis/plots/{plot_id}/config/colors/type",
        text=post_color_type,
    )

    n = Plot(
        plot_id, type=plot_type, config_path=config_file  # config location
    )

    # assign type to color sends post request
    for ctv in ["ix", "clr"]:
        n.colors.type = ctv

        # our global value gets updated via post request
        assert color_type == ctv

        # our global value gets returned via get request
        assert n.colors.type == ctv

    # assign color to color sends post request
    cs = [
        S(": :", "bg red"),
        S(": :", "bg blue"),
    ]
    for c in cs:
        n.colors = c
        assert str(n.colors) == str(c)
        assert color_values == str(c)

    t1 = S(": 1:", "fg blue")
    t2 = S("1:-1 1:-3", "fg orange")

    # appending styles gets and updates colors
    n.colors += t1
    n.colors += t2

    assert str(n.colors) == f"{cs[1]}\n{t1}\n{t2}"

    # assigning new, overrides
    cc = ": : bg pink"
    n.colors = cc

    assert str(n.colors) == cc


def test_color_freeze(requests_mock):
    plot_type = "mtable"
    plot_id = "test_plot"
    global color_type
    global color_values
    color_type = ""
    color_values = ""

    # grab our base path so we can use it for our test config
    base = os.path.dirname(os.path.abspath(__file__))
    config_file = f"{base}/test.conf"

    # read our config file as well
    config = configparser.ConfigParser()

    # check if novem config file exist
    config.read(config_file)
    api_root = config["general"]["api_root"]

    def verify(val, request, context):
        assert request.text == val

    def verify_put(val, request, context):
        assert request.url == f"{api_root}vis/plots/{plot_id}"

    requests_mock.register_uri(
        "put",
        f"{api_root}vis/plots/{plot_id}",
        text=partial(verify_put, plot_type),
    )

    requests_mock.register_uri(
        "post",
        f"{api_root}vis/plots/{plot_id}/config/type",
        text=partial(verify, plot_type),
    )

    def post_colors(request, context):
        global color_values
        color_values = request.body.decode("utf-8")

    def get_colors(request, context):
        return color_values

    def post_color_type(request, context):
        global color_type
        color_type = str(request.body.decode("utf-8"))

    def get_color_type(request, context):
        return color_type

    requests_mock.register_uri(
        "get",
        f"{api_root}vis/plots/{plot_id}/config/colors/colors",
        text=get_colors,
    )

    requests_mock.register_uri(
        "post",
        f"{api_root}vis/plots/{plot_id}/config/colors/colors",
        text=post_colors,
    )

    requests_mock.register_uri(
        "get",
        f"{api_root}vis/plots/{plot_id}/config/colors/type",
        text=get_color_type,
    )

    requests_mock.register_uri(
        "post",
        f"{api_root}vis/plots/{plot_id}/config/colors/type",
        text=post_color_type,
    )

    n = Plot(
        plot_id, type=plot_type, config_path=config_file  # config location
    )

    n.freeze()

    # assign type to color sends post request
    for ctv in ["clr", "ix"]:
        n.colors.type = ctv

        # our global value gets updated via post request
        assert color_type != ctv

        # our global value gets returned via get request
        assert n.colors.type == ctv

    # assign color to color sends post request
    cs = [
        ": : bg red",
        ": : bg blue",
    ]
    for c in cs:
        n.colors = c
        assert color_values != c
        assert str(n.colors) == c

    assert color_values == ""

    t1 = ": 1: fg blue"
    t2 = "1:-1 1:-3 fg orange"

    # appending styles gets and updates colors
    n.colors += t1
    n.colors += t2

    assert str(n.colors) == f"{cs[1]}\n{t1}\n{t2}"
    assert color_values == ""

    n.run()

    assert color_type == "ix"
    assert color_values == f"{cs[1]}\n{t1}\n{t2}"

    assert str(n.colors) == f"{cs[1]}\n{t1}\n{t2}"
    assert n.colors.type == "ix"


def test_color_selector(requests_mock):
    plot_type = "mtable"
    plot_id = "test_plot"
    global color_type
    global color_values
    color_type = ""
    color_values = ""

    # grab our base path so we can use it for our test config
    base = os.path.dirname(os.path.abspath(__file__))
    config_file = f"{base}/test.conf"

    # read our config file as well
    config = configparser.ConfigParser()

    # check if novem config file exist
    config.read(config_file)
    api_root = config["general"]["api_root"]

    def verify(val, request, context):
        assert request.text == val

    def verify_put(val, request, context):
        assert request.url == f"{api_root}vis/plots/{plot_id}"

    requests_mock.register_uri(
        "put",
        f"{api_root}vis/plots/{plot_id}",
        text=partial(verify_put, plot_type),
    )

    requests_mock.register_uri(
        "post",
        f"{api_root}vis/plots/{plot_id}/config/type",
        text=partial(verify, plot_type),
    )

    def post_colors(request, context):
        global color_values
        color_values = request.body.decode("utf-8")

    def get_colors(request, context):
        return color_values

    def post_color_type(request, context):
        global color_type
        color_type = str(request.body.decode("utf-8"))

    def get_color_type(request, context):
        return color_type

    requests_mock.register_uri(
        "get",
        f"{api_root}vis/plots/{plot_id}/config/colors/colors",
        text=get_colors,
    )

    requests_mock.register_uri(
        "post",
        f"{api_root}vis/plots/{plot_id}/config/colors/colors",
        text=post_colors,
    )

    requests_mock.register_uri(
        "get",
        f"{api_root}vis/plots/{plot_id}/config/colors/type",
        text=get_color_type,
    )

    requests_mock.register_uri(
        "post",
        f"{api_root}vis/plots/{plot_id}/config/colors/type",
        text=post_color_type,
    )

    n = Plot(
        plot_id, type=plot_type, config_path=config_file  # config location
    )

    n.freeze()

    # assign type to color sends post request
    for ctv in ["clr", "ix"]:
        n.colors.type = ctv

        # our global value gets updated via post request
        assert color_type != ctv

        # our global value gets returned via get request
        assert n.colors.type == ctv

    # assign color to color sends post request
    cs = [
        ": : bg red",
        ": : bg blue",
    ]
    for c in cs:
        n.colors = c
        assert color_values != c
        assert str(n.colors) == c

    assert color_values == ""

    t1 = ": 1: fg blue"
    t2 = "1:-1 1:-3 fg orange"

    # appending styles gets and updates colors
    n.colors += t1
    n.colors += t2

    assert str(n.colors) == f"{cs[1]}\n{t1}\n{t2}"
    assert color_values == ""

    n.run()

    assert color_type == "ix"
    assert color_values == f"{cs[1]}\n{t1}\n{t2}"

    assert str(n.colors) == f"{cs[1]}\n{t1}\n{t2}"
    assert n.colors.type == "ix"


def test_color_df_loc_selector(requests_mock):
    """ """
    plot_type = "mtable"
    plot_id = "test_plot"
    global color_type
    global color_values
    color_type = ""
    color_values = ""

    # grab our base path so we can use it for our test config
    base = os.path.dirname(os.path.abspath(__file__))
    config_file = f"{base}/test.conf"

    # read our config file as well
    config = configparser.ConfigParser()

    # check if novem config file exist
    config.read(config_file)
    api_root = config["general"]["api_root"]

    def verify(val, request, context):
        assert request.text == val

    def verify_put(val, request, context):
        assert request.url == f"{api_root}vis/plots/{plot_id}"

    requests_mock.register_uri(
        "put",
        f"{api_root}vis/plots/{plot_id}",
        text=partial(verify_put, plot_type),
    )

    requests_mock.register_uri(
        "post",
        f"{api_root}vis/plots/{plot_id}/config/type",
        text=partial(verify, plot_type),
    )

    def post_colors(request, context):
        global color_values
        color_values = request.body.decode("utf-8")

    def get_colors(request, context):
        return color_values

    def post_color_type(request, context):
        global color_type
        color_type = str(request.body.decode("utf-8"))

    def get_color_type(request, context):
        return color_type

    requests_mock.register_uri(
        "get",
        f"{api_root}vis/plots/{plot_id}/config/colors/colors",
        text=get_colors,
    )

    requests_mock.register_uri(
        "post",
        f"{api_root}vis/plots/{plot_id}/config/colors/colors",
        text=post_colors,
    )

    requests_mock.register_uri(
        "get",
        f"{api_root}vis/plots/{plot_id}/config/colors/type",
        text=get_color_type,
    )

    requests_mock.register_uri(
        "post",
        f"{api_root}vis/plots/{plot_id}/config/colors/type",
        text=post_color_type,
    )

    n = Plot(
        plot_id, type=plot_type, config_path=config_file  # config location
    )

    cpath = os.path.abspath(os.path.dirname(__file__))
    df = pd.read_csv(f"{cpath}/files/hier.csv")

    # construct a simple color selector
    n.colors.type = "ix"
    n.colors = S(df.loc[df.level == 0, :], SC("bg", "gray-100"), df)
    n.colors += S(df.loc[df.level == 1, :], SC("bg", "gray-200"), df)
    n.colors += S(df.loc[df.level == 2, :], SC("bg", "gray-300"), df)
    n.colors += S(df.loc[df.level == 3, :], SC("bg", "gray-400"), df)

    res = """1 1,2,3,4,5,6,7,8 bg gray-100
2,5,8 1,2,3,4,5,6,7,8 bg gray-200
3,6,9,12,19 1,2,3,4,5,6,7,8 bg gray-300
4,7,10,11,13,14,15,16,17,18,20,21,22,23,24,25 1,2,3,4,5,6,7,8 bg gray-400"""

    assert str(n.colors) == res


def test_color_df_iloc_selector(requests_mock):
    """ """
    plot_type = "mtable"
    plot_id = "test_plot"
    global color_type
    global color_values
    color_type = ""
    color_values = ""

    # grab our base path so we can use it for our test config
    base = os.path.dirname(os.path.abspath(__file__))
    config_file = f"{base}/test.conf"

    # read our config file as well
    config = configparser.ConfigParser()

    # check if novem config file exist
    config.read(config_file)
    api_root = config["general"]["api_root"]

    def verify(val, request, context):
        assert request.text == val

    def verify_put(val, request, context):
        assert request.url == f"{api_root}vis/plots/{plot_id}"

    requests_mock.register_uri(
        "put",
        f"{api_root}vis/plots/{plot_id}",
        text=partial(verify_put, plot_type),
    )

    requests_mock.register_uri(
        "post",
        f"{api_root}vis/plots/{plot_id}/config/type",
        text=partial(verify, plot_type),
    )

    def post_colors(request, context):
        global color_values
        color_values = request.body.decode("utf-8")

    def get_colors(request, context):
        return color_values

    def post_color_type(request, context):
        global color_type
        color_type = str(request.body.decode("utf-8"))

    def get_color_type(request, context):
        return color_type

    requests_mock.register_uri(
        "get",
        f"{api_root}vis/plots/{plot_id}/config/colors/colors",
        text=get_colors,
    )

    requests_mock.register_uri(
        "post",
        f"{api_root}vis/plots/{plot_id}/config/colors/colors",
        text=post_colors,
    )

    requests_mock.register_uri(
        "get",
        f"{api_root}vis/plots/{plot_id}/config/colors/type",
        text=get_color_type,
    )

    requests_mock.register_uri(
        "post",
        f"{api_root}vis/plots/{plot_id}/config/colors/type",
        text=post_color_type,
    )

    n = Plot(
        plot_id, type=plot_type, config_path=config_file  # config location
    )

    cpath = os.path.abspath(os.path.dirname(__file__))
    df = pd.read_csv(f"{cpath}/files/nei_rgn_tb.csv", index_col=0)

    # construct a simple color selector
    n.colors.type = "ix"
    n.colors = S(df.iloc[:10, -1], DC("bg", "gray-100"), df)

    n.colors += S(df.loc[:, "Contribution"], DC("bg", "gray-100"), df)
