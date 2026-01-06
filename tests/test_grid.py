import configparser
import os
from functools import partial

from novem import Grid, Plot
from novem.grid import GridMap


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


def setup_plot_mock(requests_mock, plot_id, shortname):
    """Helper to set up a mock plot for GridMap tests."""
    base = os.path.dirname(os.path.abspath(__file__))
    config_file = f"{base}/test.conf"
    config = configparser.ConfigParser()
    config.read(config_file)
    api_root = config["general"]["api_root"]

    # Mock plot creation
    requests_mock.register_uri("put", f"{api_root}vis/plots/{plot_id}", text="")
    # Mock shortname read
    requests_mock.register_uri("get", f"{api_root}vis/plots/{plot_id}/shortname", text=shortname)

    return Plot(plot_id, config_path=config_file)


def test_gridmap_str_conversion(requests_mock):
    """Test that GridMap converts to the correct string format."""
    p1 = setup_plot_mock(requests_mock, "plot1", "/u/testuser/p/plot1")
    p2 = setup_plot_mock(requests_mock, "plot2", "/u/testuser/p/plot2")

    gm = GridMap({"a": p1, "b": p2})
    result = str(gm)

    assert "a => /u/testuser/p/plot1" in result
    assert "b => /u/testuser/p/plot2" in result


def test_gridmap_get(requests_mock):
    """Test GridMap.get() method."""
    p1 = setup_plot_mock(requests_mock, "plot1", "/u/testuser/p/plot1")

    gm = GridMap({"a": p1})

    assert gm.get("a") == p1
    assert gm.get("nonexistent") is None


def test_gridmap_keys_values_items(requests_mock):
    """Test GridMap iteration methods."""
    p1 = setup_plot_mock(requests_mock, "plot1", "/u/testuser/p/plot1")
    p2 = setup_plot_mock(requests_mock, "plot2", "/u/testuser/p/plot2")

    gm = GridMap({"a": p1, "b": p2})

    assert set(gm.keys()) == {"a", "b"}
    assert set(gm.values()) == {p1, p2}
    assert set(gm.items()) == {("a", p1), ("b", p2)}


def test_grid_mapping_with_gridmap(requests_mock):
    """Test that Grid.mapping accepts GridMap objects."""
    # Set up plot mock
    p1 = setup_plot_mock(requests_mock, "plot1", "/u/testuser/p/plot1")

    # Set up grid mock
    base = os.path.dirname(os.path.abspath(__file__))
    config_file = f"{base}/test.conf"
    config = configparser.ConfigParser()
    config.read(config_file)
    api_root = config["general"]["api_root"]

    grid_id = "test_grid"
    expected_mapping = "a => /u/testuser/p/plot1"

    def verify_mapping_post(request, context):
        assert request.text == expected_mapping

    requests_mock.register_uri("put", f"{api_root}vis/grids/{grid_id}", text="")
    requests_mock.register_uri("post", f"{api_root}vis/grids/{grid_id}/mapping", text=verify_mapping_post)

    g = Grid(grid_id, config_path=config_file)
    gm = GridMap({"a": p1})
    g.mapping = gm
