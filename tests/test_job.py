import configparser
import io
import os
from contextlib import redirect_stdout
from functools import partial
from unittest.mock import patch

from requests import Response

import pytest

from novem import Job
from novem.exceptions import Novem403, Novem404
from novem.job import Job as _Job
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
        f"{api_root}code/jobs/{job_id}",
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
        f"{api_root}code/jobs/{job_id}",
        text=verify_create,
    )

    # Property endpoints - GET
    requests_mock.register_uri(
        "get",
        f"{api_root}code/jobs/{job_id}/name",
        text=partial(verify_read, "name", job_name),
    )

    requests_mock.register_uri(
        "get",
        f"{api_root}code/jobs/{job_id}/description",
        text=partial(verify_read, "description", job_description),
    )

    requests_mock.register_uri(
        "get",
        f"{api_root}code/jobs/{job_id}/summary",
        text=partial(verify_read, "summary", job_summary),
    )

    requests_mock.register_uri(
        "get",
        f"{api_root}code/jobs/{job_id}/config/type",
        text=partial(verify_read, "type", job_type),
    )

    # Property endpoints - POST (write)
    requests_mock.register_uri(
        "post",
        f"{api_root}code/jobs/{job_id}/name",
        text=partial(verify_write, "name", job_name),
    )

    requests_mock.register_uri(
        "post",
        f"{api_root}code/jobs/{job_id}/description",
        text=partial(verify_write, "description", job_description),
    )

    requests_mock.register_uri(
        "post",
        f"{api_root}code/jobs/{job_id}/summary",
        text=partial(verify_write, "summary", job_summary),
    )

    requests_mock.register_uri(
        "post",
        f"{api_root}code/jobs/{job_id}/config/type",
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
        f"{api_root}code/jobs/{job_id}",
        text=verify_create,
    )

    # Config endpoints - GET
    requests_mock.register_uri(
        "get",
        f"{api_root}code/jobs/{job_id}/config/type",
        text=partial(verify_read, "type", job_type),
    )

    requests_mock.register_uri(
        "get",
        f"{api_root}code/jobs/{job_id}/config/extract",
        text=partial(verify_read, "extract", job_extract),
    )

    requests_mock.register_uri(
        "get",
        f"{api_root}code/jobs/{job_id}/config/render",
        text=partial(verify_read, "render", job_render),
    )

    # Config endpoints - POST (write)
    requests_mock.register_uri(
        "post",
        f"{api_root}code/jobs/{job_id}/config/type",
        text=partial(verify_write, "type", job_type),
    )

    requests_mock.register_uri(
        "post",
        f"{api_root}code/jobs/{job_id}/config/extract",
        text=partial(verify_write, "extract", job_extract),
    )

    requests_mock.register_uri(
        "post",
        f"{api_root}code/jobs/{job_id}/config/render",
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
        f"{api_root}code/jobs/{job_id}",
        text="",
    )

    # URL and shortname endpoints
    requests_mock.register_uri(
        "get",
        f"{api_root}code/jobs/{job_id}/url",
        text=job_url,
    )

    requests_mock.register_uri(
        "get",
        f"{api_root}code/jobs/{job_id}/shortname",
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

    requests_mock.register_uri("put", f"{API_ROOT}code/jobs/{job_id}", text="", status_code=200)
    requests_mock.register_uri("get", f"{API_ROOT}code/jobs/{job_id}/log", text=log_content, status_code=200)

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
        f"{api_root}code/jobs/{job_id}",
        text="",
    )

    # API operations
    requests_mock.register_uri(
        "get",
        f"{api_root}code/jobs/{job_id}{test_path}",
        text=test_content,
    )

    requests_mock.register_uri(
        "post",
        f"{api_root}code/jobs/{job_id}{test_path}",
        text="",
    )

    requests_mock.register_uri(
        "put",
        f"{api_root}code/jobs/{job_id}{test_path}",
        text="",
    )

    requests_mock.register_uri(
        "delete",
        f"{api_root}code/jobs/{job_id}{test_path}",
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
        f"{api_root}code/jobs/{job_id}",
        text="",
    )

    # Name endpoint for property
    requests_mock.register_uri(
        "post",
        f"{api_root}code/jobs/{job_id}/name",
        text="",
    )

    # Custom key endpoint for API
    requests_mock.register_uri(
        "post",
        f"{api_root}code/jobs/{job_id}{custom_key}",
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
        f"{api_root}code/jobs/{job_id}",
        text="",
    )

    # Error responses
    requests_mock.register_uri(
        "get",
        f"{api_root}code/jobs/{job_id}{test_path}",
        status_code=404,
    )

    requests_mock.register_uri(
        "post",
        f"{api_root}code/jobs/{job_id}{test_path}",
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
        f"{api_root}code/jobs/{job_id}",
        text="",
    )

    # Config endpoints - POST
    requests_mock.register_uri(
        "post",
        f"{api_root}code/jobs/{job_id}/config/type",
        text="",
    )

    requests_mock.register_uri(
        "post",
        f"{api_root}code/jobs/{job_id}/config/extract",
        text="",
    )

    requests_mock.register_uri(
        "post",
        f"{api_root}code/jobs/{job_id}/config/render",
        text="",
    )

    # Create job instance with config dictionary
    j = Job(job_id, config_path=config_file, config=config_dict)

    # Register GET endpoints to check the config was set via the config dictionary
    requests_mock.register_uri(
        "get",
        f"{api_root}code/jobs/{job_id}/config/type",
        text=job_type,
    )

    requests_mock.register_uri(
        "get",
        f"{api_root}code/jobs/{job_id}/config/extract",
        text=job_extract,
    )

    requests_mock.register_uri(
        "get",
        f"{api_root}code/jobs/{job_id}/config/render",
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
        f"{api_root}code/jobs/{job_id}/config/type",
        text="",
    )

    requests_mock.register_uri(
        "post",
        f"{api_root}code/jobs/{job_id}/config/extract",
        text="",
    )

    requests_mock.register_uri(
        "post",
        f"{api_root}code/jobs/{job_id}/config/render",
        text="",
    )

    j.config.set({"type": new_type, "extract": new_extract, "render": new_render})

    # Update mocks for the new config values
    requests_mock.register_uri(
        "get",
        f"{api_root}code/jobs/{job_id}/config/type",
        text=new_type,
    )

    requests_mock.register_uri(
        "get",
        f"{api_root}code/jobs/{job_id}/config/extract",
        text=new_extract,
    )

    requests_mock.register_uri(
        "get",
        f"{api_root}code/jobs/{job_id}/config/render",
        text=new_render,
    )

    # Verify the new config was set through the config.set method
    assert j.config.type == new_type
    assert j.config.extract == new_extract
    assert j.config.render == new_render


