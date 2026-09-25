"""NIC Prediction Post-Mortem Lab.

Reads only post-fix, terminal outcomes and immutable call metadata. Finds repeated
failure patterns by side, quality band, and market regime. It emits bounded,
advisory feedback consumed by the prediction engine on later cycles.
"""
from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CALLS = ROOT / "analytics" / "call_ledger.jsonl"
OUTCOMES = ROOT / "analytics" / "prediction_outcomes.jsonl"
OUT = ROOT / "data" / "live" / "nic_prediction_postmortem.json"
REPORT = ROOT / "data" / "intelligence" / "nic_prediction_postmortem_report.json"
HIST_AUDIT = ROOT / "data" / "intelligence" / "nic_historical_prediction_audit_report.json"


def jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            value = json.loads(line)
            if isinstance(value, dict):
                rows.append(value)
        except Exception:
            pass
    return rows


def num(v, default=None):
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def band(value):
    score = num(value)
    if score is None:
        return "UNKNOWN"
    if score < 70:
        return "LT70"
    if score < 80:
        return "70_79"
    if score < 90:
        return "80_89"
    return "90_PLUS"


def main() -> int:
    calls = {
        str(x.get("call_id")): x
        for x in jsonl(CALLS)
        if x.get("call_id")
    }

    latest = {}
    for row in jsonl(OUTCOMES):
        if not str(row.get("evaluator_version") or "").startswith("25."):
            continue
        outcome = str(row.get("outcome") or "").upper()
        cid = str(row.get("call_id") or "")
        if cid and outcome in {"WIN", "INVALIDATED", "AMBIGUOUS"}:
            latest[cid] = row

    terminal = list(latest.values())

    def enrich(row):
        call = calls.get(str(row.get("call_id") or ""), {})
        outcome = str(row.get("outcome") or "").upper()
        win = outcome == "WIN"
        loss = outcome == "INVALIDATED"
        return {
            "call_id": str(row.get("call_id") or ""),
            "symbol": str(row.get("symbol") or call.get("symbol") or "").upper(),
            "side": str(row.get("direction") or call.get("direction") or "").upper().replace("_BIAS", ""),
            "outcome": outcome,
            "win": win,
            "loss": loss,
            "ambiguous": outcome == "AMBIGUOUS",
            "quality_band": band(call.get("nic_prediction_quality")),
            "quality_score": num(call.get("nic_prediction_quality")),
            "regime": str(call.get("market_regime_at_entry") or "UNKNOWN"),
        }

    rows = [enrich(x) for x in terminal]

    try:
        historical_audit = json.loads(HIST_AUDIT.read_text(encoding="utf-8")) if HIST_AUDIT.exists() else {}
    except Exception:
        historical_audit = {}

    legacy_diagnostics = {
        "records_audited": historical_audit.get("records_audited", 0),
        "by_direction": historical_audit.get("by_direction", {}),
        "calibration_eligible": False,
        "purpose": "structural_diagnostics_only",
    }

    def stats(items):
        wins = sum(x["win"] for x in items)
        losses = sum(x["loss"] for x in items)
        ambiguous = sum(x["ambiguous"] for x in items)
        resolved = wins + losses
        return {
            "samples": len(items),
            "wins": wins,
            "losses": losses,
            "ambiguous": ambiguous,
            "resolved_samples": resolved,
            "win_rate_excluding_ambiguous": round(wins / resolved, 4) if resolved else None,
        }

    groups = {}
    for dimension in ("side", "quality_band", "regime"):
        bucket = defaultdict(list)
        for row in rows:
            bucket[row[dimension]].append(row)
        groups[dimension] = {key: stats(value) for key, value in sorted(bucket.items())}

    # Combined segments are the most useful for repeated failure detection.
    combined = defaultdict(list)
    for row in rows:
        combined[(row["side"], row["quality_band"], row["regime"])].append(row)

    feedback = []
    for (side, quality_band, regime), items in combined.items():
        s = stats(items)
        resolved = s["resolved_samples"]
        rate = s["win_rate_excluding_ambiguous"]
        if resolved >= 5 and rate is not None and rate < 0.45:
            feedback.append({
                "action": "PENALIZE_REPEATED_FAILURE",
                "side": side,
                "quality_band": quality_band,
                "regime": regime,
                "samples": s["samples"],
                "resolved_samples": resolved,
                "win_rate": rate,
                "bounded_quality_penalty": 8.0,
                "reason": "Repeated post-fix losses in a specific prediction context.",
            })
        elif resolved >= 5 and rate is not None and rate > 0.65:
            feedback.append({
                "action": "KEEP_NO_EXTRA_BOOST",
                "side": side,
                "quality_band": quality_band,
                "regime": regime,
                "samples": s["samples"],
                "resolved_samples": resolved,
                "win_rate": rate,
                "bounded_quality_penalty": 0.0,
                "reason": "Repeatedly acceptable outcomes; preserve evidence without upward self-reinforcement.",
            })

    now = datetime.now(timezone.utc).isoformat()
    result = {
        "version": "1.0-postmortem",
        "generated_at": now,
        "evaluator_scope": "25.0-trigger-first-state-machine only",
        "terminal_samples": len(rows),
        "by_dimension": groups,
        "repeated_context_feedback": feedback,
        "legacy_prediction_diagnostics": legacy_diagnostics,
        "guardrails": [
            "Legacy outcome labels are excluded.",
            "Ambiguous candles do not count as wins or losses.",
            "Repeated success never receives a positive feedback boost; it only avoids penalty.",
            "Repeated failure can apply only a bounded advisory penalty.",
            "This layer cannot change frozen levels or bypass publication gates.",
        ],
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    REPORT.write_text(
        json.dumps({
            "version": result["version"],
            "generated_at": now,
            "terminal_samples": len(rows),
            "feedback_count": len(feedback),
            "legacy_prediction_diagnostics": legacy_diagnostics,
            "by_dimension": groups,
        }, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "status": "READY",
        "terminal_samples": len(rows),
        "feedback_count": len(feedback),
        "feedback": feedback[:10],
    }, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
