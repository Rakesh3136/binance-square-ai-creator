# NIC conversational assistant adapter

This adds a small HTTP bridge so NIC components or a future chat UI can exchange
natural-language messages with an OpenAI model. It does not connect to the
ChatGPT consumer app or share this ChatGPT conversation with NIC automatically.

## Required configuration

- `OPENAI_API_KEY`: OpenAI API credential supplied as a protected deployment
  secret. API billing/access is separate from a ChatGPT subscription.
- `NIC_CHAT_ACCESS_TOKEN`: long random bearer token for callers.
- `NIC_CHAT_MODEL`: optional model name; defaults to `gpt-4.1-mini`.
- `NIC_CHAT_HOST`: optional bind address; defaults to `127.0.0.1`.
- `NIC_CHAT_PORT`: optional port; defaults to `8765`.

Run with `python src/nic_assistant_chat.py`. Health check: `GET /healthz`.
Chat: `POST /chat` with `Authorization: Bearer <token>` and JSON
`{"message":"...", "history":[{"role":"user","content":"..."},{"role":"assistant","content":"..."}]}`.
History is supplied by the caller and bounded to the latest 12 valid messages;
the adapter does not persist chat transcripts. The service binds to loopback by
default. For any non-loopback bind, configure a strong access token and place the
service behind HTTPS and a managed secret store. Do not expose this basic server
directly to the public internet.

## Calling the assistant from NIC code

Import `ask_assistant` from `src.nic_assistant_chat_client` and call it with a
message plus optional recent `history`. Configure `NIC_ASSISTANT_URL` to the
base URL of the separately deployed assistant service and `NIC_CHAT_ACCESS_TOKEN`
through protected environment secrets. The helper sends a bearer-authenticated
POST to `/chat`, applies a timeout, and fails closed when unconfigured or when the
service returns an invalid response. It does not add itself to the production
publishing workflow automatically; the service URL, secrets, hosting, and an
explicitly tested caller integration must be configured before production use.

## NIC-specific behavior

The assistant is instructed to prioritize original Binance Square creator
content and verified Write-to-Earn evidence. It must not claim earnings are
guaranteed, mistake engagement for verified payout, copy creators' wording, or
perform trading/order actions.

## Verification status

Unit tests mock the model client and verify request construction, bounded history,
empty-message rejection, and empty provider responses. Passing those tests proves
the adapter's local behavior only. A deployed endpoint, configured secrets, real
provider response, and end-to-end NIC caller still need to be verified before
calling NIC-to-assistant communication production-ready.