# ---------------------------------------------------------------------------
# run() tests
# ---------------------------------------------------------------------------


def _make_job(requests_mock, job_id="test_job"):
    """Helper: create a Job with mocked creation endpoint."""
    base = os.path.dirname(os.path.abspath(__file__))
    config_file = f"{base}/test.conf"
    config = configparser.ConfigParser()
    config.read(config_file)
    api_root = config["general"]["api_root"]

    requests_mock.register_uri("put", f"{api_root}code/jobs/{job_id}", text="")
    return Job(job_id, config_path=config_file), api_root


def _make_shared_job(requests_mock, job_id="test_job", user="alice"):
    """Helper: create a Job pointed at another user's namespace, no create call."""
    base = os.path.dirname(os.path.abspath(__file__))
    config_file = f"{base}/test.conf"
    config = configparser.ConfigParser()
    config.read(config_file)
    api_root = config["general"]["api_root"]
    return Job(job_id, user=user, create=False, config_path=config_file), api_root


def test_job_user_prefix_api_read(requests_mock):
    """api_read on a Job with user= targets users/<user>/jobs/<id>/..."""
    j, api_root = _make_shared_job(requests_mock, user="alice")
    requests_mock.register_uri("get", f"{api_root}users/alice/code/jobs/{j.id}/log", text="hello\n")
    assert j.api_read("/log") == "hello\n"


def test_job_user_prefix_log_property(requests_mock, capsys):
    """The .log property on a shared job hits the user-prefixed path."""
    j, api_root = _make_shared_job(requests_mock, user="alice")
    requests_mock.register_uri("get", f"{api_root}users/alice/code/jobs/{j.id}/log", text="line\n")
    j.log
    assert "line" in capsys.readouterr().out


def test_job_user_prefix_run(requests_mock, tmp_path):
    """run() on a shared job posts to users/<user>/jobs/<id>/data."""
    j, api_root = _make_shared_job(requests_mock, user="alice")

    captured = {}

    def handler(request, context):
        captured["url"] = request.url
        return ""

    requests_mock.register_uri("post", f"{api_root}users/alice/code/jobs/{j.id}/data", text=handler)
    j.run()
    assert "users/alice/code/jobs/" in captured["url"]


