"""Extract a validated Binance Square publication payload from the selected draft.

The workflow pins DRAFT_PATH before this step.  This adapter intentionally accepts
several draft shapes so editorial modules can evolve without breaking publication.
It does not publish anything; it only extracts and validates the final text.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data/live/publication_payload.json"


def load_json(path: Path) -> dict:
    if not path.exists():
        raise SystemExit(f"Publication extraction: draft not found: {path}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise SystemExit(f"Publication extraction: invalid JSON in {path}: {exc}")
    if not isinstance(value, dict):
        raise SystemExit("Publication extraction: draft root must be a JSON object")
    return value


def first_text(obj: dict, keys: tuple[str, ...]) -> str:
    for key in keys:
        value = obj.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def extract(draft: dict) -> tuple[str, str, str]:
    # Prefer explicit final/publication fields, then common editorial fields.
    title = first_text(draft, ("publication_title", "final_title", "title", "headline"))
    body = first_text(
        draft,
        ("publication_text", "final_text", "body", "content", "post", "text", "article"),
    )

    # Some stages nest the final copy under publication/final/draft.
    for container_key in ("publication", "final", "selected_candidate", "draft"):
        nested = draft.get(container_key)
        if isinstance(nested, dict):
            if not title:
                title = first_text(nested, ("publication_title", "final_title", "title", "headline"))
            if not body:
                body = first_text(
                    nested,
                    ("publication_text", "final_text", "body", "content", "post", "text", "article"),
                )

    # If the model stores title and body together, preserve it rather than
    # silently publishing an empty payload.
    if not body and title and "\n" in title:
        lines = title.splitlines()
        title, body = lines[0].strip(), "\n".join(lines[1:]).strip()

    return title, body, first_text(draft, ("symbol", "ticker", "primary_symbol"))


def main() -> None:
    raw_path = os.environ.get("DRAFT_PATH", "").strip()
    if not raw_path:
        raise SystemExit("Publication extraction: DRAFT_PATH is required")

    draft_path = Path(raw_path)
    if not draft_path.is_absolute():
        draft_path = ROOT / draft_path

    draft = load_json(draft_path)
    title, body, symbol = extract(draft)

    # Binance Square needs actual publication text. Refuse an empty/placeholder
    # payload instead of allowing the publisher to make an unsafe guess.
    if not body:
        raise SystemExit("Publication extraction: final publication text is missing")
    if len(body.strip()) < 20:
        raise SystemExit("Publication extraction: final publication text is too short")

    payload = {
        "status": "READY_FOR_PUBLISH",
        "source_draft": str(draft_path.relative_to(ROOT)) if draft_path.is_relative_to(ROOT) else str(draft_path),
        "title": title,
        "text": body,
        "symbol": symbol.upper().replace("USDT", "").replace("$", "").strip(),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    github_output = os.environ.get("GITHUB_OUTPUT")
    if github_output:
        with open(github_output, "a", encoding="utf-8") as fh:
            fh.write(f"title={title.replace(chr(10), ' ').strip()}\n")
            fh.write(f"text_path={OUT.as_posix()}\n")
            fh.write("ready=true\n")

    print(json.dumps({
        "status": payload["status"],
        "source_draft": payload["source_draft"],
        "title_present": bool(title),
        "text_length": len(body),
        "symbol": payload["symbol"],
        "output": str(OUT),
    }, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
