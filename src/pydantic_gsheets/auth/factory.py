from __future__ import annotations
from enum import Enum
from typing import Optional, Sequence

from pydantic import BaseModel, Field
from googleapiclient.discovery import build
from googleapiclient.discovery import Resource

from .user_oauth import UserOAuthConfig, UserOAuthStrategy, DEFAULT_SCOPES

class AuthMethod(str, Enum):
    USER_OAUTH = "user_oauth"
    # Future: AUTO = "auto", SERVICE_ACCOUNT = "service_account", etc.

class AuthConfig(BaseModel):
    method: AuthMethod = AuthMethod.USER_OAUTH
    scopes: Sequence[str] = Field(default_factory=lambda: list(DEFAULT_SCOPES))

    # User OAuth fields
    client_secrets_file: Optional[str] = None
    token_cache_file: str = "token.json"
    local_server_port: int = 0

def get_credentials(cfg: AuthConfig):
    if cfg.method == AuthMethod.USER_OAUTH:
        assert cfg.client_secrets_file, "client_secrets_file is required for USER_OAUTH"
        strategy = UserOAuthStrategy(
            UserOAuthConfig(
                client_secrets_file=cfg.client_secrets_file,
                token_cache_file=cfg.token_cache_file,
                scopes=cfg.scopes,
                
                local_server_port=cfg.local_server_port,
            )
        )
        return strategy.get_credentials()

    raise NotImplementedError(f"Auth method {cfg.method} not implemented yet.")

def get_sheets_service(cfg: AuthConfig) -> Resource:
    """Return a googleapiclient Sheets service authorized via the chosen method."""
    creds = get_credentials(cfg)
    return build("sheets", "v4", credentials=creds)

def get_drive_service(cfg: AuthConfig) -> Resource:
    """Return a googleapiclient Drive service authorized via the chosen method."""
    creds = get_credentials(cfg)
    return build("drive", "v3", credentials=creds)
