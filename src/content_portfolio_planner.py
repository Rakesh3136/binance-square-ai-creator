"""Bounded editorial portfolio planner.

Selects a *treatment* for the next eligible post from recent publication
metadata. It never selects an asset, invents evidence, overrides Signal-First,
or bypasses any quality/production gate.
"""
from __future__ import annotations
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOG = ROOT / "analytics/publication_log.jsonl"
OUT = ROOT / "data/live/content_portfolio_plan.json"

TREATMENTS = (
    "market_setup",
    "breaking_news",
    "world_macro",
    "research_lesson",
    "education",
    "nic_learning_note",
    "follow_up",
)

CATEGORY_MAP = {
    "technical_setup": "market_setup", "capital_flow_long": "market_setup",
    "capital_flow_short": "market_setup", "flow": "market_setup",
    "top_gainers": "market_setup", "top_losers": "market_setup",
    "high_volatility": "market_setup", "volume_leaders": "market_setup",
    "breaking_news": "breaking_news", "news_and_macro": "world_macro",
    "research_insight": "research_lesson", "data_surprise": "research_lesson",
    "market_mechanism": "education", "education": "education",
    "creator_signal_outcome": "nic_learning_note", "follow_up": "follow_up",
}

def load_recent():
    if not LOG.exists():
        return []
    rows=[]
    for line in LOG.read_text(encoding="utf-8").splitlines()[-40:]:
        try:
            x=json.loads(line)
            if isinstance(x,dict) and str(x.get("status") or "").upper() in {
                "PUBLISHED_AUTONOMOUSLY","PUBLISHED_VERIFIED_BY_API_RESPONSE",
                "VERIFIED_PUBLISHED","PUBLISHED_SUBMITTED_504"
            }:
                rows.append(x)
        except Exception:
            pass
    return rows[-20:]

def category(row):
    for k in ("category","story_lane","lane","content_category"):
        v=str(row.get(k) or "").strip().lower()
        if v:
            return v
    return ""

def main():
    recent=load_recent()
    mapped=[CATEGORY_MAP.get(category(x), "") for x in recent]
    counts=Counter(x for x in mapped if x)
    # Prefer a treatment that has not appeared recently; otherwise choose the
    # least-used treatment. This is a diversity preference, not a publish rule.
    unused=[x for x in TREATMENTS if x not in counts]
    selected=unused[0] if unused else min(TREATMENTS,key=lambda x:(counts[x],TREATMENTS.index(x)))
    plan={
        "version":"1.0",
        "generated_at":datetime.now(timezone.utc).isoformat(),
        "status":"READY",
        "selected_treatment":selected,
        "recent_verified_publications":len(recent),
        "recent_treatment_counts":dict(counts),
        "principles":{
            "asset_selection_unchanged":True,
            "evidence_unchanged":True,
            "signal_first_unchanged":True,
            "quality_gates_authoritative":True,
            "no_private_chain_of_thought":True,
            "nic_learning_notes_use_only_recorded_lessons":True,
            "world_news_requires_fresh_verified_source":True,
            "one_story_per_post":True,
        },
        "treatment_contracts":{
            "market_setup":"chart-first conditional setup with trigger/invalidation",
            "breaking_news":"fresh event, source, market impact, one specific question",
            "world_macro":"macro/world event plus verified crypto transmission mechanism",
            "research_lesson":"original evidence, mechanism, why it matters",
            "education":"one market concept taught through current evidence",
            "nic_learning_note":"public learning note from recorded outcomes; never hidden reasoning",
            "follow_up":"what changed since the previous verified publication",
        },
    }
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(plan,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    print(json.dumps(plan,indent=2,ensure_ascii=False))

if __name__=="__main__":
    main()
