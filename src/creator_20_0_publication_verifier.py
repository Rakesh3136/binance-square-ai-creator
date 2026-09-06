import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ANALYTICS = ROOT / "analytics"
LIVE = ROOT / "data" / "live"
INTEL = ROOT / "data" / "intelligence"


def read_json(path, default=None):
    try:
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default
    except Exception:
        return default


def read_publications():
    path = ANALYTICS / "publication_log.jsonl"
    rows = []
    if not path.exists():
        return rows
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
            if isinstance(row, dict):
                rows.append(row)
        except json.JSONDecodeError:
            continue
    return rows


def main():
    now = datetime.now(timezone.utc).isoformat()
    rows = read_publications()
    latest = rows[-1] if rows else None
    has_post_id = bool(latest and str(latest.get("post_id") or "").strip())
    status = str(latest.get("status") or "") if latest else ""

    if has_post_id and status.startswith("PUBLISHED"):
        truth_state = "VERIFIED_PUBLISHED"
        proof = "durable publication_log.jsonl record contains a concrete Binance Square post_id"
    elif latest and status:
        truth_state = "ATTEMPTED_NOT_VERIFIED"
        proof = "publication record exists but does not contain sufficient publication proof"
    else:
        truth_state = "NO_ATTEMPT"
        proof = "no durable publication record is available"

    result = {
        "version": "20.0",
        "checked_at": now,
        "truth_state": truth_state,
        "proof": proof,
        "latest_publication": latest,
        "publication_count_observed": len(rows),
        "rules": {
            "post_id_required": True,
            "revenue_inferred": False,
            "gate_bypass": False,
            "credential_changes": False,
        },
    }
    LIVE.mkdir(parents=True, exist_ok=True)
    INTEL.mkdir(parents=True, exist_ok=True)
    (LIVE / "creator_20_0_publication_truth.json").write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    report = {
        "version": "20.0",
        "generated_at": now,
        "truth_state": truth_state,
        "publication_count_observed": len(rows),
        "latest_post_id": latest.get("post_id") if latest else None,
        "latest_link": latest.get("link") if latest else None,
        "proof": proof,
    }
    (INTEL / "creator_20_0_report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    memory_path = ANALYTICS / "creator_20_0_memory.json"
    memory = read_json(memory_path, {"checks": []}) or {"checks": []}
    checks = memory.get("checks") if isinstance(memory.get("checks"), list) else []
    checks.append({"checked_at": now, "truth_state": truth_state, "post_id": latest.get("post_id") if latest else None})
    memory["checks"] = checks[-200:]
    memory["latest_truth_state"] = truth_state
    memory_path.write_text(json.dumps(memory, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
