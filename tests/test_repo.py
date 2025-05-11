import configparser
import io
import os
from contextlib import redirect_stdout
from functools import partial
from unittest.mock import patch

from novem import Repo
from novem.exceptions import Novem403, Novem404
from novem.utils import API_ROOT


def test_repo_ref(requests_mock):
    repo_id = "test_repo"
    repo_user = "test_user"

    base = os.path.dirname(os.path.abspath(__file__))
    config_file = f"{base}/test.conf"

    config = configparser.ConfigParser()
    config.read(config_file)
    api_root = config["general"]["api_root"]

    gcheck = {
        "create": False,
    }

    def verify_create(request, context):
        gcheck["create"] = True
        return ""

    # Plot creation endpoint
    requests_mock.register_uri(
        "put",
        f"{api_root}repos/{repo_id}",
        text=verify_create,
    )
    requests_mock.register_uri(
        "get",
        f"{api_root}whoami",
        text=repo_user,
    )

    r = Repo(repo_id, config_path=config_file)
    assert r.ref("prod") == f"@{repo_user}/{repo_id}:prod"
    assert r.ref("dev") == f"@{repo_user}/{repo_id}:dev"
    assert r.ref("tag:v0.0.1") == f"@{repo_user}/{repo_id}:tag:v0.0.1"


def test_repo_type(requests_mock):
    repo_id = "test_repo"
    repo_type = "job"

    base = os.path.dirname(os.path.abspath(__file__))
    config_file = f"{base}/test.conf"

    config = configparser.ConfigParser()
    config.read(config_file)
    api_root = config["general"]["api_root"]

    gcheck = {
        "create": False,
        "type": False,
    }

    def verify_create(request, context):
        gcheck["create"] = True
        return ""

    # Plot creation endpoint
    requests_mock.register_uri(
        "put",
        f"{api_root}repos/{repo_id}",
        text=verify_create,
    )
    requests_mock.register_uri(
        "get",
        f"{api_root}repos/{repo_id}/config/type",
        text=repo_type,
    )

    r = Repo(repo_id, config_path=config_file)

    assert r.type == repo_type
    assert r.config.type == repo_type


def test_repo_properties(requests_mock):
    repo_id = "test_repo"
    repo_name = "Test Repository"
    repo_description = "This is a test repository description"
    repo_summary = "Repository summary text"
    repo_type = "job"

    base = os.path.dirname(os.path.abspath(__file__))
    config_file = f"{base}/test.conf"

    config = configparser.ConfigParser()
    config.read(config_file)
    api_root = config["general"]["api_root"]

    gcheck = {
        "create": False,
        "name_read": False,
        "name_write": False,
        "description_read": False,
        "description_write": False,
        "summary_read": False,
        "summary_write": False,
        "type_read": False,
        "type_write": False,
    }

    def verify_create(request, context):
        gcheck["create"] = True
        return ""

    def verify_write(key, val, request, context):
        gcheck[f"{key}_write"] = True
        assert request.text == val
        return ""

    def verify_read(key, val, request, context):
        gcheck[f"{key}_read"] = True
        return val

    # Repository creation endpoint
    requests_mock.register_uri(
        "put",
        f"{api_root}repos/{repo_id}",
        text=verify_create,
    )

    # Property endpoints - GET
    requests_mock.register_uri(
        "get",
        f"{api_root}repos/{repo_id}/name",
        text=partial(verify_read, "name", repo_name),
    )

    requests_mock.register_uri(
        "get",
        f"{api_root}repos/{repo_id}/description",
        text=partial(verify_read, "description", repo_description),
    )

    requests_mock.register_uri(
        "get",
        f"{api_root}repos/{repo_id}/summary",
        text=partial(verify_read, "summary", repo_summary),
    )

    requests_mock.register_uri(
        "get",
        f"{api_root}repos/{repo_id}/config/type",
        text=partial(verify_read, "type", repo_type),
    )

    # Property endpoints - POST (write)
    requests_mock.register_uri(
        "post",
        f"{api_root}repos/{repo_id}/name",
        text=partial(verify_write, "name", repo_name),
    )

    requests_mock.register_uri(
        "post",
        f"{api_root}repos/{repo_id}/description",
        text=partial(verify_write, "description", repo_description),
    )

    requests_mock.register_uri(
        "post",
        f"{api_root}repos/{repo_id}/summary",
        text=partial(verify_write, "summary", repo_summary),
    )

    requests_mock.register_uri(
        "post",
        f"{api_root}repos/{repo_id}/config/type",
        text=partial(verify_write, "type", repo_type),
    )

    # Create repository instance
    r = Repo(repo_id, config_path=config_file)

    # Test reading properties
    assert r.name == repo_name
    assert r.description == repo_description
    assert r.summary == repo_summary
    assert r.type == repo_type

    # Test writing properties
    r.name = repo_name
    r.description = repo_description
    r.summary = repo_summary
    r.type = repo_type

    # Verify all operations were performed
    for k, v in gcheck.items():
        assert v is True, f"Operation {k} was not performed"


