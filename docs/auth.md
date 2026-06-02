# Authentication

The library accepts any `google.auth.credentials.Credentials` object directly.
Four factory helpers cover every real-world auth pattern. Pass the resulting
credentials to `build_sheets_service()` / `build_drive_service()` to get API
clients.

## Credential Factories

### `credentials_from_service_account_file(key_file, *, scopes=DEFAULT_SCOPES)`
Load a service account from a JSON key file downloaded from Google Cloud
Console. Best for server-side / CI environments.

```python
from pydantic_gsheets import credentials_from_service_account_file, build_sheets_service

creds = credentials_from_service_account_file("service_account.json")
service = build_sheets_service(creds)
```

### `credentials_from_service_account_info(info, *, scopes=DEFAULT_SCOPES)`
Same as above but accepts an already-parsed `dict` (e.g. loaded from a secret
manager), avoiding a file on disk.

```python
import json
info = json.loads(os.environ["SA_JSON"])
creds = credentials_from_service_account_info(info)
```

### `credentials_from_adc(*, scopes=DEFAULT_SCOPES, quota_project_id=None)`
Application Default Credentials — automatically detects the environment
(GCE, Cloud Run, GKE, local `gcloud auth application-default login`).
Ideal for code that runs both locally and on GCP without config changes.

```python
from pydantic_gsheets import credentials_from_adc, build_sheets_service

creds = credentials_from_adc()
service = build_sheets_service(creds)
```

### `credentials_from_user_oauth(client_secrets_file, *, token_cache_file="token.json", scopes=DEFAULT_SCOPES, local_server_port=0)`
Interactive browser-based OAuth2 flow for end-user sign-in. Opens a browser
on first use; subsequent runs load the cached token automatically.

```python
from pydantic_gsheets import credentials_from_user_oauth, build_sheets_service

creds = credentials_from_user_oauth("client_secrets.json")
service = build_sheets_service(creds)
```

| Parameter | Type | Description |
|---|---|---|
| `client_secrets_file` | `str` | Path to the OAuth client JSON from Google Cloud Console. |
| `token_cache_file` | `str` | Where to persist the refreshable token. Default `"token.json"`. |
| `scopes` | `Sequence[str]` | OAuth scopes to request. Defaults to `DEFAULT_SCOPES`. |
| `local_server_port` | `int` | Port for the local callback server. `0` picks a free port. |

## Service Builders

### `build_sheets_service(credentials)`
Returns an authenticated `googleapiclient.discovery.Resource` for Sheets v4.

### `build_drive_service(credentials)`
Returns an authenticated `googleapiclient.discovery.Resource` for Drive v3.
Only needed if you use Drive-specific features (file chips, etc.).

## Scope Constants

```python
from pydantic_gsheets import SHEETS_RW, SHEETS_RO, DRIVE_FULL, DRIVE_FILE
```

| Constant | Scope | Description |
|---|---|---|
| `SHEETS_RW` | `…/auth/spreadsheets` | Full Sheets read/write |
| `SHEETS_RO` | `…/auth/spreadsheets.readonly` | Sheets read-only |
| `DRIVE_FULL` | `…/auth/drive` | Full Drive access |
| `DRIVE_FILE` | `…/auth/drive.file` | Only files created by this app |

`DEFAULT_SCOPES = (SHEETS_RW, DRIVE_FILE)` — least privilege for typical use.

## SheetsClient

`SheetsClient` wraps a raw `Resource` and adds automatic **retry** and
**rate limiting** to every API call.

```python
from pydantic_gsheets import SheetsClient, RetryConfig

client = SheetsClient(
    service,
    retry_config=RetryConfig(max_attempts=5),
)
ws = GoogleWorkSheet(model=MyRow, service=client, ...)
```

`GoogleWorkSheet` also accepts a raw `Resource` directly (it wraps it in a
`SheetsClient` automatically), but passing a `SheetsClient` lets you tune
retry behaviour.

## Deprecated API

`AuthConfig`, `AuthMethod`, `get_sheets_service()`, and `get_drive_service()`
from `pydantic_gsheets.auth.factory` still work but emit a `DeprecationWarning`
and will be removed in v3. Migrate to the factory functions above.
