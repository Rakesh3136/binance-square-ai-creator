"""Fail-closed health report for Square performance retrieval.

A zero-feed result is treated as an observability failure, never as zero
engagement. This prevents the learning/revenue layers from optimizing against
fabricated or missing metrics.
"""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / "analytics/square_performance_state.json"
OUT = ROOT / "data/intelligence/square_performance_health.json"


def main():
    state = {}
    if STATE.exists():
        try:
            state = json.loads(STATE.read_text(encoding="utf-8"))
        except Exception:
            state = {}
    feed = int(state.get("feed_records", 0) or 0)
    matched = int(state.get("matched_post_ids", 0) or 0)
    published = int(state.get("published_records", 0) or 0)
    blind = published > 0 and (feed == 0 or matched == 0)
    report = {
        "version": "1.0-fail-closed",
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "status": "BLIND" if blind else "HEALTHY" if feed > 0 else "NO_FEED_DATA",
        "published_records": published,
        "feed_records": feed,
        "matched_post_ids": matched,
        "do_not_treat_missing_metrics_as_zero": True,
        "learning_allowed": not blind,
        "revenue_learning_allowed": not blind,
        "collector_version": state.get("collector_version"),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
