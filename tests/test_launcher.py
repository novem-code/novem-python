import sys
import types

import pytest

import novem_launcher


class Execd(Exception):
    """Stands in for os.execv, which never returns."""


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
def no_native(monkeypatch):
    monkeypatch.setitem(sys.modules, "novem_cli", None)  # makes the import fail


@pytest.fixture
def execv(monkeypatch):
    calls = []

    def fake_execv(path, args):
        calls.append((path, args))
        raise Execd

    monkeypatch.setattr(novem_launcher.os, "execv", fake_execv)
    monkeypatch.setattr(sys, "argv", ["novem", "-p", "foo"])
    return calls


def _on_platform(monkeypatch, platform, machine):
    monkeypatch.setattr(novem_launcher.sys, "platform", platform)
    monkeypatch.setattr(novem_launcher.platform, "machine", lambda: machine)


@pytest.mark.skipif(sys.platform == "win32", reason="exec path")
def test_runs_native_binary(native, execv):
    with pytest.raises(Execd):
        novem_launcher.main()
    assert execv == [(native, [native, "-p", "foo"])]


@pytest.mark.skipif(sys.platform == "win32", reason="exec path")
def test_passes_python_version_to_native(monkeypatch, native, execv):
    monkeypatch.delenv("NOVEM_PYTHON_VERSION", raising=False)
    with pytest.raises(Execd):
        novem_launcher.main()
    assert novem_launcher.os.environ["NOVEM_PYTHON_VERSION"] == novem_launcher.__version__


def test_without_native_points_at_the_extra(monkeypatch, no_native, execv, capsys):
    _on_platform(monkeypatch, "linux", "x86_64")
    with pytest.raises(SystemExit) as exc:
        novem_launcher.main()
    assert exc.value.code == 1
    assert "pipx install --force 'novem[cli]'" in capsys.readouterr().err
    assert execv == []


def test_unsupported_platform_says_so(monkeypatch, no_native, execv, capsys):
    _on_platform(monkeypatch, "win32", "ARM64")
    with pytest.raises(SystemExit) as exc:
        novem_launcher.main()
    assert exc.value.code == 1
    err = capsys.readouterr().err
    assert "isn't available for win32/ARM64" in err
    assert "pipx" not in err


def test_version_matches_package():
    from novem import __version__

    assert novem_launcher.__version__ == __version__
