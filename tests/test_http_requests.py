import re
from typing import Any

from novem.vis.plot import Plot


class Capture:
    out: Any = None


def mk_responder(capture: Capture):
    def store_header(res, context):
        capture.out = res.headers["User-Agent"]
        context.status_code = 200
        return "data"

    return store_header


def test_user_agent_contains_version(requests_mock):
    capture = Capture()
    nva = Plot(id="my-plot", create=False, token="nbt-toktok")

    requests_mock.register_uri("GET", f"{nva._api_root}vis/plots/my-plot/data", text=mk_responder(capture))

    assert nva.api_read("/data")
    # should look something like NovemLib/0.4.15 Python/3.10.13
    assert re.search(r"NovemLib/\d+\.\d+\.\d+ Python/\d+\.\d+\.\d+", capture.out)


def test_user_agent_reports_if_started_from_cli(requests_mock):
    capture = Capture()
    nva = Plot(id="my-plot", create=False, token="nbt-toktok", is_cli=True)

    requests_mock.register_uri("GET", f"{nva._api_root}vis/plots/my-plot/data", text=mk_responder(capture))

    assert nva.api_read("/data")
    # should look something like NovemLib/0.4.15 Python/3.10.13
    assert re.search(r"NovemCli/\d+\.\d+\.\d+ Python/\d+\.\d+\.\d+", capture.out)
