"""NIC Forecast Decision Policy: convert calibrated evidence into bounded advisory decisions."""
from __future__ import annotations

MIN_TRUSTED_PROBABILITY=0.62
MAX_WAIT_BAND=0.08
MIN_EVIDENCE_SCORE=2.0
MIN_REGIME_STABILITY=0.55
MAX_EDGE_DECAY=0.30


def evaluate(evidence: dict, timing_state: str | None = None) -> dict:
    e=evidence or {}
    p=float(e.get("calibrated_probability") or 0.5)
    trusted=bool(e.get("probability_trusted"))
    score=float(e.get("evidence_score") or 0.0)
    stability=float(e.get("regime_stability") or 0.0)
    decay=float(e.get("edge_decay_penalty") or 1.0)
    side=str(e.get("side") or "").upper()
    timing=str(timing_state or "").upper()
    reasons=[]
    if not trusted:
        reasons.append("probability_not_trusted")
    if abs(p-0.5)<MAX_WAIT_BAND:
        reasons.append("probability_near_neutral")
    if score<MIN_EVIDENCE_SCORE:
        reasons.append("insufficient_evidence_score")
    if stability<MIN_REGIME_STABILITY:
        reasons.append("regime_unstable")
    if decay>MAX_EDGE_DECAY:
        reasons.append("edge_decay_too_high")
    if timing and timing not in {"EARLY","CONFIRMING"}:
        reasons.append("timing_not_actionable")
    direction = "BULLISH" if p>=0.5 else "BEARISH"
    if side and direction!=side:
        reasons.append("forecast_direction_conflict")
    if reasons:
        return {"decision":"WAIT","direction":direction,"confidence":round(abs(p-.5)*2,4),"reasons":reasons,"advisory_only":True,"publish_gate_unchanged":True}
    return {"decision":"LONG_CANDIDATE" if direction=="BULLISH" else "SHORT_CANDIDATE","direction":direction,"confidence":round(abs(p-.5)*2,4),"reasons":["trusted_probability","predictive_evidence","stable_regime","controlled_edge_decay","actionable_timing"],"advisory_only":True,"publish_gate_unchanged":True}

if __name__=="__main__":
    print("NIC Forecast Decision Policy: READY")
