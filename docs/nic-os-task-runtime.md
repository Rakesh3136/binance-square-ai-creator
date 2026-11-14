# NIC OS persistent task runtime

**Status:** implementation proposal in a draft pull request; not deployed or connected to a worker.

The first runtime slice adds a SQLite-backed durable task queue and append-only task event history. It is deliberately a storage primitive, not a task executor.

## Included behavior

- Owner-scoped task creation and listing.
- Durable task state across process/store restarts.
- Atomic priority-ordered worker claims with random lease IDs.
- Lease expiry and bounded retry attempts (maximum three).
- Lease fencing: only the worker holding the current unexpired lease can complete, fail or pause a running task.
- Owner-only retry of failed tasks, subject to the remaining retry budget.
- Append-only task events enforced by SQLite triggers.
- Restricted database file permissions where supported.

## Deliberate limitations

- No API routes or cockpit integration yet.
- No scheduler, background worker, WebSocket/SSE stream, browser, terminal, filesystem-write tool or external account action.
- Authentication and authorization must be enforced by the trusted API before calling this store. Worker containers must not receive owner-control database credentials.
- Task goals and results are data, not trusted instructions. A later planner must apply prompt-injection defenses and tool-broker checks before execution.
- This change does not alter emergency-stop, owner grants, publishing, deployment or financial permissions.

## Next integration slice

Wire owner-authenticated task create/list/detail/event endpoints into the API; add task event streaming; then connect a bounded worker that checks emergency stop and owner grants immediately before each tool action.
