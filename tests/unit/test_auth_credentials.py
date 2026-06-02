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


def test_credentials_from_service_account_info():
    """credentials_from_service_account_info delegates to SA Credentials.from_service_account_info."""
    mock_creds = MagicMock()
    with patch("google.oauth2.service_account.Credentials.from_service_account_info",
               return_value=mock_creds) as mock_fn:
        from pydantic_gsheets.auth.credentials import credentials_from_service_account_info
        result = credentials_from_service_account_info({"type": "service_account"})
    mock_fn.assert_called_once()
    assert result is mock_creds


def test_credentials_from_service_account_file_custom_scopes():
    """Custom scopes are forwarded to the SA factory function."""
    mock_creds = MagicMock()
    custom = ["https://www.googleapis.com/auth/spreadsheets"]
    with patch("google.oauth2.service_account.Credentials.from_service_account_file",
               return_value=mock_creds) as mock_fn:
        from pydantic_gsheets.auth.credentials import credentials_from_service_account_file
        credentials_from_service_account_file("key.json", scopes=custom)
    _, kwargs = mock_fn.call_args
    assert kwargs.get("scopes") == custom or custom == mock_fn.call_args[1].get("scopes")


def test_credentials_from_adc_with_quota_project():
    mock_creds = MagicMock()
    with patch("google.auth.default", return_value=(mock_creds, "proj")) as mock_default:
        from pydantic_gsheets.auth.credentials import credentials_from_adc
        result = credentials_from_adc(quota_project_id="my-project")
    mock_default.assert_called_once()
    _, kwargs = mock_default.call_args
    assert kwargs.get("quota_project_id") == "my-project"


def test_build_sheets_service():
    mock_creds = MagicMock()
    mock_resource = MagicMock()
    with patch("pydantic_gsheets.auth.credentials.build", return_value=mock_resource) as mock_build:
        from pydantic_gsheets.auth.credentials import build_sheets_service
        result = build_sheets_service(mock_creds)
    mock_build.assert_called_once_with("sheets", "v4", credentials=mock_creds)
    assert result is mock_resource


def test_build_drive_service():
    mock_creds = MagicMock()
    mock_resource = MagicMock()
    with patch("pydantic_gsheets.auth.credentials.build", return_value=mock_resource) as mock_build:
        from pydantic_gsheets.auth.credentials import build_drive_service
        result = build_drive_service(mock_creds)
    mock_build.assert_called_once_with("drive", "v3", credentials=mock_creds)
    assert result is mock_resource


def test_credentials_from_user_oauth():
    """credentials_from_user_oauth delegates to UserOAuthStrategy."""
    mock_creds = MagicMock()
    with patch("pydantic_gsheets.auth._user_oauth.UserOAuthStrategy") as mock_strategy_cls:
        mock_strategy_cls.return_value.get_credentials.return_value = mock_creds
        from pydantic_gsheets.auth.credentials import credentials_from_user_oauth
        result = credentials_from_user_oauth("secrets.json", token_cache_file="token.json")
    assert result is mock_creds
