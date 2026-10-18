# NIC Conversational Chat MVP

## What this adds

- A minimal browser chat at `http://127.0.0.1:8765`.
- A JSON endpoint at `POST /api/chat` and a health endpoint at `GET /health`.
- An optional Anthropic Messages API adapter configured with environment variables.
- Input-size and role validation, bounded conversation context, no prompt logging, and safe error messages.
- Tests using a fake provider response; tests do not call a paid API.

## Run locally

1. Use Python 3.12+.
2. Set `ANTHROPIC_API_KEY` in your shell or secret manager. Do not commit it to Git.
3. Optionally set `ANTHROPIC_MODEL` to a model ID enabled for your account.
4. Run `PYTHONPATH=src python -m nic_chat_server`.
5. Open `http://127.0.0.1:8765`.

Without a key, the page and health endpoint work, but model replies intentionally return a setup error. No credential has been configured or tested by this change.

## Current limitations

- This is a local MVP, not a deployed public service. The default bind address is loopback.
- It uses an Anthropic API adapter only. Muse AI is not connected because the exact Muse product/API and authorized endpoint/credentials must be confirmed before wiring an adapter.
- Conversation history lives only in the current page's memory; no server-side persistent memory exists yet.
- Public web search, market-data tools, repository tools, creator research, and provenance memory are not yet connected to chat.
- No publishing, trading, transfers, withdrawals, or other account-action tools are exposed.
- This is API inference integration, not model-weight distillation. Any teacher-output training/distillation requires separate terms review, a curated benchmark, held-out evaluation, and documented consent/authorization.

## Security before remote deployment

Do not expose the server to the public internet as-is. Before deployment, add authentication, TLS via a trusted reverse proxy, CSRF/origin protection as appropriate, rate limiting, abuse controls, secret-manager configuration, privacy/retention policy, and deployment health monitoring. Keep chat logs free of credentials and avoid persisting sensitive user messages by default.
