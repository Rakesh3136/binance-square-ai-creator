"""NIC 22.5 — Unified Publication Eligibility Controller.

Separates "no validated trade" from "nothing worth publishing".

A trade still requires NIC 22.3 confirmation (or the bounded NIC 22.4
fresh-evidence confirmation). When that is unavailable, a fresh, evidence-backed
editorial/research lane may continue without manufacturing a trade contract.
This controller is the single upstream publication-mode decision.
"""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
LIVE=ROOT/"data/live"
CONFIRMATION=LIVE/"nic22_3_confirmation_selection.json"
ADAPTIVE=LIVE/"nic22_4_adaptive_confirmation.json"
RESEARCH=LIVE/"original_research.json"
DIRECTOR=LIVE/"content_director_brief.json"
SIGNAL=LIVE/"signal_first_routing.json"
OUT=LIVE/"nic22_5_publication_eligibility.json"

MAX_AGE_MINUTES=30.0
MIN_RESEARCH_INFO=70.0
MIN_RESEARCH_UNDERCOVERAGE=60.0
MIN_RESEARCH_EVIDENCE=50.0

def load(path: Path):
    try:
        value=json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value,dict) else {}
    except Exception:
        return {}

def number(value, default=0.0):
    try: return float(value)
    except Exception: return default

def fresh(value):
    raw=str(value or "").strip()
    if not raw: return False
    try:
        stamp=datetime.fromisoformat(raw.replace("Z","+00:00"))
        if stamp.tzinfo is None: stamp=stamp.replace(tzinfo=timezone.utc)
        age=(datetime.now(timezone.utc)-stamp.astimezone(timezone.utc)).total_seconds()/60.0
        return 0 <= age <= MAX_AGE_MINUTES
    except Exception:
        return False

def research_candidate(research):
    rows=[]
    for key in ("potential_gems","potential_risks"):
        for row in research.get(key) or []:
            if not isinstance(row,dict): continue
            info=number(row.get("information_advantage_score"))
            under=number(row.get("undercoverage_score"))
            evidence=number(row.get("evidence_score"))
            if info >= MIN_RESEARCH_INFO and under >= MIN_RESEARCH_UNDERCOVERAGE and evidence >= MIN_RESEARCH_EVIDENCE:
                rows.append({
                    "symbol":str(row.get("symbol") or "").upper().replace("USDT",""),
                    "information_advantage_score":info,
                    "undercoverage_score":under,
                    "evidence_score":evidence,
                    "missing_evidence":len(row.get("missing_evidence") or []),
                })
    if not rows: return None
    return max(rows,key=lambda x:(x["information_advantage_score"]*.4+x["undercoverage_score"]*.35+x["evidence_score"]*.25,-x["missing_evidence"]))

def main():
    confirmation=load(CONFIRMATION)
    adaptive=load(ADAPTIVE)
    research=load(RESEARCH)
    director=load(DIRECTOR)
    signal=load(SIGNAL)

    # In the live creator lifecycle, Signal-First is the current-cycle
    # decision authority. NIC 22.5 validates that decision; it must not
    # reconstruct a different candidate from older upstream artifacts.
    signal_time=signal.get("generated_at")
    signal_fresh=fresh(signal_time)
    signal_selected=signal.get("selected") if isinstance(signal.get("selected"),dict) else {}
    signal_publish=bool(signal.get("publish")) and signal_fresh
    signal_decision=str(signal.get("decision") or "").upper()

    trade_confirmed=str(confirmation.get("status") or "").upper()=="CONFIRMED"
    adaptive_confirmed=bool(adaptive.get("fresh_confirmation")) and str(adaptive.get("status") or "").upper()=="CONFIRMED"
    # Current NIC 22.4 writes the confirmation artifact directly, so also
    # recognize a recheck that promoted the normal NIC 22.3 selection file.
    adaptive_confirmed = adaptive_confirmed or (
        str(adaptive.get("status") or "").upper()=="RECHECK_CONFIRMED"
        and str(confirmation.get("status") or "").upper()=="CONFIRMED"
    )
    candidate=research_candidate(research)
    research_fresh=fresh(research.get("generated_at"))

    if signal_publish and signal_decision == "PRIMARY_SIGNAL":
        contract_ok=bool(signal.get("prediction_contract_complete")) and bool(signal_selected)
        if contract_ok:
            mode="TRADE"
            eligible=True
            reason="Current-cycle Signal-First trade decision passed the publication eligibility handoff."
            selected=signal_selected
        else:
            mode="BLOCKED"
            eligible=False
            reason="Current-cycle Signal-First trade decision lacks a complete authoritative prediction contract."
            selected={}
    elif signal_publish and signal_decision == "EDITORIAL_SIGNAL":
        mode="EDITORIAL"
        eligible=True
        reason="Current-cycle Signal-First editorial decision passed the publication eligibility handoff."
        selected=signal_selected
    elif signal and signal_fresh:
        mode="BLOCKED"
        eligible=False
        reason="Current-cycle Signal-First decision did not authorize publication."
        selected={}
    else:
        director_fresh=fresh(director.get("generated_at"))
        editorial_available=bool(candidate) and research_fresh and director_fresh

        if trade_confirmed:
            mode="TRADE"
            eligible=True
            reason="NIC 22.3 produced a confirmed trade opportunity."
            selected=confirmation.get("selected_opportunity") or {}
        elif adaptive_confirmed:
            mode="TRADE"
            eligible=True
            reason="NIC 22.4 fresh evidence promoted the opportunity to confirmed."
            selected=confirmation.get("selected_opportunity") or {}
        elif editorial_available:
            mode="EDITORIAL"
            eligible=True
            reason="No validated trade was confirmed, but fresh research evidence supports an editorial lane."
            selected=candidate
        else:
            mode="BLOCKED"
            eligible=False
            selected={}
            reason="Neither a validated trade nor a fresh evidence-backed editorial opportunity is available."

    result={
        "version":"22.5-unified-publication-eligibility",
        "generated_at":datetime.now(timezone.utc).isoformat(),
        "eligible":eligible,
        "publication_mode":mode,
        "trade_authorized":mode=="TRADE",
        "selected":selected,
        "reason":reason,
        "inputs":{
            "nic22_3_confirmed":trade_confirmed,
            "nic22_4_confirmed":adaptive_confirmed,
            "research_fresh":research_fresh,
            "director_fresh":director_fresh,
            "research_candidate_available":bool(candidate),
        },
        "thresholds":{
            "research_max_age_minutes":MAX_AGE_MINUTES,
            "research_min_information_advantage":MIN_RESEARCH_INFO,
            "research_min_undercoverage":MIN_RESEARCH_UNDERCOVERAGE,
            "research_min_evidence":MIN_RESEARCH_EVIDENCE,
        },
        "policy":[
            "No trade threshold is lowered.",
            "Editorial eligibility cannot create entry, TP, SL, direction or confidence.",
            "WATCH_ONLY and developing setups remain non-trade unless independently confirmed.",
            "Only one publication mode is authoritative for the downstream cycle.",
            "Freshness is mandatory for editorial recovery; stale artifacts cannot authorize publication.",
        ],
    }
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(result,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    print(json.dumps(result,indent=2,ensure_ascii=False))

if __name__=="__main__":
    main()
