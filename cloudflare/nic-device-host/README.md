# NIC Device Host API Contract

**Status:** control-plane contract only. No device host is deployed or connected.

Cloudflare Worker calls a separately deployed NIC device-host service over HTTPS. The host is the only component allowed to call a hypervisor/container runtime. The browser never receives host credentials or direct Docker/KVM access.

## First real device: NIC Linux laptop

The first target is an isolated, persistent Linux desktop (not a Windows guest). It needs a real browser-visible display, bidirectional mouse/keyboard input, and a durable home volume. Worker owner routes:
- `GET /virtual-devices/laptop`
- `POST /virtual-devices/laptop/actions` with `{"action":"start|stop|restart"}`

The Worker maps this device to host type `linux_desktop` at:
- `GET /v1/devices/linux_desktop`
- `POST /v1/devices/linux_desktop/actions`

A start is reported as completed only when the host confirms the guest is running and both screen streaming and remote input are live. The legacy Android and Windows registry remains separate; Linux laptop is not mislabeled as Windows.

## Authentication and transport
- HTTPS is mandatory. The Worker refuses non-HTTPS host URLs.
- Every request carries `Authorization: Bearer <NIC_DEVICE_HOST_TOKEN>` from a Cloudflare Worker secret.
- Use a high-entropy, dedicated host token; do not reuse the chat or owner token.
- Host firewall must allow only the Worker egress path or a private authenticated tunnel. Do not expose Docker, libvirt, VNC, RDP, ADB, or raw host APIs publicly.
- The host must validate request IDs, enforce per-owner/device authorization, rate limits, idempotency and action timeouts.

## `GET /v1/devices`
Return one record per registered legacy device type (`android`, `windows`) in a `devices` array. Each record has `device_type`, `lifecycle_state`, `provider_state`, `provider_name`, `external_instance_id`, `screen_streaming_live`, and `remote_input_live`.

## `GET /v1/devices/linux_desktop`
Return one JSON object:
```json
{
  "device_type": "linux_desktop",
  "lifecycle_state": "stopped",
  "provider_state": "healthy",
  "provider_name": "nic-linux-host",
  "external_instance_id": "stable-provider-id",
  "screen_streaming_live": false,
  "remote_input_live": false
}
```

## Action endpoint
`POST /v1/devices/{android|windows|linux_desktop}/actions` accepts:
```json
{ "action": "start", "request_id": "uuid-from-worker" }
```
Allowed actions: `start`, `stop`, `restart`. Echo the exact request ID and device type. A completed start/restart response must include `lifecycle_state: "running"`, `performed: true`, `screen_streaming_live: true`, and `remote_input_live: true`. A completed stop must be `stopped` with remote input false. For asynchronous transitions, return the actual transitional state with `performed: false`; never claim a completed start before health checks pass.

## Device runtime requirements
- Linux desktop: isolated persistent guest/container, browser-rendered remote display, bidirectional mouse/keyboard, durable home volume.
- Android device: genuine Android Emulator on a host where KVM availability has been tested; persistent AVD/data volume; authenticated display and touch/key input.
- Windows guest: only after a compatible hypervisor and properly licensed image are approved.
- Owner screen and NIC computer-use agent must attach to the same session and share a serialized input lock. Owner takeover suspends NIC input.
- Emergency STOP must revoke NIC input even if the guest or streaming gateway is unhealthy.
- Screen sessions use short-lived, owner-scoped tickets issued by a separate session gateway; this lifecycle API does not return public stream URLs or long-lived credentials.

## Cloudflare Worker configuration
- `NIC_DEVICE_HOST_URL`: HTTPS base URL for the host API (non-secret Worker variable).
- `NIC_DEVICE_HOST_TOKEN`: dedicated secret set with Wrangler/Cloudflare dashboard.
- If either is missing, the Worker reports the host as not configured and blocks lifecycle actions.
- No host is provisioned by setting these values alone; deployment and end-to-end verification are separate steps.
