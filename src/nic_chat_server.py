"""Minimal NIC chat web server with an optional Anthropic Messages API adapter.

Run with: PYTHONPATH=src python -m nic_chat_server
Requires ANTHROPIC_API_KEY for model-backed replies. No publishing tools exist here.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
HTML_PATH = ROOT / "dashboard" / "nic_chat.html"
MAX_BODY_BYTES = 64 * 1024
MAX_MESSAGES = 20
MAX_MESSAGE_CHARS = 8000
DEFAULT_MODEL = "claude-opus-5-5"

SYSTEM_PROMPT = """You are NIC, the user's crypto research and creator-assistant partner.
Be conversational, useful, and direct. Separate sourced facts from interpretation,
state uncertainty, and never promise profitable trades. For market claims, ask for
or use timestamped evidence and explain invalidation/risk. Analyze public creators
for transferable craft, never copy their posts. Do not claim to have searched,
remembered, learned, or executed actions unless the available tools actually did so.
You have no publishing, trading, transfer, withdrawal, or account-control tools in this chat.
When research tools are not connected, say so and offer a clear next step."""


class ChatError(RuntimeError):
    pass


def _validate_messages(messages: Any) -> list[dict[str, str]]:
    if not isinstance(messages, list) or not messages:
        raise ValueError("messages must be a non-empty list")
    cleaned: list[dict[str, str]] = []
    for item in messages[-MAX_MESSAGES:]:
        if not isinstance(item, dict) or item.get("role") not in {"user", "assistant"}:
            raise ValueError("Each message must have role user or assistant")
        content = item.get("content")
        if not isinstance(content, str) or not content.strip() or len(content) > MAX_MESSAGE_CHARS:
            raise ValueError("Message content must be non-empty and within the size limit")
        cleaned.append({"role": item["role"], "content": content.strip()})
    if cleaned[-1]["role"] != "user":
        raise ValueError("The last message must be from the user")
    return cleaned


def generate_reply(
    messages: Any,
    environ: dict[str, str] | None = None,
    opener: Callable[..., Any] = urlopen,
) -> dict[str, Any]:
    """Call the configured Anthropic model. Inject opener for deterministic tests."""
    env = os.environ if environ is None else environ
    clean = _validate_messages(messages)
    api_key = env.get("ANTHROPIC_API_KEY", "").strip()
    if not api_key:
        raise ChatError("NIC chat is installed, but no model API key is configured yet.")
    model = env.get("ANTHROPIC_MODEL", DEFAULT_MODEL).strip() or DEFAULT_MODEL
    payload = {
        "model": model,
        "max_tokens": 1200,
        "system": SYSTEM_PROMPT,
        "messages": clean,
    }
    request = Request(
        "https://api.anthropic.com/v1/messages",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "content-type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
        },
        method="POST",
    )
    try:
        with opener(request, timeout=45) as response:
            body = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        # Never include request headers or credential values in errors.
        if exc.code in {401, 403}:
            raise ChatError("The model provider rejected the API credential or access.") from None
        if exc.code == 429:
            raise ChatError("The model provider rate limit was reached. Try again shortly.") from None
        raise ChatError(f"The model provider returned HTTP {exc.code}.") from None
    except (URLError, TimeoutError, OSError, json.JSONDecodeError):
        raise ChatError("NIC could not reach the model provider. Check connectivity and try again.") from None
    blocks = body.get("content", [])
    reply = "\n".join(
        block.get("text", "") for block in blocks
        if isinstance(block, dict) and block.get("type") == "text"
    ).strip()
    if not reply:
        raise ChatError("The model returned no text response.")
    return {"reply": reply, "model": model, "provider": "anthropic"}


def make_handler(environ: dict[str, str] | None = None, reply_fn: Callable[..., dict[str, Any]] = generate_reply):
    """Factory keeps HTTP handlers testable without external network calls."""
    class Handler(BaseHTTPRequestHandler):
        def _send(self, status: int, payload: bytes, content_type: str) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(payload)))
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(payload)

        def do_GET(self) -> None:
            if self.path == "/health":
                self._send(200, b'{"status":"ok","model_configured":' +
                           (b"true" if (environ or os.environ).get("ANTHROPIC_API_KEY") else b"false") +
                           b"}", "application/json; charset=utf-8")
                return
            if self.path != "/":
                self._send(404, b'{"error":"not found"}', "application/json; charset=utf-8")
                return
            try:
                content = HTML_PATH.read_bytes()
            except OSError:
                self._send(500, b"NIC chat UI file is missing.", "text/plain; charset=utf-8")
                return
            self._send(200, content, "text/html; charset=utf-8")

        def do_POST(self) -> None:
            if self.path != "/api/chat":
                self._send(404, b'{"error":"not found"}', "application/json; charset=utf-8")
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if length <= 0 or length > MAX_BODY_BYTES:
                    raise ValueError("Request body is empty or too large")
                data = json.loads(self.rfile.read(length).decode("utf-8"))
                messages = _validate_messages(data.get("messages") if isinstance(data, dict) else None)
                result = reply_fn(messages, environ=environ)
                payload = json.dumps(result).encode("utf-8")
                self._send(200, payload, "application/json; charset=utf-8")
            except (ValueError, UnicodeDecodeError, json.JSONDecodeError) as exc:
                payload = json.dumps({"error": str(exc)}).encode("utf-8")
                self._send(400, payload, "application/json; charset=utf-8")
            except ChatError as exc:
                payload = json.dumps({"error": str(exc)}).encode("utf-8")
                self._send(503, payload, "application/json; charset=utf-8")
            except Exception:
                self._send(500, b'{"error":"Unexpected server error"}', "application/json; charset=utf-8")

        def log_message(self, fmt: str, *args: Any) -> None:
            # Do not log prompts or chat contents.
            super().log_message(fmt, *args)

    return Handler


def main() -> None:
    host = os.environ.get("NIC_CHAT_HOST", "127.0.0.1")
    port = int(os.environ.get("NIC_CHAT_PORT", "8765"))
    server = ThreadingHTTPServer((host, port), make_handler())
    print(f"NIC chat listening on http://{host}:{port} (Ctrl+C to stop)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
