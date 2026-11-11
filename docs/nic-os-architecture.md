# NIC OS architecture

**Status:** foundation proposal, not a deployed operating system  
**Owner:** repository owner  
**Autonomy target:** high autonomy inside explicitly granted scopes  
**Production policy:** NIC may prepare and test releases independently; every production deployment requires owner approval for the exact commit.

## Product definition

NIC OS is one persistent assistant/runtime exposed through Android and desktop clients. The clients are control surfaces, not separate agents or separate sources of truth. The runtime, task queue, memory, activity ledger, permission service and development environment live in the backend.

NIC OS is an application/workspace architecture, not a replacement Android or Windows kernel. The first delivery is an installable responsive web app/PWA plus a desktop browser cockpit; a native Android shell can follow without duplicating the runtime.

## System topology

```text
 Android PWA / Android shell       Desktop browser cockpit
             |                                |
             +--------- authenticated -------+
                              |
                     NIC OS API gateway
                     - chat / voice sessions
                     - task and approval API
                     - live event stream
                              |
                     NIC persistent runtime
                     - planner / scheduler
                     - dynamic task specialists
                     - memory and task state
                     - tool and permission broker
                     - activity ledger / daily report
                              |
       +----------------------+----------------------+
       |                      |                      |
 Isolated NIC computer   Development lab        Learning services
 - browser               - Git worktrees         - research evidence
 - terminal              - tests / CI            - outcome learning
 - file workspace        - PR creation           - daily reports
 - screen stream         - release candidates    - creator workflow
       |                      |
       +---------- scoped tool broker ------------+
                              |
             External services / internet / APIs
          (only approved domains, sessions and scopes)

       Separate owner control plane (outside worker VM)
       - emergency stop
       - permission grants and revocation
       - production deployment approvals
       - audit retention
```

## Service boundaries

| Service | Responsibility | Trust boundary |
|---|---|---|
| Client apps | Chat, voice, screen view, task timeline, approvals, takeover | Untrusted client; authenticate every request |
| API gateway | Authentication, authorization, rate limits, WebSocket events | Public edge; TLS required |
| NIC runtime | Planning, scheduling, task execution coordination | No direct secrets or unrestricted host access |
| Tool broker | Validates every tool call against scopes and policy | Only route to external systems |
| NIC computer | Browser, shell and files for approved tasks | Ephemeral isolated VM/container; no host socket or control-plane credentials |
| Development lab | Branches, code changes, tests, pull requests | Isolated worktree; no production credentials |
| Owner control plane | Stop, permission grants, approvals, deployment authorization | Separate service and credentials; unavailable to agent workers |
| Activity ledger | Append-only task/action/evidence events | Runtime may append; cannot rewrite prior events |
| Report service | Daily evidence-backed summary | Reads ledger; labels unknowns and failed tasks honestly |

## High-autonomy operating contract

NIC may independently:
- plan and decompose work, create temporary specialists, and schedule scoped tasks;
- research public sources, browse approved sites and use approved APIs;
- create files and code inside its isolated workspace, run tests, build artifacts and open pull requests;
- propose changes to its own code, frontend, backend, prompts and task skills;
- monitor tasks, retry transient failures within bounded limits, and prepare daily reports.

NIC must not:
- grant itself new permissions, alter the owner policy, disable or bypass the emergency stop, or obtain owner-control-plane credentials;
- deploy to production without a fresh owner approval bound to the exact commit and successful required checks;
- access passwords, recovery codes, seed phrases, private keys or 2FA codes through chat or logs;
- make financial transfers, withdrawals, trades, purchases, or legally binding account actions unless a separate explicit user-approved product flow is designed for that action;
- bypass CAPTCHA, identity checks, phone/email verification, terms acceptance or provider access controls;
- claim a task, learning outcome, publication, deployment or reward without evidence.

## Production release lifecycle

1. NIC creates a branch and makes changes in an isolated development environment.
2. NIC runs unit, integration, security and policy tests; records exact commit SHA and test results.
3. NIC opens a pull request and prepares a release summary, risk analysis and rollback plan.
4. The owner reviews and approves the exact commit SHA in the owner control plane.
5. A deployment executor rechecks the approval, expiry, commit SHA, required checks and emergency-stop state immediately before deployment.
6. Deployment health checks run. On failure, automated rollback is allowed only under a separately approved rollback policy; otherwise stop and request owner action.
7. Record deployment, approver, commit, test evidence and health outcome in the activity ledger.

A pull-request merge is not the same as production deployment. The first implementation does not grant NIC any production deployment credentials.

## Live screen and takeover

- Browser/desktop sessions run in isolated workers.
- Stream pixels and task events to authenticated clients; use WebRTC for interactive low-latency video where infrastructure supports it.
- The owner can pause a task, take over the browser, revoke a session, or stop all NIC execution.
- Screen capture must visibly indicate when NIC is operating; do not capture unrelated personal desktop content.
- Never store raw passwords, OTPs or recovery codes in recordings or the activity ledger.

## Activity and daily report contract

Every event should contain: event ID, task ID, timestamp (UTC), actor, action, target/resource, permission scope, result, evidence references, duration, and error/block reason. Event types include task planned/started/completed/failed, page visited, artifact created, test run, PR opened, approval requested/approved/denied, deployment attempted/completed/rolled back, and learning observation recorded.

Daily reports distinguish:
- **Done:** backed by an artifact, API response, test result or other evidence.
- **Learned:** a durable finding with source/evidence and what changed as a result.
- **Attempted / blocked / failed:** explicitly not presented as completed.
- **In progress:** current state and next action.
- **Not verified:** evidence not available.

Do not expose private chain-of-thought. Report concise decisions, actions, evidence, uncertainty and next steps.

## Data model (initial)

- `users`: owner identity and authentication metadata.
- `devices`: registered Android/desktop sessions and revocation status.
- `tasks`: task goal, status, schedule, scope, parent task and runtime lease.
- `task_events`: append-only activity events with evidence pointers.
- `permission_grants`: resource/action scope, expiry, issuer and revocation state.
- `approval_requests`: exact action/commit fingerprint, approver, expiry and one-time consumption.
- `workspaces`: isolated computer and development workspace metadata.
- `artifacts`: files, test reports, screenshots and PR/release references.
- `daily_reports`: generated report plus source event range.
- `sessions`: encrypted references to provider sessions; never raw credentials.

## Initial implementation sequence

1. Architecture, permission and release contracts (this change).
2. Persistent owner-control store, owner grant/revoke API and tool-broker enforcement (implemented in PR #216; not deployed). Persistent task/event API integration remains.
3. NIC cockpit: chat, task queue, live activity, approvals, pause/stop.
4. Isolated browser/terminal worker with visible screen streaming and takeover.
5. Development lab: branch, patch, tests, PR and release-candidate workflow.
6. Android installable PWA and desktop parity; native Android wrapper if needed.
7. Daily report and evidence-backed learning integration.
8. Provider integrations (Binance, Google and others) using user-owned sessions and least privilege.

## Acceptance criteria

- Android and desktop show the same task, conversation and event timeline.
- An owner can observe a browser task, pause it and take over the session.
- A worker cannot access host/control-plane credentials or modify permission policy.
- A production deployment is denied without owner approval for the exact commit, unexpired approval and successful required checks.
- Emergency stop blocks task execution and deployment independently of the agent runtime.
- Daily reports link claims to ledger events and artifacts.
- A failed test or deployment is never reported as a success.
