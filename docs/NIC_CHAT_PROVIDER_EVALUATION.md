# NIC Chat Provider Configuration and Teacher Evaluation

## What is implemented

- Chat runtime supports Anthropic Messages API and a configurable OpenAI-compatible Chat Completions endpoint.
- Default runtime remains Anthropic. No provider is called by tests or CI.
- A five-task benchmark and an opt-in runner capture responses for a blinded human-scored comparison.
- This is provider inference and evaluation, not model-weight distillation. No teacher is considered superior until results are scored.

## Credentials

### Claude Opus 5.5
Set in the server process or deployment secret manager:
- `NIC_CHAT_PROVIDER=anthropic`
- `ANTHROPIC_API_KEY` — secret API key with billing/access enabled
- `ANTHROPIC_MODEL=claude-opus-5-5` (optional; this is the documented model ID)

Official model reference: https://platform.claude.com/docs/en/models/overview

### Muse AI
“Muse AI” can refer to different products. This implementation does **not** hard-code an unverified Muse URL or claim an integration with any particular vendor. It can connect only if the specific product/account provides an authorized OpenAI-compatible Chat Completions endpoint:
- `NIC_CHAT_PROVIDER=muse`
- `MUSE_AI_BASE_URL` — documented base URL ending at the API root (for example, a provider's `/v1`)
- `MUSE_AI_API_KEY` — provider-issued API credential
- `MUSE_AI_MODEL` — exact model identifier supported by that endpoint

Remote endpoints must use HTTPS. HTTP is permitted only for loopback/local services. Confirm the exact product, endpoint, model ID, account access, data-retention policy, and whether benchmark outputs may be used for training before using it. Do not paste keys into chat, commit them, or include them in benchmark output.

## Run locally

Python 3.12+ is sufficient; this code uses the standard library.

```bash
# Configure exactly one runtime provider in the shell/secret manager.
export NIC_CHAT_PROVIDER=anthropic
export ANTHROPIC_API_KEY='...'
export ANTHROPIC_MODEL='claude-opus-5-5'   # optional
PYTHONPATH=src python -m nic_chat_server
```

Open `http://127.0.0.1:8765`. The default host binds to loopback and is not a remote deployment.

For a local Muse-compatible endpoint, instead set `NIC_CHAT_PROVIDER=muse`, `MUSE_AI_BASE_URL`, `MUSE_AI_API_KEY`, and `MUSE_AI_MODEL`. Do not set real credentials in a shared terminal or commit them.

## Side-by-side evaluation (paid API calls)

Run this only after credentials are configured and provider terms are reviewed:

```bash
PYTHONPATH=src python scripts/evaluate_nic_teachers.py --live --providers anthropic,muse
```

Output defaults to `data/reports/nic_teacher_eval.json`. It includes model outputs and is potentially sensitive; keep it local/private and do not commit it. Score responses blind against each task's rubric, plus factual accuracy, citation fidelity when sources are supplied, originality, usefulness, latency, and cost. Preserve failed cases. Use held-out tasks before adopting any change. A successful request is not proof of model quality, profitability, or permission to distill.

## Deployment checklist

1. Merge the prerequisite agent-core and chat PRs in dependency order, then update/rebase this stacked PR.
2. Deploy on a private host or managed app platform; do not expose the current standard-library server directly to the internet.
3. Put the app behind an identity-aware access gateway or add application authentication, TLS, rate limits, origin/CSRF controls, abuse controls, and monitoring before remote access.
4. Add only the selected provider's API credential to a secret manager; set provider/model env vars.
5. Bind only to loopback behind a reverse proxy, or to the platform's required interface only after access controls are verified.
6. Test `/health`, sign-in/access restriction, a real provider reply, provider error handling, logs/secret redaction, and restart behavior with a non-sensitive prompt.
7. Keep Binance Square publishing disabled. This chat server has no publishing/trading tools.

## Honest status

CI tests use fake provider responses. They prove request construction and response parsing, not credential validity, vendor availability, remote deployment, or live conversation. No live provider call has been made by this PR; no Muse product has been identified conclusively; no distillation has occurred.
