# Authentication

The authentication helpers centralize how the library obtains Google API
credentials and builds service clients.

## `AuthStrategy` Protocol
Protocol defining a single method:

```python
get_credentials() -> google.auth.credentials.Credentials
```
Implementations provide refreshed Google credentials.

## `AuthMethod` Enum
`AuthMethod` selects how credentials are acquired. Currently only:

- `USER_OAUTH` – interactive OAuth flow for end users. If you'd like to learn how to use this authentication method, please refer to the [Google sheets OAuth documentation](https://developers.google.com/workspace/sheets/api/quickstart/python).

## `AuthConfig`
Pydantic model configuring authentication.

| Field | Type | Description |
| --- | --- | --- |
| `method` | `AuthMethod` | Strategy used to obtain credentials. |
| `scopes` | `Sequence[str]` | OAuth scopes requested. Defaults to Sheets and Drive access. |
| `client_secrets_file` | `str` or `None` | Path to OAuth client JSON when using user OAuth. |
| `token_cache_file` | `str` | Location to store the refreshable token. |
| `local_server_port` | `int` | Port used by the OAuth local server. `0` picks a free port. |

### `get_credentials(cfg: AuthConfig)`
Resolve credentials using the configured method. For `USER_OAUTH` it
launches the local web server flow and caches the resulting token.

### `get_sheets_service(cfg: AuthConfig)`
Return an authenticated `googleapiclient.discovery.Resource` for the Sheets API.

### `get_drive_service(cfg: AuthConfig)`
Return an authenticated `googleapiclient.discovery.Resource` for the Drive API.

## `UserOAuthConfig`
Dataclass used by the user OAuth strategy.

| Field | Type | Description |
| --- | --- | --- |
| `client_secrets_file` | `str` | OAuth client secret file. |
| `token_cache_file` | `str` | Where to cache the token. |
| `scopes` | `Sequence[str]` | Scopes requested. |
| `local_server_port` | `int` | Port for the local callback server. |

## `UserOAuthStrategy`
Strategy implementing the interactive OAuth flow.

### `get_credentials()`
Reads cached credentials if present, otherwise acquires a new token and
persists the resulting token for reuse.