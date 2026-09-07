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


def read_jsonl(path):
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


def num(v, default=0.0):
    try:
        return float(v)
    except Exception:
        return default


def engagement(row):
    views = num(row.get("views"))
    likes = num(row.get("likes"))
    replies = num(row.get("replies"))
    quotes = num(row.get("quotes"))
    shares = num(row.get("shares"))
    if views <= 0:
        return 0.0
    return min(1.0, (likes + 2 * replies + 2 * quotes + 3 * shares) / views)


def hook(row):
    text = str(row.get("title") or row.get("headline") or row.get("content") or "")
    if not text:
        return "unknown"
    low = text.lower()
    if any(x in low for x in ["why", "because", "what this means"]):
        return "explanation"
    if any(x in low for x in ["🚨", "breaking", "just in", "alert"]):
        return "breaking"
    if "?" in text:
        return "question"
    if any(x in low for x in ["but", "however", "instead", "really"]):
        return "contrarian"
    return "fact_led"


def main():
    now = datetime.now(timezone.utc).isoformat()
    outcomes = read_jsonl(ANALYTICS / "creator_7_2_outcomes.jsonl")
    pubs = read_jsonl(ANALYTICS / "publication_log.jsonl")
    recent = outcomes[-100:]

    enriched = []
    for row in recent:
        views = num(row.get("views"))
        e = engagement(row)
        enriched.append({
            "symbol": row.get("symbol"),
            "format": row.get("format"),
            "category": row.get("category"),
            "style": row.get("style"),
            "visual_type": row.get("visual_type"),
            "hook_type": row.get("hook_type") or hook(row),
            "views": views,
            "engagement_rate": e,
        })

    # Evidence is observational. We only promote a pattern when it has enough samples.
    groups = {}
    for row in enriched:
        key = (row["category"] or "unknown", row["hook_type"], row["visual_type"] or "unknown")
        g = groups.setdefault(key, {"n": 0, "views": [], "eng": []})
        g["n"] += 1
        g["views"].append(row["views"])
        g["eng"].append(row["engagement_rate"])

    patterns = []
    for key, g in groups.items():
        if g["n"] < 3:
            continue
        patterns.append({
            "category": key[0], "hook_type": key[1], "visual_type": key[2],
            "samples": g["n"],
            "avg_views": round(sum(g["views"]) / g["n"], 2),
            "avg_engagement_rate": round(sum(g["eng"]) / g["n"], 6),
        })
    patterns.sort(key=lambda x: (x["avg_engagement_rate"], x["avg_views"]), reverse=True)

    latest_pub = pubs[-1] if pubs else {}
    publication_truth = read_json(LIVE / "creator_20_0_publication_truth.json", {}) or {}
    truth = publication_truth.get("truth_state", "UNKNOWN")

    # Conservative anti-spam / anti-generic guardrails.
    weak_signal = len(patterns) == 0
    top = patterns[:5]
    decision = "PUBLISH_ONLY_STRONG_EDITORIAL_ANGLE" if not weak_signal else "RESEARCH_AND_WAIT"

    result = {
        "version": "21.0",
        "generated_at": now,
        "decision": decision,
        "editorial_mode": "HUMAN_LEVEL_EDITOR",
        "publication_truth": truth,
        "observed_publications": len(pubs),
        "latest_publication": latest_pub,
        "evidence_samples": len(enriched),
        "top_observed_patterns": top,
        "rules": {
            "minimum_pattern_samples": 3,
            "never_infer_revenue": True,
            "never_fake_engagement": True,
            "never_guarantee_returns": True,
            "do_not_publish_generic_price_recap_without_strong_angle": True,
            "do_not_bypass_editorial_or_publication_gates": True,
        },
        "editorial_instructions": [
            "Prefer a specific thesis over a generic price recap.",
            "Generate multiple hooks and select the strongest evidence-supported hook.",
            "Lead with why the reader should care, then show the evidence.",
            "Use disagreement, questions, or implications only when supported by facts.",
            "Make charts explain one claim instead of merely displaying candles.",
            "If no strong evidence-backed angle exists, wait rather than post filler.",
        ],
    }
    LIVE.mkdir(parents=True, exist_ok=True)
    INTEL.mkdir(parents=True, exist_ok=True)
    (LIVE / "creator_21_0_editorial_state.json").write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    (INTEL / "creator_21_0_report.json").write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
