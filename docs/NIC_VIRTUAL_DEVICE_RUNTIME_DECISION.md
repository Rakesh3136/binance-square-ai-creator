# NIC virtual-device runtime: implementation decision

**Status:** architecture decision; no host provisioned and no device is claimed to be running.

## Product requirement

NIC owns two persistent virtual devices, independent of the owner's personal phone and laptop:
1. **NIC Laptop:** a real, persistent desktop OS with a browser-accessible live screen and bidirectional keyboard/mouse control.
2. **NIC Phone:** a real Android emulator with persistent app/data storage, live screen and bidirectional touch/key input.

The owner web cockpit must attach to the same device session NIC operates. The owner can watch, take control, return control to NIC, and stop automation. A static mock desktop or locally rendered app grid does not satisfy this requirement.

## Decision: separate control plane from device runtime

Cloudflare Worker remains the authenticated control plane (identity, chat, task APIs, permissions, device registry and activity journal). It must not pretend to be the VM host or run a long-lived emulator inside a request handler.

A separate Linux device host runs isolated per-owner device workloads. The host adapter must expose authenticated, short-lived, owner-scoped commands:
- provision / start / stop / restart / destroy;
- report actual provider state and health;
- attach / detach persistent disk;
- issue a short-lived screen-stream ticket;
- accept scoped keyboard, pointer, and touch input;
- report session disconnects and action outcomes.

Every operation is idempotent where possible, validates owner + device identity, has bounded timeouts, and emits an append-only activity event. A requested start is never reported as running until the host confirms the guest booted and its screen/input channels are healthy.

## First runtime target: Linux desktop

Implement the first end-to-end computer environment as a real Linux desktop guest/container on a Linux host, with persistent home storage and a browser-compatible remote desktop gateway (for example, Apache Guacamole/noVNC with secured transport). NIC must use the same screen and input bridge as the owner. Keep the provider adapter replaceable so the host can move without changing the cockpit API.

Acceptance is not a screenshot of a mock desktop. It is:
1. NIC requests start for its registered laptop device.
2. Host starts a real desktop and attaches its persistent disk.
3. Owner opens a short-lived authenticated screen session in the cockpit.
4. NIC reads a real screen frame and performs a harmless test action through the input bridge.
5. Owner sees that same action on the same live stream and can take over.
6. Stop/restart preserves a test file and desktop state.
7. Emergency STOP blocks subsequent NIC input while owner viewing remains available.

## Android phone runtime

Use the Android Emulator on a Linux host only after the host proves KVM is available to the emulator. Google documents that accelerated Android emulators need KVM on bare metal or a VM with supported nested virtualization; a generic container/serverless host is not sufficient. Android emulator images must be genuine system images, with ADB/input and display streaming secured behind the same owner/device session model.

Do not mark Android provisioned merely because an Android-shaped frontend exists. Acceptance requires a booted emulator, persistent AVD/data disk, a live owner-visible stream, a harmless NIC touch action, and persistence across restart.

## Hosting and cost gate

No provider is selected or provisioned by this decision. No paid resources, card verification, billing changes, trial conversion, or license purchases are authorized.

- Cloudflare Workers are the control plane, not the VM host.
- Oracle Always Free advertises small AMD/Arm VM allocations and block storage, but those published limits do not establish that a chosen instance exposes nested KVM or has enough resources for a desktop plus Android emulator. Do not promise this path without a real capability test. The owner has previously rejected a card-verification-dependent path; do not retry it as a workaround.
- Commercial browser desktops can provide persistent streamed desktops, but require an explicit cost decision before use.
- Windows guest support is a later option only after an appropriate Windows license and host cost are explicitly approved. The first laptop environment may be Linux, but the product must continue to call it NIC Laptop and preserve the eventual Windows option.

Before provisioning, present the exact provider, region, CPU/RAM/disk, bandwidth limits, monthly and overage cost, billing requirements, KVM/nested-virtualization evidence, persistence/backup behavior, and teardown plan. If any are unknown, do not provision.

## Security boundary

- Device credentials are unique, revocable and never shipped to the browser.
- Screen-stream tickets are short-lived and device/owner scoped; no public VNC/RDP/ADB ports.
- Input is accepted only for an active owner-authorized task and active permission grant.
- Owner takeover suspends NIC input. Emergency STOP revokes active NIC input immediately and remains available independently of the device host.
- Destructive actions, installs, external account actions and security changes require owner approval.
- No bypass of OS login, CAPTCHA, platform security, or permission prompts.

## Required implementation sequence

1. Define typed provider contract, device lifecycle states and error taxonomy: not_provisioned, provisioning, running, stopping, stopped, failed, blocked_no_provider.
2. Add a fake provider for deterministic tests only; label it test-only and never expose fake state as a live device.
3. Implement the real Linux host adapter and screen/input gateway behind a deployment-time feature flag.
4. Add owner cockpit session attach/takeover/stop controls using short-lived stream tickets.
5. Prove Linux desktop end-to-end with persistent disk and audit receipts.
6. Prove Android KVM capability on the same approved host class, then implement the emulator adapter.
7. Add voice only after real microphone permission, speech input/output, and session interruption behavior are tested.

## Definition of live

NIC is not live until the owner can sign in to the deployed cockpit, exchange real messages with the persistent NIC runtime, see a real NIC-owned desktop stream, watch NIC perform a harmless input action, take over and return control, stop NIC, and verify that the device's files survive restart. Android is a separate required acceptance milestone. CI passing or a UI preview does not meet this definition.