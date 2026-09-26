"""Bounded Creative Variation Guard.

Chooses a fresh editorial treatment from recent verified publication metadata.
It never changes the authoritative asset, market thesis, evidence, eligibility,
or quality gates. It only supplies a bounded creative preference so consecutive
posts do not collapse into one reusable voice/template.
"""
from __future__ import annotations
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOG = ROOT / "analytics/publication_log.jsonl"
OUT = ROOT / "data/live/creative_variation_guard.json"

VOICE_MODES = (
    "field_note","analyst_take","mini_case","chart_lesson",
    "contrarian_read","event_breakdown","scenario_test","postmortem",
)
STRUCTURES = (
    "tension_then_evidence","fact_then_mechanism","question_then_test",
    "chart_then_interpretation","event_then_second_order_effect",
    "comparison_then_decision","thesis_then_invalidation","result_then_next_test",
)
HOOK_FAMILIES = (
    "decision_point","unexpected_detail","second_order_effect",
    "evidence_gap","contrast","question_led","accountability","direct_observation",
)
VISUAL_PROFILES = (
    "candles_volume","heikin_ashi","clean_structure","higher_timeframe","line_context",
)

def rows():
    if not LOG.exists():
        return []
    out=[]
    for line in LOG.read_text(encoding="utf-8").splitlines()[-30:]:
        try:
            x=json.loads(line)
            if isinstance(x,dict) and str(x.get("status") or "") in {
                "PUBLISHED_AUTONOMOUSLY","PUBLISHED_VERIFIED_BY_API_RESPONSE",
                "VERIFIED_PUBLISHED","PUBLISHED_SUBMITTED_504"
            }:
                out.append(x)
        except Exception:
            pass
    return out

def pick(values, counts):
    return min(values, key=lambda x:(counts[x], values.index(x)))

def main():
    recent=rows()
    def c(key):
        return Counter(str(r.get(key) or "").strip().lower() for r in recent)
    voice=c("voice_mode"); structure=c("structure"); hook=c("hook_family"); visual=c("visual_profile")
    selected={
        "voice_mode":pick(VOICE_MODES,voice),
        "structure":pick(STRUCTURES,structure),
        "hook_family":pick(HOOK_FAMILIES,hook),
        "visual_profile":pick(VISUAL_PROFILES,visual),
    }
    # A recent exact combination is avoided when alternatives exist.
    recent_combo={(str(r.get("voice_mode") or ""),str(r.get("structure") or ""),str(r.get("hook_family") or ""),str(r.get("visual_profile") or "")) for r in recent}
    if tuple(selected[k] for k in ("voice_mode","structure","hook_family","visual_profile")) in recent_combo:
        for v in VOICE_MODES:
            candidate=dict(selected); candidate["voice_mode"]=v
            if tuple(candidate[k] for k in ("voice_mode","structure","hook_family","visual_profile")) not in recent_combo:
                selected=candidate; break
    state={
        "version":"1.0",
        "generated_at":datetime.now(timezone.utc).isoformat(),
        "status":"READY",
        "recent_verified_publications":len(recent),
        "selection":selected,
        "recent_counts":{
            "voice_mode":dict(voice),"structure":dict(structure),
            "hook_family":dict(hook),"visual_profile":dict(visual),
        },
        "contract":{
            "asset_selection_unchanged":True,
            "evidence_unchanged":True,
            "signal_first_unchanged":True,
            "quality_gates_authoritative":True,
            "no_story_forcing":True,
            "no_revenue_inference":True,
        },
    }
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(state,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    print(json.dumps({"status":"READY","selection":selected,"recent_verified_publications":len(recent)},ensure_ascii=False))

if __name__=="__main__":
    main()
