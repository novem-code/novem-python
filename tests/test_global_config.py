import os
from unittest.mock import patch

import pytest

from novem import NovemConfig, Plot, config
from novem.config import resolve
from novem.exceptions import NovemAuthError
from novem.utils import API_ROOT

from .test_config import setup_fake_config
from .test_profile import setup_multi_profile_config


def test_naked_plot_uses_global_token(requests_mock, fs):
    """A token set via novem.config lets naked constructors connect."""
    requests_mock.register_uri("get", f"{API_ROOT}vis/plots/foo/url", text="test-url", status_code=200)

    config.set_token("global_token")

    p = Plot(id="foo", create=False)
    assert p.token == "global_token"
    assert p.url == "test-url"


def test_explicit_token_overrides_global(requests_mock, fs):
    """An explicit per-call token always wins over the global default."""
    config.set_token("global_token")

    p = Plot(id="foo", token="explicit_token", create=False)
    assert p.token == "explicit_token"


def test_global_api_root(requests_mock, fs):
    """set_api_root changes the resolved api root (trailing slash enforced)."""
    config.set_token("global_token")
    config.set_api_root("https://custom.example.com/v9")

    p = Plot(id="foo", create=False)
    assert p._api_root == "https://custom.example.com/v9/"


def test_reset_clears_overrides(requests_mock, fs):
    """After reset() a naked constructor has no token and raises."""
    config.set_token("global_token")
    config.reset()

    with pytest.raises(NovemAuthError):
        Plot(id="foo", create=False)


def test_global_token_beats_env(requests_mock, fs):
    """A programmatically set token wins over NOVEM_TOKEN."""
    config.set_token("global_token")

    with patch.dict(os.environ, {"NOVEM_TOKEN": "env_token"}):
        _, cfg = resolve()
    assert cfg.token == "global_token"


def test_use_profile_selects_config_file_profile(requests_mock, fs):
    """use_profile selects the matching [profile:...] from the config file."""
    setup_fake_config(fs, token="file_token", api_root=API_ROOT)

    config.use_profile("demo")

    _, cfg = resolve()
    assert isinstance(cfg, NovemConfig)
    assert cfg.token == "file_token"
    assert cfg.username == "sondov"


def test_explicit_profile_beats_global_profile(requests_mock, fs):
    """An explicit `profile` arg wins over a globally configured profile."""
    setup_multi_profile_config(fs, API_ROOT)

    config.use_profile("default_user")

    # global default resolves to the default profile
    _, default_cfg = resolve()
    assert default_cfg.token == "DEFAULT_TOKEN"

    # explicit profile (public alias) overrides the global one
    _, explicit_cfg = resolve(profile="other_user")
    assert explicit_cfg.token == "OTHER_TOKEN"

    # the internal config_profile alias works too
    _, alias_cfg = resolve(config_profile="other_user")
    assert alias_cfg.token == "OTHER_TOKEN"


def test_resolve_returns_novemconfig_dataclass(requests_mock, fs):
    config.set_token("global_token")
    found, cfg = resolve()
    assert found is True
    assert isinstance(cfg, NovemConfig)
    assert cfg.token == "global_token"
