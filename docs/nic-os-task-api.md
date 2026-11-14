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
