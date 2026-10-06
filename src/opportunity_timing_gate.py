"""Deterministic timing gate: prefer early/confirming setups and refuse fresh trade posts after the move is extended.

This is a timing/entry-quality gate, not a price predictor. It never claims a coin
will pump; it only asks whether a new trade-oriented publication is still actionable.
"""
from __future__ import annotations
import math

TRADE_LANES={"flow","capital_flow_long","capital_flow_short","creator_signal_outcome","follow_up","next_gainer_candidate","next_loser_candidate"}
EDITORIAL_POST_MOVE_ALLOWED={"breaking_news","news_and_macro","research_insight","education","market_mechanism","data_surprise","watchlist"}

def num(v, default=0.0):
    try:
        x=float(v)
        return x if math.isfinite(x) else default
    except Exception:
        return default

def evaluate(candidate, flow_row=None, market_row=None):
    c=candidate if isinstance(candidate,dict) else {}
    f=flow_row if isinstance(flow_row,dict) else {}
    m=market_row if isinstance(market_row,dict) else {}
    state=str(f.get("flow_state") or c.get("flow_state") or "").upper()
    move=max(abs(num(c.get("price_change_percent"))), abs(num(m.get("price_change_percent"))))
    if not move:
        move=abs(num(c.get("price_change_6h_pct")))
    intraday=max(num(f.get("range_6h_pct")), num(c.get("intraday_range_percent")), num(m.get("intraday_range_percent")))
    vol=max(num(f.get("volume_acceleration")), num(c.get("volume_acceleration")))
    dist=num(f.get("breakout_distance_pct"), num(c.get("breakout_distance_pct"), 99))
    category=str(c.get("category") or c.get("lane") or "").lower()
    if state=="EXHAUSTED" or move>=12 or (move>=8 and dist<=1 and vol>=2.5):
        timing="EXHAUSTED"
        reason="move is statistically/structurally too extended for a fresh trade entry"
    elif state=="LATE" or move>=6 or (move>=8 and intraday>=10):
        timing="LATE"
        reason="material price expansion has already occurred; fresh entry risks chasing"
    elif state=="CONFIRMED":
        timing="CONFIRMING"
        reason="participation and structure are confirmed while extension remains bounded"
    elif state in {"EARLY","DEVELOPING"}:
        timing="EARLY" if state=="EARLY" else "CONFIRMING"
        reason="participation is developing before a major price extension"
    elif move<=3 and (vol>=1.25 or dist<=7):
        timing="EARLY"
        reason="price remains relatively close to structure while participation is emerging"
    else:
        timing="WATCH"
        reason="timing evidence is insufficient to call the setup early or actionable"
    allowed=timing in {"EARLY","CONFIRMING"}
    if timing in {"LATE","EXHAUSTED"} and category in EDITORIAL_POST_MOVE_ALLOWED:
        allowed=True
        mode="EDITORIAL_POST_MOVE"
    else:
        mode="FRESH_TRADE" if category in TRADE_LANES or category else "RESEARCH"
    return {"allowed":allowed,"timing_state":timing,"timing_reason":reason,"publication_mode":mode,
            "price_move_pct":round(move,4),"intraday_range_pct":round(intraday,4),
            "volume_acceleration":round(vol,4),"breakout_distance_pct":round(dist,4)}

if __name__=="__main__":
    print(evaluate({"symbol":"TEST","category":"capital_flow_long","price_change_percent":9},
                   {"flow_state":"LATE","breakout_distance_pct":1,"volume_acceleration":3}, {}))
