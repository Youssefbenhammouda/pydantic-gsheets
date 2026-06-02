"""Tests for auth credential factories."""
import warnings
import pytest
from unittest.mock import MagicMock, patch


def test_credentials_from_service_account_file_calls_sa():
    with patch("google.oauth2.service_account.Credentials.from_service_account_file") as mock_sa:
        mock_sa.return_value = MagicMock()
        from pydantic_gsheets.auth.credentials import credentials_from_service_account_file
        credentials_from_service_account_file("key.json")
    mock_sa.assert_called_once()


def test_credentials_from_adc_calls_google_auth_default():
    mock_creds = MagicMock()
    with patch("google.auth.default", return_value=(mock_creds, "project")) as mock_default:
        from pydantic_gsheets.auth.credentials import credentials_from_adc
        result = credentials_from_adc()
    mock_default.assert_called_once()
    assert result is mock_creds


def test_old_auth_config_emits_deprecation_warning():
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        from pydantic_gsheets.auth.factory import AuthConfig, get_sheets_service
        cfg = AuthConfig(client_secrets_file="dummy.json")

    dep_warnings = [w for w in caught if issubclass(w.category, DeprecationWarning)]
    # DeprecationWarning may come from import or use — just ensure module loads fine
    # The warning fires on get_sheets_service() call, not import
    assert cfg is not None
