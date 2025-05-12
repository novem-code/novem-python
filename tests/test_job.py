import configparser
import io
import os
from contextlib import redirect_stdout
from functools import partial
from unittest.mock import patch

from novem import Job
from novem.exceptions import Novem403, Novem404
from novem.utils import API_ROOT


def test_job_ref(requests_mock):
    job_id = "test_job"
    job_user = "test_user"

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

    # Job creation endpoint
    requests_mock.register_uri(
        "put",
        f"{api_root}jobs/{job_id}",
        text=verify_create,
    )
    requests_mock.register_uri(
        "get",
        f"{api_root}whoami",
        text=job_user,
    )

    j = Job(job_id, config_path=config_file)
    assert j.ref("prod") == f"/{job_user}/{job_id}:prod"
    assert j.ref("dev") == f"/{job_user}/{job_id}:dev"
    assert j.ref("tag:v0.0.1") == f"/{job_user}/{job_id}:tag:v0.0.1"


def test_job_properties(requests_mock):
    job_id = "test_job"
    job_name = "Test Job"
    job_description = "This is a test job description"
    job_summary = "Job summary text"
    job_type = "batch"

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

    # Job creation endpoint
    requests_mock.register_uri(
        "put",
        f"{api_root}jobs/{job_id}",
        text=verify_create,
    )

    # Property endpoints - GET
    requests_mock.register_uri(
        "get",
        f"{api_root}jobs/{job_id}/name",
        text=partial(verify_read, "name", job_name),
    )

    requests_mock.register_uri(
        "get",
        f"{api_root}jobs/{job_id}/description",
        text=partial(verify_read, "description", job_description),
    )

    requests_mock.register_uri(
        "get",
        f"{api_root}jobs/{job_id}/summary",
        text=partial(verify_read, "summary", job_summary),
    )

    requests_mock.register_uri(
        "get",
        f"{api_root}jobs/{job_id}/config/type",
        text=partial(verify_read, "type", job_type),
    )

    # Property endpoints - POST (write)
    requests_mock.register_uri(
        "post",
        f"{api_root}jobs/{job_id}/name",
        text=partial(verify_write, "name", job_name),
    )

    requests_mock.register_uri(
        "post",
        f"{api_root}jobs/{job_id}/description",
        text=partial(verify_write, "description", job_description),
    )

    requests_mock.register_uri(
        "post",
        f"{api_root}jobs/{job_id}/summary",
        text=partial(verify_write, "summary", job_summary),
    )

    requests_mock.register_uri(
        "post",
        f"{api_root}jobs/{job_id}/config/type",
        text=partial(verify_write, "type", job_type),
    )

    # Create job instance
    j = Job(job_id, config_path=config_file)

    # Test reading properties
    assert j.name == job_name
    assert j.description == job_description
    assert j.summary == job_summary
    assert j.type == job_type

    # Test writing properties
    j.name = job_name
    j.description = job_description
    j.summary = job_summary
    j.type = job_type

    # Verify all operations were performed
    for k, v in gcheck.items():
        assert v is True, f"Operation {k} was not performed"


