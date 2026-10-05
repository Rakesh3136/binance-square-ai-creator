"""NIC 23.5 — Counterfactual and adversarial decision challenge.

The engine attempts to disprove an actionable thesis before allowing a trade.
It never creates a direction or levels; it only downgrades/blocks decisions
when the opposing case or robustness tests are too strong.
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
]


def load(p):
    try:
        v=json.loads(p.read_text(encoding="utf-8"))
        return v if isinstance(v,dict) else {}
    except Exception:
        return {}


def num(v, default=0.0):
    try: return float(v)
    except Exception: return default


def first_data():
    for p in INPUTS:
        d=load(p)
        if d: return d
    return {}


def main():
    d=first_data()
    decision=str(d.get("decision") or d.get("status") or "UNKNOWN").upper()
    direction=str(d.get("direction") or d.get("primary_direction") or "").upper()
    bull=num(d.get("bull_case", d.get("bull_score", d.get("confidence",0))))
    bear=num(d.get("bear_case", d.get("bear_score", 0)))
    if not bear:
        bear=num(d.get("opposing_score", d.get("counter_case",0)))
    conflict=str(d.get("conflict_level") or "UNKNOWN").upper()
    robustness=num(d.get("thesis_robustness", d.get("robustness", 100)))
    dependency=num(d.get("single_signal_dependency", 0))
    invalidation=bool(d.get("invalidation_defined", d.get("invalidation")))

    tests=[]
    if bear:
        tests.append({"name":"opposite_thesis","passed":bull > bear+5,"bull_case":bull,"bear_case":bear})
    else:
        tests.append({"name":"opposite_thesis","passed":False,"reason":"opposing_case_not_measured"})
    tests.append({"name":"thesis_robustness","passed":robustness>=60,"score":robustness})
    tests.append({"name":"single_signal_dependency","passed":dependency<=0.35,"dependency":dependency})
    tests.append({"name":"invalidation_defined","passed":invalidation})
    tests.append({"name":"conflict","passed":conflict not in {"HIGH","SEVERE"},"level":conflict})

    failures=[t["name"] for t in tests if not t["passed"]]
    pass_count=sum(1 for t in tests if t["passed"])
    # Counterfactual challenge can never turn a non-trade into a trade.
    challenged_trade=decision in {"TRADE","CONFIRMED","LONG","SHORT"}
    if challenged_trade and failures:
        final="WATCH"
        trade_authorized=False
        reason="Counterfactual challenge found material weaknesses: "+", ".join(failures)
    elif challenged_trade:
        final="TRADE"
        trade_authorized=True
        reason="Counterfactual challenge passed all material tests."
    else:
        final=decision if decision in {"WATCH","RESEARCH","EDITORIAL","NO_TRADE","BLOCKED"} else "WATCH"
        trade_authorized=False
        reason="No trade authorization is created by the adversarial layer."

    result={
        "version":"23.5.0",
        "generated_at":datetime.now(timezone.utc).isoformat(),
        "input_decision":decision,
        "primary_direction":direction,
        "decision":final,
        "trade_authorized":trade_authorized,
        "challenge_passed":not failures,
        "tests":tests,
        "failed_tests":failures,
        "pass_count":pass_count,
        "test_count":len(tests),
        "reason":reason,
        "policy":[
            "Never lower confirmation thresholds.",
            "Never invent a direction, entry, stop, or target.",
            "A counterfactual failure can downgrade a trade to WATCH but cannot promote WATCH to TRADE.",
            "A thesis dependent on one dominant signal is not robust enough for automatic trade authorization.",
        ],
    }
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(result,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    print(json.dumps(result,indent=2,ensure_ascii=False))

if __name__=="__main__":
    main()
