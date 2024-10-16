import configparser
import io
import os
from contextlib import redirect_stdout
from functools import partial
from unittest.mock import patch

from novem import Plot
from novem.utils import API_ROOT

to_csv_test_string = "the to_csv function was invoked"


class TestFrame(object):
    def to_csv(self):
        # simple test class to make sure that the novem library invokes to_csv.
        return to_csv_test_string

    def pipe(self, func, **kwargs):
        # utility function to simulate dataframe df.call
        func(self, **kwargs)


def test_plot(requests_mock):
    plot_type = "bar"
    plot_id = "test_plot"
    plot_name = "long test name"
    plot_description = "long test description"
    plot_caption = "plot caption is nice to have"

    # grab our base path so we can use it for our test config
    base = os.path.dirname(os.path.abspath(__file__))
    config_file = f"{base}/test.conf"

    # read our config file as well
    config = configparser.ConfigParser()

    # check if novem config file exist
    config.read(config_file)
    api_root = config["general"]["api_root"]

    # need to verify that assertions are called

    gcheck = {
        "create": False,
        "type": False,
        "desc": False,
        "name": False,
        "caption": False,
        "data": False,
    }

    def verify(key, val, request, context):
        gcheck[key] = True
        assert request.text == val

    def verify_put(key, val, request, context):
        gcheck[key] = True
        assert request.url == f"{api_root}vis/plots/{plot_id}"

    requests_mock.register_uri(
        "put",
        f"{api_root}vis/plots/{plot_id}",
        text=partial(verify_put, "create", plot_type),
    )

    requests_mock.register_uri(
        "post",
        f"{api_root}vis/plots/{plot_id}/config/type",
        text=partial(verify, "type", plot_type),
    )

    requests_mock.register_uri(
        "post",
        f"{api_root}vis/plots/{plot_id}/config/caption",
        text=partial(verify, "caption", plot_caption),
    )

    requests_mock.register_uri(
        "post",
        f"{api_root}vis/plots/{plot_id}/name",
        text=partial(verify, "name", plot_name),
    )

    requests_mock.register_uri(
        "post",
        f"{api_root}vis/plots/{plot_id}/description",
        text=partial(verify, "desc", plot_description),
    )

    requests_mock.register_uri(
        "post",
        f"{api_root}vis/plots/{plot_id}/data",
        text=partial(verify, "data", to_csv_test_string),
    )

    # create a novem api object
    n = Plot(
        plot_id,
        type=plot_type,
        config_path=config_file,  # config location
        caption=plot_caption,
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
        text=partial(verify, "data", lit_str),
    )
    n.data = lit_str

    for k, v in gcheck.items():
        assert v is True

    assert n._api_root == "https://api.novem.no/v1/"


@patch.dict(os.environ, {"NOVEM_TOKEN": "test_token"})
def test_plot_log(requests_mock, fs):
    requests_mock.register_uri("get", f"{API_ROOT}vis/plots/foo", text='{"id": "foo"}', status_code=200)
    requests_mock.register_uri("get", f"{API_ROOT}vis/plots/foo/log", text="log_test_plot", status_code=200)

    p = Plot(id="foo", create=False)

    # Redirect stdout to a StringIO object
    f = io.StringIO()
    with redirect_stdout(f):
        p.log

    # Get the printed output
    output = f.getvalue().strip()

    # Assert that the output matches the expected string
    assert output == "log_test_plot"
