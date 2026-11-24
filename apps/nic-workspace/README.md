# NIC Phone + Desktop Workspace

This folder contains the first interactive UI shell for NIC's device workspace.

## Included now
- Responsive Android-style home screen and app launcher.
- Windows-style desktop shell with navigation and window area.
- Local notes that persist in the current browser profile.
- Visible device-bridge connection status and permission boundary.
- No external app, operating-system, or device-control claims.

## Important capability boundary
This is a browser-based workspace prototype, **not** an Android emulator, Windows virtual machine, remote desktop, or device-control agent. The app tiles and desktop panels are local UI placeholders except for notes. It cannot tap the real phone, control Windows, launch installed apps, read arbitrary files, or execute shell commands.

## Device-control architecture to implement next
1. Android companion: user-installed Android app with an explicit foreground session, visible notification, narrowly scoped Accessibility Service only after the user enables it in Android Settings, and optional ADB pairing for development. No hidden capture or bypass of Android permission prompts.
2. Windows companion: signed, user-installed desktop agent running in the logged-in user's session. It exposes an authenticated local WebSocket/HTTPS bridge, enumerates only user-approved capabilities, and supports screenshot, pointer, keyboard, app launch, and file operations with per-action permission checks.
3. NIC device gateway: authenticated device registration, short-lived pairing codes, device heartbeat, capability negotiation, task queue, cancellation, approval requests, and append-only audit events. Never expose a raw shell or unrestricted filesystem endpoint.
4. Owner approval: ask before messages, purchases, installs, deletion/overwrite, security changes, or external submissions. Provide a persistent stop control and revoke-device control.
5. Remote execution: add an explicitly selected, isolated Android emulator and Windows VM only if the owner chooses hosted virtual devices. Cloudflare Workers cannot themselves host a full Windows VM or Android emulator; the Worker remains the control/API layer.

## Acceptance tests for real device control
- Pairing requires a one-time code and owner confirmation.
- No device action runs before pairing and capability approval.
- Screenshot, click, type, open app, and safe file listing work on each supported device.
- Destructive/high-impact actions pause for owner approval.
- Stop cancels queued work and revokes the active session.
- Every action records actor, device, capability, result, and timestamp without recording passwords or hidden reasoning.
- Offline devices fail clearly; NIC never claims success without device acknowledgement.

## Run locally
Open `index.html` in a modern browser. No build tool or third-party service is required.
