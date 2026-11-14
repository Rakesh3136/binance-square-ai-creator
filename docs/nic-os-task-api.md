# NIC OS owner task API

**Status:** draft implementation; not deployed. The task API is available only through the authenticated owner control plane.

## Storage configuration

- Set `NIC_OWNER_IDENTITY` to the trusted owner identity supplied by server configuration.
- Set `NIC_TASK_RUNTIME_DB` to a private persistent SQLite path. If omitted and `NIC_OWNER_CONTROL_DB` is set, NIC derives `<NIC_OWNER_CONTROL_DB>.tasks.sqlite3`.
- Keep the task database on private persistent storage. Do not mount owner-control or task database files into worker containers.
- Browser calls require the existing owner session cookie, CSRF token and same-site allowed Origin for mutations. Trusted service calls may use the owner bearer token over TLS.

## Endpoints

| Method | Path | Behavior |
|---|---|---|
| GET | `/control/tasks?limit=50` | List tasks belonging to the authenticated owner |
| POST | `/control/tasks` | Create a queued task with `goal`, optional `priority` and `max_attempts` |
| GET | `/control/tasks/{task_id}` | Read one owner-scoped task |
| GET | `/control/tasks/{task_id}/events` | Read append-only task history |
| POST | `/control/tasks/{task_id}/pause` | Pause and revoke any active worker lease |
| POST | `/control/tasks/{task_id}/resume` | Requeue an owner-paused task |
| POST | `/control/tasks/{task_id}/cancel` | Cancel and revoke any active worker lease |
| POST | `/control/tasks/{task_id}/retry` | Owner retry of a failed task within its configured attempt budget |

Task action POSTs use an empty JSON object. Task creation does not grant execution permissions. A future worker must separately check the owner autonomy grant, task ID, exact tool scope and emergency-stop state immediately before every action.

## Not yet implemented

There is no task executor, scheduler, browser/terminal worker, live WebSocket/SSE event stream, or cockpit task timeline in this slice. Creating a task stores it; it does not mean NIC has started or completed the requested work. API authentication is not a substitute for task-level execution authorization.


## Trusted scheduler (opt-in, read-only first phase)

The API service can start a trusted in-process scheduler only when all of these are true:

- `NIC_TASK_WORKER_ENABLED=1`
- `OPENAI_API_KEY` is configured on the trusted service
- The owner-control store and persistent task store are configured

Optional bounds:

- `NIC_TASK_WORKER_POLL_SECONDS` (0.25–60; default 2)
- `NIC_TASK_WORKER_LEASE_SECONDS` (30–900; default 300)

The scheduler checks the owner emergency-stop state and discovers active, unexpired grants that explicitly include each task ID. It claims only those tasks. Every model-requested tool call goes through `OwnerAuthorizedToolBroker`, which rechecks the exact tool resource, `execute` action, task ID, grant ID and emergency-stop state. The grant is checked again before committing the task result. A revoked/expired grant or active stop pauses the task; execution failures are recorded without storing provider exception payloads.

This first worker runs inside the trusted API service process. It is not yet an isolated worker container or separate service. It only has the existing read-only tool catalog. There is no shell, browser/computer control, arbitrary filesystem access, publishing, trading, financial action, or production deployment capability. Keep the API service and its owner/task databases on private infrastructure.

To authorize a task, create it first, copy its task ID, then issue an owner grant whose task_ids contains that exact ID and whose scopes list only the required `nic_tool:<tool_name>` resources with the `execute` action. The scheduler ignores queued tasks without an active matching grant. Revoking the grant or activating emergency stop prevents subsequent tool calls and prevents the worker from committing its result.
