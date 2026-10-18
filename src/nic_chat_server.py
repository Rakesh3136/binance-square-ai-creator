"""NIC chat API with explicit Anthropic and OpenAI-compatible provider adapters.

Run: PYTHONPATH=src python -m nic_chat_server
Default provider is Anthropic. No external actions or publishing tools are exposed.
"""
from __future__ import annotations
import json
import os
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
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
remembered, learned, or executed actions unless available tools actually did so.
You have no publishing, trading, transfer, withdrawal, or account-control tools.
When research tools are not connected, say so and offer a clear next step."""

class ChatError(RuntimeError):
    pass

def _validate_messages(messages: Any) -> list[dict[str, str]]:
    if not isinstance(messages, list) or not messages:
        raise ValueError("messages must be a non-empty list")
    cleaned = []
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

def _read_provider_response(request: Request, opener: Callable[..., Any]) -> dict[str, Any]:
    try:
        with opener(request, timeout=45) as response:
            body = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        if exc.code in {401, 403}:
            raise ChatError("The model provider rejected the API credential or access.") from None
        if exc.code == 429:
            raise ChatError("The model provider rate limit was reached. Try again shortly.") from None
        raise ChatError(f"The model provider returned HTTP {exc.code}.") from None
    except (URLError, TimeoutError, OSError, json.JSONDecodeError):
        raise ChatError("NIC could not reach the model provider. Check connectivity and try again.") from None
    return body

def _anthropic_reply(messages: list[dict[str, str]], env: dict[str, str], opener: Callable[..., Any]) -> dict[str, Any]:
    api_key = env.get("ANTHROPIC_API_KEY", "").strip()
    if not api_key:
        raise ChatError("Anthropic is selected but ANTHROPIC_API_KEY is not configured.")
    model = env.get("ANTHROPIC_MODEL", DEFAULT_MODEL).strip() or DEFAULT_MODEL
    request = Request("https://api.anthropic.com/v1/messages",
        data=json.dumps({"model": model, "max_tokens": 1200, "system": SYSTEM_PROMPT, "messages": messages}).encode(),
        headers={"content-type":"application/json", "x-api-key":api_key, "anthropic-version":"2023-06-01"},
        method="POST")
    body = _read_provider_response(request, opener)
    reply = "\n".join(b.get("text", "") for b in body.get("content", [])
                       if isinstance(b, dict) and b.get("type") == "text").strip()
    if not reply:
        raise ChatError("The model returned no text response.")
    return {"reply":reply, "model":model, "provider":"anthropic"}

def _openai_compatible_reply(messages: list[dict[str, str]], env: dict[str, str], opener: Callable[..., Any]) -> dict[str, Any]:
    """OpenAI-compatible endpoint adapter; it does not assume a particular Muse product."""
    base_url = env.get("MUSE_AI_BASE_URL", "").strip().rstrip("/")
    api_key = env.get("MUSE_AI_API_KEY", "").strip()
    model = env.get("MUSE_AI_MODEL", "").strip()
    if not base_url or not api_key or not model:
        raise ChatError("OpenAI-compatible provider needs MUSE_AI_BASE_URL, MUSE_AI_API_KEY, and MUSE_AI_MODEL.")
    parsed = urlparse(base_url)
    if parsed.scheme not in {"https", "http"} or not parsed.netloc:
        raise ChatError("MUSE_AI_BASE_URL must be a valid HTTP(S) endpoint.")
    if parsed.scheme == "http" and parsed.hostname not in {"localhost", "127.0.0.1", "::1"}:
        raise ChatError("HTTP is allowed only for localhost; use HTTPS for remote model endpoints.")
    url = base_url if base_url.endswith("/chat/completions") else base_url + "/chat/completions"
    payload = {"model":model, "messages":[{"role":"system","content":SYSTEM_PROMPT}, *messages],
               "max_tokens":1200, "stream":False}
    request = Request(url, data=json.dumps(payload).encode(),
        headers={"content-type":"application/json", "authorization":"Bearer "+api_key}, method="POST")
    body = _read_provider_response(request, opener)
    choices = body.get("choices", [])
    reply = ""
    if choices and isinstance(choices[0], dict):
        message = choices[0].get("message", {})
        if isinstance(message, dict) and isinstance(message.get("content"), str):
            reply = message["content"].strip()
    if not reply:
        raise ChatError("The model returned no text response.")
    return {"reply":reply, "model":model, "provider":"openai-compatible"}

def generate_reply(messages: Any, environ: dict[str, str] | None = None,
                   opener: Callable[..., Any] = urlopen) -> dict[str, Any]:
    """Dispatch to a configured provider. The opener is injectable for offline tests."""
    env = os.environ if environ is None else environ
    clean = _validate_messages(messages)
    provider = env.get("NIC_CHAT_PROVIDER", "anthropic").strip().lower()
    if provider == "anthropic":
        return _anthropic_reply(clean, env, opener)
    if provider in {"muse", "openai-compatible", "openai_compatible"}:
        return _openai_compatible_reply(clean, env, opener)
    raise ChatError("Unknown NIC_CHAT_PROVIDER; use 'anthropic' or 'muse'.")

def make_handler(environ: dict[str, str] | None = None,
                 reply_fn: Callable[..., dict[str, Any]] = generate_reply):
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
                env = os.environ if environ is None else environ
                provider = env.get("NIC_CHAT_PROVIDER", "anthropic").strip().lower()
                configured = (bool(env.get("ANTHROPIC_API_KEY")) if provider == "anthropic" else
                    all(env.get(k) for k in ("MUSE_AI_BASE_URL","MUSE_AI_API_KEY","MUSE_AI_MODEL")))
                self._send(200, json.dumps({"status":"ok","provider":provider,"model_configured":configured}).encode(),
                           "application/json; charset=utf-8")
                return
            if self.path != "/":
                self._send(404, b'{"error":"not found"}', "application/json; charset=utf-8"); return
            try:
                content = HTML_PATH.read_bytes()
            except OSError:
                self._send(500, b"NIC chat UI file is missing.", "text/plain; charset=utf-8"); return
            self._send(200, content, "text/html; charset=utf-8")
        def do_POST(self) -> None:
            if self.path != "/api/chat":
                self._send(404, b'{"error":"not found"}', "application/json; charset=utf-8"); return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if length <= 0 or length > MAX_BODY_BYTES:
                    raise ValueError("Request body is empty or too large")
                data = json.loads(self.rfile.read(length).decode("utf-8"))
                messages = _validate_messages(data.get("messages") if isinstance(data, dict) else None)
                result = reply_fn(messages, environ=environ)
                self._send(200, json.dumps(result).encode(), "application/json; charset=utf-8")
            except (ValueError, UnicodeDecodeError, json.JSONDecodeError) as exc:
                self._send(400, json.dumps({"error":str(exc)}).encode(), "application/json; charset=utf-8")
            except ChatError as exc:
                self._send(503, json.dumps({"error":str(exc)}).encode(), "application/json; charset=utf-8")
            except Exception:
                self._send(500, b'{"error":"Unexpected server error"}', "application/json; charset=utf-8")
        def log_message(self, fmt: str, *args: Any) -> None:
            # The standard HTTP logger records paths/status, not message bodies.
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
