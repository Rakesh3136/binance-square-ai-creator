# NIC cross-device personal AI system

## Product direction

NIC is a general-purpose personal AI assistant. Binance Square, trading, and creator monetization are out of scope for this product direction.

The same NIC identity, conversation history, task records, skill registry, and permission model should be available from:
- **Android app:** primary mobile companion and remote control surface.
- **Windows desktop app:** full desktop workspace with an optional screen-aware computer-use surface.

The Android and Windows clients are interfaces to one NIC service, not separate assistants with divergent memories.

## User experience

### Android
- Chat-first interface with voice input/output, attachments, task progress, activity history, and approval prompts.
- Start, pause, resume, and cancel tasks.
- Review proposed actions before any action that changes external state.
- Pair securely with the Windows desktop client.
- Show whether a capability is available, permission-blocked, offline, or awaiting approval.

### Windows
- Chat and task workspace alongside a user-controlled desktop/screen view.
- User-invoked screen understanding and computer-use sessions.
- File and folder selection through native OS pickers; never silently scan the whole device.
- App/browser workflows through explicit, visible automation sessions.
- Task timeline showing planned steps, completed actions, failures, and approvals.
- Stop/pause control always visible during computer-use sessions.

## Shared NIC service

- One authenticated API for chat, conversations, tasks, device pairing, skill discovery, approvals, and activity events.
- D1 stores conversations, task metadata, device registrations, approval decisions, and append-only activity summaries.
- Model inference uses the configured Cloudflare Workers AI binding. Do not add OpenAI or other paid AI API dependencies.
- A dynamic task planner may create temporary specialist agents only when needed. Each specialist must invoke registered executable skills; no fake agent-count simulation.
- Skills are versioned, typed, least-privilege tools with input validation, timeouts, output limits, and audit events.
- Long-running or device-local work is executed by a paired Android/Windows agent, not inside a request-bound Worker.

## Device execution architecture

- **Windows local agent:** a signed, user-installed desktop companion that exposes a narrow local skill bridge to NIC. It can only use explicitly granted capabilities such as selected-file operations, approved app automation, and user-started screen capture.
- **Android companion:** native Android client. Use supported intents, document picker, share sheet, notifications, microphone/camera permissions, and foreground services where justified. Accessibility-based interaction, if ever added, must be separately explained and explicitly enabled by the user; never silently enable it.
- **Pairing:** short-lived pairing code, device-bound credentials, revocation, and encrypted transport. Never put long-lived owner secrets in a mobile or desktop web bundle.
- **Offline behavior:** queue user-approved local tasks safely and show their status; do not claim completion until the device reports success.

## Permission and safety model

Capabilities are denied by default. Permissions are scoped by device, skill, resource, and action. Require fresh confirmation for consequential or irreversible actions, including external sends/posts, purchases, deleting/overwriting files, installing software, and security/account changes. Offer a visible stop control for active automation. Never bypass OS security, authentication, CAPTCHAs, or app permission prompts.

'Do anything I say' means broad assistance through supported tools and explicit permissions; it does not mean invisible, unrestricted access to every app, account, or device.

## Delivery milestones

1. **Cross-device foundation:** generic NIC identity, persistent conversations, task API, activity journal, device-pairing design, and capability/permission contracts.
2. **Android client:** polished chat UI, sign-in/pairing, conversation sync, task list, approvals, voice/attachments, and activity feed.
3. **Windows client:** polished desktop shell, chat, task workspace, selected-file access, visible screen-sharing/computer-use session, and stop control.
4. **Executable skills:** add real tools incrementally (web research, document creation/editing, selected-file operations, calendar/email only when separately connected and approved).
5. **Dynamic specialist runtime:** task planner delegates to temporary agents backed by the real skill registry; bounded concurrency, budgets, retries, cancellation, and audit.
6. **End-to-end verification:** Android-to-Windows task handoff, memory continuity, permission denials, cancellation, offline/reconnect, and action receipts.

## Current verified baseline and limitations

The current Cloudflare Worker branch supplies authenticated chat, Workers AI inference, D1 conversation memory, and an append-only activity journal. It is not yet a deployed/live product and has no Android-to-Windows pairing, native clients, desktop control, local file access, voice, or executable general-purpose skills. Do not describe NIC as finished until those components are built and tested on real devices.