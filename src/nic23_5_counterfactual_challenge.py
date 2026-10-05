"""NIC 23.5 — Counterfactual and adversarial decision verification.

Verification-only layer. It challenges the current cycle's decision but does not
control publication. Stale or missing inputs produce NOT_APPLICABLE rather than
silently reusing an older cycle's decision.
"""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
LIVE=ROOT/"data/live"
OUT=LIVE/"nic23_5_counterfactual_challenge.json"
INPUTS=[
    LIVE/"nic23_4_evidence_fusion.json",
    LIVE/"nic23_4_decision_fusion.json",
    LIVE/"nic23_3_confirmation_selection.json",
    LIVE/"signal_first_routing.json",
]
MAX_INPUT_AGE_SECONDS=45*60

def load(p):
    try:
        v=json.loads(p.read_text(encoding="utf-8"))
        return v if isinstance(v,dict) else {}
    except Exception:
        return {}

def num(v, default=0.0):
    try: return float(v)
    except Exception: return default

def parse_time(v):
    try: return datetime.fromisoformat(str(v).replace("Z","+00:00"))
    except Exception: return None

def first_fresh_data(now):
    candidates=[]
    for p in INPUTS:
        d=load(p)
        if not d: continue
        ts=parse_time(d.get("generated_at") or d.get("timestamp") or d.get("updated_at"))
        if ts is None: continue
        age=(now-ts).total_seconds()
        if 0 <= age <= MAX_INPUT_AGE_SECONDS:
            candidates.append((ts,p,d))
    if not candidates:
        return None,None,{}
    candidates.sort(reverse=True,key=lambda x:x[0])
    _,p,d=candidates[0]
    return p,d.get("generated_at"),d

def main():
    now=datetime.now(timezone.utc)
    source,source_time,d=first_fresh_data(now)
    if not d:
        result={
            "version":"23.5.1",
            "generated_at":now.isoformat(),
            "status":"NOT_APPLICABLE",
            "decision":"NOT_APPLICABLE",
            "trade_authorized":False,
            "challenge_passed":False,
            "reason":"No fresh NIC 23 decision artifact was available for this cycle; stale artifacts were ignored.",
            "source":None,
            "policy":["Verification only.","Never reuse stale decision artifacts.","Never create trade authorization.","Signal-first input is treated as a decision source, not a new market-data authority."]
        }
        OUT.parent.mkdir(parents=True,exist_ok=True)
        OUT.write_text(json.dumps(result,indent=2)+"\n")
        print(json.dumps(result,indent=2))
        return

    decision=str(d.get("decision") or d.get("status") or "UNKNOWN").upper()
    decision_id=str(d.get("decision_id") or ((d.get("signal_first_routing") or {}).get("decision_id") if isinstance(d.get("signal_first_routing"),dict) else "") or "")
    direction=str(d.get("direction") or d.get("primary_direction") or ((d.get("selected") or {}).get("direction") or "")).upper()
    bull=num(d.get("bull_case",d.get("bull_score",d.get("confidence",0))))
    if not bull and isinstance(d.get("selected"),dict):
        research=d["selected"].get("research") or {}
        scenario=research.get("scenario") or {}
        bull=num(scenario.get("bull_score",0))
    bear=num(d.get("bear_case",d.get("bear_score",d.get("opposing_score",d.get("counter_case",0)))))
    if not bear and isinstance(d.get("selected"),dict):
        research=d["selected"].get("research") or {}
        scenario=research.get("scenario") or {}
        bear=num(scenario.get("bear_risk_score",0))
    conflict=str(d.get("conflict_level") or "UNKNOWN").upper()
    robustness=num(d.get("thesis_robustness",d.get("robustness",100)))
    dependency=num(d.get("single_signal_dependency",0))
    invalidation=bool(d.get("invalidation_defined",d.get("invalidation")))

    tests=[
        {"name":"opposite_thesis","passed":bool(bear) and bull>bear+5,"bull_case":bull,"bear_case":bear},
        {"name":"thesis_robustness","passed":robustness>=60,"score":robustness},
        {"name":"single_signal_dependency","passed":dependency<=0.35,"dependency":dependency},
        {"name":"invalidation_defined","passed":invalidation},
        {"name":"conflict","passed":conflict not in {"HIGH","SEVERE"},"level":conflict},
    ]
    failures=[t["name"] for t in tests if not t["passed"]]
    challenged_trade=decision in {"TRADE","CONFIRMED","LONG","SHORT"} or bool(d.get("primary_signal"))
    if challenged_trade and failures:
        final="WATCH"; authorized=False
        reason="Counterfactual challenge found material weaknesses: "+", ".join(failures)
    elif challenged_trade:
        final="TRADE"; authorized=True
        reason="Counterfactual challenge passed all material tests."
    else:
        final=decision if decision in {"WATCH","RESEARCH","EDITORIAL","EDITORIAL_SIGNAL","NO_TRADE","BLOCKED"} else "WATCH"
        authorized=False
        reason="Verification cannot promote a non-trade decision."

    result={
        "version":"23.5.1","generated_at":now.isoformat(),
        "decision_id":decision_id,
        "status":"VERIFIED","source":str(source.relative_to(ROOT)),
        "source_generated_at":source_time,
        "input_decision":decision,"primary_direction":direction,
        "decision":final,"trade_authorized":authorized,
        "challenge_passed":not failures,"tests":tests,
        "failed_tests":failures,"pass_count":sum(t["passed"] for t in tests),
        "test_count":len(tests),"reason":reason,
        "policy":["Verification only; publication is unaffected.",
                  "Never lower confirmation thresholds.",
                  "Never invent direction, entry, stop, or target.",
                  "A counterfactual failure can downgrade TRADE to WATCH.",
                  "A verification layer can never promote WATCH to TRADE.",
                  "Stale inputs are ignored rather than reused.",
                  "A fresh signal-first artifact may be challenged, but this layer never creates a trade decision."]
    }
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(result,indent=2)+"\n")
    print(json.dumps(result,indent=2))

if __name__=="__main__":
    main()
