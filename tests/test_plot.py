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
        return to_csv_test_string

    def pipe(self, func, **kwargs):
        func(self, **kwargs)


def test_plot(requests_mock):
    plot_type = "bar"
    plot_id = "test_plot"
    plot_name = "long test name"
    plot_description = "long test description"
    plot_caption = "plot caption is nice to have"
    custom_js = "function test() { return 'test'; }"
    custom_css = ".test { color: red; }"

    base = os.path.dirname(os.path.abspath(__file__))
    config_file = f"{base}/test.conf"

    config = configparser.ConfigParser()
    config.read(config_file)
    api_root = config["general"]["api_root"]

    gcheck = {
        "create": False,
        "type": False,
        "desc": False,
        "name": False,
        "caption": False,
        "data": False,
        "custom_js_read": False,
        "custom_js_write": False,
        "custom_css_read": False,
        "custom_css_write": False,
    }

    def verify_write(key, val, request, context):
        gcheck[key] = True
        assert request.text == val
        return ""

    def verify_read(key, val, request, context):
        gcheck[key] = True
        return val

    def verify_create(request, context):
        gcheck["create"] = True
        return ""

    # Plot creation endpoint
    requests_mock.register_uri(
        "put",
        f"{api_root}vis/plots/{plot_id}",
        text=verify_create,
    )

    requests_mock.register_uri(
        "post",
        f"{api_root}vis/plots/{plot_id}/config/type",
        text=partial(verify_write, "type", plot_type),
    )

    requests_mock.register_uri(
        "post",
        f"{api_root}vis/plots/{plot_id}/config/caption",
        text=partial(verify_write, "caption", plot_caption),
    )

    requests_mock.register_uri(
        "post",
        f"{api_root}vis/plots/{plot_id}/name",
        text=partial(verify_write, "name", plot_name),
    )

    requests_mock.register_uri(
        "post",
        f"{api_root}vis/plots/{plot_id}/description",
        text=partial(verify_write, "desc", plot_description),
    )

    # Custom JS endpoints
    requests_mock.register_uri(
        "get",
        f"{api_root}vis/plots/{plot_id}/config/custom/custom.js",
        text=partial(verify_read, "custom_js_read", custom_js),
    )

    requests_mock.register_uri(
        "post",
        f"{api_root}vis/plots/{plot_id}/config/custom/custom.js",
        text=partial(verify_write, "custom_js_write", custom_js),
    )

    # Custom CSS endpoints
    requests_mock.register_uri(
        "get",
        f"{api_root}vis/plots/{plot_id}/config/custom/custom.css",
        text=partial(verify_read, "custom_css_read", custom_css),
    )

    requests_mock.register_uri(
        "post",
        f"{api_root}vis/plots/{plot_id}/config/custom/custom.css",
        text=partial(verify_write, "custom_css_write", custom_css),
    )

    # Data endpoints
    requests_mock.register_uri(
        "post",
        f"{api_root}vis/plots/{plot_id}/data",
        text=partial(verify_write, "data", to_csv_test_string),
    )

    # Create plot instance
    n = Plot(
        plot_id,
        type=plot_type,
        config_path=config_file,
        caption=plot_caption,
    )

    # Test basic properties
    n.name = plot_name
    n.description = plot_description

    # Test custom properties
    # Test reading custom.js
    js_content = n.custom.js
    assert js_content == custom_js
    assert gcheck["custom_js_read"] is True

    # Test writing custom.js
    n.custom.js = custom_js
    assert gcheck["custom_js_write"] is True

    # Test reading custom.css
    css_content = n.custom.css
    assert css_content == custom_css
    assert gcheck["custom_css_read"] is True

    # Test writing custom.css
    n.custom.css = custom_css
    assert gcheck["custom_css_write"] is True

    # Test data
    tf = TestFrame()
    tf.pipe(n)

    lit_str = "A literal string also works"
    requests_mock.register_uri(
        "post",
        f"{api_root}vis/plots/{plot_id}/data",
        text=partial(verify_write, "data", lit_str),
    )
    n.data = lit_str

    # Verify all operations were performed
    for k, v in gcheck.items():
        assert v is True, f"Operation {k} was not performed"

    assert n._api_root == "https://api.novem.io/v1/"


@patch.dict(os.environ, {"NOVEM_TOKEN": "test_token"})
def test_plot_log(requests_mock, fs):
    requests_mock.register_uri("get", f"{API_ROOT}vis/plots/foo", text='{"id": "foo"}', status_code=200)
    requests_mock.register_uri("get", f"{API_ROOT}vis/plots/foo/log", text="log_test_plot", status_code=200)

    p = Plot(id="foo", create=False)

    f = io.StringIO()
    with redirect_stdout(f):
        p.log

    output = f.getvalue().strip()
    assert output == "log_test_plot"
