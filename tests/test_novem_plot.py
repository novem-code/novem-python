import configparser
import os
from functools import partial

from novem import Plot, __version__

to_csv_test_string = "the to_csv function was invoked"


class TestFrame(object):
    def to_csv(self):
        # simple test class to make sure that the novem library invokes to_csv.
        return to_csv_test_string

    def pipe(self, func, **kwargs):
        # utility function to simulate dataframe df.call
        func(self, **kwargs)


def test_version():
    assert __version__ == "0.1.0"


def test_plot(requests_mock):
    plot_type = "bar"
    plot_id = "test_plot"
    plot_name = "long test name"
    plot_description = "long test description"

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

    requests_mock.register_uri(
        "post",
        f"{api_root}vis/plots/{plot_id}/name",
        text=partial(verify, plot_name),
    )

    requests_mock.register_uri(
        "post",
        f"{api_root}vis/plots/{plot_id}/description",
        text=partial(verify, plot_description),
    )

    requests_mock.register_uri(
        "post",
        f"{api_root}vis/plots/{plot_id}/data",
        text=partial(verify, to_csv_test_string),
    )

    # create a novem api object
    n = Plot(
        plot_id, type=plot_type, config_path=config_file  # config location
    )

    # set plot name
    n.name = plot_name
    n.description = plot_description

    tf = TestFrame()

    # n should call /data endpoint with content of tf.to_string
    tf.pipe(n)

    lit_str = "A literal string also works"
    requests_mock.register_uri(
        "post",
        f"{api_root}vis/plots/{plot_id}/data",
        text=partial(verify, lit_str),
    )
    n.data = lit_str

    assert n.api_root == "https://api.novem.no/v1/"