def test_job_run_no_files(requests_mock):
    """run() without files sends empty JSON to /data."""
    j, api_root = _make_job(requests_mock)

    captured = {}

    def handler(request, context):
        captured["content_type"] = request.headers.get("Content-Type", "")
        captured["body"] = request.text
        return ""

    requests_mock.register_uri("post", f"{api_root}code/jobs/{j.id}/data", text=handler)

    j.run()
    assert "application/json" in captured["content_type"]
    assert captured["body"] == "{}"


def test_job_run_with_files(requests_mock, tmp_path):
    """run() with @-prefixed files sends multipart/form-data preserving filenames."""
    j, api_root = _make_job(requests_mock)

    # Create temp files
    f1 = tmp_path / "data.csv"
    f1.write_text("a,b\n1,2\n")
    f2 = tmp_path / "config.json"
    f2.write_text('{"key": "val"}')

    captured = {}

    def handler(request, context):
        captured["content_type"] = request.headers.get("Content-Type", "")
        captured["body"] = request.body
        return ""

    requests_mock.register_uri("post", f"{api_root}code/jobs/{j.id}/data", text=handler)

    j.run(files=[f"@{f1}", f"@{f2}"])

    assert "multipart/form-data" in captured["content_type"]
    body = captured["body"]
    # requests encodes multipart as bytes or PreparedRequest body
    if isinstance(body, bytes):
        body = body.decode("utf-8", errors="replace")
    else:
        body = str(body)
    # Filenames should be preserved in Content-Disposition headers
    assert "data.csv" in body
    assert "config.json" in body
    # Field names should follow file_0, file_1 convention
    assert "file_0" in body
    assert "file_1" in body


def test_job_run_missing_at_prefix(requests_mock, tmp_path):
    """run() rejects file args without @ prefix."""
    j, api_root = _make_job(requests_mock)
    requests_mock.register_uri("post", f"{api_root}code/jobs/{j.id}/data", text="")

    f1 = tmp_path / "data.csv"
    f1.write_text("a,b\n1,2\n")

    with pytest.raises(SystemExit):
        j.run(files=[str(f1)])


def test_job_run_file_not_found(requests_mock):
    """run() exits if a file does not exist."""
    j, api_root = _make_job(requests_mock)
    requests_mock.register_uri("post", f"{api_root}code/jobs/{j.id}/data", text="")

    with pytest.raises(SystemExit):
        j.run(files=["@nonexistent.csv"])


def test_job_run_single_file(requests_mock, tmp_path):
    """run() works with a single file."""
    j, api_root = _make_job(requests_mock)

    f1 = tmp_path / "report.xlsx"
    f1.write_bytes(b"\x00\x01\x02")

    captured = {}

    def handler(request, context):
        captured["content_type"] = request.headers.get("Content-Type", "")
        captured["body"] = request.body
        return ""

    requests_mock.register_uri("post", f"{api_root}code/jobs/{j.id}/data", text=handler)

    j.run(files=[f"@{f1}"])

    assert "multipart/form-data" in captured["content_type"]
    body = captured["body"]
    if isinstance(body, bytes):
        body = body.decode("utf-8", errors="replace")
    else:
        body = str(body)
    assert "file_0" in body
    assert "report.xlsx" in body


def test_job_run_api_error(requests_mock, tmp_path, capsys):
    """run() prints error and exits on non-ok response."""
    j, api_root = _make_job(requests_mock)

    requests_mock.register_uri(
        "post",
        f"{api_root}code/jobs/{j.id}/data",
        json={"error": "quota exceeded"},
        status_code=402,
    )

    with pytest.raises(SystemExit):
        j.run()

    out = capsys.readouterr().out
    assert "quota exceeded" in out


# ---------------------------------------------------------------------------
# run() input directory tests (-i)
# ---------------------------------------------------------------------------


def test_job_run_with_input_dir_preserves_subpaths(requests_mock, tmp_path):
    """run(input_dir=...) walks the folder and preserves relative paths."""
    j, api_root = _make_job(requests_mock)

    indir = tmp_path / "in"
    (indir / "sub").mkdir(parents=True)
    (indir / "top.csv").write_text("x\n")
    (indir / "sub" / "nested.json").write_text("{}")

    captured = {}

    def handler(request, context):
        captured["content_type"] = request.headers.get("Content-Type", "")
        captured["body"] = request.body
        return ""

    requests_mock.register_uri("post", f"{api_root}code/jobs/{j.id}/data", text=handler)

    j.run(input_dir=str(indir))

    assert "multipart/form-data" in captured["content_type"]
    body = captured["body"]
    if isinstance(body, bytes):
        body = body.decode("utf-8", errors="replace")
    # Relative path with forward slash must reach the wire
    assert "sub/nested.json" in body
    assert "top.csv" in body


