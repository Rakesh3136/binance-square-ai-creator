# NIC Cloudflare edge bootstrap

This is a deliberately limited Cloudflare Worker adapter. It is not a port of the full Python NIC OS.

## AI provider

NIC chat uses Cloudflare Workers AI through the Worker `AI` binding. It does not call OpenAI or any external paid inference API.

Default model: `@cf/zai-org/glm-4.7-flash` (Cloudflare-hosted open model with multilingual dialogue, reasoning, and function-calling support). The model can be changed with `NIC_CHAT_MODEL` after validating its availability and input schema.

Workers AI currently includes 10,000 Neurons per day at no charge on Workers Free. Once that daily allocation is exceeded, requests stop on Free; there is no automatic paid overage. Do not upgrade the account or enable paid billing to work around quota exhaustion without the owner's explicit approval. Monitor usage in the Cloudflare dashboard.

## Routes

- `GET /healthz`: reports configuration booleans and model identity, never secret values.
- `POST /chat`: requires `Authorization: Bearer <NIC_CHAT_ACCESS_TOKEN>`; invokes the Workers AI binding.
- `GET /activity`: requires the separate owner token and returns the last 100 append-only activity summaries.
- `POST /activity`: requires the owner token and appends a bounded activity summary.

## Required Worker secrets

Set these with Wrangler secrets or the Cloudflare dashboard; never commit them:

- `NIC_CHAT_ACCESS_TOKEN` (generate a random token)
- `NIC_OWNER_CONTROL_TOKEN` (generate a different random token)

There is no AI-provider API key. Do not add an OpenAI key or ask the owner to supply one.

## Bindings

The Worker needs:
- Workers AI binding named `AI`
- D1 binding named `DB`, pointing to `nic-activity-journal`

## Deploy

From this directory:

```sh
npx wrangler d1 migrations apply nic-activity-journal --remote
npx wrangler secret put NIC_CHAT_ACCESS_TOKEN
npx wrangler secret put NIC_OWNER_CONTROL_TOKEN
npx wrangler deploy
```

The database binding points at the account's APAC D1 database. D1 and Workers Free have quotas; inference stops when the free daily Workers AI allocation is exhausted. No paid upgrade is configured or authorized.

## Important capability boundary

This adapter does not import or execute the Python NIC orchestrator. The existing Python API uses `http.server`, a local SQLite file, filesystem-backed research artifacts, and modules with dependencies that are not a drop-in Workers runtime. This edge adapter currently offers authenticated model chat plus an owner activity journal only. It has no NIC research tools, temporary specialist tool dispatch, Binance publishing, reward ingestion, scheduled creator loop, browser automation, or owner autonomy-control integration. Do not call NIC fully live or production-complete on this basis.

Before widening capabilities, port each read-only tool to Workers-compatible code and add tests. Publishing must remain disabled until the existing authorization, originality, eligibility, duplicate-prevention, and publication-proof gates are connected and independently tested.
