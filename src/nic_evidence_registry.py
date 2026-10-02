"""NIC 20.1 — Evidence Registry.
Normalizes fetched research into durable, traceable evidence records.
Evidence strength is descriptive, never a claim of truth by itself.
"""
from __future__ import annotations
import hashlib,json
from datetime import datetime,timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
INP=ROOT/"data/live/nic_research_raw.json"
OUT=ROOT/"data/live/nic_evidence_registry.json"
REPORT=ROOT/"data/intelligence/nic_evidence_registry_report.json"

def load(p,d):
    try:
        x=json.loads(p.read_text(encoding="utf-8")) if p.exists() else d
        return x if isinstance(x,type(d)) else d
    except Exception:return d

def level(source_type):
    return {"official":"primary","regulator":"primary","exchange":"primary","academic":"primary","news":"secondary","creator":"observation","search":"discovery"}.get(source_type,"unknown")

def main():
    raw=load(INP,{"records":[]})
    records=[]; seen=set()
    for r in raw.get("records",[]):
        if not isinstance(r,dict): continue
        url=str(r.get("url") or "").strip()
        title=str(r.get("title") or "").strip()
        text=str(r.get("text") or "").strip()
        if not url or not (title or text): continue
        h=hashlib.sha256((url+"\n"+title+"\n"+text).encode()).hexdigest()
        if h in seen: continue
        seen.add(h)
        st=str(r.get("source_type") or "unknown")
        records.append({
          "evidence_id":"ev-"+h[:16],"url":url,"title":title[:300],
          "source_type":st,"evidence_class":level(st),
          "retrieved_at":r.get("retrieved_at"),"published_at":r.get("published_at"),
          "text":text[:5000],"content_hash":h,
          "supports":list(r.get("supports") or []),"limitations":list(r.get("limitations") or [])
        })
    out={"version":"20.1","status":"READY","generated_at":datetime.now(timezone.utc).isoformat(),
         "count":len(records),"records":records,
         "policy":["primary evidence outranks secondary context","creator material is pattern observation, not authority","discovery snippets are not sufficient for factual publication","missing evidence remains UNKNOWN"]}
    OUT.parent.mkdir(parents=True,exist_ok=True); REPORT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(out,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    REPORT.write_text(json.dumps({"version":"20.1","status":"READY","count":len(records),"primary":sum(x["evidence_class"]=="primary" for x in records),"secondary":sum(x["evidence_class"]=="secondary" for x in records),"creator_observation":sum(x["evidence_class"]=="observation" for x in records)},indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"status":"READY","evidence_count":len(records)},ensure_ascii=False))
if __name__=="__main__":main()
