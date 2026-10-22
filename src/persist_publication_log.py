"""Persist the append-only Binance Square publication log across GitHub-hosted runners."""
from __future__ import annotations

import base64
import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path

LOG_PATH = Path("analytics/publication_log.jsonl")
API_ROOT = "https://api.github.com"


def merge_lines(remote_text: str, local_text: str) -> str:
    """Keep every existing JSONL event exactly once, preserving remote history first."""
    output = []
    seen = set()
    for source in (remote_text, local_text):
        for raw in source.splitlines():
            line = raw.strip()
            if not line or line in seen:
                continue
            # Only persist valid JSON objects; malformed rows must not poison future readers.
            try:
                value = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(value, dict):
                continue
            seen.add(line)
            output.append(line)
    return "\n".join(output) + ("\n" if output else "")


def request_json(url: str, token: str, method: str = "GET", payload: dict | None = None):
    body = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = urllib.request.Request(
        url,
        data=body,
        method=method,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "Content-Type": "application/json",
            "User-Agent": "binance-square-ai-creator-publication-history",
        },
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def persist(local_text: str, repo: str, token: str, attempts: int = 5) -> dict:
    url = f"{API_ROOT}/repos/{repo}/contents/analytics/publication_log.jsonl"
    for attempt in range(1, attempts + 1):
        remote = request_json(f"{url}?ref=main", token)
        remote_text = base64.b64decode(remote["content"]).decode("utf-8")
        merged = merge_lines(remote_text, local_text)
        if merged == remote_text:
            return {"status": "UNCHANGED", "rows": len(merged.splitlines()), "attempt": attempt}
        payload = {
            "message": "Persist Binance Square publication history for duplicate prevention",
            "content": base64.b64encode(merged.encode("utf-8")).decode("ascii"),
            "sha": remote["sha"],
            "branch": "main",
        }
        try:
            result = request_json(url, token, method="PUT", payload=payload)
            return {
                "status": "PERSISTED",
                "rows": len(merged.splitlines()),
                "commit_sha": (result.get("commit") or {}).get("sha"),
                "attempt": attempt,
            }
        except urllib.error.HTTPError as exc:
            if exc.code not in (409, 422) or attempt == attempts:
                raise
            time.sleep(attempt)
    raise RuntimeError("publication history could not be persisted after retries")


def main() -> int:
    token = (os.getenv("GH_TOKEN") or os.getenv("GITHUB_TOKEN") or "").strip()
    repo = (os.getenv("GITHUB_REPOSITORY") or "").strip()
    if not token or not repo:
        raise RuntimeError("GH_TOKEN/GITHUB_TOKEN and GITHUB_REPOSITORY are required")
    if not LOG_PATH.exists():
        print(json.dumps({"status": "NO_LOCAL_PUBLICATION_LOG", "path": str(LOG_PATH)}))
        return 0
    result = persist(LOG_PATH.read_text(encoding="utf-8"), repo, token)
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
