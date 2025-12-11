import configparser
import json
import os
from functools import partial
from unittest.mock import MagicMock

from novem.tags import NovemTags, is_valid_tag


def test_is_valid_tag():
    """Test the is_valid_tag helper function"""
    # Valid system tags
    assert is_valid_tag("fav") is True
    assert is_valid_tag("like") is True
    assert is_valid_tag("ignore") is True
    assert is_valid_tag("wip") is True
    assert is_valid_tag("archived") is True

    # Valid user tags (start with +)
    assert is_valid_tag("+mytag") is True
    assert is_valid_tag("+custom_tag") is True
    assert is_valid_tag("+123") is True

    # Invalid tags
    assert is_valid_tag("") is False
    assert is_valid_tag("invalid") is False
    assert is_valid_tag("favorite") is False
    assert is_valid_tag("FAV") is False  # case sensitive


def test_novem_tags_standalone():
    """Test standalone NovemTags functionality with a mocked API"""
    api = MagicMock()
    tag_path = "test/path"
    tag_data = []

    # Setup mock API responses
    def mock_read(path):
        return json.dumps([{"name": t} for t in tag_data])

    def mock_create(path):
        # Extract tag from path
        tag = path.split("/")[-1]
        if tag not in tag_data:
            tag_data.append(tag)
        return ""

    def mock_delete(path):
        # Extract tag from path
        tag = path.split("/")[-1]
        if tag in tag_data:
            tag_data.remove(tag)
        return ""

    # Configure the mock API
    api.read = mock_read
    api.create = mock_create
    api.delete = mock_delete

    # Create a NovemTags instance
    tags = NovemTags(api, tag_path)

    # Test get method with empty data
    assert tags.get() == []

    # Test set method with a valid string
    tags.set("fav")
    assert tag_data == ["fav"]

    # Test set method with a list of valid tags
    tags.set(["fav", "like", "wip"])
    assert sorted(tag_data) == sorted(["fav", "like", "wip"])

    # Test __iadd__ operator
    tags += "archived"
    assert sorted(tag_data) == sorted(["fav", "like", "wip", "archived"])

    # Test __isub__ operator
    tags -= "like"
    assert sorted(tag_data) == sorted(["fav", "wip", "archived"])

    # Test __str__ method
    string_repr = str(tags)
    assert sorted(string_repr.split("\n")) == sorted(["fav", "wip", "archived"])

    # Test __len__ method
    length = len(tags)
    assert length == 3

    # Test __iter__ method
    items = list(tags)
    assert sorted(items) == sorted(["fav", "wip", "archived"])

    # Test __getitem__ method
    assert len(tags[0:3]) == 3

    # Test __eq__ method
    assert tags == ["fav", "wip", "archived"]
    assert not (tags == ["fav", "like"])

    # Test __contains__ method
    assert "fav" in tags
    assert "like" not in tags


def test_novem_tags_user_tags():
    """Test user tags (tags starting with +)"""
    api = MagicMock()
    tag_path = "test/path"
    tag_data = []

    def mock_read(path):
        return json.dumps([{"name": t} for t in tag_data])

    def mock_create(path):
        tag = path.split("/")[-1]
        if tag not in tag_data:
            tag_data.append(tag)
        return ""

    def mock_delete(path):
        tag = path.split("/")[-1]
        if tag in tag_data:
            tag_data.remove(tag)
        return ""

    api.read = mock_read
    api.create = mock_create
    api.delete = mock_delete

    tags = NovemTags(api, tag_path)

    # Test user tags
    tags.set("+mytag")
    assert tag_data == ["+mytag"]

    tags += "+another_tag"
    assert sorted(tag_data) == sorted(["+mytag", "+another_tag"])

    # Mix of system and user tags
    tags.set(["fav", "+custom", "wip", "+project_a"])
    assert sorted(tag_data) == sorted(["fav", "+custom", "wip", "+project_a"])