def test_repo_url_shortname(requests_mock):
    repo_id = "test_repo"
    repo_url = "https://test.novem.no/repo/test_repo"
    repo_shortname = "test_repo_short"

    base = os.path.dirname(os.path.abspath(__file__))
    config_file = f"{base}/test.conf"

    config = configparser.ConfigParser()
    config.read(config_file)
    api_root = config["general"]["api_root"]

    # Repository creation endpoint
    requests_mock.register_uri(
        "put",
        f"{api_root}repos/{repo_id}",
        text="",
    )

    # URL and shortname endpoints
    requests_mock.register_uri(
        "get",
        f"{api_root}repos/{repo_id}/url",
        text=repo_url,
    )

    requests_mock.register_uri(
        "get",
        f"{api_root}repos/{repo_id}/shortname",
        text=repo_shortname,
    )

    # Create repository instance
    r = Repo(repo_id, config_path=config_file)

    # Test read-only properties
    assert r.url == repo_url
    assert r.shortname == repo_shortname


@patch.dict(os.environ, {"NOVEM_TOKEN": "test_token"})
def test_repo_log(requests_mock, fs):
    repo_id = "test_repo"
    log_content = "2023-05-01 12:00:00 - Repository created\n2023-05-01 12:05:00 - Files uploaded"

    requests_mock.register_uri("put", f"{API_ROOT}repos/{repo_id}", text="", status_code=200)
    requests_mock.register_uri("get", f"{API_ROOT}repos/{repo_id}/log", text=log_content, status_code=200)

    r = Repo(repo_id)

    f = io.StringIO()
    with redirect_stdout(f):
        r.log

    output = f.getvalue().strip()
    assert output == log_content


def test_repo_api_operations(requests_mock):
    repo_id = "test_repo"
    test_content = "test content"
    test_path = "/test/path"

    base = os.path.dirname(os.path.abspath(__file__))
    config_file = f"{base}/test.conf"

    config = configparser.ConfigParser()
    config.read(config_file)
    api_root = config["general"]["api_root"]

    # Repository creation endpoint
    requests_mock.register_uri(
        "put",
        f"{api_root}repos/{repo_id}",
        text="",
    )

    # API operations
    requests_mock.register_uri(
        "get",
        f"{api_root}repos/{repo_id}{test_path}",
        text=test_content,
    )

    requests_mock.register_uri(
        "post",
        f"{api_root}repos/{repo_id}{test_path}",
        text="",
    )

    requests_mock.register_uri(
        "put",
        f"{api_root}repos/{repo_id}{test_path}",
        text="",
    )

    requests_mock.register_uri(
        "delete",
        f"{api_root}repos/{repo_id}{test_path}",
        text="",
    )

    # Create repository instance
    r = Repo(repo_id, config_path=config_file)

    # Test API methods
    assert r.api_read(test_path) == test_content
    r.api_write(test_path, test_content)
    r.api_create(test_path)
    r.api_delete(test_path)


