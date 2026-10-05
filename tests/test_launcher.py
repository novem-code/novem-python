import sys
import types

import pytest

import novem_launcher


@pytest.fixture
def native(monkeypatch, tmp_path):
    """Install a fake novem_cli whose binary lives in tmp_path."""
    binary = tmp_path / "novem"
    binary.write_text("")
    mod = types.ModuleType("novem_cli")
    mod.find_binary = lambda: str(binary)  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "novem_cli", mod)
    return str(binary)


@pytest.fixture
def calls(monkeypatch):
    calls = []
    monkeypatch.setattr(novem_launcher.os, "execv", lambda path, args: calls.append(("native", path, args)))
    monkeypatch.setattr("novem.cli.run_cli", lambda: calls.append(("python",)))
    monkeypatch.setattr(sys, "argv", ["novem", "-p", "foo"])
    monkeypatch.delenv("NOVEM_PYTHON_CLI", raising=False)
    return calls


@pytest.mark.skipif(sys.platform == "win32", reason="exec path")
def test_runs_native_binary(native, calls):
    novem_launcher.main()
    assert calls[0] == ("native", native, [native, "-p", "foo"])


def test_falls_back_to_python_cli(monkeypatch, calls):
    monkeypatch.setitem(sys.modules, "novem_cli", None)  # makes the import fail
    novem_launcher.main()
    assert calls == [("python",)]


def test_env_forces_python_cli(monkeypatch, native, calls):
    monkeypatch.setenv("NOVEM_PYTHON_CLI", "1")
    novem_launcher.main()
    assert calls == [("python",)]


def test_version_matches_package():
    from novem import __version__

    assert novem_launcher.__version__ == __version__


@pytest.mark.skipif(sys.platform == "win32", reason="exec path")
def test_passes_python_version_to_native(monkeypatch, native, calls):
    monkeypatch.delenv("NOVEM_PYTHON_VERSION", raising=False)
    novem_launcher.main()
    assert novem_launcher.os.environ["NOVEM_PYTHON_VERSION"] == novem_launcher.__version__


def _on_native_platform_tty(monkeypatch):
    # in the test body: pytest swaps sys.stderr between fixture setup and the call
    monkeypatch.setattr(sys.stderr, "isatty", lambda: True)
    monkeypatch.setattr(novem_launcher.platform, "machine", lambda: "x86_64")
    monkeypatch.setattr(novem_launcher.sys, "platform", "linux")


def test_python_cli_is_flagged_deprecated(monkeypatch, calls, capsys):
    _on_native_platform_tty(monkeypatch)
    monkeypatch.setitem(sys.modules, "novem_cli", None)
    novem_launcher.main()
    assert "pipx install 'novem[cli]'" in capsys.readouterr().err
    assert calls == [("python",)]


def test_deprecation_notice_skipped_when_forced(monkeypatch, calls, capsys):
    _on_native_platform_tty(monkeypatch)
    monkeypatch.setitem(sys.modules, "novem_cli", None)
    monkeypatch.setenv("NOVEM_PYTHON_CLI", "1")
    novem_launcher.main()
    assert capsys.readouterr().err == ""
