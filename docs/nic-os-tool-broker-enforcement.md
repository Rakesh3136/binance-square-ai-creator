# NIC OS owner-scoped tool execution

## What is now connected

The chat orchestrator and owner operator endpoint use `OwnerScopedToolBroker` for every tool invocation. The broker checks the persistent owner-control store immediately before dispatch and rejects calls when:
- no grant or task ID is supplied;
- the grant is missing, revoked, expired, or outside its task binding;
- the requested exact tool resource/action is outside the grant;
- the owner emergency stop is active;
- the control store cannot return an affirmative authorization decision.

The resource naming convention for the current read-only catalog is `nic_tool:<tool_name>`, with action `execute`. Example scope: `{"resource":"nic_tool:get_agent_registry","actions":["execute"]}`. A specialist receives the same broker callback as the orchestrator; it cannot bypass the check by calling the raw registry executor.

## Owner API

All control routes require the separate `NIC_OWNER_CONTROL_TOKEN` bearer token. The persistent store must be configured using `NIC_OS_OWNER_IDENTITY` and `NIC_OS_OWNER_DB_PATH`.

- `POST /control/autonomy/grants`: owner issues a grant with explicit `task_ids`, `scopes`, `mode` and `duration_seconds`.
- `POST /control/autonomy/grants/{grant_id}/revoke`: owner revokes a grant.
- `GET /control/status`: reports the authoritative owner-store stop plus local control status.
- `GET /control/autonomy/grants`: lists bounded grant metadata for the authenticated owner cockpit.
- `POST /control/stop` and `POST /control/resume`: update both local and owner-store stop state, and attempt the configured shared GitHub Actions stop update.

The chat request may include `autonomy_grant_id` and `task_id`. Without a valid configured store and both values, the chat model receives no tool definitions and cannot invoke tools. The owner operator endpoint likewise requires a valid grant and task ID.

## Boundaries and limitations

This is an integration step, not a production-ready owner identity platform. The owner bearer token is a static shared secret; deploy only over TLS, store it in a secret manager, rotate it, and do not expose it to workers or browser JavaScript. The configured owner identity is server-side configuration, never request data. The owner-control database credentials must remain in the API process and outside worker environments.

The existing static NIC dashboard now includes a temporary Full Power grant form, active-grant selection for chat, grant listing and immediate revoke controls. It keeps API tokens in page memory only, not localStorage. The dashboard is not deployed with this backend branch; connect it only after deploying the API behind HTTPS and configuring its server-side secrets.

The current tool catalog remains read-only. This change does not add shell, filesystem write, browser interaction, publishing, financial operations, or deployment tools. Full Power is therefore limited to explicitly scoped tools that exist today; it does not conjure new capabilities. Production release, financial and owner-security actions remain non-delegable.

The persistent store starts with emergency stop ON. An owner must intentionally clear it through the protected control flow before issuing grants. If store configuration is absent, chat remains conversational but tool execution is disabled. A separate hard-stop service outside the chat process and full production identity/session hardening remain future work.
