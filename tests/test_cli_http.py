import pytest

from novem.utils import API_ROOT

from .conftest import CliExit
from .utils import write_config

auth_req = {
    "username": "demouser",
    "password": "demopass",
    "token_name": "demotoken",
    "token_description": "test token",
}


def _no_stdin(monkeypatch):
    """Pretend stdin is a TTY so http handler doesn't try to read it."""
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)


def test_http_get(cli, requests_mock, fs, monkeypatch):
    """--get PATH performs a GET and prints the response body."""
    write_config(auth_req)
    _no_stdin(monkeypatch)

    requests_mock.register_uri(
        "GET",
        f"{API_ROOT}vis/plots/my-plot/data",
        text="hello,world\n1,2\n",
    )

    out, err = cli("--get", "/vis/plots/my-plot/data")

    assert out == "hello,world\n1,2\n"


def test_http_get_strips_leading_slash(cli, requests_mock, fs, monkeypatch):
    """Path without leading slash works the same."""
    write_config(auth_req)
    _no_stdin(monkeypatch)

    requests_mock.register_uri(
        "GET",
        f"{API_ROOT}whoami",
        text="demouser",
    )

    out, err = cli("--get", "whoami")

    assert "demouser" in out


def test_http_post_inline(cli, requests_mock, fs, monkeypatch):
    """--post PATH DATA sends DATA as the request body."""
    write_config(auth_req)
    _no_stdin(monkeypatch)

    captured = {}

    def capture(request, context):
        captured["body"] = request.text
        captured["content_type"] = request.headers.get("Content-type")
        context.status_code = 200
        return ""

    requests_mock.register_uri("POST", f"{API_ROOT}vis/plots/my-plot/data", text=capture)

    cli("--post", "/vis/plots/my-plot/data", "hello world")

    assert captured["body"] == "hello world"
    assert captured["content_type"] == "text/plain"


def test_http_post_from_file(cli, requests_mock, fs, monkeypatch):
    """--post PATH @file reads DATA from file and guesses Content-type from extension."""
    write_config(auth_req)
    _no_stdin(monkeypatch)

    with open("data.csv", "w") as f:
        f.write("a,b,c\n1,2,3\n")

    captured = {}

    def capture(request, context):
        captured["body"] = request.text
        captured["content_type"] = request.headers.get("Content-type")
        context.status_code = 200
        return ""

    requests_mock.register_uri("POST", f"{API_ROOT}vis/plots/my-plot/data", text=capture)

    cli("--post", "/vis/plots/my-plot/data", "@data.csv")

    assert captured["body"] == "a,b,c\n1,2,3\n"
    assert captured["content_type"] == "text/csv"


def test_http_post_from_json_file(cli, requests_mock, fs, monkeypatch):
    """@file with .json extension sets Content-type to application/json."""
    write_config(auth_req)
    _no_stdin(monkeypatch)

    with open("payload.json", "w") as f:
        f.write('{"a": 1}')

    captured = {}

    def capture(request, context):
        captured["content_type"] = request.headers.get("Content-type")
        context.status_code = 200
        return ""

    requests_mock.register_uri("POST", f"{API_ROOT}vis/plots/my-plot/config", text=capture)

    cli("--post", "/vis/plots/my-plot/config", "@payload.json")

    assert captured["content_type"] == "application/json"


def test_http_post_unknown_extension_defaults_to_text_plain(cli, requests_mock, fs, monkeypatch):
    """@file with an extension mimetypes can't guess falls back to text/plain."""
    write_config(auth_req)
    _no_stdin(monkeypatch)

    with open("blob.weirdext", "w") as f:
        f.write("anything")

    captured = {}

    def capture(request, context):
        captured["content_type"] = request.headers.get("Content-type")
        context.status_code = 200
        return ""

    requests_mock.register_uri("POST", f"{API_ROOT}whatever", text=capture)

    cli("--post", "/whatever", "@blob.weirdext")

    assert captured["content_type"] == "text/plain"


