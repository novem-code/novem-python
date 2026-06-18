from novem.cli import _cli_excepthook
from novem.exceptions import Novem404


def test_excepthook_hides_internal_type_and_auth_hint(capsys):
    """CLI output shows the detail, but not the class name or the auth hint."""
    exc = Novem404("/v1/vis/plots/asf/asdf/fad")
    _cli_excepthook(type(exc), exc, None)

    err = capsys.readouterr().err
    assert "Resource not found: /v1/vis/plots/asf/asdf/fad" in err
    assert "Novem404" not in err
    assert "(Are you authenticated?)" not in err  # hint is library-only


def test_library_message_keeps_auth_hint():
    """Library callers (no up-front auth check) still get the hint via str()."""
    exc = Novem404("/x")
    assert str(exc) == "Resource not found: /x (Are you authenticated?)"
    assert exc.cli_message == "Resource not found: /x"


def test_excepthook_keeps_type_for_unexpected_errors(capsys):
    """Unexpected (non-novem) errors keep their type to aid debugging."""
    _cli_excepthook(ValueError, ValueError("boom"), None)

    err = capsys.readouterr().err
    assert "ValueError: boom" in err
