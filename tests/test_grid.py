import configparser
import os
from functools import partial

from novem import Grid


def setup_grid_mock(requests_mock, conf):
    # grab our base path so we can use it for our test config
    base = os.path.dirname(os.path.abspath(__file__))
    config_file = f"{base}/test.conf"

    # read our config file as well
    config = configparser.ConfigParser()

    # check if novem config file exist
    config.read(config_file)
    api_root = config["general"]["api_root"]

    # egrid mock
    grid_id = conf["grid_id"]

    def verify_grid_put(key, val, request, context):
        assert request.url == f"{api_root}vis/grids/{grid_id}"

    # create mock
    requests_mock.register_uri(
        "put",
        f"{api_root}vis/grids/{grid_id}",
        text=partial(verify_grid_put, "create", "ignore"),
    )

    for r in conf["reqs"]:
        if r[0] == "post":

            def verify_post(key, val, request, context):
                assert request.url == f"{api_root}vis/grids/{grid_id}{r[1]}"
                assert request.text == r[2]

            requests_mock.register_uri(
                "post",
                f"{api_root}vis/grids/{grid_id}{r[1]}",
                text=partial(verify_post, "create", "ignore"),
            )
        elif r[0] == "get":
            requests_mock.register_uri("get", f"{api_root}vis/grids/{grid_id}{r[1]}", text=r[2])

    g = Grid(
        grid_id,
        config_path=config_file,  # config location
    )

    return g


def test_grid_attrib_mapping(requests_mock):
    conf = {
        "grid_id": "test_grid",
        "reqs": [
            ["get", "/mapping", "test mapping out"],
            ["post", "/mapping", "test mapping in"],
        ],
    }
    g = setup_grid_mock(requests_mock, conf)
    g.mapping = "test mapping in"
    assert g.mapping == "test mapping out"


def test_grid_attrib_layout(requests_mock):
    conf = {
        "grid_id": "test_grid",
        "reqs": [
            ["get", "/layout", "test layout out"],
            ["post", "/layout", "test layout in"],
        ],
    }
    g = setup_grid_mock(requests_mock, conf)
    g.layout = "test layout in"
    assert g.layout == "test layout out"


def test_grid_attrib_type(requests_mock):
    conf = {
        "grid_id": "test_grid",
        "reqs": [
            ["get", "/config/type", "test type out"],
            ["post", "/config/type", "test type in"],
        ],
    }
    g = setup_grid_mock(requests_mock, conf)
    g.type = "test type in"
    assert g.type == "test type out"


def test_grid_share(requests_mock):
    conf = {
        "grid_id": "test_grid",
        "reqs": [
            [
                "get",
                "/shared",
                """
[
  {
    "name": "public",
    "uri": "/v1/vis/grids/test_grid/shared/public",
    "target": null,
    "permissions": [
      "d"
    ],
    "documentation_uri": "https://neuf.run/doc/api/v1/vis/grids/:grid/shared/public",
    "actions": [
      "OPTION",
      "DELETE"
    ],
    "ETag": "a1fa7ac8b0340169b88ff607e257503c30f61fd9",
    "created_on": "Fri, 29 Nov 2024 09:39:33 UTC",
    "last_modified": "Fri, 29 Nov 2024 09:39:33 UTC",
    "size": 0,
    "type": "file"
  }
]
""",
            ],
            ["put", "/shared/public", "layout in"],
        ],
    }
    g = setup_grid_mock(requests_mock, conf)
    g.shared = "public"
    assert g.shared.get() == ["public"]
