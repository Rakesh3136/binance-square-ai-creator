"""Keyless NIC Opportunity Genome.
Builds evidence-backed feature combinations from historical publication/outcome data.
No external model, no invented causality or revenue. Learns patterns only after repeats.
"""
from __future__ import annotations
import json, hashlib
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; AN=ROOT/"analytics"; LIVE=ROOT/"data/live"; INTEL=ROOT/"data/intelligence"
ATTR=AN/"publication_attribution.jsonl"; PERF=AN/"square_performance.jsonl"; OUT=LIVE/"nic_opportunity_genome.json"; REPORT=INTEL/"nic_opportunity_genome_report.json"
def rows(p):
 o=[]
 if p.exists():
  for l in p.read_text(encoding="utf-8").splitlines():
   try:
    x=json.loads(l)
    if isinstance(x,dict): o.append(x)
   except Exception: pass
 return o
def pid(x): return str(x.get("canonical_post_id") or x.get("post_id") or x.get("publication_id") or "").strip().lower()
def main():
 attrs={pid(x):x for x in rows(ATTR) if pid(x)}; perf={pid(x):x for x in rows(PERF) if pid(x)}; g=defaultdict(lambda:{"n":0,"views":0.0,"eng":0.0,"rev":0.0,"verified":0})
 for p,a in attrs.items():
  r=perf.get(p,{})
  regime=str(a.get("market_regime") or a.get("regime") or "unknown"); cat=str(a.get("category") or "unknown"); fmt=str(a.get("format") or "unknown"); fam=str(a.get("content_family") or "unknown"); hook=str(a.get("hook_family") or a.get("hook_type") or "unknown"); widget=str(bool(a.get("trading_widget") or a.get("widget_present") or a.get("cashtag_present")))
  k=(regime,cat,fmt,fam,hook,widget); z=g[k]; z["n"]+=1
  def num(*ks):
   for k2 in ks:
    try:return float(r.get(k2,0) or 0)
    except Exception: pass
   return 0.0
  z["views"]+=num("views","view_count","impressions"); z["eng"]+=num("likes","like_count")+2*num("comments","reply_count")+3*num("shares","share_count")
  if a.get("revenue_verified") is True: z["verified"]+=1; z["rev"]+=num("revenue_amount","verified_revenue_amount","earnings_amount")
 observations=[]
 for k,z in g.items():
  observations.append({"regime":k[0],"category":k[1],"format":k[2],"content_family":k[3],"hook_family":k[4],"monetization_surface":k[5],"observations":z["n"],"views":round(z["views"],2),"engagement_per_1000":round(z["eng"]*1000/max(z["views"],1),4),"verified_revenue_posts":z["verified"],"verified_revenue":round(z["rev"],8),"evidence":"observational"})
 repeat=[x for x in observations if x["observations"]>=3]; verified=[x for x in repeat if x["verified_revenue_posts"]>0]
 experiments=[]
 for x in sorted(repeat,key=lambda q:(q["verified_revenue"],q["engagement_per_1000"]),reverse=True)[:10]:
  key="|".join(str(x[k]) for k in ("regime","category","format","content_family","hook_family","monetization_surface")); experiments.append({"genome_id":hashlib.sha256(key.encode()).hexdigest()[:12],"features":{k:x[k] for k in ("regime","category","format","content_family","hook_family","monetization_surface")},"observations":x["observations"],"verified_revenue":x["verified_revenue"],"action":"TEST_AGAIN_ONLY_WITH_FRESH_EVIDENCE"})
 state={"version":"1.0","generated_at":datetime.now(timezone.utc).isoformat(),"status":"READY","observations":observations[:200],"repeatable_patterns":repeat[:50],"verified_patterns":verified[:50],"next_experiments":experiments,"policy":["No causal claim from observational data.","Minimum 3 comparable observations before policy change.","Verified revenue is separate from engagement.","Genome informs experiments; signal and safety gates remain authoritative."]}
 LIVE.mkdir(parents=True,exist_ok=True); INTEL.mkdir(parents=True,exist_ok=True); OUT.write_text(json.dumps(state,indent=2)+chr(10)); REPORT.write_text(json.dumps({"status":"READY","repeatable_patterns":len(repeat),"verified_patterns":len(verified),"output":str(OUT.relative_to(ROOT))},indent=2)+chr(10)); print(json.dumps({"status":"READY","observations":len(observations),"repeatable_patterns":len(repeat),"verified_patterns":len(verified)}))
if __name__=="__main__": main()
