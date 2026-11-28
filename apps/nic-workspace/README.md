# NIC Cloud Virtual Devices

## Product definition
NIC owns two persistent virtual machines in its cloud workspace:
- **Virtual Android:** a real Android emulator with its own OS, apps, storage, and session state.
- **Virtual Windows:** a real Windows VM with its own desktop, apps, files, and session state.

The owner signs in to NIC from the Android app or web app and views the same running device session. NIC and the owner interact through live remote display and input. These are NIC's machines, not the owner's personal phone or laptop.

## Current status
The current `index.html` is only a responsive control-console shell. It is not an emulator, Windows VM, remote desktop, or live screen stream. Screen areas and app panels are placeholders until VM hosts, session gateway, streaming, and remote input are connected. Do not label the feature live until actual VM sessions launch and end-to-end viewer/control tests pass.

## Required architecture
1. **VM hosts:** isolated Android emulator on Linux/KVM; Windows VM on a compatible hypervisor with a properly licensed Windows image; persistent per-owner disks.
2. **Session orchestrator:** provision/start/stop/restart/snapshot/health-check; stable owner-to-device mapping across logins; quotas and idle shutdown.
3. **Live display:** capture actual guest display; low-latency authenticated WebRTC stream to web and Android clients; reconnect to the same session.
4. **Remote input:** route touch, pointer, keyboard, and clipboard events to the selected VM; visible owner/NIC control indicator and serialized handoff.
5. **NIC agent channel:** NIC observes the same display and uses constrained input/action APIs; log actions; ask approval for purchases, messages, installs, deletion/overwrite, and security changes.
6. **Security:** owner authentication, short-lived signed stream/input tickets, encryption, tenant isolation, rate limits, revocation, and no hypervisor/raw-host access from browser.
7. **Cross-client continuity:** Android and web clients call the same session API; login reattaches to existing devices rather than creating duplicates.

## Cost and deployment constraint
Persistent Windows and Android VMs require compute, storage, bandwidth, and Windows licensing. Cloudflare Workers can provide identity, API routing, orchestration metadata, and signaling, but cannot themselves run full Windows or Android VMs. Do not provision paid hosts, enable billing, or incur charges without explicit owner approval. A free-only design cannot promise an always-on Windows VM.

## Delivery stages
- Stage 1: UI and session API contract, device list, connection state, and mock stream.
- Stage 2: boot one Android VM, stream its actual screen, support touch/keyboard.
- Stage 3: boot a licensed Windows VM, stream its desktop, support mouse/keyboard.
- Stage 4: persistent owner sessions and reconnect from web and Android app.
- Stage 5: NIC agent operates the same devices with approval, audit, and stop controls.

## Acceptance tests
- Same owner sees the same Android and Windows VM identities from web and Android app.
- Live video shows actual guest OS pixels, not a simulated UI.
- Touch/keyboard and mouse/keyboard change the respective VMs.
- Reconnect restores the same session and files.
- Owner/NIC handoff prevents conflicting input.
- Stop/revoke blocks further input.
- Tenant isolation prevents cross-owner access.
- No paid infrastructure is provisioned before explicit approval.
