"""Durable stage tracker for one autonomous Binance Square production run."""
from __future__ import annotations
import json,re,sys
from datetime import datetime,timezone
from pathlib import Path
OUT=Path("data/live/pipeline_status.json")
STAGES=["creator_benchmark","intelligence","scan","select","creator_brain","ai_draft","visual","visual_symbol","visual_content","quality_gate","publish","verify","record","learn","complete","finalize"]
def now(): return datetime.now(timezone.utc).isoformat()
def load():
    if not OUT.exists(): return {"run_started_at":now(),"stages":{}}
    try:
        d=json.loads(OUT.read_text(encoding="utf-8")); return d if isinstance(d,dict) else {"run_started_at":now(),"stages":{}}
    except Exception: return {"run_started_at":now(),"stages":{}}
def save(d): OUT.parent.mkdir(parents=True,exist_ok=True); OUT.write_text(json.dumps(d,indent=2,ensure_ascii=False),encoding="utf-8")
def reset_run(reason="New autonomous production cycle"):
    d={"run_started_at":now(),"last_updated_at":now(),"current_stage":"start","last_successful_stage":None,"blocked_at":None,"stages":{},"reason":reason}; save(d); print(json.dumps(d,indent=2)); return d
def set_stage(stage,status,reason="",**details):
    if stage not in STAGES: raise SystemExit(f"Unknown pipeline stage: {stage}")
    d=load(); d.setdefault("stages",{}); d["last_updated_at"]=now(); d["current_stage"]=stage; d["stages"][stage]={"status":status,"updated_at":now(),"reason":reason,**details}
    if status=="success": d["last_successful_stage"]=stage
    if status in {"failed","blocked"}: d["blocked_at"]=stage
    if stage=="finalize": d["run_finished_at"]=now()
    save(d); print(json.dumps(d,indent=2,ensure_ascii=False)); return d
def verify_publish():
    p=Path("/tmp/publish-result.txt")
    if not p.exists(): set_stage("verify","failed","publish result file missing"); return 1
    result=p.read_text(encoding="utf-8",errors="replace"); post_id=re.search(r"ID:\s*(\S+)",result); link=next((x.split("Link:",1)[1].strip() for x in result.splitlines() if x.startswith("Link:")),None)
    if not post_id or not link: set_stage("verify","failed","publisher did not return a Binance post ID and link",result_tail=result[-1200:]); return 1
    set_stage("verify","success","Binance publisher returned post ID and link",post_id=post_id.group(1),link=link); return 0
def main():
    if len(sys.argv)>=2 and sys.argv[1]=="reset": reset_run(" ".join(sys.argv[2:]) or "New autonomous production cycle"); return 0
    if len(sys.argv)>=2 and sys.argv[1]=="verify-publish": return verify_publish()
    if len(sys.argv)<3: raise SystemExit("usage: pipeline_stage.py <stage> <status> [reason] | reset [reason]")
    set_stage(sys.argv[1],sys.argv[2]," ".join(sys.argv[3:]) if len(sys.argv)>3 else ""); return 0
if __name__=="__main__": raise SystemExit(main())