def test_http_post_type_overrides_filename_guess(cli, requests_mock, fs, monkeypatch):
    """--type explicitly set wins over the extension-based guess."""
    write_config(auth_req)
    _no_stdin(monkeypatch)

    with open("data.csv", "w") as f:
        f.write("a,b\n1,2\n")

    captured = {}

    def capture(request, context):
        captured["content_type"] = request.headers.get("Content-type")
        context.status_code = 200
        return ""

    requests_mock.register_uri("POST", f"{API_ROOT}vis/plots/my-plot/data", text=capture)

    cli("--type", "application/octet-stream", "--post", "/vis/plots/my-plot/data", "@data.csv")

    assert captured["content_type"] == "application/octet-stream"


def test_http_post_type_with_inline_data(cli, requests_mock, fs, monkeypatch):
    """--type sets Content-type even when DATA is an inline string (no filename to guess)."""
    write_config(auth_req)
    _no_stdin(monkeypatch)

    captured = {}

    def capture(request, context):
        captured["content_type"] = request.headers.get("Content-type")
        context.status_code = 200
        return ""

    requests_mock.register_uri("POST", f"{API_ROOT}some/path", text=capture)

    cli("--type", "application/json", "--post", "/some/path", '{"k": "v"}')

    assert captured["content_type"] == "application/json"


def test_http_post_type_with_stdin(cli, requests_mock, fs):
    """--type applies to stdin-piped bodies too."""
    write_config(auth_req)

    captured = {}

    def capture(request, context):
        captured["content_type"] = request.headers.get("Content-type")
        context.status_code = 200
        return ""

    requests_mock.register_uri("POST", f"{API_ROOT}some/path", text=capture)

    cli("--type", "text/csv", "--post", "/some/path", stdin="a,b\n1,2\n")

    assert captured["content_type"] == "text/csv"


def test_http_put_type_with_file(cli, requests_mock, fs, monkeypatch):
    """--put with @file guesses Content-type from extension."""
    write_config(auth_req)
    _no_stdin(monkeypatch)

    with open("doc.html", "w") as f:
        f.write("<p>hi</p>")

    captured = {}

    def capture(request, context):
        captured["content_type"] = request.headers.get("Content-type")
        context.status_code = 200
        return ""

    requests_mock.register_uri("PUT", f"{API_ROOT}vis/docs/my-doc/content", text=capture)

    cli("--put", "/vis/docs/my-doc/content", "@doc.html")

    assert captured["content_type"] == "text/html"


def test_http_post_missing_file(cli, requests_mock, fs, monkeypatch):
    """@file pointing to a non-existent file errors out cleanly."""
    write_config(auth_req)
    _no_stdin(monkeypatch)

    requests_mock.register_uri("POST", f"{API_ROOT}vis/plots/my-plot/data", text="")

    try:
        cli("--post", "/vis/plots/my-plot/data", "@nope.csv")
        assert False, "expected SystemExit"
    except CliExit as e:
        assert e.code == 1
        assert "does not exist" in e.args[1]


def test_http_post_from_stdin(cli, requests_mock, fs):
    """--post PATH (no DATA) reads body from piped stdin."""
    write_config(auth_req)

    captured = {}

    def capture(request, context):
        captured["body"] = request.text
        context.status_code = 200
        return ""

    requests_mock.register_uri("POST", f"{API_ROOT}vis/plots/my-plot/data", text=capture)

    cli("--post", "/vis/plots/my-plot/data", stdin="from stdin\n")

    assert captured["body"] == "from stdin\n"


def test_http_post_no_data_tty_errors(cli, requests_mock, fs, monkeypatch):
    """--post with no DATA and no piped stdin (TTY) is a usage error."""
    write_config(auth_req)
    _no_stdin(monkeypatch)

    try:
        cli("--post", "/vis/plots/my-plot/data")
        assert False, "expected SystemExit"
    except CliExit as e:
        assert e.code == 1
        assert "--post requires DATA" in e.args[1]


def test_http_put_no_data(cli, requests_mock, fs, monkeypatch):
    """--put PATH with no DATA and no stdin sends an empty PUT."""
    write_config(auth_req)
    _no_stdin(monkeypatch)

    captured = {}

    def capture(request, context):
        captured["body"] = request.text or ""
        captured["content_type"] = request.headers.get("Content-type")
        context.status_code = 200
        return ""

    requests_mock.register_uri("PUT", f"{API_ROOT}vis/plots/my-plot", text=capture)

    cli("--put", "/vis/plots/my-plot")

    assert captured["body"] == ""
    # No data => no Content-type set by us
    assert captured["content_type"] != "text/plain"


