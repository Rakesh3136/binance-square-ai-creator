# NIC OS tool-broker autonomy enforcement

This increment connects owner grants to the actual NIC chat tool-call path.

## Runtime wiring

Configure these values only in the trusted NIC API service environment:
- `NIC_OWNER_CONTROL_TOKEN`: high-entropy owner API bearer secret.
- `NIC_OWNER_IDENTITY`: stable configured owner identity; never accept this from request JSON.
- `NIC_OWNER_CONTROL_DB`: path to the owner-control SQLite database on a persistent, service-private volume.
- Existing `NIC_CHAT_ACCESS_TOKEN` remains separate.

If the owner store is not configured, the chat model is not offered tools. If a chat request has no grant ID and task ID, tools are not offered. A grant ID is only a selector; it is not a credential.

## Owner API authentication

Trusted CLI/service callers may continue to use `Authorization: Bearer <NIC_OWNER_CONTROL_TOKEN>`. The browser cockpit must use the session exchange instead:

- `POST /control/session/login` accepts the owner token over HTTPS from an exact origin in `NIC_CHAT_ALLOWED_ORIGINS`, then sets a short-lived `NIC_OWNER_SESSION` HttpOnly, SameSite=Strict cookie and returns a CSRF token.
- `GET /control/session/status` validates the cookie and CSRF header.
- `POST /control/session/logout` revokes the server-side session and clears the cookie.
- Browser owner requests send the cookie automatically plus `X-NIC-CSRF`; mutating requests also require an allowed `Origin`.
- The owner token is not stored in localStorage/sessionStorage and is not sent with subsequent browser control requests.

Sessions are held in process memory and expire on process restart (default 30 minutes; configurable with `NIC_OWNER_SESSION_TTL_SECONDS`, bounded to 60 seconds–12 hours). Use one API instance or sticky routing until a shared session store is implemented. The cockpit must be served from the same site as the API (or a trusted same-site reverse proxy); cross-site static hosting will not work with the SameSite=Strict cookie. Configure TLS and an exact `NIC_CHAT_ALLOWED_ORIGINS` allowlist. In local development only, `NIC_OWNER_SESSION_ALLOW_INSECURE_LOCALHOST=1` permits localhost HTTP; never enable this remotely.

The owner cockpit is `dashboard/owner.html`. It provides Standard/Full Power mode selection, exact task/resource scopes, a maximum 12-hour grant, grant revocation, stop/resume confirmation, and recent grant visibility. The mode never expands the selected scopes or overrides non-delegable actions.

- `GET /control/autonomy/status`: read emergency-stop state.
- `POST /control/autonomy/resume`: owner clears the autonomy broker stop.
- `POST /control/autonomy/stop`: owner activates the autonomy broker stop.
- `POST /control/autonomy/grants`: issue a scoped grant. Body accepts `mode`, `task_ids`, `scopes`, and optional `duration_seconds`.
- `POST /control/autonomy/grants/{grant_id}/revoke`: revoke a grant.

Example grant body:

```json
{
  "task_ids": ["task-2026-11-11-research"],
  "scopes": [
    {"resource": "nic_tool:get_live_market_data", "actions": ["execute"]},
    {"resource": "nic_tool:search_public_news", "actions": ["execute"]}
  ],
  "duration_seconds": 3600
}
```

The returned grant ID and task ID must be attached to the authenticated chat request as `autonomy_grant_id` and `autonomy_task_id`. The chat API does not accept owner identity, approval status, scopes, or expiry from the chat payload.

## Enforcement

- The orchestrator and temporary specialists both use the same broker.
- The broker asks the owner store to authorize the exact `nic_tool:<tool-name>` resource, `execute` action, task ID, and grant ID immediately before each tool call.
- Emergency stop, missing/expired/revoked grant, wrong task, wrong resource, or unlisted action denies execution before the executor is called.
- Revocation is checked on the next tool call; no cached positive decision is retained.
- Owner-authenticated `/operator/execute` remains a separate manual read-only operator path, not an autonomous Full Power grant.

## Important limitations

This is backend enforcement for the existing read-only chat tool registry. It does not add arbitrary shell, filesystem-write, browser, Binance publishing, account, trading, or deployment tools. The existing non-delegable policy remains in force.

The initial browser session store is process-local, not a distributed session service. The API still accepts static bearer authentication for trusted non-browser clients; deploy only behind TLS, store the owner token in a secret manager, rotate it, and restrict access. Do not expose it to the chat client or NIC worker. The SQLite database must be on a persistent private volume and accessible only to the owner-control API. This PR does not provision infrastructure, configure secrets, or deploy the service. Production publisher/workflow emergency-stop propagation remains a separate integration and must not be assumed from this broker stop alone.
