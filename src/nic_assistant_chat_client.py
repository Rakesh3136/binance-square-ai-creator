"""Client helper for NIC components to call a separately deployed assistant."""
from __future__ import annotations
import json
import os
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

class AssistantUnavailable(RuntimeError):
    """Raised when the assistant endpoint is unconfigured or unreachable."""

def ask_assistant(message: str, history: list[dict[str, str]] | None = None, *,
                  endpoint: str | None = None, token: str | None = None,
                  timeout: float = 20.0, opener=urlopen) -> str:
    """Send a creator-workflow question to NIC's assistant service.

    Endpoint and bearer token must come from protected environment configuration;
    callers should not hard-code secrets. No request or response is logged.
    """
    if not isinstance(message, str) or not message.strip():
        raise ValueError("message must be a non-empty string")
    base = (endpoint or os.getenv("NIC_ASSISTANT_URL", "")).rstrip("/")
    access_token = token or os.getenv("NIC_CHAT_ACCESS_TOKEN", "")
    if not base or not access_token:
        raise AssistantUnavailable("NIC_ASSISTANT_URL or NIC_CHAT_ACCESS_TOKEN is not configured")
    body = json.dumps({"message": message, "history": history or []}).encode("utf-8")
    request = Request(
        base + "/chat", data=body, method="POST",
        headers={"Authorization": "Bearer " + access_token,
                 "Content-Type": "application/json; charset=utf-8",
                 "Accept": "application/json"},
    )
    try:
        with opener(request, timeout=timeout) as response:
            if response.status != 200:
                raise AssistantUnavailable("assistant endpoint returned a non-success status")
            payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        raise AssistantUnavailable(f"assistant endpoint returned HTTP {exc.code}") from None
    except (URLError, TimeoutError, OSError) as exc:
        raise AssistantUnavailable("assistant endpoint is unreachable or timed out") from None
    if not isinstance(payload, dict) or not isinstance(payload.get("reply"), str) or not payload["reply"].strip():
        raise AssistantUnavailable("assistant endpoint returned an invalid response")
    return payload["reply"].strip()
