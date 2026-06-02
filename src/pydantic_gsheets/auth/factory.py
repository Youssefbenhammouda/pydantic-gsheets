"""Backward-compatible auth shims. Deprecated — use credentials_from_*() instead."""
from __future__ import annotations

import warnings
from collections.abc import Sequence
from enum import Enum
from typing import Optional

from pydantic import BaseModel

from ._scopes import SHEETS_RW, DRIVE_FULL
from .credentials import (
    credentials_from_user_oauth,
    build_sheets_service as _build_sheets,
    build_drive_service as _build_drive,
)

_MSG = (
    "AuthConfig and AuthMethod are deprecated and will be removed in v3. "
    "Use credentials_from_user_oauth() / credentials_from_service_account_file() / "
    "credentials_from_adc() + build_sheets_service() instead."
)


class AuthMethod(Enum):
    USER_OAUTH = "user_oauth"


class AuthConfig(BaseModel):
    method: AuthMethod = AuthMethod.USER_OAUTH
    scopes: Sequence[str] = (SHEETS_RW, DRIVE_FULL)
    client_secrets_file: Optional[str] = None
    token_cache_file: str = "token.json"
    local_server_port: int = 0


def get_credentials(cfg: AuthConfig):
    warnings.warn(_MSG, DeprecationWarning, stacklevel=2)
    if cfg.method == AuthMethod.USER_OAUTH:
        return credentials_from_user_oauth(
            cfg.client_secrets_file or "client_secrets.json",
            token_cache_file=cfg.token_cache_file,
            scopes=list(cfg.scopes),
            local_server_port=cfg.local_server_port,
        )
    raise ValueError(f"Unsupported auth method: {cfg.method}")


def get_sheets_service(cfg: AuthConfig):
    warnings.warn(_MSG, DeprecationWarning, stacklevel=2)
    return _build_sheets(get_credentials(cfg))


def get_drive_service(cfg: AuthConfig):
    warnings.warn(_MSG, DeprecationWarning, stacklevel=2)
    return _build_drive(get_credentials(cfg))