def test_http_put_with_data(cli, requests_mock, fs, monkeypatch):
    """--put PATH DATA sends DATA as the request body."""
    write_config(auth_req)
    _no_stdin(monkeypatch)

    captured = {}

    def capture(request, context):
        captured["body"] = request.text
        context.status_code = 200
        return ""

    requests_mock.register_uri("PUT", f"{API_ROOT}vis/plots/my-plot/name", text=capture)

    cli("--put", "/vis/plots/my-plot/name", "My Plot")

    assert captured["body"] == "My Plot"


def test_http_put_from_stdin(cli, requests_mock, fs):
    """--put PATH (no DATA) reads body from piped stdin."""
    write_config(auth_req)

    captured = {}

    def capture(request, context):
        captured["body"] = request.text
        context.status_code = 200
        return ""

    requests_mock.register_uri("PUT", f"{API_ROOT}vis/plots/my-plot/config/type", text=capture)

    cli("--put", "/vis/plots/my-plot/config/type", stdin="bar")

    assert captured["body"] == "bar"


def test_http_delete(cli, requests_mock, fs, monkeypatch):
    """--delete PATH performs a DELETE."""
    write_config(auth_req)
    _no_stdin(monkeypatch)

    requests_mock.register_uri("DELETE", f"{API_ROOT}vis/plots/my-plot", status_code=204, text="")

    out, err = cli("--delete", "/vis/plots/my-plot")

    assert out == ""


HTTP_FLAGS = [
    ("--get", ("/whoami",)),
    ("--post", ("/some/path", "data")),
    ("--put", ("/some/path", "data")),
    ("--delete", ("/some/path",)),
]

PRIMARY_COMMANDS = [
    ("-p", ("my-plot",)),
    ("-g", ("my-grid",)),
    ("-m", ("my-mail",)),
    ("-u", ("alice",)),
    ("--gql", ("{ me { username } }",)),
]


@pytest.mark.parametrize("http_flag, http_args", HTTP_FLAGS)
@pytest.mark.parametrize("primary_flag, primary_args", PRIMARY_COMMANDS)
def test_http_rejects_combining_with_primary(
    cli,
    requests_mock,
    fs,
    monkeypatch,
    http_flag,
    http_args,
    primary_flag,
    primary_args,
):
    """HTTP flags must not be combined with primary commands."""
    write_config(auth_req)
    _no_stdin(monkeypatch)

    try:
        cli(http_flag, *http_args, primary_flag, *primary_args)
        assert False, "expected SystemExit"
    except CliExit as e:
        assert e.code == 1
        assert "must be used in isolation" in e.args[1]


@pytest.mark.parametrize("a_flag, a_args", HTTP_FLAGS)
@pytest.mark.parametrize("b_flag, b_args", HTTP_FLAGS)
def test_http_rejects_combining_two_http_flags(
    cli,
    requests_mock,
    fs,
    monkeypatch,
    a_flag,
    a_args,
    b_flag,
    b_args,
):
    """Two http flags cannot be used together."""
    if a_flag == b_flag:
        pytest.skip("same flag combined with itself is not a meaningful pair")

    write_config(auth_req)
    _no_stdin(monkeypatch)

    try:
        cli(a_flag, *a_args, b_flag, *b_args)
        assert False, "expected SystemExit"
    except CliExit as e:
        assert e.code == 1
        assert "cannot be combined" in e.args[1]


def test_http_get_error_response(cli, requests_mock, fs, monkeypatch):
    """Non-2xx responses print the body and exit non-zero."""
    write_config(auth_req)
    _no_stdin(monkeypatch)

    requests_mock.register_uri(
        "GET",
        f"{API_ROOT}vis/plots/missing",
        status_code=404,
        text="not found",
    )

    try:
        cli("--get", "/vis/plots/missing")
        assert False, "expected SystemExit"
    except CliExit as e:
        assert e.code == 1
        assert "not found" in e.args[0]
