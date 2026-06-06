import novem
from novem import Session
from novem.utils import API_ROOT

from .test_profile import setup_multi_profile_config


def test_session_binds_token(requests_mock, fs):
    """A Session resolves its bound token into constructed widgets."""
    s = Session(token="sess_token")
    p = s.Plot("foo", create=False)
    assert p.token == "sess_token"


def test_session_binds_profile_from_config_file(requests_mock, fs):
    """A Session bound to a profile resolves that profile's token."""
    setup_multi_profile_config(fs, API_ROOT)

    prod = Session(profile="other_user")
    p = prod.Plot("earnings", create=False)
    assert p.token == "OTHER_TOKEN"


def test_two_sessions_coexist(requests_mock, fs):
    """Differently-bound sessions don't interfere with each other."""
    setup_multi_profile_config(fs, API_ROOT)

    prod = Session(profile="default_user")
    staging = Session(profile="other_user")

    p_prod = prod.Plot("earnings", create=False)
    p_staging = staging.Plot("earnings", create=False)

    assert p_prod.token == "DEFAULT_TOKEN"
    assert p_staging.token == "OTHER_TOKEN"


def test_session_does_not_mutate_global_config(requests_mock, fs):
    """Building a Session leaves novem.config untouched."""
    Session(token="sess_token", profile="prod")
    assert novem.config._overrides == {}


def test_session_api_root_override(requests_mock, fs):
    """api_root override flows through to the constructed widget."""
    s = Session(token="t", api_root="https://custom.example/v9")
    p = s.Plot("foo", create=False)
    assert p._api_root == "https://custom.example/v9/"


def test_config_session_inherits_global_overrides(requests_mock, fs):
    """novem.config.session() layers on a snapshot of the global overrides."""
    novem.config.set_api_root("https://global.example/v1")
    s = novem.config.session(token="t")

    p = s.Plot("foo", create=False)
    assert p.token == "t"
    assert p._api_root == "https://global.example/v1/"