def test_repo_w_function(requests_mock):
    repo_id = "test_repo"
    repo_name = "Test Repository"
    custom_key = "/custom/key"
    custom_value = "custom value"

    base = os.path.dirname(os.path.abspath(__file__))
    config_file = f"{base}/test.conf"

    config = configparser.ConfigParser()
    config.read(config_file)
    api_root = config["general"]["api_root"]

    # Repository creation endpoint
    requests_mock.register_uri(
        "put",
        f"{api_root}repos/{repo_id}",
        text="",
    )

    # Name endpoint for property
    requests_mock.register_uri(
        "post",
        f"{api_root}repos/{repo_id}/name",
        text="",
    )

    # Custom key endpoint for API
    requests_mock.register_uri(
        "post",
        f"{api_root}repos/{repo_id}{custom_key}",
        text="",
    )

    # Create repository instance
    r = Repo(repo_id, config_path=config_file)

    # Test w() with property
    result = r.w("name", repo_name)
    assert result == r  # Should return self for chaining

    # Test w() with custom API path
    result = r.w(custom_key, custom_value)
    assert result == r  # Should return self for chaining


def test_repo_error_handling(requests_mock):
    repo_id = "test_repo"
    test_path = "/test/path"

    base = os.path.dirname(os.path.abspath(__file__))
    config_file = f"{base}/test.conf"

    config = configparser.ConfigParser()
    config.read(config_file)
    api_root = config["general"]["api_root"]

    # Repository creation endpoint
    requests_mock.register_uri(
        "put",
        f"{api_root}repos/{repo_id}",
        text="",
    )

    # Error responses
    requests_mock.register_uri(
        "get",
        f"{api_root}repos/{repo_id}{test_path}",
        status_code=404,
    )

    requests_mock.register_uri(
        "post",
        f"{api_root}repos/{repo_id}{test_path}",
        status_code=403,
    )

    # Create repository instance
    r = Repo(repo_id, config_path=config_file)

    # Test error handling
    try:
        r.api_read(test_path)
        assert False, "Should have raised Novem404"
    except Novem404:
        pass

    try:
        r.api_write(test_path, "test")
        assert False, "Should have raised Novem403"
    except Novem403:
        pass


def test_repo_with_config_type(requests_mock):
    repo_id = "test_repo"
    repo_type = "job"

    base = os.path.dirname(os.path.abspath(__file__))
    config_file = f"{base}/test.conf"

    config = configparser.ConfigParser()
    config.read(config_file)
    api_root = config["general"]["api_root"]

    # Repository creation endpoint
    requests_mock.register_uri(
        "put",
        f"{api_root}repos/{repo_id}",
        text="",
    )

    # Custom config endpoints
    requests_mock.register_uri(
        "post",
        f"{api_root}repos/{repo_id}/config/type",
        text="",
    )

    # Test setting type directly
    r = Repo(repo_id, config_path=config_file, type=repo_type)

    # Register a GET endpoint to check the type was set
    requests_mock.register_uri(
        "get",
        f"{api_root}repos/{repo_id}/config/type",
        text=repo_type,
    )

    # Verify the type was set
    assert r.type == repo_type


def test_repo_with_config_dict(requests_mock):
    """Test the new dictionary-based config setting functionality"""
    repo_id = "test_repo"
    repo_type = "job"
    config_dict = {"type": repo_type}

    base = os.path.dirname(os.path.abspath(__file__))
    config_file = f"{base}/test.conf"

    config = configparser.ConfigParser()
    config.read(config_file)
    api_root = config["general"]["api_root"]

    # Repository creation endpoint
    requests_mock.register_uri(
        "put",
        f"{api_root}repos/{repo_id}",
        text="",
    )

    # Custom config endpoints
    requests_mock.register_uri(
        "post",
        f"{api_root}repos/{repo_id}/config/type",
        text="",
    )

    # Create repository instance with config dictionary
    r = Repo(repo_id, config_path=config_file, config=config_dict)

    # Register a GET endpoint to check the type was set via the config dictionary
    requests_mock.register_uri(
        "get",
        f"{api_root}repos/{repo_id}/config/type",
        text=repo_type,
    )

    # Verify the type was set through the config dictionary
    assert r.type == repo_type

    # Test directly using the set method
    new_type = "pipeline"
    requests_mock.register_uri(
        "post",
        f"{api_root}repos/{repo_id}/config/type",
        text="",
    )

    r.config.set({"type": new_type})

    # Update mock for the new type
    requests_mock.register_uri(
        "get",
        f"{api_root}repos/{repo_id}/config/type",
        text=new_type,
    )

    # Verify the new type was set through the config.set method
    assert r.type == new_type
