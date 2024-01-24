import io
import sys
import pytest

from novem.cli import run_cli


class CliExit(RuntimeError):
    def __init__(self, args, code):
        self.args = args
        self.code = code


@pytest.fixture
def cli(capsys, monkeypatch):
    # captreus sys
    def inner(*args, stdin=None):
        sys.argv = ["novem"]
        sys.argv.extend(args)
        if stdin:
            monkeypatch.setattr("sys.stdin", io.StringIO(stdin))
        try:
            run_cli()
            return capsys.readouterr()
        except SystemExit as e:
            raise CliExit(args=capsys.readouterr(), code=e.code)

    return inner