def test_novem_tags_invalid_tags_ignored():
    """Test that invalid tags are silently ignored"""
    api = MagicMock()
    tag_path = "test/path"
    tag_data = []

    def mock_read(path):
        return json.dumps([{"name": t} for t in tag_data])

    def mock_create(path):
        tag = path.split("/")[-1]
        if tag not in tag_data:
            tag_data.append(tag)
        return ""

    def mock_delete(path):
        tag = path.split("/")[-1]
        if tag in tag_data:
            tag_data.remove(tag)
        return ""

    api.read = mock_read
    api.create = mock_create
    api.delete = mock_delete

    tags = NovemTags(api, tag_path)

    # Invalid tag should be ignored
    tags.set("invalid_tag")
    assert tag_data == []

    # Invalid tag via += should be ignored
    tags += "not_valid"
    assert tag_data == []

    # Mix of valid and invalid tags - only valid ones should be added
    tags.set(["fav", "invalid", "wip", "also_invalid", "+valid_user_tag"])
    assert sorted(tag_data) == sorted(["fav", "wip", "+valid_user_tag"])


def test_novem_tags_api_parameters():
    """Test that NovemTags correctly constructs API paths"""
    api = MagicMock()

    # Track API calls to verify paths
    api_paths = {"read": [], "create": [], "delete": []}

    def mock_read(path):
        api_paths["read"].append(path)
        return json.dumps([{"name": "fav"}, {"name": "wip"}])

    def mock_create(path):
        api_paths["create"].append(path)
        return ""

    def mock_delete(path):
        api_paths["delete"].append(path)
        return ""

    api.read = mock_read
    api.create = mock_create
    api.delete = mock_delete

    # Test with different tag paths
    tag_paths = ["vis/plots/plot1", "vis/grids/grid1", "vis/mails/mail1"]

    for path in tag_paths:
        api_paths = {"read": [], "create": [], "delete": []}
        tags = NovemTags(api, path)

        # Test get method
        tags.get()
        assert api_paths["read"] == [f"{path}/tags"]

        # Test set method
        tags.set(["fav", "like"])
        assert f"{path}/tags" in api_paths["read"]

        # Test direct operations
        tags += "archived"
        tags -= "wip"

        # Verify create/delete calls have correct path formatting
        assert f"{path}/tags/like" in api_paths["create"] or f"{path}/tags/archived" in api_paths["create"]
        assert f"{path}/tags/wip" in api_paths["delete"]


def test_plot_tags_integration(requests_mock):
    """Test the plot tags functionality with mocked HTTP endpoints"""
    from novem import Plot

    plot_type = "bar"
    plot_id = "test_plot"
    valid_tags = []

    # Load test configuration
    base = os.path.dirname(os.path.abspath(__file__))
    config_file = f"{base}/test.conf"
    config = configparser.ConfigParser()
    config.read(config_file)
    api_root = config["general"]["api_root"]

    def verify(val, request, context):
        assert request.text == val

    def verify_put(val, request, context):
        assert request.url == f"{api_root}vis/plots/{plot_id}"

    def put_tag(val, request, context):
        valid_tags.append(val)
        return ""

    def del_tag(val, request, context):
        if val in valid_tags:
            valid_tags.remove(val)
        return ""

    def get_tags(request, context):
        return json.dumps([{"name": v} for v in valid_tags])

    # Mock all the necessary endpoints
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

    # Tags endpoints
    requests_mock.register_uri(
        "get",
        f"{api_root}vis/plots/{plot_id}/tags",
        text=get_tags,
    )

    # Mock PUT for valid tags
    for tag in ["fav", "like", "ignore", "wip", "archived"]:
        requests_mock.register_uri(
            "put",
            f"{api_root}vis/plots/{plot_id}/tags/{tag}",
            text=partial(put_tag, tag),
        )
        requests_mock.register_uri(
            "delete",
            f"{api_root}vis/plots/{plot_id}/tags/{tag}",
            text=partial(del_tag, tag),
        )

    # Mock user tags
    for user_tag in ["+mytag", "+project"]:
        requests_mock.register_uri(
            "put",
            f"{api_root}vis/plots/{plot_id}/tags/{user_tag}",
            text=partial(put_tag, user_tag),
        )
        requests_mock.register_uri(
            "delete",
            f"{api_root}vis/plots/{plot_id}/tags/{user_tag}",
            text=partial(del_tag, user_tag),
        )

    # Create a Plot instance
    n = Plot(plot_id, type=plot_type, config_path=config_file)

    # Tag as favorite
    n.tags = "fav"
    assert valid_tags == ["fav"]

    # Set multiple tags
    n.tags = ["fav", "wip"]
    assert sorted(valid_tags) == sorted(["fav", "wip"])

    # Incrementally add another tag
    n.tags += "like"
    assert sorted(valid_tags) == sorted(["fav", "wip", "like"])

    # Incrementally remove a tag
    n.tags -= "wip"
    assert sorted(valid_tags) == sorted(["fav", "like"])

    # Add a user tag
    n.tags += "+mytag"
    assert sorted(valid_tags) == sorted(["fav", "like", "+mytag"])

    # Test string representation
    tag_string = str(n.tags)
    assert sorted(tag_string.split("\n")) == sorted(valid_tags)

    # Test contains
    assert "fav" in n.tags
    assert "wip" not in n.tags

    # Clear tags
    n.tags = ""
    assert valid_tags == []


