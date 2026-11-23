# NIC backend deployment

This repository now includes a Docker image definition for the NIC chat/control API.
It is deployment-ready infrastructure, **not a deployed public service**. The owner
must choose a hosting provider, create secrets there, deploy the image, attach durable
storage, and configure HTTPS before the Android client can connect.

## Runtime

- Container command: `python -m src.nic_assistant_chat`
- Internal port: `8765`
- Health endpoint: `GET /healthz`
- Chat endpoint: `POST /chat` (Bearer chat token)
- Owner activity endpoint: `GET /activity` (Bearer owner token)
- Persistent journal: `/data/nic_activity_journal.sqlite3`

The service binds to `0.0.0.0` inside the container. Put it behind the hosting
provider's HTTPS ingress/reverse proxy. Do not expose the raw container port to the
public internet without TLS.

## Required secrets and environment

Configure these in the hosting provider's secret manager, never in Git:

- `OPENAI_API_KEY`: provider key used by the assistant.
- `NIC_CHAT_ACCESS_TOKEN`: long random secret for chat authentication.
- `NIC_OWNER_CONTROL_TOKEN`: a different long random secret for owner routes.
- `NIC_CHAT_HOST=0.0.0.0`
- `NIC_CHAT_PORT=8765`
- `NIC_ACTIVITY_JOURNAL_DB=/data/nic_activity_journal.sqlite3`

Keep `/data` on a persistent volume. Without it, the SQLite activity journal may be
lost when the container is replaced. Generate the two access tokens independently;
never reuse an API key as an app access token.

Optional settings include `NIC_CHAT_MODEL` and `NIC_TRANSPARENCY_JOURNAL_PATH`.
Do not configure broad CORS origins unless a browser dashboard needs them. Android
native requests do not require CORS.

## Deployment checklist

1. Build the repository's Dockerfile on a trusted container host.
2. Attach a persistent volume at `/data`.
3. Add the secrets above using the host's secret manager.
4. Configure HTTPS and route requests to container port `8765`.
5. Visit `https://YOUR-HOST/healthz`; confirm `status=ok` and all three
   configuration booleans are true (`model_configured`,
   `chat_token_configured`, `owner_control_token_configured`).
6. Keep the chat token and owner token separate. The owner token grants access to
   activity and control endpoints; do not share it.
7. Enter the HTTPS base URL and matching tokens in NIC Android, then test chat and
   owner activity.

## Current security and capability limits

- The current chat bridge exposes bounded read-only tools and temporary specialists.
- Publishing, trading, arbitrary device control, and cloud desktop execution are not
  enabled by this deployment recipe.
- The control gate is not yet wired into every NIC executor; do not treat its presence
  as a complete global safety boundary.
- The health endpoint is intentionally unauthenticated and reports configuration
  booleans only, never secret values.
- Use provider-managed TLS, secret storage, access logs with sensitive-header
  redaction, backups, and a persistent volume.
- Do not place secrets in Android screenshots, source control, build artifacts, or
  chat messages.

## Local container smoke test

With environment variables supplied through a private local environment file:

```sh
docker build -t nic-assistant:local .
docker run --rm --env-file .env -p 127.0.0.1:8765:8765 \
  -v nic-data:/data nic-assistant:local
```

Then request `http://127.0.0.1:8765/healthz` from the local machine only.
