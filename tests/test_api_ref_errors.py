import pytest

from novem.api_ref import Novem403, Novem404, Novem409, NovemAPI, NovemException

API_ROOT = "https://api.novem.io/v1/"


@pytest.fixture
def api():
    return NovemAPI(token="nbt-toktok", api_root=API_ROOT, ignore_config=True)


def test_write_raises_on_server_error(api, requests_mock, capsys):
    """A 5xx on write must raise, not print the body and return."""
    requests_mock.register_uri("POST", f"{API_ROOT}vis/plots/my-plot/data", status_code=500, json={"message": "boom"})

    with pytest.raises(NovemException, match="boom"):
        api.write("vis/plots/my-plot/data", "1,2,3")

    assert capsys.readouterr().out == ""


def test_write_raises_on_forbidden(api, requests_mock):
    requests_mock.register_uri("POST", f"{API_ROOT}vis/plots/my-plot/data", status_code=403, json={"message": "nope"})

    with pytest.raises(Novem403, match="nope"):
        api.write("vis/plots/my-plot/data", "1,2,3")


def test_write_raises_novem404_on_non_json_body(api, requests_mock):
    """A 404 whose body is not JSON must still raise Novem404."""
    requests_mock.register_uri("POST", f"{API_ROOT}vis/plots/my-plot/data", status_code=404, text="<html>404</html>")

    with pytest.raises(Novem404):
        api.write("vis/plots/my-plot/data", "1,2,3")


def test_create_raises_on_server_error(api, requests_mock, capsys):
    """A 5xx on create must raise, not report success."""
    requests_mock.register_uri("PUT", f"{API_ROOT}vis/plots/my-plot", status_code=500, json={"message": "boom"})

    with pytest.raises(NovemException, match="boom"):
        api.create("vis/plots/my-plot")

    assert capsys.readouterr().out == ""


def test_create_raises_novem404_on_non_json_body(api, requests_mock):
    requests_mock.register_uri("PUT", f"{API_ROOT}vis/plots/my-plot", status_code=404, text="<html>404</html>")

    with pytest.raises(Novem404):
        api.create("vis/plots/my-plot")


def test_create_returns_false_on_conflict(api, requests_mock):
    requests_mock.register_uri("PUT", f"{API_ROOT}vis/plots/my-plot", status_code=409, json={"message": "exists"})

    assert api.create("vis/plots/my-plot") is False


def test_create_raises_on_conflict_when_asked(api, requests_mock):
    requests_mock.register_uri("PUT", f"{API_ROOT}vis/plots/my-plot", status_code=409, json={"message": "exists"})

    with pytest.raises(Novem409, match="exists"):
        api.create("vis/plots/my-plot", raise_on_conflict=True)


def test_create_tolerates_non_json_conflict(api, requests_mock):
    """A 409 with a non-JSON body must still return False, not blow up."""
    requests_mock.register_uri("PUT", f"{API_ROOT}vis/plots/my-plot", status_code=409, text="<html>409</html>")

    assert api.create("vis/plots/my-plot") is False


def test_create_returns_true_on_success(api, requests_mock):
    requests_mock.register_uri("PUT", f"{API_ROOT}vis/plots/my-plot", status_code=201, text="")

    assert api.create("vis/plots/my-plot") is True


def test_write_returns_none_on_success(api, requests_mock):
    requests_mock.register_uri("POST", f"{API_ROOT}vis/plots/my-plot/data", status_code=200, text="")

    assert api.write("vis/plots/my-plot/data", "1,2,3") is None
