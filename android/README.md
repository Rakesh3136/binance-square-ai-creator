# NIC Assistant Android companion (MVP)

This is the first native Android shell for NIC. It includes:
- HTTPS server URL configuration
- NIC chat through the existing `POST /chat` API
- Owner activity timeline through the existing authenticated `GET /activity` API
- Separate chat and owner tokens
- Session-only token handling (the app does not persist either token)
- A GitHub Actions workflow that builds and uploads a debug APK artifact

## Build

Requires JDK 17 and Gradle 8.9+:

```sh
cd android
gradle assembleDebug
```

APK output: `app/build/outputs/apk/debug/app-debug.apk`.

## First launch

1. Enter the deployed NIC server's HTTPS base URL.
2. Enter the chat token configured as `NIC_CHAT_ACCESS_TOKEN`.
3. Enter the owner token configured as `NIC_OWNER_CONTROL_TOKEN` only if you want the owner activity view.
4. Check server, then send a test chat.

Tokens are held only in app memory and must be re-entered after the app process is closed. Do not use an HTTP URL or place secrets in source code.

## Current limitations

This is an MVP client, not the full computer-use companion. It requires the NIC API to be deployed and reachable. It does not yet include voice, push notifications, cloud desktop streaming, device-control permissions, or a release-signed APK. The debug APK is for owner testing only.