def test_tags_empty_and_none_handling():
    """Test that empty strings and None values are handled properly"""
    api = MagicMock()
    tag_path = "test/path"

    api_calls = []
    current_tags = []

    def mock_read(path):
        return json.dumps([{"name": t} for t in current_tags])

    def mock_create(path):
        api_calls.append(("create", path))
        return ""

    def mock_delete(path):
        api_calls.append(("delete", path))
        return ""

    api.read = mock_read
    api.create = mock_create
    api.delete = mock_delete

    tags = NovemTags(api, tag_path)

    # Empty string should not trigger API calls
    api_calls.clear()
    tags.set("")
    assert len(api_calls) == 0

    # None in list should be handled (filtered out)
    api_calls.clear()
    tags.set([None])
    assert len(api_calls) == 0

    # Empty string via += should not trigger API calls
    api_calls.clear()
    tags += ""
    assert len(api_calls) == 0


def test_grid_tags_integration(requests_mock):
    """Test the grid tags functionality with mocked HTTP endpoints"""
    from novem import Grid

    grid_id = "test_grid"
    valid_tags = []

    # Load test configuration
    base = os.path.dirname(os.path.abspath(__file__))
    config_file = f"{base}/test.conf"
    config = configparser.ConfigParser()
    config.read(config_file)
    api_root = config["general"]["api_root"]

    def put_tag(val, request, context):
        valid_tags.append(val)
        return ""

    def del_tag(val, request, context):
        if val in valid_tags:
            valid_tags.remove(val)
        return ""

    def get_tags(request, context):
        return json.dumps([{"name": v} for v in valid_tags])

    # Mock grid creation endpoint
    requests_mock.register_uri(
        "put",
        f"{api_root}vis/grids/{grid_id}",
        text="",
    )

    # Tags endpoints
    requests_mock.register_uri(
        "get",
        f"{api_root}vis/grids/{grid_id}/tags",
        text=get_tags,
    )

    # Mock PUT/DELETE for valid tags
    for tag in ["fav", "like", "ignore", "wip", "archived"]:
        requests_mock.register_uri(
            "put",
            f"{api_root}vis/grids/{grid_id}/tags/{tag}",
            text=partial(put_tag, tag),
        )
        requests_mock.register_uri(
            "delete",
            f"{api_root}vis/grids/{grid_id}/tags/{tag}",
            text=partial(del_tag, tag),
        )

    # Create a Grid instance
    g = Grid(grid_id, config_path=config_file)

    # Tag as favorite
    g.tags = "fav"
    assert valid_tags == ["fav"]

    # Set multiple tags
    g.tags = ["fav", "wip"]
    assert sorted(valid_tags) == sorted(["fav", "wip"])

    # Incrementally add another tag
    g.tags += "like"
    assert sorted(valid_tags) == sorted(["fav", "wip", "like"])

    # Incrementally remove a tag
    g.tags -= "wip"
    assert sorted(valid_tags) == sorted(["fav", "like"])

    # Test contains
    assert "fav" in g.tags
    assert "wip" not in g.tags

    # Clear tags
    g.tags = ""
    assert valid_tags == []


