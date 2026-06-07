import pytest

from novem import Mail, Plot
from novem.config import ConfigManager
from novem.utils import API_ROOT


def test_named_content_arg_is_applied(requests_mock, fs):
    """An explicit content kwarg is written to the API via its setter."""
    m = requests_mock.register_uri("post", f"{API_ROOT}vis/plots/foo/config/type", status_code=200)

    Plot(id="foo", token="t", create=False, type="bar")

    assert m.called
    assert m.last_request.text == "bar"


def test_deferred_content_applied_last(requests_mock, fs):
    """data is applied after other props (it triggers a render)."""
    requests_mock.register_uri("post", f"{API_ROOT}vis/plots/foo/config/type", status_code=200)
    data_req = requests_mock.register_uri("post", f"{API_ROOT}vis/plots/foo/data", status_code=200)

    Plot(id="foo", token="t", create=False, type="bar", data="a,b\n1,2\n")

    assert data_req.called


def test_unknown_kwarg_warns_and_is_non_fatal(requests_mock, fs):
    """An unknown kwarg is warned about, not raised, and construction succeeds."""
    with pytest.warns(UserWarning, match="unknown keyword argument 'titel'"):
        p = Plot(id="foo", token="t", create=False, titel="typo")

    # construction still succeeded despite the bogus kwarg
    assert p.id == "foo"
    assert p.token == "t"


def test_connection_kwarg_does_not_warn(requests_mock, fs, recwarn):
    """Connection/behaviour kwargs must never be flagged as unknown."""
    Plot(id="foo", token="t", create=False, api_root=API_ROOT, debug=True)

    assert not [w for w in recwarn.list if "unknown keyword argument" in str(w.message)]


def test_mail_content_args_explicit(requests_mock, fs):
    """Mail accepts its recipient content args as named params."""
    to_req = requests_mock.register_uri("post", f"{API_ROOT}vis/mails/m/recipients/to", status_code=200)
    subj_req = requests_mock.register_uri("post", f"{API_ROOT}vis/mails/m/config/subject", status_code=200)

    Mail(id="m", token="t", create=False, to="a@b.c", subject="hi")

    assert to_req.called and to_req.last_request.text == "a@b.c"
    assert subj_req.called and subj_req.last_request.text == "hi"


def test_shared_tags_kwargs_not_flagged_unknown(requests_mock, fs, recwarn, monkeypatch):
    """shared/tags are settable on every vis and must not warn (back-compat)."""
    monkeypatch.setattr("novem.shared.NovemShare.set", lambda self, value: None)
    monkeypatch.setattr("novem.tags.NovemTags.set", lambda self, value: None)

    Plot(id="foo", token="t", create=False, shared="@user", tags="x")

    assert not [w for w in recwarn.list if "unknown keyword argument" in str(w.message)]


def test_config_manager_binding(requests_mock, fs):
    """A bound ConfigManager resolves the connection instead of the global default."""
    cm = ConfigManager()
    cm.set_token("bound_token")

    p = Plot(id="foo", create=False, config_manager=cm)
    assert p.token == "bound_token"
