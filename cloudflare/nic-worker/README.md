# NIC Cloudflare edge bootstrap

This is a deliberately limited Cloudflare Worker adapter, not a port of the full Python NIC OS.

## AI provider
NIC chat uses Cloudflare Workers AI through the Worker `AI` binding. It does not call OpenAI or an external paid inference API. Default model: `@cf/zai-org/glm-4.7-flash`, a Cloudflare-hosted open model with multilingual dialogue, reasoning, and function-calling support. Model selection is configurable with `NIC_CHAT_MODEL`.

Workers AI Free currently includes 10,000 Neurons per day. On Workers Free, requests fail after the daily free allocation is exceeded. No paid upgrade or overage is authorized; do not change billing without explicit owner approval.

## Routes
- `GET /healthz`: reports configuration booleans and model identity, never secret values.
- `POST /chat`: requires `Authorization: Bearer <NIC_CHAT_ACCESS_TOKEN>`; invokes Workers AI and stores user/assistant messages in D1. Pass returned `conversation_id` on later messages to resume; omit it to start a new conversation.
- `GET /activity`: requires separate owner token; returns last 100 append-only activity summaries.
- `POST /activity`: requires owner token; appends a bounded activity summary.

Conversation messages live in `nic_messages`; the activity journal remains separate and append-only. Only user and assistant messages are persisted, not hidden reasoning. The chat token authorizes the single-owner chat service; do not distribute it to untrusted clients.

## Required Worker secrets
Set through Wrangler or Cloudflare dashboard; never commit them:
- `NIC_CHAT_ACCESS_TOKEN`
- `NIC_OWNER_CONTROL_TOKEN` (different random token)
There is no AI-provider API key. Do not add an OpenAI key.

## Bindings
- Workers AI binding `AI`
- D1 binding `DB`, database `nic-activity-journal`

## Deploy
```sh
npx wrangler d1 migrations apply nic-activity-journal --remote
npx wrangler secret put NIC_CHAT_ACCESS_TOKEN
npx wrangler secret put NIC_OWNER_CONTROL_TOKEN
npx wrangler deploy
```
The database points to the account's APAC D1 database. No paid upgrade is configured or authorized.

## Capability boundary
This adapter does not import or execute the Python NIC orchestrator. Existing Python API uses `http.server`, local SQLite, filesystem artifacts, and packages that are not a drop-in Workers runtime. This adapter currently offers authenticated model chat, D1-backed conversation memory, and owner activity journal only. It does not yet have live research tools, dynamic specialist tool execution, Binance publishing, reward ingestion, scheduled creator loop, browser automation, or full owner autonomy controls. Do not call NIC fully live or production-complete on this basis.

Next work: port read-only research tools to Workers-compatible code, then add a bounded dynamic specialist executor with explicit permissions. Publishing remains disabled until authorization, originality, eligibility, duplicate-prevention, and publication-proof gates are connected and tested.
