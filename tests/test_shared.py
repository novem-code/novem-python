import configparser
import json
import os
from functools import partial
from unittest.mock import MagicMock

from novem.shared import NovemShare


class MockGroup:
    """Mock Group class for testing"""

    def __init__(self, group_id: str):
        self.group_id = group_id

    def get_share_string(self) -> str:
        return f"+group~{self.group_id}"


class MockClaim:
    """Mock Claim class for testing"""

    def __init__(self, claim_id: str):
        self.claim_id = claim_id

    def get_share_string(self) -> str:
        return f"@claim/{self.claim_id}"


def test_novem_share_standalone():
    """Test standalone NovemShare functionality with a mocked API"""
    api = MagicMock()
    share_path = "test/path"
    share_data = []

    # Setup mock API responses
    def mock_read(path):
        return json.dumps([{"name": s} for s in share_data])

    def mock_create(path):
        # Extract user_id from path
        user = path.split("/")[-1]
        if user not in share_data:
            share_data.append(user)
        return ""

    def mock_delete(path):
        # Extract user_id from path
        user = path.split("/")[-1]
        if user in share_data:
            share_data.remove(user)
        return ""

    # Configure the mock API
    api.read = mock_read
    api.create = mock_create
    api.delete = mock_delete

    # Create a NovemShare instance
    share = NovemShare(api, share_path)

    # Test get method with empty data
    assert share.get() == []

    # Test set method with a string
    share.set("user1")
    assert share_data == ["user1"]

    # Test set method with a list
    share.set(["user1", "user2", "user3"])
    assert sorted(share_data) == sorted(["user1", "user2", "user3"])

    # Test __iadd__ operator
    share += "user4"
    assert sorted(share_data) == sorted(["user1", "user2", "user3", "user4"])

    # Test __isub__ operator
    share -= "user2"
    assert sorted(share_data) == sorted(["user1", "user3", "user4"])

    # Test __str__ method
    string_repr = str(share)
    assert sorted(string_repr.split("\n")) == sorted(["user1", "user3", "user4"])

    # Test __len__ method
    length = len(share)
    assert length == 3

    # Test __iter__ method
    items = list(share)
    assert sorted(items) == sorted(["user1", "user3", "user4"])

    # Test __getitem__ method
    # Note: we can't test direct indexing since the order is not guaranteed
    assert len(share[0:3]) == 3

    # Test __eq__ method
    assert share == ["user1", "user3", "user4"]
    assert not (share == ["user1", "user2"])


def test_novem_share_api_parameters():
    """Test that NovemShare correctly constructs API paths"""
    api = MagicMock()

    # Track API calls to verify paths
    api_paths = {"read": [], "create": [], "delete": []}

    # Setup mock API to track call paths
    def mock_read(path):
        api_paths["read"].append(path)
        return json.dumps([{"name": "user1"}, {"name": "user2"}])

    def mock_create(path):
        api_paths["create"].append(path)
        return ""

    def mock_delete(path):
        api_paths["delete"].append(path)
        return ""

    # Configure the mock API
    api.read = mock_read
    api.create = mock_create
    api.delete = mock_delete

    # Test with different share paths
    share_paths = ["repos/repo1", "vis/plots/plot1", "admin/orgs/org1"]

    for path in share_paths:
        api_paths = {"read": [], "create": [], "delete": []}
        share = NovemShare(api, path)

        # Test get method
        share.get()
        assert api_paths["read"] == [f"{path}/shared"]

        # Test set method
        share.set(["user1", "user3"])
        assert f"{path}/shared" in api_paths["read"]

        # Test direct operations
        share += "user4"
        share -= "user2"

        # Verify create calls have correct path formatting
        assert f"{path}/shared/user3" in api_paths["create"] or f"{path}/shared/user4" in api_paths["create"]
        assert f"{path}/shared/user2" in api_paths["delete"]