def test_mail_tags_integration(requests_mock):
    """Test the mail tags functionality with mocked HTTP endpoints"""
    from novem import Mail

    mail_id = "test_mail"
    valid_tags = []

    # Load test configuration
    base = os.path.dirname(os.path.abspath(__file__))
    config_file = f"{base}/test.conf"
    config = configparser.ConfigParser()
    config.read(config_file)
    api_root = config["general"]["api_root"]

    def put_tag(val, request, context):
        valid_tags.append(val)
        return ""

    def del_tag(val, request, context):
        if val in valid_tags:
            valid_tags.remove(val)
        return ""

    def get_tags(request, context):
        return json.dumps([{"name": v} for v in valid_tags])

    # Mock mail creation endpoint
    requests_mock.register_uri(
        "put",
        f"{api_root}vis/mails/{mail_id}",
        text="",
    )

    # Tags endpoints
    requests_mock.register_uri(
        "get",
        f"{api_root}vis/mails/{mail_id}/tags",
        text=get_tags,
    )

    # Mock PUT/DELETE for valid tags
    for tag in ["fav", "like", "ignore", "wip", "archived"]:
        requests_mock.register_uri(
            "put",
            f"{api_root}vis/mails/{mail_id}/tags/{tag}",
            text=partial(put_tag, tag),
        )
        requests_mock.register_uri(
            "delete",
            f"{api_root}vis/mails/{mail_id}/tags/{tag}",
            text=partial(del_tag, tag),
        )

    # Create a Mail instance
    m = Mail(mail_id, config_path=config_file)

    # Tag as favorite
    m.tags = "fav"
    assert valid_tags == ["fav"]

    # Set multiple tags
    m.tags = ["fav", "archived"]
    assert sorted(valid_tags) == sorted(["fav", "archived"])

    # Incrementally add another tag
    m.tags += "wip"
    assert sorted(valid_tags) == sorted(["fav", "archived", "wip"])

    # Incrementally remove a tag
    m.tags -= "archived"
    assert sorted(valid_tags) == sorted(["fav", "wip"])

    # Test contains
    assert "fav" in m.tags
    assert "archived" not in m.tags

    # Clear tags
    m.tags = ""
    assert valid_tags == []


def test_job_tags_integration(requests_mock):
    """Test the job tags functionality with mocked HTTP endpoints"""
    from novem import Job

    job_id = "test_job"
    valid_tags = []

    # Load test configuration
    base = os.path.dirname(os.path.abspath(__file__))
    config_file = f"{base}/test.conf"
    config = configparser.ConfigParser()
    config.read(config_file)
    api_root = config["general"]["api_root"]

    def put_tag(val, request, context):
        valid_tags.append(val)
        return ""

    def del_tag(val, request, context):
        if val in valid_tags:
            valid_tags.remove(val)
        return ""

    def get_tags(request, context):
        return json.dumps([{"name": v} for v in valid_tags])

    # Mock job creation endpoint
    requests_mock.register_uri(
        "put",
        f"{api_root}jobs/{job_id}",
        text="",
    )

    # Tags endpoints
    requests_mock.register_uri(
        "get",
        f"{api_root}jobs/{job_id}/tags",
        text=get_tags,
    )

    # Mock PUT/DELETE for valid tags
    for tag in ["fav", "like", "ignore", "wip", "archived", "+project_x"]:
        requests_mock.register_uri(
            "put",
            f"{api_root}jobs/{job_id}/tags/{tag}",
            text=partial(put_tag, tag),
        )
        requests_mock.register_uri(
            "delete",
            f"{api_root}jobs/{job_id}/tags/{tag}",
            text=partial(del_tag, tag),
        )

    # Create a Job instance
    j = Job(job_id, config_path=config_file)

    # Tag as favorite
    j.tags = "fav"
    assert valid_tags == ["fav"]

    # Set multiple tags including user tag
    j.tags = ["fav", "wip", "+project_x"]
    assert sorted(valid_tags) == sorted(["fav", "wip", "+project_x"])

    # Incrementally add another tag
    j.tags += "like"
    assert sorted(valid_tags) == sorted(["fav", "wip", "+project_x", "like"])

    # Incrementally remove a tag
    j.tags -= "wip"
    assert sorted(valid_tags) == sorted(["fav", "+project_x", "like"])

    # Test contains
    assert "fav" in j.tags
    assert "+project_x" in j.tags
    assert "wip" not in j.tags

    # Test string representation
    tag_string = str(j.tags)
    assert sorted(tag_string.split("\n")) == sorted(valid_tags)

    # Test len
    assert len(j.tags) == 3

    # Clear tags
    j.tags = ""
    assert valid_tags == []


