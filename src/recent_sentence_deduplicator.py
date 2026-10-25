"""Rewrite exact repeated non-factual sentences before the authoritative originality judge.

This is a narrow repair, not a bypass: factual sentences are never rewritten,
and the elite judge still decides whether the resulting draft is publishable.
"""
from __future__ import annotations
import json, os, re
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOG = ROOT / "analytics/publication_log.jsonl"
OUT = ROOT / "data/live/recent_sentence_deduplication.json"
REPORT_DIR = ROOT / "data/reports"


def norm(text: str) -> str:
    return re.sub(r"[^a-z0-9 ]", "", re.sub(r"\\s+", " ", str(text or "").lower())).strip()


def load_json(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except Exception:
        return {}


def recent_sentences() -> set[str]:
    found = set()
    if not LOG.exists():
        return found
    for row in LOG.read_text(encoding="utf-8").splitlines()[-12:]:
        try:
            item = json.loads(row)
        except Exception:
            continue
        post = str(item.get("text") or item.get("post") or item.get("content") or "")
        for sentence in re.split(r"(?<=[.!?])\\s+|\\n+", post):
            n = norm(sentence)
            if len(n.split()) >= 6:
                found.add(n)
    return found


def resolve_draft() -> Path:
    raw = os.getenv("DRAFT_PATH", "").strip()
    if raw:
        path = Path(raw)
        if not path.exists():
            raise SystemExit(f"Recent sentence deduplication: DRAFT_PATH missing: {raw}")
        return path
    reports = sorted(REPORT_DIR.glob("*-multi-agent.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not reports:
        raise SystemExit("Recent sentence deduplication: no draft report")
    return reports[0]


def main() -> int:
    path = resolve_draft()
    data = load_json(path)
    draft = data.get("draft") if isinstance(data.get("draft"), dict) else data
    text = str(draft.get("post") or draft.get("text") or "").strip()
    if not text:
        raise SystemExit("Recent sentence deduplication: empty draft")

    symbol = str(draft.get("symbol") or draft.get("resolved_asset") or "").upper()
    if not symbol:
        match = re.search(r"\\$([A-Z][A-Z0-9]{1,14})\\b", text.upper())
        symbol = match.group(1) if match else ""
    symbol = re.sub(r"[^A-Z0-9]", "", symbol.replace("USDT", "").replace("$", ""))
    recent = recent_sentences()
    used = set()
    replacements = []
    factual = re.compile(r"\\$[A-Z][A-Z0-9]{1,14}\\b|\\b\\d+(?:\\.\\d+)?%|\\$\\s?\\d", re.I)

    exact_replacements = {
        "that keeps the read falsifiable the next measurable reaction either supports the structure or weakens it":
            "The next observed response should either strengthen this thesis or give a concrete reason to set it aside.",
        "the available evidence supports a scenario to test not certainty about the next candle":
            "Treat this as a working hypothesis; the next confirmed response should decide whether it still fits.",
    }

    def fresh_replacement(sentence: str) -> str | None:
        n = norm(sentence)
        candidates = []
        if n in exact_replacements:
            candidates.append(exact_replacements[n])
        if symbol:
            candidates.extend([
                f"For ${symbol}, the next observed response can support this thesis or show why it no longer fits.",
                f"The useful test for ${symbol} is whether the next response confirms the stated evidence or contradicts it.",
            ])
        candidates.extend([
            "The thesis remains provisional until new evidence either supports it or gives a reason to reject it.",
            "The next evidence point should determine whether this interpretation still holds up.",
        ])
        for candidate in candidates:
            cn = norm(candidate)
            if cn and cn not in recent and cn not in used and cn != n:
                return candidate
        return None

    # Split on sentence boundaries but keep the original separators/punctuation
    # in the unchanged portions. Only exact repeated sentences with no numeric
    # values or explicit cashtags are eligible for replacement.
    parts = re.split(r"(?<=[.!?])(?=\\s)|(?<=\\n)", text)
    output = []
    changed = 0
    for part in parts:
        stripped = part.strip()
        n = norm(stripped)
        if len(n.split()) >= 6 and n in recent:
            if factual.search(stripped):
                replacements.append({"sentence": stripped, "status": "preserved_factual_repeat"})
                output.append(part)
                continue
            candidate = fresh_replacement(stripped)
            if candidate:
                # Keep any leading/trailing whitespace from the original segment.
                leading = part[:len(part)-len(part.lstrip())]
                trailing = part[len(part.rstrip()):]
                output.append(leading + candidate + trailing)
                used.add(norm(candidate))
                changed += 1
                replacements.append({"sentence": stripped, "replacement": candidate, "status": "replaced"})
                continue
            replacements.append({"sentence": stripped, "status": "no_safe_alternative"})
        output.append(part)

    new_text = "".join(output).strip()
    # Fail closed if repair would break the publisher's copy contract.
    questions = new_text.count("?")
    if changed and (len(new_text) > 740 or questions != 1):
        result = {"version": "1.0", "status": "BLOCKED_REPAIR_CONTRACT", "changed": changed,
                  "replacements": replacements, "reason": "repair would violate 740-character or one-question contract"}
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\\n", encoding="utf-8")
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 1

    if changed:
        draft["post"] = new_text
        draft["text"] = new_text
        draft["recent_sentence_deduplication"] = {"status": "REPAIRED", "changed_sentences": changed}
        if isinstance(data.get("draft"), dict):
            data["draft"] = draft
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\\n", encoding="utf-8")

    result = {"version": "1.0", "generated_at": datetime.now(timezone.utc).isoformat(),
              "status": "REPAIRED" if changed else "UNCHANGED", "changed": changed,
              "factual_sentences_rewritten": 0, "replacements": replacements,
              "draft_path": str(path), "recheck_required": True}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\\n", encoding="utf-8")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
