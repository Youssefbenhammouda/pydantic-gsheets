from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Sequence, Optional

from google.auth.transport.requests import Request
from google.auth.credentials import Credentials  # Base credential interface
from google.oauth2.credentials import Credentials as UserCredentials
from google_auth_oauthlib.flow import InstalledAppFlow

DEFAULT_SCOPES = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]

@dataclass
class UserOAuthConfig:
    client_secrets_file: str                 # path to the downloaded OAuth client JSON
    token_cache_file: str = "token.json"     # where to store the refreshable user token
    scopes: Sequence[str] = tuple(DEFAULT_SCOPES)
    local_server_port: int = 0     # 0 = auto-pick an open port

class UserOAuthStrategy:
    def __init__(self, cfg: UserOAuthConfig):
        self.cfg = cfg

    def get_credentials(self) -> Credentials:
        creds: Optional[Credentials] = None

        # Load cached credentials if present
        if os.path.exists(self.cfg.token_cache_file):
            creds = UserCredentials.from_authorized_user_file(
                self.cfg.token_cache_file, list(self.cfg.scopes)
            )

        # Refresh or obtain new credentials
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    self.cfg.client_secrets_file, scopes=list(self.cfg.scopes)
                )
                
                # Opens a browser and starts a tiny local server to receive the callback.
                creds = flow.run_local_server(
                    port=self.cfg.local_server_port
                )

            # Persist for reuse
            # Create the directories of the token cache file if they don't exist
            os.makedirs(os.path.dirname(self.cfg.token_cache_file), exist_ok=True)
            with open(self.cfg.token_cache_file, "w+") as f:
                f.write(creds.to_json())

        assert creds is not None  # for type checker
        return creds
