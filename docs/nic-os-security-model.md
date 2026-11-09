# NIC OS security and autonomy model

## Security objective

Give NIC broad ability to do useful work while keeping owner authority, credentials, emergency stop and production deployment outside the agent's trust boundary.

## Non-negotiable separation

1. **Agent plane:** planner, dynamic specialists, browser workers, terminal workers and development agents. Treat all agent output and retrieved web content as untrusted.
2. **Tool broker:** validates identity, task scope, resource allowlist, action type, quota and current stop state before each tool call.
3. **Owner control plane:** owns permission grants, revocation, emergency stop and production approvals. It must run under separate credentials and preferably a separate deployment/account.
4. **Production plane:** deployment identity is available only to the deployment executor after owner approval. Never mount it into the agent VM, browser, chat process or development container.

No amount of prompt text is a security boundary. Enforce permissions in the broker, operating system, cloud IAM and deployment pipeline.

## Emergency stop

- Provide a hardware-independent owner control endpoint and a separate environment/cloud-level kill switch.
- Stop new task leases, cancel queued tasks, revoke browser/terminal worker leases, and block tool calls and deployments.
- The worker cannot clear the stop. Only an authenticated owner action can clear it.
- If the control service or state store is unavailable, fail closed.
- Test stop propagation and recovery regularly.
- The stop must not rely solely on a file inside a worker container that the worker can edit.

The repository's existing `ControlGate` is a useful local policy primitive, but it is not yet a hardened, externally isolated control plane. Production deployment must not treat it as sufficient by itself.

## Permission model

Grant narrowly by principal, task, resource, action, environment and expiry. Examples:
- public web read: approved domains, GET only, bounded rate and response size;
- browser session: one isolated profile and named websites;
- workspace write: one task-specific workspace;
- GitHub: selected repository, branch-scoped writes and pull-request creation; no secrets administration;
- provider account: explicit session and allowed action list;
- deployment: separate executor, exact commit and one-time owner approval.

All grants expire and can be revoked. NIC may request more scope but cannot approve its own request.

## Self-improvement

NIC may propose changes to its own source code, tests, skills, UI and backend. It must work on a branch or isolated worktree, run required checks, produce a diff and explain risks. It cannot change the release gate, owner-control-plane implementation, permission policy, emergency-stop implementation or CI policy in a way that weakens protection without an owner-reviewed security change. Production deployment always requires owner approval for the exact commit.

## Credentials and accounts

Use a secret manager or encrypted provider-session store. Keep secrets out of Git, prompts, task context, browser screenshots, logs, reports and artifacts. Use user-mediated sign-in and provider-supported OAuth where available. User completes CAPTCHA, identity checks, OTP and terms acceptance.

## Threats to test

- Prompt injection in webpages, files, issues and repository content.
- Agent attempts to call tools outside task scope or forge approval metadata.
- Expired, replayed or commit-mismatched deployment approval.
- Emergency stop during a running browser or terminal task.
- Worker compromise attempting host escape or control-plane access.
- Leaked browser session, GitHub token or provider credentials.
- Tampered or missing activity evidence.
- Malicious dependency, test fixture or generated code.
