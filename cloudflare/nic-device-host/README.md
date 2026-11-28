# NIC Device Host API Contract

**Status:** control-plane contract only. No device host is deployed or connected.

Cloudflare Worker calls a separately deployed NIC device-host service over HTTPS. The host is the only component allowed to call a hypervisor/container runtime. The browser never receives host credentials or direct Docker/KVM access.

## Authentication and transport
- HTTPS is mandatory. The Worker refuses non-HTTPS host URLs.
- Every request carries `Authorization: Bearer <NIC_DEVICE_HOST_TOKEN>` from a Cloudflare Worker secret.
- Use a high-entropy, dedicated host token; do not reuse the chat or owner token.
- Host firewall must allow only the Worker egress path or a private authenticated tunnel. Do not expose Docker, libvirt, VNC, RDP, ADB, or raw host APIs publicly.
- The host must validate request IDs, enforce per-owner/device authorization, rate limits, idempotency and action timeouts.

## `GET /v1/devices`
Return JSON:
```json
{
  "devices": [
    {
      "device_type": "android",
      "lifecycle_state": "stopped",
      "provider_state": "healthy",
      "provider_name": "nic-linux-host",
      "external_instance_id": "stable-provider-id",
      "screen_streaming_live": false,
      "remote_input_live": false
    }
  ]
}
```
Return one record per registered device type (`android`, `windows`). Lifecycle state must be one of `not_provisioned`, `provisioning`, `running`, `stopping`, `stopped`, `failed`, or `blocked_no_provider`. A device is `running` only after guest boot and required health checks pass. Screen/input booleans must describe real, currently working channels, never intended or mocked capabilities.

## `POST /v1/devices/{android|windows}/actions`
Request:
```json
{ "action": "start", "request_id": "uuid-from-worker" }
```
Allowed actions: `start`, `stop`, `restart`.

Successful, verified response:
```json
{
  "request_id": "same-request-id",
  "device_type": "android",
  "lifecycle_state": "running",
  "provider_state": "healthy",
  "provider_name": "nic-linux-host",
  "external_instance_id": "stable-provider-id",
  "performed": true,
  "screen_streaming_live": true,
  "remote_input_live": true,
  "message": "Guest boot and screen/input health checks passed."
}
```
Echo the exact request ID and device type. `performed: true` means the requested state transition actually completed and was verified. For asynchronous transitions, return the actual transitional state (`provisioning` or `stopping`) with `performed: false`; never claim a completed start before health checks pass. Reject mismatched IDs, unsupported actions, stale requests and cross-owner IDs.

## Device runtime requirements
- First device: isolated persistent Linux desktop environment, browser-rendered remote display, bidirectional mouse/keyboard, durable home volume.
- Android device: genuine Android Emulator on a host where KVM availability has been tested; persistent AVD/data volume; authenticated display and touch/key input.
- Windows guest: only after a compatible hypervisor and properly licensed image are approved.
- Owner screen and NIC computer-use agent must attach to the same session and share a serialized input lock. Owner takeover suspends NIC input.
- Emergency STOP must revoke NIC input even if the guest or streaming gateway is unhealthy.
- Screen sessions use short-lived, owner-scoped tickets issued by a separate session gateway; this lifecycle API does not return public stream URLs or long-lived credentials.

## Cloudflare Worker configuration
- `NIC_DEVICE_HOST_URL`: HTTPS base URL for the host API (non-secret Worker variable).
- `NIC_DEVICE_HOST_TOKEN`: dedicated secret set with Wrangler/Cloudflare dashboard.
- If either is missing, the Worker must continue to report `not_configured` and block lifecycle actions.
- No host is provisioned by setting these values alone; deployment and end-to-end verification are separate steps.