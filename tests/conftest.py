import io
import sys

import pytest

from novem import config
from novem.cli import run_cli


@pytest.fixture(autouse=True)
def reset_global_config():
    """Ensure global connection-config overrides never leak between tests."""
    config.reset()
    yield
    config.reset()


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