def test_tags_duplicate_handling():
    """Test that adding duplicate tags doesn't create duplicates"""
    api = MagicMock()
    tag_path = "test/path"
    tag_data = []
    api_calls = []

    def mock_read(path):
        return json.dumps([{"name": t} for t in tag_data])

    def mock_create(path):
        tag = path.split("/")[-1]
        api_calls.append(("create", tag))
        if tag not in tag_data:
            tag_data.append(tag)
        return ""

    def mock_delete(path):
        tag = path.split("/")[-1]
        api_calls.append(("delete", tag))
        if tag in tag_data:
            tag_data.remove(tag)
        return ""

    api.read = mock_read
    api.create = mock_create
    api.delete = mock_delete

    tags = NovemTags(api, tag_path)

    # Add a tag
    tags.set("fav")
    assert tag_data == ["fav"]

    # Try to add the same tag again via +=
    api_calls.clear()
    tags += "fav"
    # Should not make any API call since tag already exists
    assert len([c for c in api_calls if c[0] == "create"]) == 0
    assert tag_data == ["fav"]


def test_tags_remove_nonexistent():
    """Test that removing a non-existent tag doesn't cause errors"""
    api = MagicMock()
    tag_path = "test/path"
    tag_data = ["fav"]
    api_calls = []

    def mock_read(path):
        return json.dumps([{"name": t} for t in tag_data])

    def mock_create(path):
        tag = path.split("/")[-1]
        api_calls.append(("create", tag))
        if tag not in tag_data:
            tag_data.append(tag)
        return ""

    def mock_delete(path):
        tag = path.split("/")[-1]
        api_calls.append(("delete", tag))
        if tag in tag_data:
            tag_data.remove(tag)
        return ""

    api.read = mock_read
    api.create = mock_create
    api.delete = mock_delete

    tags = NovemTags(api, tag_path)

    # Try to remove a tag that doesn't exist
    api_calls.clear()
    tags -= "wip"
    # Should not make any API call since tag doesn't exist
    assert len([c for c in api_calls if c[0] == "delete"]) == 0
    assert tag_data == ["fav"]


def test_tags_equality_edge_cases():
    """Test equality comparison edge cases"""
    api = MagicMock()
    tag_path = "test/path"

    def mock_read(path):
        return json.dumps([{"name": "fav"}, {"name": "wip"}])

    api.read = mock_read
    api.create = MagicMock()
    api.delete = MagicMock()

    tags = NovemTags(api, tag_path)

    # Comparison with list works
    assert tags == ["fav", "wip"]
    assert tags == ["wip", "fav"]  # Order doesn't matter

    # Comparison with non-list returns False (Python falls back from NotImplemented)
    assert (tags == "fav") is False
    assert (tags == 123) is False
    assert (tags == {"fav", "wip"}) is False

    # Comparison with list containing non-strings returns False
    assert (tags == ["fav", 123]) is False


def test_tags_indexing_and_slicing():
    """Test indexing and slicing functionality"""
    api = MagicMock()
    tag_path = "test/path"

    def mock_read(path):
        return json.dumps([{"name": "archived"}, {"name": "fav"}, {"name": "wip"}])

    api.read = mock_read
    api.create = MagicMock()
    api.delete = MagicMock()

    tags = NovemTags(api, tag_path)

    # Tags are sorted, so order is: archived, fav, wip
    assert tags[0] == "archived"
    assert tags[1] == "fav"
    assert tags[2] == "wip"

    # Slicing
    assert tags[0:2] == ["archived", "fav"]
    assert tags[1:] == ["fav", "wip"]
    assert tags[:2] == ["archived", "fav"]

    # Negative indexing
    assert tags[-1] == "wip"


def test_tags_str_empty():
    """Test string representation when no tags exist"""
    api = MagicMock()
    tag_path = "test/path"

    def mock_read(path):
        return json.dumps([])

    api.read = mock_read
    api.create = MagicMock()
    api.delete = MagicMock()

    tags = NovemTags(api, tag_path)

    assert str(tags) == ""
    assert len(tags) == 0
    assert list(tags) == []
