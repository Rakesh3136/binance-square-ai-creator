# NIC Private Chat Without API Keys

## Recommended architecture

NIC now defaults to **local Ollama inference**. Chat prompts are sent to the Ollama service on the same machine at `http://127.0.0.1:11434/api/chat`; the adapter sends no Authorization header and refuses non-loopback URLs. No cloud API key is needed for this local mode.

Ollama's official documentation describes the local API and OpenAI-compatible interface: https://github.com/ollama/ollama/blob/main/docs/api/introduction.mdx

## Local setup

1. Install Ollama from https://ollama.com/download for your OS.
2. Start Ollama and download a model that your hardware can run. For example, choose an appropriate model from the Ollama library; do not assume every model fits every device.
3. Confirm the local model is installed with `ollama list`.
4. Configure NIC and start the chat server:

```bash
export NIC_CHAT_PROVIDER=ollama
export OLLAMA_BASE_URL=http://127.0.0.1:11434
export OLLAMA_MODEL='YOUR_INSTALLED_MODEL_TAG'
PYTHONPATH=src python -m nic_chat_server
```

Open `http://127.0.0.1:8765` on that same computer. No API key is required. The chat page currently keeps history in browser memory only; persistent conversations are not implemented.

If no `OLLAMA_MODEL` is set, NIC will fail with a clear configuration error instead of guessing a model.

## Compare local models

Run the evaluator against a local provider with explicit opt-in (requests consume your machine's compute):

```bash
PYTHONPATH=src python scripts/evaluate_nic_teachers.py --live --providers ollama
```

Set `OLLAMA_MODEL` to the local model being evaluated. For fair comparisons, keep the same five benchmark tasks, record model tag and hardware, score outputs blind against the rubrics, and include latency, memory use, factuality, evidence handling, originality, usefulness, and failure rate. The evaluator does not automatically declare a winner.

## What about Muse AI and Claude Opus 5.5?

- **Claude Opus 5.5 hosted service:** the standard hosted API requires authorized account credentials. If no API key is allowed, do not route prompts to that hosted API. A local model with a different name is not Claude Opus 5.5.
- **Muse AI:** the name is ambiguous. If you mean a specific Muse model that can legally be downloaded and run locally, we can evaluate that local model through Ollama or another compatible local runtime only after verifying its official weights, license, hardware/runtime instructions, and supported model format. A hosted Muse API generally needs its provider credentials. This PR does not pretend the local adapter is a Muse integration.
- If the goal is specifically comparing the actual hosted Claude Opus 5.5 and hosted Muse service, the no-API-key constraint means that comparison cannot be performed through those hosted APIs. We can instead benchmark available local models without keys.

## Security and deployment

- The chat server binds to `127.0.0.1` by default. It is local/private, not accessible from another device by default.
- Do not expose this standard-library server or Ollama port directly to the internet. For private remote access, deploy behind a private VPN or identity-aware gateway, TLS, authentication, rate limits, origin/CSRF controls, and monitoring. Keep the Ollama endpoint reachable only by the trusted server.
- Store any optional remote-provider credentials only in a secret manager. This no-key local path does not require them.
- The assistant has no publishing, trading, transfer, withdrawal, or account-control tools. Binance Square auto-publishing remains disabled.

## Verification status

CI tests use a fake Ollama response and verify that no Authorization header is sent and remote endpoints are rejected. This proves adapter behavior only. It does **not** prove Ollama is installed on your computer, a model is downloaded, live local inference works, the chat is deployed, or any model is best. A live local smoke test must be run on the target machine.
