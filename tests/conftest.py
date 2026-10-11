import pytest

from novem import config


@pytest.fixture(autouse=True)
def reset_global_config():
    """Ensure global connection-config overrides never leak between tests."""
    config.reset()
    yield
    config.reset()
