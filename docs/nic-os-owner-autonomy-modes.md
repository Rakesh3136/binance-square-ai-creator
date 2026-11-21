# NIC owner autonomy modes

## Owner-controlled autonomy

NIC should expose an owner-controlled autonomy selector in its cockpit:

- **Standard:** execute only task/resource/action permissions already granted.
- **Full Power (temporary):** permit NIC to plan and execute all non-prohibited actions within the exact resource/action scopes selected by the owner. The owner confirms the grant, sees its expiry and can revoke it immediately.

Full Power is not root access, unrestricted access to the host, or permission to bypass platform safeguards. It is temporary delegation of broad operational autonomy.

## Non-delegable owner boundaries

Neither mode can authorize NIC to:
- deploy to production (requires separate approval for the exact commit SHA and successful checks);
- transfer or withdraw funds, trade, or make purchases;
- change owner security policy, grant/revoke owner permissions, or disable/clear emergency stop;
- access owner-control credentials, private keys or recovery phrases;
- bypass CAPTCHA, OTP, identity checks, terms acceptance or provider controls.

Sensitive actions require their own explicit owner-facing approval flow. The owner completes provider sign-in and verification.

## Grant contract

Each grant must be issued by the independent owner control plane and contain:
- unique grant ID, authenticated owner identity and approved mode;
- explicit task IDs and resource/action pairs (no implicit wildcard);
- issue and expiry timestamps (maximum 12 hours);
- revocation state and auditable grant/revoke events.

The tool broker checks the current grant and stop state on every action. Revocation must take effect before the next tool call and cancel queued tasks where possible. Missing, stale or unavailable control-plane state fails closed.

## Implementation status

Implementation now includes the policy evaluator, persistent SQLite owner-control store, owner-authenticated grant/revoke API routes, and an owner-scoped broker wired into chat, temporary specialists and the owner operator endpoint. GitHub Actions validates the integration. The owner API still uses a static bearer token and server-side owner identity; the static NIC dashboard now has a temporary grant editor, expiry setting, grant list, select-for-chat and revoke controls, but no live countdown or production identity/session hardening, external hard-stop service, or deployed runtime. Full Power is therefore implemented as a tested backend capability but is not live or available to the user until deployment and owner UI setup are completed.
