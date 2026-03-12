import os

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
