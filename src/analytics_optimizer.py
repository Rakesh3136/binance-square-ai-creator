import csv
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

LOG = Path("analytics/performance_log.csv")
MEMORY = Path("analytics/strategy_memory.json")


def num(row, key):
    try:
        return float(row.get(key, ""))
    except (TypeError, ValueError):
        return 0.0


def main():
    if not LOG.exists():
        raise SystemExit(f"Missing {LOG}")

    with LOG.open("r", encoding="utf-8", newline="") as f:
        rows = [r for r in csv.DictReader(f) if r.get("post_id")]

    if not rows:
        memory = {
            "version": 1,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "sample_size": 0,
            "best_topics": [],
            "best_formats": [],
            "best_hook_patterns": [],
            "avoid_patterns": [],
            "recommended_strategy": "No performance data yet. Prefer evidence-led, specific stories over generic market recaps.",
            "note": "Add verified Creator Center performance metrics, then rerun this optimizer.",
        }
        MEMORY.write_text(json.dumps(memory, indent=2, ensure_ascii=False), encoding="utf-8")
        print(json.dumps({"status": "NO_DATA", "sample_size": 0}, indent=2))
        return

    topic_scores = defaultdict(list)
    format_scores = defaultdict(list)
    hook_scores = defaultdict(list)

    for row in rows:
        views = num(row, "views")
        likes = num(row, "likes")
        comments = num(row, "comments")
        shares = num(row, "shares")
        saves = num(row, "saves")
        followers = num(row, "followers_gained")

        engagement = (likes + 2 * comments + 3 * shares + 2 * saves) / max(views, 1) * 100
        growth = followers / max(views, 1) * 100
        score = 0.65 * min(100, engagement * 20) + 0.35 * min(100, growth * 50)

        topic = (row.get("topic") or "unknown").strip().lower()
        fmt = (row.get("format") or "unknown").strip().lower()
        hook = (row.get("notes") or "").strip()
        topic_scores[topic].append(score)
        format_scores[fmt].append(score)
        if hook:
            hook_scores[hook[:120]].append(score)

    def ranked(groups):
        values = [(k, sum(v) / len(v), len(v)) for k, v in groups.items()]
        return [
            {"name": k, "score": round(s, 2), "sample_size": n}
            for k, s, n in sorted(values, key=lambda x: x[1], reverse=True)[:5]
        ]

    memory = {
        "version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "sample_size": len(rows),
        "best_topics": ranked(topic_scores),
        "best_formats": ranked(format_scores),
        "best_hook_patterns": ranked(hook_scores),
        "avoid_patterns": [x["name"] for x in ranked(topic_scores)[-3:]][::-1] if len(topic_scores) > 3 else [],
        "recommended_strategy": "Prefer the highest-performing topics and formats in this memory, while keeping evidence quality and originality as hard constraints.",
    }
    MEMORY.write_text(json.dumps(memory, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({
        "status": "OK",
        "sample_size": len(rows),
        "best_topics": memory["best_topics"],
        "best_formats": memory["best_formats"],
        "memory": str(MEMORY),
    }, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
