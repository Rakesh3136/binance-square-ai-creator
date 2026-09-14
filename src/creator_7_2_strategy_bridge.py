"""Creator 7.2 -> strategy-memory bridge.

Turns verified publication outcomes into bounded strategy signals. Asset-level and
lane-level results are descriptive evidence only: they never authorize factual
claims, guaranteed returns, manipulation, spam, or bypassing editorial gates.
"""
from __future__ import annotations
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LEARNED = ROOT / "analytics/creator_7_2_strategy.json"
OUTCOMES = ROOT / "analytics/creator_7_2_outcomes.jsonl"
MEMORY = ROOT / "analytics/strategy_memory.json"


def load(path):
    try:
        value = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
        return value if isinstance(value, dict) else {}
    except Exception:
        return {}


def jsonl(path):
    rows = []
    if not path.exists():
        return rows
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            value = json.loads(line)
            if isinstance(value, dict):
                rows.append(value)
        except Exception:
            pass
    return rows


def num(value):
    try:
        x = float(value)
        return x if x == x and abs(x) != float("inf") else 0.0
    except (TypeError, ValueError):
        return 0.0


def median(values):
    xs = sorted(values)
    if not xs:
        return 0.0
    n = len(xs)
    return xs[n // 2] if n % 2 else (xs[n // 2 - 1] + xs[n // 2]) / 2


def build_group(rows, key):
    groups = defaultdict(list)
    for row in rows:
        value = str(row.get(key) or "unknown").strip()
        if value and value.lower() != "unknown":
            groups[value].append(row)
    result = []
    for value, items in groups.items():
        if len(items) < 3:
            continue
        scores = [num(x.get("outcome_score")) for x in items]
        wins = sum(str(x.get("verdict", "")).upper() == "WIN" for x in items)
        losses = sum(str(x.get("verdict", "")).upper() == "LOSS" for x in items)
        result.append({
            "value": value,
            "sample": len(items),
            "median_score": round(median(scores), 4),
            "win_rate": round(wins / len(items), 4),
            "loss_rate": round(losses / len(items), 4),
        })
    return sorted(result, key=lambda x: (x["median_score"], x["sample"]), reverse=True)


def main():
    learned = load(LEARNED)
    memory = load(MEMORY)
    outcomes = jsonl(OUTCOMES)
    if not learned:
        print(json.dumps({"status": "NO_7_2_DATA", "message": "No Creator 7.2 strategy exists yet."}))
        return

    assets = build_group(outcomes, "symbol")
    categories = build_group(outcomes, "category")
    formats = build_group(outcomes, "experiment_format")
    hooks = build_group(outcomes, "hook_type")

    verified_revenue = [x for x in outcomes if x.get("verified_revenue") is not None]
    revenue_total = round(sum(num(x.get("verified_revenue")) for x in verified_revenue), 8)

    # Only repeated evidence becomes a preference. Single-post winners stay exploratory.
    strong_assets = [x for x in assets if x["sample"] >= 3 and x["win_rate"] >= 0.67]
    weak_assets = [x for x in assets if x["sample"] >= 3 and x["loss_rate"] >= 0.67]

    memory["creator_7_2"] = {
        "version": learned.get("version", "7.2"),
        "generated_at": learned.get("generated_at"),
        "learning_status": learned.get("learning_status"),
        "sample_size": learned.get("sample_size", 0),
        "wins": learned.get("wins", 0),
        "losses": learned.get("losses", 0),
        "mixed": learned.get("mixed", 0),
        "preference_changes": learned.get("preference_changes", []),
        "next_strategy": learned.get("next_strategy", {}),
        "revenue": learned.get("revenue", {}),
        "asset_outcomes": assets[:30],
        "category_outcomes": categories[:20],
        "format_outcomes": formats[:20],
        "hook_outcomes": hooks[:20],
        "strong_repeated_assets": strong_assets[:10],
        "weak_repeated_assets": weak_assets[:10],
        "verified_revenue": {
            "sample": len(verified_revenue),
            "total": revenue_total,
            "source": "explicit_verified_fields_only",
        },
        "guardrails": {
            "minimum_repeated_sample": 3,
            "minimum_asset_win_rate": 0.67,
            "never_guarantee_outcomes": True,
            "never_infer_revenue": True,
            "never_override_editorial_or_safety_gates": True,
        },
    }
    memory["learning_overlay"] = (
        "Creator 7.2 is an evidence layer. Repeated outcomes may change bounded testing preference "
        "for assets, categories, formats and hooks. They cannot force a post, predict a pump, imply "
        "future returns, fabricate revenue, or bypass freshness, originality, evidence, or anti-manipulation gates."
    )
    memory["generated_at"] = datetime.now(timezone.utc).isoformat()
    MEMORY.parent.mkdir(parents=True, exist_ok=True)
    MEMORY.write_text(json.dumps(memory, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({
        "status": "OK",
        "version": "7.2-asset-lane-learning",
        "sample_size": len(outcomes),
        "assets_with_repeated_samples": len(assets),
        "strong_repeated_assets": len(strong_assets),
        "weak_repeated_assets": len(weak_assets),
        "verified_revenue_samples": len(verified_revenue),
        "verified_revenue_total": revenue_total,
        "memory": str(MEMORY),
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
