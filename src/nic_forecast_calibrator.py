"""NIC forecast calibration joined to immutable snapshots and terminal outcome events."""
from __future__ import annotations
import json, math
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
LEDGER=ROOT/"data/intelligence/nic_forecast_truth_ledger.jsonl"
EVENTS=ROOT/"data/intelligence/nic_forecast_outcome_events.jsonl"
OUT=ROOT/"data/intelligence/nic_forecast_calibration.json"
H=(6,12,24); MIN=30

def read_jsonl(path):
    if not path.exists(): return []
    rows=[]
    for number,line in enumerate(path.read_text(encoding="utf-8").splitlines(),1):
        if not line.strip(): continue
        try: row=json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid JSONL in {path.name}:{number}") from exc
        if not isinstance(row,dict): raise ValueError(f"non-object JSONL row in {path.name}:{number}")
        rows.append(row)
    return rows

def read():
    """Join forecast snapshots to terminal outcomes by exact forecast_id; never infer missing labels."""
    snapshots=read_jsonl(LEDGER)
    events=read_jsonl(EVENTS)
    terminal={}
    for event in events:
        if event.get("event_type")!="FORECAST_RESOLVED": continue
        fid=str(event.get("forecast_id") or "").strip()
        if not fid: continue
        prior=terminal.get(fid)
        if prior is not None:
            comparable=("signed_return","hit","outcome_price","horizon_hours","symbol","side")
            if any(prior.get(k)!=event.get(k) for k in comparable):
                raise ValueError(f"conflicting terminal outcomes for forecast_id={fid}")
            continue
        terminal[fid]=event
    by_snapshot={}
    for snapshot in snapshots:
        fid=str(snapshot.get("forecast_id") or "").strip()
        if not fid: continue
        if fid in by_snapshot and by_snapshot[fid] != snapshot:
            raise ValueError(f"conflicting immutable snapshots for forecast_id={fid}")
        by_snapshot[fid]=snapshot
    joined=[]
    for fid,snapshot in by_snapshot.items():
        horizon=int(snapshot.get("horizon_hours") or 0)
        if horizon not in H: continue
        event=terminal.get(fid)
        if event is not None:
            if str(event.get("symbol") or "").upper() != str(snapshot.get("symbol") or "").upper():
                raise ValueError(f"symbol mismatch for forecast_id={fid}")
            if str(event.get("side") or "").upper() != str(snapshot.get("side") or "").upper():
                raise ValueError(f"side mismatch for forecast_id={fid}")
            try: signed=float(event["signed_return"])
            except (KeyError,TypeError,ValueError) as exc:
                raise ValueError(f"terminal outcome missing signed_return for forecast_id={fid}") from exc
            if not math.isfinite(signed): raise ValueError(f"invalid signed_return for forecast_id={fid}")
            row=dict(snapshot); row["resolved"]=True; row["signed_return"]=signed
            row["hit"]=bool(event.get("hit")) if isinstance(event.get("hit"),bool) else signed>0
            row["outcome_source"]="terminal_event"
            joined.append(row)
        elif snapshot.get("resolved") is True and isinstance(snapshot.get("hit"),bool) and snapshot.get("signed_return") is not None:
            row=dict(snapshot); row["outcome_source"]="legacy_snapshot"; joined.append(row)
    return joined

def clamp(v): return max(0.0,min(1.0,float(v)))
def metrics(rows):
    scored=[]
    for row in rows:
        p=row.get("forecast_probability")
        hit=row.get("hit")
        if p is None or not isinstance(hit,bool): continue
        try: probability=clamp(p)
        except (TypeError,ValueError): continue
        if not math.isfinite(probability): continue
        scored.append((probability,1.0 if hit else 0.0))
    if not scored: return {"samples":0,"brier_score":None,"log_loss":None,"coverage":0.0}
    bs=ll=0.0
    for p,y in scored:
        bs+=(p-y)**2
        ll -= math.log(max(1e-6,p) if y else max(1e-6,1.0-p))
    return {"samples":len(scored),"brier_score":round(bs/len(scored),6),
            "log_loss":round(ll/len(scored),6),"coverage":round(len(scored)/len(rows),4)}

def calibrate(rows=None):
    rows=read() if rows is None else rows
    groups={}
    for row in rows:
        try: horizon=int(row.get("horizon_hours") or 0); signed=float(row.get("signed_return"))
        except (TypeError,ValueError): continue
        if horizon not in H or not math.isfinite(signed): continue
        side=str(row.get("side") or "").upper(); reg=str(row.get("regime") or "UNKNOWN")
        groups.setdefault((side,reg,horizon),[]).append(signed)
    cells={}
    for (side,reg,horizon),values in groups.items():
        wins=sum(value>0 for value in values); count=len(values)
        raw=(wins+1)/(count+2); confidence=min(1.0,count/MIN)
        probability=.5+(raw-.5)*confidence
        cells[f"{side}|{reg}|{horizon}h"]={"side":side,"regime":reg,"horizon_hours":horizon,
            "samples":count,"wins":wins,"raw_rate":round(wins/count,4),
            "calibrated_probability":round(probability,4),"confidence":round(confidence,4),
            "trusted":count>=MIN}
    return cells

def reliability(rows):
    bins={}
    for row in rows:
        p=row.get("forecast_probability"); hit=row.get("hit")
        if p is None or not isinstance(hit,bool): continue
        try: probability=clamp(p)
        except (TypeError,ValueError): continue
        bucket=min(9,int(probability*10)); key=str(bucket)
        item=bins.setdefault(key,{"count":0,"probability_sum":0.0,"outcome_sum":0})
        item["count"]+=1; item["probability_sum"]+=probability; item["outcome_sum"]+=1 if hit else 0
    return {key:{"samples":value["count"],"mean_predicted":round(value["probability_sum"]/value["count"],4),
        "observed_rate":round(value["outcome_sum"]/value["count"],4)} for key,value in bins.items()}

def main():
    rows=read(); cells=calibrate(rows)
    payload={"schema":"NIC-FORECAST-CALIBRATION-3.0",
        "generated_at":__import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
        "minimum_events":MIN,"cells":cells,"global_metrics":metrics(rows),
        "reliability_bins":reliability(rows),
        "evidence":{"joined_resolved_snapshots":len(rows),
            "terminal_event_rows":sum(1 for row in rows if row.get("outcome_source")=="terminal_event"),
            "legacy_resolved_snapshots":sum(1 for row in rows if row.get("outcome_source")=="legacy_snapshot"),
            "unresolved_snapshots_excluded":True},
        "policy":"Calibration joins immutable forecast snapshots to unique terminal outcome events by exact forecast_id. Missing labels are excluded, conflicting duplicate outcomes fail closed, and unresolved forecasts are never scored."}
    OUT.parent.mkdir(parents=True,exist_ok=True); OUT.write_text(json.dumps(payload,indent=2)+"\n",encoding="utf-8")
    return payload
if __name__=="__main__": print(json.dumps({"cells":len(main()["cells"])}))