def test_job_run_input_dir_skips_dotfiles(requests_mock, tmp_path):
    """run(input_dir=...) skips hidden files and hidden directories."""
    j, api_root = _make_job(requests_mock)

    indir = tmp_path / "in"
    (indir / "sub").mkdir(parents=True)
    (indir / ".git").mkdir()
    (indir / "data.csv").write_text("x\n")
    (indir / ".secret").write_text("nope")
    (indir / "sub" / "ok.json").write_text("{}")
    (indir / "sub" / ".hidden").write_text("nope")
    (indir / ".git" / "HEAD").write_text("ref")

    captured = {}

    def handler(request, context):
        captured["body"] = request.body
        return ""

    requests_mock.register_uri("post", f"{api_root}code/jobs/{j.id}/data", text=handler)

    j.run(input_dir=str(indir))

    body = captured["body"]
    if isinstance(body, bytes):
        body = body.decode("utf-8", errors="replace")
    assert "data.csv" in body
    assert "sub/ok.json" in body
    # dotfiles and contents of hidden dirs must not appear
    assert ".secret" not in body
    assert ".hidden" not in body
    assert "HEAD" not in body


def test_job_run_input_dir_missing(requests_mock):
    """run(input_dir=...) exits if the directory does not exist."""
    j, api_root = _make_job(requests_mock)
    requests_mock.register_uri("post", f"{api_root}code/jobs/{j.id}/data", text="")

    with pytest.raises(SystemExit):
        j.run(input_dir="/nope/does/not/exist")


def test_job_run_files_override_input_dir(requests_mock, tmp_path, capsys):
    """When -R basename collides with an -i entry, -R wins and a warning is emitted."""
    j, api_root = _make_job(requests_mock)

    indir = tmp_path / "in"
    indir.mkdir()
    (indir / "data.csv").write_text("from-input\n")

    other = tmp_path / "other"
    other.mkdir()
    explicit = other / "data.csv"
    explicit.write_text("from-R\n")

    captured = {}

    def handler(request, context):
        captured["body"] = request.body
        return ""

    requests_mock.register_uri("post", f"{api_root}code/jobs/{j.id}/data", text=handler)

    j.run(files=[f"@{explicit}"], input_dir=str(indir))

    body = captured["body"]
    if isinstance(body, bytes):
        body = body.decode("utf-8", errors="replace")
    # Only the -R version's content should be present
    assert "from-R" in body
    assert "from-input" not in body

    err = capsys.readouterr().err
    assert "overrides" in err


# ---------------------------------------------------------------------------
# run() output tests (-o)
# ---------------------------------------------------------------------------


def test_job_run_output_saves_file(requests_mock, tmp_path):
    """run(output=...) saves response body using server filename."""
    j, api_root = _make_job(requests_mock)
    out_dir = str(tmp_path / "results")

    requests_mock.register_uri(
        "post",
        f"{api_root}code/jobs/{j.id}/data",
        content=b"col1,col2\n1,2\n",
        headers={"Content-Disposition": 'attachment; filename="report.csv"'},
    )

    j.run(output=out_dir)

    saved = os.path.join(out_dir, "report.csv")
    assert os.path.isfile(saved)
    assert open(saved, "rb").read() == b"col1,col2\n1,2\n"


def test_job_run_output_rfc8187_filename(requests_mock, tmp_path):
    """run(output=...) parses RFC 8187 filename* header."""
    j, api_root = _make_job(requests_mock)
    out_dir = str(tmp_path / "out")

    requests_mock.register_uri(
        "post",
        f"{api_root}code/jobs/{j.id}/data",
        content=b"data",
        headers={"Content-Disposition": "attachment; filename*=UTF-8''r%C3%A9sult.pdf"},
    )

    j.run(output=out_dir)

    saved = os.path.join(out_dir, "résult.pdf")
    assert os.path.isfile(saved)


def test_job_run_output_fallback_name(requests_mock, tmp_path):
    """run(output=...) falls back to 'output' when no filename in header."""
    j, api_root = _make_job(requests_mock)
    out_dir = str(tmp_path / "out")

    requests_mock.register_uri(
        "post",
        f"{api_root}code/jobs/{j.id}/data",
        content=b"hello",
        headers={},
    )

    j.run(output=out_dir)

    saved = os.path.join(out_dir, "output")
    assert os.path.isfile(saved)
    assert open(saved, "rb").read() == b"hello"


