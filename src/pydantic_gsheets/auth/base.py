from typing import Protocol
from google.auth.credentials import Credentials as GoogleCredentials

class AuthStrategy(Protocol):
    def get_credentials(self) -> GoogleCredentials:
        """Return valid Google credentials (refresh if needed)."""
        ...
