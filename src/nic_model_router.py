"""NIC (Neural Intelligence Core) model router.

The Creator's intelligence is not owned by any one external model.
Providers are interchangeable specialists. Deterministic/local fallbacks remain
available when all hosted providers are unavailable.

Supported optional providers:
- claude: Anthropic Messages API
- openai: OpenAI Responses API
- nemotron: NVIDIA Nemotron 3 Ultra via OpenAI-compatible endpoint

No provider is allowed to override frozen market facts or publication gates.
"""
from __future__ import annotations

import json
import os
import urllib.request
from typing import Callable

DEFAULT_ORDER = ()


def provider_order() -> list[str]:
    raw = os.getenv("NIC_PROVIDER_ORDER", ",".join(DEFAULT_ORDER))
    return [x.strip().lower() for x in raw.split(",") if x.strip()]


def _post_json(url: str, payload: dict, headers: dict, timeout: int = 45) -> dict:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", **headers},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def _claude(prompt: str, system: str) -> str:
    key = os.getenv("ANTHROPIC_API_KEY", "").strip()
    if not key:
        raise RuntimeError("ANTHROPIC_API_KEY unavailable")
    model = os.getenv("CLAUDE_MODEL", "claude-sonnet-5")
    data = _post_json(
        "https://api.anthropic.com/v1/messages",
        {"model": model, "max_tokens": int(os.getenv("CLAUDE_MAX_OUTPUT_TOKENS", "1800")), "system": system, "messages": [{"role": "user", "content": prompt}]},
        {"x-api-key": key, "anthropic-version": "2023-06-01"},
    )
    text = "".join(str(b.get("text", "")) for b in data.get("content") or [] if isinstance(b, dict)).strip()
    if not text:
        raise RuntimeError("Claude returned empty output")
    return text


def _openai(prompt: str, system: str) -> str:
    key = os.getenv("OPENAI_API_KEY", "").strip()
    if not key:
        raise RuntimeError("OPENAI_API_KEY unavailable")
    model = os.getenv("OPENAI_MODEL", "gpt-6-astra")
    data = _post_json(
        "https://api.openai.com/v1/responses",
        {"model": model, "reasoning": {"effort": os.getenv("OPENAI_REASONING_EFFORT", "medium")}, "input": [{"role": "system", "content": system}, {"role": "user", "content": prompt}]},
        {"Authorization": f"Bearer {key}"},
    )
    output_text = data.get("output_text")
    if isinstance(output_text, str) and output_text.strip():
        return output_text.strip()
    chunks = []
    for item in data.get("output") or []:
        for content in item.get("content") or []:
            if isinstance(content, dict) and isinstance(content.get("text"), str):
                chunks.append(content["text"])
    text = "".join(chunks).strip()
    if not text:
        raise RuntimeError("OpenAI returned empty output")
    return text


def _nemotron(prompt: str, system: str) -> str:
    """Nemotron 3 Ultra deep-research specialist over an OpenAI-compatible API."""
    key = os.getenv("NEMOTRON_API_KEY", "").strip()
    url = os.getenv("NEMOTRON_API_URL", "https://integrate.api.nvidia.com/v1").strip()
    model = os.getenv("NEMOTRON_MODEL", "nvidia/nemotron-3-ultra-550b-a55b")
    if not key:
        raise RuntimeError("NEMOTRON_API_KEY unavailable")
    data = _post_json(
        url.rstrip("/") + "/chat/completions",
        {
            "model": model,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}],
            "chat_template_kwargs": {
                "enable_thinking": os.getenv("NEMOTRON_ENABLE_THINKING", "true").strip().lower() in {"1", "true", "yes", "on"},
                "force_nonempty_content": True,
            },
            "temperature": float(os.getenv("NEMOTRON_TEMPERATURE", "0.2")),
            "max_tokens": int(os.getenv("NEMOTRON_MAX_TOKENS", "12000")),
        },
        {"Authorization": f"Bearer {key}"},
        timeout=int(os.getenv("NEMOTRON_TIMEOUT", "180")),
    )
    choices = data.get("choices") or []
    message = choices[0].get("message") if choices and isinstance(choices[0], dict) else {}
    text = str((message or {}).get("content") or "").strip()
    if not text:
        raise RuntimeError("Nemotron returned empty output")
    return text


CALLERS: dict[str, Callable[[str, str], str]] = {
    "claude": _claude,
    "openai": _openai,
    "nemotron": _nemotron,
}


def external_models_enabled() -> bool:
    return os.getenv("NIC_EXTERNAL_MODELS", "false").strip().lower() in {"1", "true", "yes", "on"}


def generate(prompt: str, system: str) -> tuple[str, dict]:
    if not external_models_enabled():
        raise RuntimeError(json.dumps({"nic": "external_models_disabled", "attempts": []}))
    return _generate_from_order(prompt, system, provider_order())


def generate_specialist(prompt: str, system: str, provider: str) -> tuple[str, dict]:
    """Run one named specialist without changing the global provider order."""
    if not external_models_enabled():
        raise RuntimeError(json.dumps({"nic": "external_models_disabled", "attempts": []}))
    provider = provider.strip().lower()
    if provider not in CALLERS:
        raise RuntimeError(json.dumps({"nic": "unsupported_specialist", "provider": provider}))
    return _generate_from_order(prompt, system, [provider])


def _generate_from_order(prompt: str, system: str, order: list[str]) -> tuple[str, dict]:
    attempts = []
    for provider in order:
        fn = CALLERS.get(provider)
        if fn is None:
            attempts.append({"provider": provider, "status": "unsupported"})
            continue
        try:
            text = fn(prompt, system)
            return text, {
                "provider": provider,
                "status": "success",
                "attempts": attempts,
                "model": {
                    "claude": os.getenv("CLAUDE_MODEL", "claude-sonnet-5"),
                    "openai": os.getenv("OPENAI_MODEL", "gpt-6-astra"),
                    "nemotron": os.getenv("NEMOTRON_MODEL", "nvidia/nemotron-3-ultra-550b-a55b"),
                }.get(provider),
            }
        except Exception as exc:
            attempts.append({"provider": provider, "status": "unavailable", "error": type(exc).__name__})
    raise RuntimeError(json.dumps({"nic": "all_hosted_providers_unavailable", "attempts": attempts}))


def status() -> dict:
    return {
        "nic_version": "1.2-gemini-free-provider-independent",
        "external_models_enabled": external_models_enabled(),
        "provider_order": provider_order(),
        "configured": {
            "claude": bool(os.getenv("ANTHROPIC_API_KEY")),
            "openai": bool(os.getenv("OPENAI_API_KEY")),
            "nemotron": bool(os.getenv("NEMOTRON_API_KEY")),
        },
        "models": {
            "claude": os.getenv("CLAUDE_MODEL", "claude-sonnet-5"),
            "openai": os.getenv("OPENAI_MODEL", "gpt-6-astra"),
            "nemotron": os.getenv("NEMOTRON_MODEL", "nvidia/nemotron-3-ultra-550b-a55b"),
        },
        "authority": "deterministic_market_contract_and_quality_gates",
    }


if __name__ == "__main__":
    print(json.dumps(status(), indent=2))
