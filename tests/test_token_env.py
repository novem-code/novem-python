import base64
from unittest.mock import patch

import pytest
import requests_mock

from novem import Mail, Plot


def get_basic_auth_header(token):
    return f"Basic {base64.b64encode(f':{token}'.encode()).decode()}"


@pytest.fixture(autouse=True)
def mock_requests():
    with requests_mock.Mocker() as m:
        m.put("https://api.novem.no/v1/vis/plots/plot_id")
        m.put("https://api.novem.no/v1/vis/mails/mail_id")
        yield m


@pytest.fixture
def mock_env_token(monkeypatch):
    monkeypatch.setenv("NOVEM_TOKEN", "test_token_from_env")


@pytest.fixture
def mock_missing_config():
    with patch("builtins.open", side_effect=FileNotFoundError):
        yield


def test_plot_token_from_env(mock_env_token, mock_missing_config, mock_requests):
    plot = Plot("plot_id")
    assert plot.token == "test_token_from_env"
    expected_auth = get_basic_auth_header("test_token_from_env")
    assert mock_requests.last_request.headers["Authorization"] == expected_auth


def test_mail_token_from_env(mock_env_token, mock_missing_config, mock_requests):
    mail = Mail("mail_id")
    assert mail.token == "test_token_from_env"
    expected_auth = get_basic_auth_header("test_token_from_env")
    assert mock_requests.last_request.headers["Authorization"] == expected_auth


def test_no_token_no_file(monkeypatch, mock_missing_config):
    monkeypatch.delenv("NOVEM_TOKEN", raising=False)
    with pytest.raises(SystemExit) as excinfo:
        Plot("plot_id")
    assert excinfo.value.code == 0


def test_custom_token(mock_missing_config, mock_requests):
    custom_token = "custom_test_token"
    plot = Plot("plot_id", token=custom_token)
    assert plot.token == custom_token
    expected_auth = get_basic_auth_header(custom_token)
    assert mock_requests.last_request.headers["Authorization"] == expected_auth
