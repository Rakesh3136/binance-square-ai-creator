# NIC owner control-plane store

This increment adds a persistent SQLite-backed owner-control store with:
- fail-closed bootstrap (emergency stop starts **ON**);
- owner-identity checks at the control-store boundary;
- temporary, task-bound, exact resource/action grants (maximum 12 hours; no wildcards);
- immediate grant revocation checked on the next authorization call;
- emergency-stop checks performed atomically with grant lookup;
- append-only owner-control audit events.

## Critical deployment boundary

This is a storage and policy-enforcement primitive, **not a complete secure control plane**. The `authenticated_owner` argument MUST be injected by a trusted owner-authenticated API middleware after a real session/identity check. Never accept it from request JSON, a browser field, a NIC prompt, or a worker. The owner-control database and its credentials must be isolated from all NIC workers; only the owner-control API may access it.

The current NIC chat orchestrator, temporary specialists and owner operator endpoint now invoke `OwnerScopedToolBroker`, which calls `authorize_action` before every tool dispatch. Missing grants, task IDs, revoked/expired grants, out-of-scope tools and active emergency stop fail closed. The model is not given tool definitions at all when no broker is available. This integration is covered by GitHub Actions tests. SQLite is suitable for a local/single-instance foundation only; production requires a hardened service/database, authenticated owner sessions, CSRF protection, audit retention, backup, and concurrency/recovery review.

Production deployment, financial operations, owner-security changes, emergency-stop changes, permission administration, secrets and provider-verification bypass remain non-delegable under the autonomy evaluator. The separate production release approval flow remains mandatory.