def test_job_config(requests_mock):
    job_id = "test_job"
    job_type = "batch"
    job_extract = "sql"
    job_render = "chart"

    base = os.path.dirname(os.path.abspath(__file__))
    config_file = f"{base}/test.conf"

    config = configparser.ConfigParser()
    config.read(config_file)
    api_root = config["general"]["api_root"]

    gcheck = {
        "create": False,
        "type_read": False,
        "type_write": False,
        "extract_read": False,
        "extract_write": False,
        "render_read": False,
        "render_write": False,
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

    # Job creation endpoint
    requests_mock.register_uri(
        "put",
        f"{api_root}jobs/{job_id}",
        text=verify_create,
    )

    # Config endpoints - GET
    requests_mock.register_uri(
        "get",
        f"{api_root}jobs/{job_id}/config/type",
        text=partial(verify_read, "type", job_type),
    )

    requests_mock.register_uri(
        "get",
        f"{api_root}jobs/{job_id}/config/extract",
        text=partial(verify_read, "extract", job_extract),
    )

    requests_mock.register_uri(
        "get",
        f"{api_root}jobs/{job_id}/config/render",
        text=partial(verify_read, "render", job_render),
    )

    # Config endpoints - POST (write)
    requests_mock.register_uri(
        "post",
        f"{api_root}jobs/{job_id}/config/type",
        text=partial(verify_write, "type", job_type),
    )

    requests_mock.register_uri(
        "post",
        f"{api_root}jobs/{job_id}/config/extract",
        text=partial(verify_write, "extract", job_extract),
    )

    requests_mock.register_uri(
        "post",
        f"{api_root}jobs/{job_id}/config/render",
        text=partial(verify_write, "render", job_render),
    )

    # Create job instance
    j = Job(job_id, config_path=config_file)

    # Test reading config properties
    assert j.config.type == job_type
    assert j.config.extract == job_extract
    assert j.config.render == job_render

    # Test writing config properties
    j.config.type = job_type
    j.config.extract = job_extract
    j.config.render = job_render

    # Verify all operations were performed
    for k, v in gcheck.items():
        assert v is True, f"Operation {k} was not performed"


def test_job_url_shortname(requests_mock):
    job_id = "test_job"
    job_url = "https://test.novem.no/job/test_job"
    job_shortname = "test_job_short"

    base = os.path.dirname(os.path.abspath(__file__))
    config_file = f"{base}/test.conf"

    config = configparser.ConfigParser()
    config.read(config_file)
    api_root = config["general"]["api_root"]

    # Job creation endpoint
    requests_mock.register_uri(
        "put",
        f"{api_root}jobs/{job_id}",
        text="",
    )

    # URL and shortname endpoints
    requests_mock.register_uri(
        "get",
        f"{api_root}jobs/{job_id}/url",
        text=job_url,
    )

    requests_mock.register_uri(
        "get",
        f"{api_root}jobs/{job_id}/shortname",
        text=job_shortname,
    )

    # Create job instance
    j = Job(job_id, config_path=config_file)

    # Test read-only properties
    assert j.url == job_url
    assert j.shortname == job_shortname


@patch.dict(os.environ, {"NOVEM_TOKEN": "test_token"})
def test_job_log(requests_mock, fs):
    job_id = "test_job"
    log_content = "2023-05-01 12:00:00 - Job created\n2023-05-01 12:05:00 - Job started"

    requests_mock.register_uri("put", f"{API_ROOT}jobs/{job_id}", text="", status_code=200)
    requests_mock.register_uri("get", f"{API_ROOT}jobs/{job_id}/log", text=log_content, status_code=200)

    j = Job(job_id)

    f = io.StringIO()
    with redirect_stdout(f):
        j.log

    output = f.getvalue().strip()
    assert output == log_content


def test_job_api_operations(requests_mock):
    job_id = "test_job"
    test_content = "test content"
    test_path = "/test/path"

    base = os.path.dirname(os.path.abspath(__file__))
    config_file = f"{base}/test.conf"

    config = configparser.ConfigParser()
    config.read(config_file)
    api_root = config["general"]["api_root"]

    # Job creation endpoint
    requests_mock.register_uri(
        "put",
        f"{api_root}jobs/{job_id}",
        text="",
    )

    # API operations
    requests_mock.register_uri(
        "get",
        f"{api_root}jobs/{job_id}{test_path}",
        text=test_content,
    )

    requests_mock.register_uri(
        "post",
        f"{api_root}jobs/{job_id}{test_path}",
        text="",
    )

    requests_mock.register_uri(
        "put",
        f"{api_root}jobs/{job_id}{test_path}",
        text="",
    )

    requests_mock.register_uri(
        "delete",
        f"{api_root}jobs/{job_id}{test_path}",
        text="",
    )

    # Create job instance
    j = Job(job_id, config_path=config_file)

    # Test API methods
    assert j.api_read(test_path) == test_content
    j.api_write(test_path, test_content)
    j.api_create(test_path)
    j.api_delete(test_path)


def test_job_w_function(requests_mock):
    job_id = "test_job"
    job_name = "Test Job"
    custom_key = "/custom/key"
    custom_value = "custom value"

    base = os.path.dirname(os.path.abspath(__file__))
    config_file = f"{base}/test.conf"

    config = configparser.ConfigParser()
    config.read(config_file)
    api_root = config["general"]["api_root"]

    # Job creation endpoint
    requests_mock.register_uri(
        "put",
        f"{api_root}jobs/{job_id}",
        text="",
    )

    # Name endpoint for property
    requests_mock.register_uri(
        "post",
        f"{api_root}jobs/{job_id}/name",
        text="",
    )

    # Custom key endpoint for API
    requests_mock.register_uri(
        "post",
        f"{api_root}jobs/{job_id}{custom_key}",
        text="",
    )

    # Create job instance
    j = Job(job_id, config_path=config_file)

    # Test w() with property
    result = j.w("name", job_name)
    assert result == j  # Should return self for chaining

    # Test w() with custom API path
    result = j.w(custom_key, custom_value)
    assert result == j  # Should return self for chaining


def test_job_error_handling(requests_mock):
    job_id = "test_job"
    test_path = "/test/path"

    base = os.path.dirname(os.path.abspath(__file__))
    config_file = f"{base}/test.conf"

    config = configparser.ConfigParser()
    config.read(config_file)
    api_root = config["general"]["api_root"]

    # Job creation endpoint
    requests_mock.register_uri(
        "put",
        f"{api_root}jobs/{job_id}",
        text="",
    )

    # Error responses
    requests_mock.register_uri(
        "get",
        f"{api_root}jobs/{job_id}{test_path}",
        status_code=404,
    )

    requests_mock.register_uri(
        "post",
        f"{api_root}jobs/{job_id}{test_path}",
        status_code=403,
    )

    # Create job instance
    j = Job(job_id, config_path=config_file)

    # Test error handling
    try:
        j.api_read(test_path)
        assert False, "Should have raised Novem404"
    except Novem404:
        pass

    try:
        j.api_write(test_path, "test")
        assert False, "Should have raised Novem403"
    except Novem403:
        pass


def test_job_with_config_dict(requests_mock):
    """Test the dictionary-based config setting functionality"""
    job_id = "test_job"
    job_type = "batch"
    job_extract = "sql"
    job_render = "chart"
    config_dict = {"type": job_type, "extract": job_extract, "render": job_render}

    base = os.path.dirname(os.path.abspath(__file__))
    config_file = f"{base}/test.conf"

    config = configparser.ConfigParser()
    config.read(config_file)
    api_root = config["general"]["api_root"]

    # Job creation endpoint
    requests_mock.register_uri(
        "put",
        f"{api_root}jobs/{job_id}",
        text="",
    )

    # Config endpoints - POST
    requests_mock.register_uri(
        "post",
        f"{api_root}jobs/{job_id}/config/type",
        text="",
    )

    requests_mock.register_uri(
        "post",
        f"{api_root}jobs/{job_id}/config/extract",
        text="",
    )

    requests_mock.register_uri(
        "post",
        f"{api_root}jobs/{job_id}/config/render",
        text="",
    )

    # Create job instance with config dictionary
    j = Job(job_id, config_path=config_file, config=config_dict)

    # Register GET endpoints to check the config was set via the config dictionary
    requests_mock.register_uri(
        "get",
        f"{api_root}jobs/{job_id}/config/type",
        text=job_type,
    )

    requests_mock.register_uri(
        "get",
        f"{api_root}jobs/{job_id}/config/extract",
        text=job_extract,
    )

    requests_mock.register_uri(
        "get",
        f"{api_root}jobs/{job_id}/config/render",
        text=job_render,
    )

    # Verify the config was set through the config dictionary
    assert j.config.type == job_type
    assert j.config.extract == job_extract
    assert j.config.render == job_render

    # Test directly using the set method
    new_type = "scheduled"
    new_extract = "api"
    new_render = "table"

    requests_mock.register_uri(
        "post",
        f"{api_root}jobs/{job_id}/config/type",
        text="",
    )

    requests_mock.register_uri(
        "post",
        f"{api_root}jobs/{job_id}/config/extract",
        text="",
    )

    requests_mock.register_uri(
        "post",
        f"{api_root}jobs/{job_id}/config/render",
        text="",
    )

    j.config.set({"type": new_type, "extract": new_extract, "render": new_render})

    # Update mocks for the new config values
    requests_mock.register_uri(
        "get",
        f"{api_root}jobs/{job_id}/config/type",
        text=new_type,
    )

    requests_mock.register_uri(
        "get",
        f"{api_root}jobs/{job_id}/config/extract",
        text=new_extract,
    )

    requests_mock.register_uri(
        "get",
        f"{api_root}jobs/{job_id}/config/render",
        text=new_render,
    )

    # Verify the new config was set through the config.set method
    assert j.config.type == new_type
    assert j.config.extract == new_extract
    assert j.config.render == new_render
