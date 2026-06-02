from __future__ import annotations

import os
from collections.abc import Sequence

from googleapiclient.discovery import build, Resource
from google.auth.credentials import Credentials

from ._scopes import DEFAULT_SCOPES


def credentials_from_service_account_file(
    key_file: str | os.PathLike[str],
    *,
    scopes: Sequence[str] = DEFAULT_SCOPES,
) -> Credentials:
    """Load credentials from a service account JSON key file."""
    from google.oauth2.service_account import Credentials as SACredentials
    return SACredentials.from_service_account_file(str(key_file), scopes=list(scopes))


def credentials_from_service_account_info(
    info: dict,
    *,
    scopes: Sequence[str] = DEFAULT_SCOPES,
) -> Credentials:
    """Load credentials from an already-parsed service account dict."""
    from google.oauth2.service_account import Credentials as SACredentials
    return SACredentials.from_service_account_info(info, scopes=list(scopes))


def credentials_from_adc(
    *,
    scopes: Sequence[str] = DEFAULT_SCOPES,
    quota_project_id: str | None = None,
) -> Credentials:
    """Application Default Credentials — works in GCE, Cloud Run, GKE, local gcloud."""
    import google.auth
    creds, _ = google.auth.default(scopes=list(scopes), quota_project_id=quota_project_id)
    return creds


def credentials_from_user_oauth(
    client_secrets_file: str | os.PathLike[str],
    *,
    token_cache_file: str | os.PathLike[str] = "token.json",
    scopes: Sequence[str] = DEFAULT_SCOPES,
    local_server_port: int = 0,
) -> Credentials:
    """Browser-based installed-app OAuth2 flow."""
    from ._user_oauth import UserOAuthConfig, UserOAuthStrategy
    return UserOAuthStrategy(UserOAuthConfig(
        client_secrets_file=str(client_secrets_file),
        token_cache_file=str(token_cache_file),
        scopes=list(scopes),
        local_server_port=local_server_port,
    )).get_credentials()


def build_sheets_service(credentials: Credentials) -> Resource:
    """Build a Sheets v4 API Resource from credentials."""
    return build("sheets", "v4", credentials=credentials)


def build_drive_service(credentials: Credentials) -> Resource:
    """Build a Drive v3 API Resource from credentials."""
    return build("drive", "v3", credentials=credentials)
