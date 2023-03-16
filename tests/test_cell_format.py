import configparser
import os
from functools import partial

from novem import Plot

# test novem colors
test_values = ""


def test_color_assign(requests_mock):
    plot_type = "mtable"
    plot_id = "test_plot"
    global test_values
    test_values = ""

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

    def post_value(request, context):
        global test_values
        test_values = request.body.decode("utf-8")

    def get_value(request, context):
        return test_values

    requests_mock.register_uri(
        "get",
        f"{api_root}vis/plots/{plot_id}/config/table/cell/align",
        text=get_value,
    )

    requests_mock.register_uri(
        "post",
        f"{api_root}vis/plots/{plot_id}/config/table/cell/align",
        text=post_value,
    )

    n = Plot(
        plot_id, type=plot_type, config_path=config_file  # config location
    )

    for t in [": : <", ": : -", ": : >"]:
        n.cell.align = t
        assert t == test_values
        assert t == str(n.cell.align)

    # verify that we can expand a string with append
    n.cell.align = "123"
    n.cell.align += "456"
    n.cell.align += "789"

    assert str(n.cell.align) == "123\n456\n789"

    test_values = ""

    p = Plot(
        plot_id, type=plot_type, config_path=config_file  # config location
    )

    p.freeze()

    for t in [": : <", ": : -", ": : >"]:
        p.cell.align = t
        assert t != test_values
        assert t == str(p.cell.align)

    # verify that we can expand a string with append
    p.cell.align = "123"
    p.cell.align += "456"
    p.cell.align += "789"

    ts = "123\n456\n789"
    assert str(p.cell.align) == ts

    assert test_values == ""

    p.run()
    assert test_values == ts
