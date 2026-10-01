"""NIC 4.x candidate handoff — bind the actual fresh creator draft to the NIC13 input contract.

candidate_generation_4 builds the strategy/prompt; the creator runner produces the
finished draft. This module closes that contract boundary without inventing text,
facts, candidates, or private reasoning.
"""
from __future__ import annotations
import json, re
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PREF = ROOT / "data/live/editorial_preflight.json"
CONTEXT = ROOT / "data/live/publication_context.json"
REPORTS = ROOT / "data/reports"

def load(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
        return value if isinstance(value, dict) else {}
    except Exception:
        return {}

def parse_dt(value: object):
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except Exception:
        return None

def text_from_candidate(item: object) -> str:
    if isinstance(item, str):
        return item.strip()
    if isinstance(item, dict):
        for key in ("script", "text", "post", "content", "body", "caption", "final_text", "generated_text"):
            value = item.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return ""

def extract_candidates(report: dict) -> list[dict]:
    raw = report.get("candidate_scripts_4")
    if not isinstance(raw, list):
        raw = report.get("candidates")
    result = []
    if isinstance(raw, list):
        for index, item in enumerate(raw):
            text = text_from_candidate(item)
            if text:
                result.append({
                    "source_index": index,
                    "script": text,
                    "source": "creator_candidate_output",
                })
    if result:
        return result

    draft = report.get("draft") if isinstance(report.get("draft"), dict) else {}
    text = text_from_candidate(draft)
    if text:
        return [{
            "source_index": 0,
            "script": text,
            "source": "fresh_creator_draft",
        }]
    return []

def latest_valid_report() -> tuple[Path, dict]:
    candidates = []
    for path in REPORTS.glob("*-multi-agent.json"):
        if not path.is_file():
            continue
        report = load(path)
        draft = report.get("draft") if isinstance(report.get("draft"), dict) else {}
        if text_from_candidate(draft):
            candidates.append((path.stat().st_mtime_ns, path, report))
    if not candidates:
        raise RuntimeError("NIC candidate handoff: no fresh creator draft report found")
    candidates.sort(key=lambda x: (x[0], str(x[1])), reverse=True)
    return candidates[0][1], candidates[0][2]

def main() -> int:
    pre = load(PREF)
    context = load(CONTEXT)
    report_path, report = latest_valid_report()
    generated = parse_dt(report.get("generated_at"))
    locked = parse_dt(context.get("locked_at"))

    # Never let an older report silently satisfy a new publication cycle.
    if generated is not None and locked is not None and generated < locked:
        raise RuntimeError(
            f"NIC candidate handoff: stale report {report_path.name}; "
            f"generated_at={generated.isoformat()} locked_at={locked.isoformat()}"
        )

    candidates = extract_candidates(report)
    if not candidates:
        raise RuntimeError("NIC candidate handoff: creator report contains no finished candidate text")

    selected = pre.get("selected_opportunity") if isinstance(pre.get("selected_opportunity"), dict) else {}
    symbol = str(
        selected.get("symbol")
        or context.get("symbol")
        or ((report.get("draft") or {}).get("symbol") if isinstance(report.get("draft"), dict) else "")
        or ""
    ).upper().replace("USDT", "").replace("$", "").strip()

    for item in candidates:
        item["symbol"] = symbol
        item["generation_mode"] = str(report.get("generation_mode") or ((report.get("draft") or {}).get("generation_mode") if isinstance(report.get("draft"), dict) else "") or "")
        item["source_report"] = str(report_path.relative_to(ROOT))

    pre["candidate_scripts_4"] = candidates
    pre["candidate_handoff_4"] = {
        "version": "1.0",
        "status": "READY",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_report": str(report_path.relative_to(ROOT)),
        "source_report_generated_at": report.get("generated_at"),
        "candidate_count": len(candidates),
        "symbol": symbol,
        "policy": [
            "Bind only fresh creator output to NIC13.",
            "Preserve creator text verbatim.",
            "Never invent facts, candidates, outcomes, revenue, or private reasoning.",
            "Fail closed when no fresh finished draft exists.",
        ],
    }
    PREF.parent.mkdir(parents=True, exist_ok=True)
    PREF.write_text(json.dumps(pre, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({
        "status": "READY",
        "candidate_count": len(candidates),
        "symbol": symbol,
        "source_report": str(report_path.relative_to(ROOT)),
    }, indent=2))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
