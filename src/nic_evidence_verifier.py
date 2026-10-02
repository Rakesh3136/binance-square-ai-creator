"""NIC 20.2 evidence retrieval/verification layer."""
from __future__ import annotations
import json,re
from datetime import datetime,timezone,timedelta
from pathlib import Path
from urllib.request import Request,urlopen
from urllib.parse import urlparse
ROOT=Path(__file__).resolve().parents[1]; LIVE=ROOT/"data/live"; INTEL=ROOT/"data/intelligence"
RAW=LIVE/"nic_research_raw.json"; OUT=LIVE/"nic_verified_evidence.json"; REPORT=INTEL/"nic_evidence_verification_report.json"
def classify(url):
 h=urlparse(url).netloc.lower()
 if h.endswith("binance.com") or h.endswith(".gov") or h.endswith(".edu"): return "primary"
 if any(x in h for x in ("reuters.com","apnews.com","bloomberg.com","coindesk.com","theblock.co")): return "secondary"
 return "discovery"
def main():
 raw=json.loads(RAW.read_text()) if RAW.exists() else {}; now=datetime.now(timezone.utc); rows=[]
 for x in raw.get("records",[])[:40]:
  url=x.get("url"); row={"url":url,"title":x.get("title"),"source_class":"discovery","retrieval_status":"NOT_ATTEMPTED","freshness":"UNKNOWN"}
  if not url: row["retrieval_status"]="FAILED"; row["error"]="missing URL"; rows.append(row); continue
  try:
   req=Request(url,headers={"User-Agent":"NIC-EvidenceVerifier/20.2"})
   with urlopen(req,timeout=15) as r: body=r.read(300000).decode("utf-8","ignore"); final=r.geturl()
   row.update({"final_url":final,"source_class":classify(final),"retrieval_status":"RETRIEVED"})
   m=re.search(r'(?:article:published_time|date|pubdate)[^>]+content=["\']([^"\']+)',body,re.I)
   if m:
    try:
     dt=datetime.fromisoformat(m.group(1).replace("Z","+00:00")); row["published_at"]=dt.isoformat(); row["freshness"]="FRESH" if now-dt<=timedelta(days=90) else "STALE"
    except ValueError: row["freshness"]="UNKNOWN"
  except Exception as e: row.update({"retrieval_status":"FAILED","error":type(e).__name__+": "+str(e)[:250]})
  rows.append(row)
 out={"version":"20.2","status":"READY","generated_at":now.isoformat(),"count":len(rows),"records":rows,"policy":["retrieval is not proof of truth","unknown remains unknown","discovery is not publication-grade evidence"]}
 LIVE.mkdir(exist_ok=True); INTEL.mkdir(exist_ok=True); OUT.write_text(json.dumps(out,indent=2)+"\n"); REPORT.write_text(json.dumps({"version":"20.2","status":"READY","count":len(rows),"retrieved":sum(r["retrieval_status"]=="RETRIEVED" for r in rows),"primary":sum(r["source_class"]=="primary" and r["retrieval_status"]=="RETRIEVED" for r in rows),"fresh":sum(r["freshness"]=="FRESH" for r in rows)},indent=2)+"\n"); print(json.dumps({"status":"READY","count":len(rows)}))
if __name__=="__main__": main()
