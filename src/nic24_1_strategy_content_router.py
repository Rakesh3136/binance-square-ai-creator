"""NIC 24.1 — Strategy-to-Content Router.

Bridges observable market regime to a diverse research/content treatment.
It never authorizes a trade and never changes frozen levels.

Design goals:
- same coin must not imply same story;
- same regime must not imply the same format;
- recent publication history creates deterministic diversity pressure;
- charts are selected as a presentation treatment, not as evidence;
- editorial/news lanes remain eligible without a trade contract.
"""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
LIVE=ROOT/"data/live"
REGIME=LIVE/"nic24_regime_strategy_router.json"
PUBLICATIONS=ROOT/"analytics/publication_log.jsonl"
OUT=LIVE/"nic24_1_strategy_content_plan.json"

FORMATS={
    "BREAKOUT_EXPANSION":["breakout_case_study","levels_and_invalidation","catalyst_plus_structure"],
    "TREND_CONTINUATION":["trend_map","multi_timeframe_walkthrough","pullback_plan"],
    "MEAN_REVERSION":["reversion_setup","oversold_overbought_context","risk_first_scenario"],
    "MOMENTUM":["momentum_snapshot","acceleration_vs_exhaustion","catalyst_momentum"],
    "RANGE":["range_map","support_resistance_playbook","false_breakout_watch"],
    "UNCLASSIFIED":["market_explainer","data_observation","watchlist_question"],
}
CHARTS={
    "breakout_case_study":"breakout_structure",
    "levels_and_invalidation":"risk_levels",
    "catalyst_plus_structure":"catalyst_structure",
    "trend_map":"trend_structure",
    "multi_timeframe_walkthrough":"multi_timeframe",
    "pullback_plan":"pullback_levels",
    "reversion_setup":"mean_reversion",
    "oversold_overbought_context":"oscillator_context",
    "risk_first_scenario":"risk_scenario",
    "momentum_snapshot":"momentum_structure",
    "acceleration_vs_exhaustion":"momentum_vs_exhaustion",
    "catalyst_momentum":"catalyst_momentum",
    "range_map":"range_structure",
    "support_resistance_playbook":"support_resistance",
    "false_breakout_watch":"breakout_watch",
    "market_explainer":"clean_market_context",
    "data_observation":"data_observation",
    "watchlist_question":"watchlist_context",
}

def load(path):
    try:
        v=json.loads(path.read_text(encoding="utf-8"))
        return v if isinstance(v,dict) else {}
    except Exception:
        return {}

def recent():
    if not PUBLICATIONS.exists():
        return []
    out=[]
    for line in PUBLICATIONS.read_text(encoding="utf-8").splitlines()[-80:]:
        try:
            x=json.loads(line)
            if isinstance(x,dict) and str(x.get("status","")).upper() in {
                "PUBLISHED_AUTONOMOUSLY","PUBLISHED_VERIFIED_BY_API_RESPONSE",
                "VERIFIED_PUBLISHED","PUBLISHED_SUBMITTED_504"
            }:
                out.append(x)
        except Exception:
            pass
    return out[-12:]

def symbol(x):
    return str(x.get("symbol") or "").upper().replace("USDT","").strip()

def category(x):
    return str(x.get("category") or x.get("lane") or x.get("type") or "").lower()

def pick_format(regime, used_formats):
    choices=FORMATS.get(regime,FORMATS["UNCLASSIFIED"])
    for f in choices:
        if f not in used_formats:
            return f
    return choices[0]

def main():
    regime=load(REGIME)
    routes=regime.get("routes") if isinstance(regime.get("routes"),list) else []
    pubs=recent()
    used_symbols=[symbol(x) for x in pubs if symbol(x)]
    used_formats=[str(x.get("content_format") or x.get("format") or x.get("content_strategy") or "").lower() for x in pubs]
    used_categories=[category(x) for x in pubs]

    plans=[]
    for r in routes:
        if not isinstance(r,dict):
            continue
        sym=symbol(r)
        reg=str(r.get("regime") or "UNCLASSIFIED").upper()
        fmt=pick_format(reg,used_formats)
        symbol_recent=bool(sym and sym in used_symbols[-5:])
        format_recent=fmt in used_formats[-5:]
        category_recent=bool(category(r) and category(r) in used_categories[-5:])
        repeat_penalty=(25 if symbol_recent else 0)+(15 if format_recent else 0)+(10 if category_recent else 0)
        plans.append({
            "symbol":sym,
            "side":str(r.get("side") or "").upper(),
            "regime":reg,
            "strategy":r.get("strategy","no_trade_research"),
            "content_format":fmt,
            "chart_style":CHARTS[fmt],
            "repeat_penalty":repeat_penalty,
            "rotation_state":"EXPLORE" if repeat_penalty==0 else "ROTATE",
            "reader_value_focus":{
                "BREAKOUT_EXPANSION":"what confirms the move and where the thesis fails",
                "TREND_CONTINUATION":"structure, pullback quality and invalidation",
                "MEAN_REVERSION":"why reversion is plausible and what disproves it",
                "MOMENTUM":"acceleration, exhaustion and risk asymmetry",
                "RANGE":"range boundaries, false breaks and scenario risk",
                "UNCLASSIFIED":"explain the observation without forcing a trade",
            }.get(reg,"explain the observation without forcing a trade"),
        })
    result={
        "schema":"NIC-24.1-STRATEGY-CONTENT-ROUTER",
        "generated_at":datetime.now(timezone.utc).isoformat(),
        "plans":plans,
        "recent_publication_window":{"symbols":used_symbols[-5:],"formats":used_formats[-5:],"categories":used_categories[-5:]},
        "policy":[
            "Market regime selects a research strategy, not a trade authorization.",
            "Content format and chart treatment must rotate when recent history makes them repetitive.",
            "Repeated assets are penalized, not blindly banned when no stronger eligible alternative exists.",
            "Reader value, evidence and risk disclosure outrank novelty.",
            "This layer cannot modify entry, invalidation, TP1 or TP2 and cannot bypass publication gates.",
        ],
    }
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(result,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    print(json.dumps(result,indent=2,ensure_ascii=False))

if __name__=="__main__":
    main()
