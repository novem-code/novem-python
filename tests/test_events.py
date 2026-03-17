import os
import subprocess
import sys
from unittest.mock import patch

from novem.events import EventMessage, Events, _derive_ws_url


def test_event_message_fields():
    msg = EventMessage(
        subscription="/u/alice/p/*/e/*",
        event_class="content",
        event_type="data_update",
        target_fqnp="/u/alice/p/myplot",
        actor="bob",
        ts="2026-03-12T10:00:00Z",
    )

    assert msg.subscription == "/u/alice/p/*/e/*"
    assert msg.event_class == "content"
    assert msg.event_type == "data_update"
    assert msg.target_fqnp == "/u/alice/p/myplot"
    assert msg.actor == "bob"
    assert msg.ts == "2026-03-12T10:00:00Z"
    assert msg.level is None


def test_event_message_uri_alias():
    msg = EventMessage(
        subscription="",
        event_class="",
        event_type="",
        target_fqnp="/u/alice/p/myplot",
        actor="",
        ts="",
    )
    assert msg.uri == "/u/alice/p/myplot"
    assert msg.fqnp == "/u/alice/p/myplot"


def test_event_message_level():
    msg = EventMessage(
        subscription="",
        event_class="",
        event_type="",
        target_fqnp="",
        actor="",
        ts="",
        level="info",
    )
    assert msg.level == "info"


def test_derive_ws_url():
    assert _derive_ws_url("https://api.novem.io/v1/") == "https://api.novem.io"
    assert _derive_ws_url("http://localhost:8080/v1/") == "http://localhost:8080"
    assert _derive_ws_url("https://api.novem.io/v1") == "https://api.novem.io"


def test_events_init():
    """Events should resolve auth from config kwargs."""
    base = os.path.dirname(os.path.abspath(__file__))
    config_file = f"{base}/test.conf"

    evt = Events(
        ["/u/alice/p/*/e/*"],
        config_path=config_file,
    )
    assert evt._patterns == ["/u/alice/p/*/e/*"]
    assert evt._token == "FAKETOKEN"
    assert evt._ws_url == "https://api.novem.io"


def test_events_token_kwarg():
    """Direct token kwarg should override config."""
    base = os.path.dirname(os.path.abspath(__file__))
    config_file = f"{base}/test.conf"

    evt = Events(
        ["/u/alice/p/*/e/*"],
        config_path=config_file,
        token="DIRECTTOKEN",
    )
    assert evt._token == "DIRECTTOKEN"


def test_events_profile_kwarg():
    """Profile kwarg should be mapped to config_profile."""
    base = os.path.dirname(os.path.abspath(__file__))
    config_file = f"{base}/test.conf"

    evt = Events(
        ["/u/alice/p/*/e/*"],
        config_path=config_file,
        profile="demo",
    )
    assert evt._token == "FAKETOKEN"


# ---------------------------------------------------------------------------
# Example script argument parsing
# ---------------------------------------------------------------------------

_EXAMPLE_SCRIPT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "examples", "mention_responder.py")


def _run_example_stderr(*args: str) -> str:
    """Run the example script and return stderr (script may hang at connect, so we use a short timeout)."""
    try:
        result = subprocess.run(
            [sys.executable, _EXAMPLE_SCRIPT, *args],
            capture_output=True,
            text=True,
            timeout=2,
        )
        return result.stderr
    except subprocess.TimeoutExpired as exc:
        # Script printed to stderr before hanging at websocket connect
        return (exc.stderr or b"").decode() if isinstance(exc.stderr, bytes) else (exc.stderr or "")


def test_example_help():
    result = subprocess.run(
        [sys.executable, _EXAMPLE_SCRIPT, "--help"],
        capture_output=True,
        text=True,
        timeout=5,
    )
    assert result.returncode == 0
    assert "--profile" in result.stdout
    assert "pattern" in result.stdout


def test_example_default_patterns():
    stderr = _run_example_stderr()
    assert "Listening on: /u/*/p/*/e/mention" in stderr
    assert "Listening on: /u/*/grp/*/e/mention" in stderr
    assert "Listening on: /o/*/g/*/e/mention" in stderr


def test_example_custom_pattern():
    stderr = _run_example_stderr("/u/bob/p/*/e/mention")
    assert "Listening on: /u/bob/p/*/e/mention" in stderr
    # Custom pattern replaces defaults
    assert "/u/*/grp/" not in stderr


def test_example_profile_flag():
    stderr = _run_example_stderr("--profile", "sd")
    assert "Listening on: /u/*/p/*/e/mention" in stderr
    assert "Listening on: /o/*/g/*/e/mention" in stderr


def test_example_profile_with_pattern():
    stderr = _run_example_stderr("/u/me/p/*/e/*", "--profile", "sd")
    assert "Listening on: /u/me/p/*/e/*" in stderr


# ---------------------------------------------------------------------------
# Events env-var fallback tests
# ---------------------------------------------------------------------------


@patch.dict(os.environ, {"NOVEM_TOKEN": "env_token"}, clear=False)
def test_events_token_from_env(fs):
    """Events should resolve token from NOVEM_TOKEN when no config file exists."""
    evt = Events(["/u/alice/p/*/e/*"], ignore_config=True)
    assert evt._token == "env_token"


@patch.dict(os.environ, {"NOVEM_TOKEN": "env_token", "NOVEM_API_ROOT": "https://custom.api.test/v1/"}, clear=False)
def test_events_api_root_from_env(fs):
    """Events should resolve api_root from NOVEM_API_ROOT when no config file exists."""
    evt = Events(["/u/alice/p/*/e/*"], ignore_config=True)
    assert evt._token == "env_token"
    assert evt._ws_url == "https://custom.api.test"


def test_events_config_token_over_env():
    """Config file token should take priority over NOVEM_TOKEN for Events."""
    base = os.path.dirname(os.path.abspath(__file__))
    config_file = f"{base}/test.conf"

    with patch.dict(os.environ, {"NOVEM_TOKEN": "env_token"}, clear=False):
        evt = Events(["/u/alice/p/*/e/*"], config_path=config_file)
        assert evt._token == "FAKETOKEN"


def test_events_kwarg_token_over_env():
    """Direct token kwarg should take priority over NOVEM_TOKEN for Events."""
    with patch.dict(os.environ, {"NOVEM_TOKEN": "env_token"}, clear=False):
        evt = Events(["/u/alice/p/*/e/*"], token="kwarg_token")
        assert evt._token == "kwarg_token"
