"""NIC Decision Outcome Ledger: evaluate whether NIC decisions were actually useful."""
from __future__ import annotations
import json
from pathlib import Path
from datetime import datetime, timezone

ROOT=Path(__file__).resolve().parents[1]
LEDGER=ROOT/"data/intelligence/nic_decision_outcome_ledger.jsonl"


def score(decision: str, side: str, hit: bool | None) -> dict:
    d=str(decision or "WAIT").upper(); s=str(side or "").upper()
    if hit is None:
        return {"utility":0.0,"outcome":"UNRESOLVED"}
    if d=="WAIT":
        return {"utility":0.25 if not hit else -0.10,"outcome":"ABSTAINED"}
    aligned=(d=="LONG_CANDIDATE" and s=="BULLISH") or (d=="SHORT_CANDIDATE" and s=="BEARISH")
    if not aligned:
        return {"utility":-1.0,"outcome":"DIRECTION_CONFLICT"}
    return {"utility":1.0 if hit else -1.0,"outcome":"WIN" if hit else "LOSS"}


def append(row: dict) -> None:
    LEDGER.parent.mkdir(parents=True,exist_ok=True)
    with LEDGER.open("a",encoding="utf-8") as f:
        f.write(json.dumps(row,separators=(",",":"))+"\n")


def summarize(rows: list[dict]) -> dict:
    resolved=[r for r in rows if r.get("outcome") not in {None,"UNRESOLVED"}]
    if not resolved: return {"samples":0,"utility":0.0,"win_rate":None,"abstention_rate":None}
    utility=sum(float(r.get("utility",0)) for r in resolved)/len(resolved)
    active=[r for r in resolved if r.get("outcome") in {"WIN","LOSS"}]
    return {"samples":len(resolved),"utility":round(utility,6),"win_rate":round(sum(r.get("outcome")=="WIN" for r in active)/len(active),6) if active else None,"abstention_rate":round(sum(r.get("outcome")=="ABSTAINED" for r in resolved)/len(resolved),6)}

if __name__=="__main__":
    rows=[]
    if LEDGER.exists():
        rows=[json.loads(x) for x in LEDGER.read_text().splitlines() if x.strip()]
    print(json.dumps({"schema":"NIC-DECISION-OUTCOME-1.0","generated_at":datetime.now(timezone.utc).isoformat(),"summary":summarize(rows),"policy":"Decision utility is advisory; unresolved outcomes never become wins or losses."},indent=2))