def test_job_run_output_dedup(requests_mock, tmp_path):
    """run(output=...) adds (1), (2), … for duplicate filenames."""
    j, api_root = _make_job(requests_mock)
    out_dir = str(tmp_path / "out")
    os.makedirs(out_dir)
    # Pre-create a file to trigger dedup
    open(os.path.join(out_dir, "report.csv"), "w").close()

    requests_mock.register_uri(
        "post",
        f"{api_root}code/jobs/{j.id}/data",
        content=b"new data",
        headers={"Content-Disposition": 'attachment; filename="report.csv"'},
    )

    j.run(output=out_dir)

    saved = os.path.join(out_dir, "report (1).csv")
    assert os.path.isfile(saved)
    assert open(saved, "rb").read() == b"new data"


def test_job_run_output_creates_dir(requests_mock, tmp_path):
    """run(output=...) creates the output directory if it doesn't exist."""
    j, api_root = _make_job(requests_mock)
    out_dir = str(tmp_path / "a" / "b" / "c")

    requests_mock.register_uri(
        "post",
        f"{api_root}code/jobs/{j.id}/data",
        content=b"ok",
        headers={"Content-Disposition": 'attachment; filename="out.txt"'},
    )

    j.run(output=out_dir)

    assert os.path.isfile(os.path.join(out_dir, "out.txt"))


# ---------------------------------------------------------------------------
# _parse_filename / _dedup_path unit tests
# ---------------------------------------------------------------------------


def test_parse_filename_plain():
    assert _Job._parse_filename('attachment; filename="report.csv"') == "report.csv"


def test_parse_filename_unquoted():
    assert _Job._parse_filename("attachment; filename=report.csv") == "report.csv"


def test_parse_filename_rfc8187():
    assert _Job._parse_filename("attachment; filename*=UTF-8''r%C3%A9port.pdf") == "réport.pdf"


def test_parse_filename_rfc8187_takes_precedence():
    header = "attachment; filename=\"fallback.csv\"; filename*=UTF-8''preferred.csv"
    assert _Job._parse_filename(header) == "preferred.csv"


def test_parse_filename_missing():
    assert _Job._parse_filename("attachment") is None
    assert _Job._parse_filename("") is None


def test_dedup_path_no_conflict(tmp_path):
    assert _Job._dedup_path(str(tmp_path), "file.txt") == os.path.join(str(tmp_path), "file.txt")


def test_dedup_path_with_conflicts(tmp_path):
    open(tmp_path / "file.txt", "w").close()
    assert _Job._dedup_path(str(tmp_path), "file.txt") == os.path.join(str(tmp_path), "file (1).txt")

    open(tmp_path / "file (1).txt", "w").close()
    assert _Job._dedup_path(str(tmp_path), "file.txt") == os.path.join(str(tmp_path), "file (2).txt")


# ---------------------------------------------------------------------------
# timeout tests
# ---------------------------------------------------------------------------


def _ok_response(content=b""):
    r = Response()
    r.status_code = 200
    r._content = content
    return r


def test_session_default_timeout(requests_mock):
    """Default (10, 120) timeout reaches session.send for ordinary API calls."""
    j, _ = _make_job(requests_mock)

    with patch.object(j._session, "send", return_value=_ok_response(b"ok")) as mock_send:
        j.api_read("/log")

    assert mock_send.call_args.kwargs.get("timeout") == (10, 120)


def test_job_run_no_files_uses_job_timeout(requests_mock):
    """run() without files passes timeout=(30, 1800) through to session.send."""
    j, _ = _make_job(requests_mock)

    with patch.object(j._session, "send", return_value=_ok_response()) as mock_send:
        j.run()

    assert mock_send.call_args.kwargs.get("timeout") == (30, 1800)


def test_job_run_with_files_uses_job_timeout(requests_mock, tmp_path):
    """run() with files passes timeout=(30, 1800) through to session.send."""
    j, _ = _make_job(requests_mock)

    f1 = tmp_path / "data.csv"
    f1.write_text("a,b\n1,2\n")

    with patch.object(j._session, "send", return_value=_ok_response()) as mock_send:
        j.run(files=[f"@{f1}"])

    assert mock_send.call_args.kwargs.get("timeout") == (30, 1800)
