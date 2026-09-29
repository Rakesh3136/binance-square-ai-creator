"""NIC Story Discovery 5.0 — information-first story selection."""
from __future__ import annotations
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data/live/nic_story_discovery.json"
PORTFOLIO = ROOT / "data/live/nic_adaptive_content_portfolio_8.json"

def load(name):
    p = ROOT / "data/live" / name
    try:
        value = json.loads(p.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except Exception:
        return {}

def text(value):
    return str(value or "").strip()

def main():
    research = load("original_research.json")
    strategy = load("agent_strategy.json")
    context = load("publication_context.json")
    monetization = load("nic_monetization_contract.json")
    portfolio = load("content_portfolio_plan.json")
    attribution = load("nic_attribution_intelligence_7.json")
    portfolio8 = load("nic_adaptive_content_portfolio_8.json")

    symbol = text(context.get("symbol") or strategy.get("symbol")).upper().replace("USDT", "").replace("$", "")
    evidence = []
    for source, label in ((research, "research"), (strategy, "strategy"), (context, "context")):
        for key in ("information_advantage", "why_now", "mechanism", "primary_observation", "thesis", "narrative", "summary", "key_finding"):
            value = text(source.get(key))
            if value:
                evidence.append({"source": label, "field": key, "text": value[:500]})

    news = load("news_snapshot.json").get("articles") or []
    news = [x for x in news if isinstance(x, dict) and (x.get("title") or x.get("summary"))][:12]
    evidence.extend({"source": "news", "field": "event", "text": text(x.get("title") or x.get("summary"))[:500]} for x in news[:5])
    if not evidence:
        raise SystemExit("Story discovery: insufficient evidence")

    verified_lanes = {}
    for item in attribution.get("learning", {}).get("lane_priors", []) or []:
        try:
            count = int(item.get("verified_rewards") or 0)
        except Exception:
            count = 0
        if count > 0:
            verified_lanes[text(item.get("lane")).lower()] = count

    corpus = " ".join(x["text"].lower() for x in evidence)
    lanes = [
        ("data_investigation", "surprise_in_the_data"),
        ("breaking_news", "verified_event"),
        ("world_macro", "macro_transmission"),
        ("research_lesson", "evidence_finding"),
        ("contrarian_thesis", "alternative_explanation"),
        ("follow_up", "changed_since_last"),
        ("market_setup", "conditional_setup"),
    ]
    scored = []
    for lane, kind in lanes:
        score = 0
        if lane == str(monetization.get("content_lane") or ""):
            score += 2
        if lane != "market_setup":
            score += 1
        if kind == "verified_event" and news:
            score += 3
        if kind == "macro_transmission" and any(word in corpus for word in ("fed", "rates", "inflation", "dollar", "liquidity", "macro")):
            score += 3
        if kind == "evidence_finding" and research:
            score += 3
        if kind == "surprise_in_the_data" and len(evidence) >= 3:
            score += 3
        if kind == "alternative_explanation":
            score += 2
        if kind == "changed_since_last":
            score += 2
        if kind == "conditional_setup" and strategy.get("prediction_ready"):
            score += 2
        score += min(2, verified_lanes.get(lane, 0))
        scored.append({"lane": lane, "score": score})

    portfolio_scores = {str(x.get("lane")): float(x.get("target_share") or 0) for x in portfolio8.get("allocations", []) or []}\n    for item in scored:\n        item["portfolio_target_share"] = portfolio_scores.get(item["lane"], 0.0)\n        item["score"] += min(0.5, item["portfolio_target_share"] * 5.0)\n    scored.sort(key=lambda item: (item["score"], item["lane"]), reverse=True)
    selected = scored[0]
    fingerprint = "|".join(x["text"] for x in evidence[:10])
    story_id = "story5-" + hashlib.sha256(f"{symbol}|{selected['lane']}|{fingerprint}".encode()).hexdigest()[:16]

    discovery = {
        "version": "5.0",
        "status": "DISCOVERED",
        "story_id": story_id,
        "asset": symbol,
        "selected_lane": selected["lane"],
        "story_kind": selected["lane"],
        "story_question": "What is the most useful verified insight here that a reader would not get from a routine price-level post?",
        "evidence_count": len(evidence),
        "evidence": evidence[:10],
        "ranked_story_types": scored,
        "selected_treatment": monetization.get("content_lane") or portfolio.get("selected_treatment"),
        "discovery_rule": "information-first; technical_setup is eligible only when the supplied evidence makes the setup itself the story",
        "attribution_learning": {
            "verified_reward_lane_count": verified_lanes.get(selected["lane"], 0),
            "bounded_tiebreaker": True,
            "portfolio_8_target_share": portfolio_scores.get(selected["lane"], 0.0),
            "unknown_does_not_reduce_score": True,
        },
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    OUT.write_text(json.dumps(discovery, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(discovery, indent=2))

if __name__ == "__main__":
    main()
