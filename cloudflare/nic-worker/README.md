# NIC Cloudflare edge bootstrap

This is a deliberately limited Cloudflare Worker adapter. It is not a port of the full Python NIC OS.

## Routes

- `GET /healthz`: reports configuration booleans, never secret values.
- `POST /chat`: requires `Authorization: Bearer <NIC_CHAT_ACCESS_TOKEN>`; calls the OpenAI Responses API.
- `GET /activity`: requires the separate owner token and returns the last 100 append-only activity summaries.
- `POST /activity`: requires the owner token and appends a bounded activity summary.

## Required Worker secrets

Set these with Wrangler secrets or the Cloudflare dashboard; never commit them:

- `OPENAI_API_KEY`
- `NIC_CHAT_ACCESS_TOKEN` (generate a random token)
- `NIC_OWNER_CONTROL_TOKEN` (generate a different random token)

Do not paste secrets into GitHub, chat, source files, or screenshots.

## Deploy

From this directory:

```sh
npx wrangler d1 migrations apply nic-activity-journal --remote
npx wrangler secret put OPENAI_API_KEY
npx wrangler secret put NIC_CHAT_ACCESS_TOKEN
npx wrangler secret put NIC_OWNER_CONTROL_TOKEN
npx wrangler deploy
```

The database binding points at the account's APAC D1 database. D1 is on the free tier, subject to daily read/write and storage quotas. Workers Free has request and CPU limits; quota exhaustion can temporarily stop requests. No paid upgrade is configured.

## Important capability boundary

This adapter does not import or execute the Python NIC orchestrator. The existing Python API uses `http.server`, a local SQLite file, filesystem-backed research artifacts, and modules with dependencies that are not a drop-in Workers runtime. This edge adapter currently offers authenticated chat plus an owner activity journal only. It has no NIC research tools, temporary specialist tool dispatch, Binance publishing, reward ingestion, scheduled creator loop, browser automation, or owner autonomy-control integration. Do not call NIC fully live or production-complete on this basis.

Before widening capabilities, port each read-only tool to Workers-compatible code and add tests. Publishing must remain disabled until the existing authorization, originality, eligibility, duplicate-prevention, and publication-proof gates are connected and independently tested.
