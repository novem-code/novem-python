import configparser
import json
import os
from functools import partial

from novem import Plot

valid_names = []


def test_plot(requests_mock):
    plot_type = "bar"
    plot_id = "test_plot"

    # grab our base path so we can use it for our test config
    base = os.path.dirname(os.path.abspath(__file__))
    config_file = f"{base}/test.conf"

    # read our config file as well
    config = configparser.ConfigParser()

    # check if novem config file exist
    config.read(config_file)
    api_root = config["default"]["api_root"]

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

    def put_share(val, request, context):
        valid_names.append(val)

    def del_share(val, request, context):
        global valid_names
        valid_names = set(valid_names) - set([val])

    def get_shares(request, context):
        return json.dumps([{"name": v} for v in valid_names])

    requests_mock.register_uri(
        "get", f"{api_root}vis/plots/{plot_id}/shared", text=get_shares
    )

    requests_mock.register_uri(
        "put",
        f"{api_root}vis/plots/{plot_id}/shared/public",
        text=partial(put_share, "public"),
    )

    requests_mock.register_uri(
        "put",
        f"{api_root}vis/plots/{plot_id}/shared/+novem_demo~novem_demo",
        text=partial(put_share, "+novem_demo~novem_demo"),
    )

    requests_mock.register_uri(
        "put",
        f"{api_root}vis/plots/{plot_id}/shared/+novem_demo~novem_test",
        text=partial(put_share, "+novem_demo~novem_test"),
    )

    requests_mock.register_uri(
        "delete",
        f"{api_root}vis/plots/{plot_id}/shared/+novem_demo~novem_test",
        text=partial(del_share, "+novem_demo~novem_test"),
    )

    # create a novem api object
    n = Plot(
        plot_id, type=plot_type, config_path=config_file  # config location
    )

    # share with public and novem_demo
    n.shared = "public"

    n.shared = ["public", "+novem_demo~novem_demo"]

    # incrementally add another share
    n.shared += "+novem_demo~novem_test"
    # print(n.shared.get())

    n.shared -= "+novem_demo~novem_test"
    # print(n.shared.get())
