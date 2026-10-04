"""NIC 23.1 append-only Trade Experience Ledger.

Prediction snapshots and outcome events are immutable JSONL records. The ledger
never rewrites a historical prediction when an outcome arrives.
"""
from __future__ import annotations
import hashlib, json
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
LIVE=ROOT/"data/live"
PREDICTION=LIVE/"nic_prediction_engine.json"
OUTCOME_SOURCES=(ROOT/"analytics/prediction_outcomes.jsonl", LIVE/"nic_trade_outcome_events.jsonl")
LEDGER=LIVE/"nic_trade_experience_ledger.jsonl"
STATE=LIVE/"nic_trade_experience_state.json"
TERMINAL={"WIN","TP1","TP2","LOSS","SL","INVALIDATED"}

def now(): return datetime.now(timezone.utc).isoformat()
def sha256(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()).hexdigest()
def read_json(path,default):
    try: return json.loads(path.read_text(encoding="utf-8"))
    except Exception: return default
def read_jsonl(path):
    if not path.exists(): return []
    out=[]
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            x=json.loads(line)
            if isinstance(x,dict): out.append(x)
        except Exception: pass
    return out
def append(path,row):
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open("a",encoding="utf-8") as f: f.write(json.dumps(row,sort_keys=True,ensure_ascii=False)+"\n")
def records():
    return read_jsonl(LEDGER)
def prediction_id(row):
    for k in ("prediction_id","call_id","trade_id","id"):
        v=str(row.get(k) or "").strip()
        if v:return v
    return ""
def make_prediction_id(row):
    return sha256({"symbol":row.get("symbol"),"side":row.get("side"),
        "created_at":row.get("created_at") or row.get("generated_at"),
        "trigger":(row.get("recommended_setup") or {}).get("trigger"),
        "invalidation":(row.get("recommended_setup") or {}).get("invalidation"),
        "tp1":(row.get("recommended_setup") or {}).get("tp1"),
        "tp2":(row.get("recommended_setup") or {}).get("tp2")})[:24]
def prediction_snapshot(row):
    setup=row.get("recommended_setup") if isinstance(row.get("recommended_setup"),dict) else {}
    return {"symbol":str(row.get("symbol") or "").upper(),"side":str(row.get("side") or "").upper(),
      "created_at":row.get("created_at") or row.get("generated_at") or now(),
      "quality_score":row.get("quality_score"),"calibrated_confidence":row.get("calibrated_confidence"),
      "setup_type":row.get("setup_type") or row.get("setup_family") or "unknown",
      "market_regime":row.get("market_regime") or row.get("regime") or "unknown",
      "timeframe":row.get("timeframe") or "unknown",
      "recommended_setup":{"trigger":setup.get("trigger"),"invalidation":setup.get("invalidation"),
                           "tp1":setup.get("tp1"),"tp2":setup.get("tp2")},
      "walk_forward":row.get("walk_forward") if isinstance(row.get("walk_forward"),dict) else {},
      "latest_completed_candle":row.get("latest_completed_candle") if isinstance(row.get("latest_completed_candle"),dict) else {}}
def outcome_name(row): return str(row.get("outcome") or row.get("result") or "").upper().strip()

def main():
    existing=records()
    prediction_ids={str(x.get("prediction_id")) for x in existing if x.get("record_type")=="PREDICTION_SNAPSHOT"}
    event_ids={str(x.get("event_id")) for x in existing if x.get("record_type")=="OUTCOME_EVENT"}
    doc=read_json(PREDICTION,{})
    candidates=doc.get("candidates") if isinstance(doc.get("candidates"),list) else []
    added_predictions=0
    for row in candidates:
        if not isinstance(row,dict) or str(row.get("status","")).upper()!="PASS": continue
        pid=make_prediction_id(row)
        if pid in prediction_ids: continue
        snap=prediction_snapshot(row)
        append(LEDGER,{"record_type":"PREDICTION_SNAPSHOT","schema_version":"1.1","prediction_id":pid,
            "recorded_at":now(),"prediction":snap,"prediction_hash":sha256(snap),"immutable":True})
        prediction_ids.add(pid); added_predictions+=1

    added_outcomes=0
    for source in OUTCOME_SOURCES:
        for row in read_jsonl(source):
            outcome=outcome_name(row)
            if outcome not in TERMINAL: continue
            pid=prediction_id(row)
            if not pid or pid not in prediction_ids: continue
            event_id=str(row.get("event_id") or row.get("outcome_id") or "").strip()
            if not event_id:
                event_id=sha256({"prediction_id":pid,"outcome":outcome,
                    "evaluated_at":row.get("evaluated_at") or row.get("timestamp") or row.get("created_at")})[:24]
            if event_id in event_ids: continue
            append(LEDGER,{"record_type":"OUTCOME_EVENT","schema_version":"1.1","event_id":event_id,
                "prediction_id":pid,"outcome":outcome,
                "evaluated_at":row.get("evaluated_at") or row.get("timestamp") or row.get("created_at"),
                "evaluator_version":row.get("evaluator_version"),"immutable":True})
            event_ids.add(event_id); added_outcomes+=1

    all_records=records()
    terminal=[x for x in all_records if x.get("record_type")=="OUTCOME_EVENT" and x.get("outcome") in TERMINAL]
    wins=sum(x.get("outcome") in {"WIN","TP1","TP2"} for x in terminal)
    losses=sum(x.get("outcome") in {"LOSS","SL","INVALIDATED"} for x in terminal)
    state={"schema_version":"1.1","updated_at":now(),"new_prediction_snapshots":added_predictions,
      "new_outcome_events":added_outcomes,"prediction_count":len(prediction_ids),
      "terminal_outcome_count":len(terminal),"wins":wins,"losses":losses,
      "prediction_ledger":str(LEDGER.relative_to(ROOT)),
      "policy":["Prediction snapshots are append-only and immutable.",
        "Outcomes are separate immutable events.","Duplicate outcome events are ignored.",
        "Learning may consume outcomes but may not mutate historical prediction snapshots.",
        "Future information cannot be inserted into a historical prediction snapshot."]}
    STATE.write_text(json.dumps(state,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(state,indent=2))
if __name__=="__main__": raise SystemExit(main())