def test_plot_share_integration(requests_mock):
    """Test the original plot share functionality remains working"""
    from novem import Plot

    plot_type = "bar"
    plot_id = "test_plot"
    valid_names = []

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

    def put_share(val, request, context):
        valid_names.append(val)
        return ""

    def del_share(val, request, context):
        if val in valid_names:
            valid_names.remove(val)
        return ""

    def get_shares(request, context):
        return json.dumps([{"name": v} for v in valid_names])

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

    # Shared endpoints
    requests_mock.register_uri(
        "get",
        f"{api_root}vis/plots/{plot_id}/shared",
        text=get_shares,
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

    requests_mock.register_uri(
        "delete",
        f"{api_root}vis/plots/{plot_id}/shared/+novem_demo~novem_demo",
        text=partial(del_share, "+novem_demo~novem_demo"),
    )

    requests_mock.register_uri(
        "delete",
        f"{api_root}vis/plots/{plot_id}/shared/public",
        text=partial(del_share, "public"),
    )

    # Create a Plot instance
    n = Plot(plot_id, type=plot_type, config_path=config_file)

    # Share with public
    n.shared = "public"
    assert valid_names == ["public"]

    # Share with multiple users
    n.shared = ["public", "+novem_demo~novem_demo"]
    assert sorted(valid_names) == sorted(["public", "+novem_demo~novem_demo"])

    # Incrementally add another share
    n.shared += "+novem_demo~novem_test"
    assert sorted(valid_names) == sorted(["public", "+novem_demo~novem_demo", "+novem_demo~novem_test"])

    # Incrementally remove a share
    n.shared -= "+novem_demo~novem_test"
    assert sorted(valid_names) == sorted(["public", "+novem_demo~novem_demo"])

    # Test string representation
    share_string = str(n.shared)
    assert sorted(share_string.split("\n")) == sorted(valid_names)

    # Clear shares
    n.shared = ""
    assert valid_names == []


def test_share_with_group_and_claim():
    """Test sharing with Group and Claim objects"""
    api = MagicMock()
    share_path = "test/path"

    # Track API calls instead of mocking share data
    api_calls = []

    # Define mock API methods and the current state of shares
    current_shares = []

    def mock_read(path):
        # Return the current shares
        return json.dumps([{"name": s} for s in current_shares])

    def mock_create(path):
        api_calls.append(("create", path))
        return ""

    def mock_delete(path):
        api_calls.append(("delete", path))
        return ""

    # Configure the API mock
    api.read = mock_read
    api.create = mock_create
    api.delete = mock_delete

    # Create a NovemShare instance
    share = NovemShare(api, share_path)

    # Create mock Group and Claim objects
    group1 = MockGroup("engineering")
    group2 = MockGroup("marketing")
    claim1 = MockClaim("claim123")
    claim2 = MockClaim("claim456")

    # Test with a Group object
    api_calls.clear()
    share.set(group1)
    expected_path = f"{share_path}/shared/{group1.get_share_string()}"
    assert any(
        call[0] == "create" and expected_path in call[1] for call in api_calls
    ), f"Expected path containing '{group1.get_share_string()}' not found in API calls"

    # Test with a Claim object
    api_calls.clear()
    share.set(claim1)
    expected_path = f"{share_path}/shared/{claim1.get_share_string()}"
    assert any(
        call[0] == "create" and expected_path in call[1] for call in api_calls
    ), f"Expected path containing '{claim1.get_share_string()}' not found in API calls"

    # Test with a mix of strings, Groups and Claims
    api_calls.clear()

    # Update the current shares for the test
    current_shares.clear()

    share.set(["public", group1, claim1, group2])

    # Check all expected paths were created
    expected_items = ["public", group1.get_share_string(), claim1.get_share_string(), group2.get_share_string()]

    for item in expected_items:
        expected_path = f"{share_path}/shared/{item}"
        assert any(
            call[0] == "create" and expected_path in call[1] for call in api_calls
        ), f"Expected path containing '{item}' not found in API calls"

    # Update the current shares to match what would happen after the API calls
    current_shares.extend(expected_items)

    # Test incrementally adding with += operator
    api_calls.clear()
    share += claim2
    expected_path = f"{share_path}/shared/{claim2.get_share_string()}"
    assert any(
        call[0] == "create" and expected_path in call[1] for call in api_calls
    ), f"Expected path containing '{claim2.get_share_string()}' not found in API calls"

    # Update current shares
    current_shares.append(claim2.get_share_string())

    # Test incrementally removing with -= operator
    api_calls.clear()
    share -= group1
    expected_path = f"{share_path}/shared/{group1.get_share_string()}"
    assert any(
        call[0] == "delete" and expected_path in call[1] for call in api_calls
    ), f"Expected path containing '{group1.get_share_string()}' not found in API calls"

    # Update current shares
    current_shares.remove(group1.get_share_string())

    # Test empty objects are handled properly
    class EmptyShareable:
        def get_share_string(self) -> str:
            return ""

    api_calls.clear()
    empty_obj = EmptyShareable()
    share.set([empty_obj])
    assert len(api_calls) == 0, "API calls should not be made for empty share strings"

    # Test None objects are handled properly
    api_calls.clear()
    share.set([None])
    assert len(api_calls) == 0, "API calls should not be made for None objects"
