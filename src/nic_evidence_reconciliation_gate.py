"""Fail-closed reconciliation gate for NIC forecast evidence."""
from __future__ import annotations
import hashlib, json
from pathlib import Path

def rows(path):
    if not path.exists(): return []
    result=[]
    for n,line in enumerate(path.read_text(encoding="utf-8").splitlines(),1):
        try: value=json.loads(line)
        except json.JSONDecodeError as exc: raise AssertionError(f"{path.name}:{n}: malformed JSONL") from exc
        if not isinstance(value,dict): raise AssertionError(f"{path.name}:{n}: row is not an object")
        result.append(value)
    return result

def obj(path):
    if not path.exists(): raise AssertionError(f"Missing artifact: {path}")
    value=json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value,dict): raise AssertionError(f"{path.name}: expected object")
    return value

def sha(path): return hashlib.sha256(path.read_bytes() if path.exists() else b"").hexdigest()

def validate(root):
    d=root/"data/intelligence"; sp=d/"nic_forecast_truth_ledger.jsonl"; ep=d/"nic_forecast_outcome_events.jsonl"
    snaps=rows(sp); events=rows(ep); lab=obj(d/"nic_forecast_laboratory_report.json")
    portfolio=obj(d/"nic_portfolio_reality.json"); profit=obj(d/"nic_forecast_profitability.json")
    ids=[str(x.get("forecast_id") or "") for x in snaps]
    if any(not x for x in ids) or len(ids)!=len(set(ids)): raise AssertionError("Missing or duplicate snapshot forecast IDs")
    terminal=[x for x in events if x.get("event_type")=="FORECAST_RESOLVED"]
    tids=[str(x.get("forecast_id") or "") for x in terminal]
    if any(not x for x in tids) or len(tids)!=len(set(tids)): raise AssertionError("Missing or duplicate terminal outcome IDs")
    if set(tids)-set(ids): raise AssertionError("Terminal outcome has no immutable snapshot")
    if int(lab.get("appended_snapshots") or 0)>0 and not snaps: raise AssertionError("Laboratory reports appended snapshots but truth ledger is empty")
    sh,eh=sha(sp),sha(ep)
    pe=portfolio.get("source_evidence") or {}; pf=portfolio.get("source_file_evidence") or {}
    if pf.get("snapshot_ledger_sha256")!=sh or pf.get("outcome_ledger_sha256")!=eh: raise AssertionError("Portfolio Reality source file hash mismatch")
    if pe.get("snapshot_count")!=len(snaps) or pe.get("terminal_outcome_count")!=len(terminal): raise AssertionError("Portfolio Reality counts disagree with ledgers")
    if portfolio.get("status")!="NOT_PROVEN" or portfolio.get("trade_or_publication_authorization") is not False: raise AssertionError("Portfolio must remain non-authorizing and NOT_PROVEN")
    source=profit.get("source_evidence")
    if not isinstance(source,dict): raise AssertionError("Profitability report missing source provenance")
    if source.get("snapshot_ledger_sha256")!=sh or source.get("outcome_ledger_sha256")!=eh: raise AssertionError("Profitability source hash mismatch")
    if source.get("snapshot_count")!=len(snaps) or source.get("terminal_outcome_count")!=len(terminal): raise AssertionError("Profitability counts disagree with ledgers")
    if profit.get("status")!="NOT_PROVEN" or profit.get("publication_or_trade_authorization") is not False: raise AssertionError("Profitability must remain non-authorizing and NOT_PROVEN")
    if not snaps and (int(profit.get("resolved_forecast_count") or 0) or int(profit.get("sample_count") or 0)): raise AssertionError("Profitability claims samples with empty truth ledger")
    return {"status":"PASS","snapshots":len(snaps),"terminal_outcomes":len(terminal),"trade_or_publication_authorization":False}

if __name__=="__main__":
    print(json.dumps(validate(Path(__file__).resolve().parents[1]),sort_keys=True))
