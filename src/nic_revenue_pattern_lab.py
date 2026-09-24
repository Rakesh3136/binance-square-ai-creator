"""NIC Revenue Pattern Lab — evidence-first Write-to-Earn experiment planner.

It compares verified monetization observations with publication metadata and
creates bounded next experiments. It never invents attribution or revenue.
"""
from __future__ import annotations
import json
from collections import defaultdict
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; AN=ROOT/"analytics"; LIVE=ROOT/"data/live"; INTEL=ROOT/"data/intelligence"
ATTR=AN/"publication_attribution.jsonl"; PERF=AN/"square_performance.jsonl"; OUT=LIVE/"nic_revenue_pattern_lab.json"; REPORT=INTEL/"nic_revenue_pattern_lab_report.json"
def rows(p):
    out=[]
    if p.exists():
        for line in p.read_text(encoding="utf-8").splitlines():
            try:
                x=json.loads(line)
                if isinstance(x,dict):out.append(x)
            except Exception: pass
    return out
def pid(x): return str(x.get("canonical_post_id") or x.get("post_id") or x.get("publication_id") or "").strip().lower()
def num(x,*ks):
    for k in ks:
        try:return float(x.get(k,0) or 0)
        except Exception:pass
    return 0.0
def main():
    attrs={pid(x):x for x in rows(ATTR) if pid(x)}; perf={pid(x):x for x in rows(PERF) if pid(x)}
    groups=defaultdict(lambda:{"posts":0,"views":0.0,"engagement":0.0,"verified_revenue":0.0,"verified_posts":0})
    for p,a in attrs.items():
        k=(str(a.get("category") or "unknown"),str(a.get("format") or "unknown"),str(a.get("content_family") or "unknown"))
        g=groups[k]; g["posts"]+=1; r=perf.get(p,{})
        g["views"]+=num(r,"views","view_count","impressions"); g["engagement"]+=num(r,"likes","like_count")+2*num(r,"comments","reply_count")+3*num(r,"shares","share_count")
        if a.get("revenue_verified") is True:
            g["verified_posts"]+=1; g["verified_revenue"]+=max(0,num(a,"revenue_amount","verified_revenue_amount","earnings_amount"))
    observations=[]
    for (cat,fmt,fam),g in groups.items():
        observations.append({"category":cat,"format":fmt,"content_family":fam,"posts":g["posts"],"views":round(g["views"],2),"engagement_per_1000_views":round(g["engagement"]*1000/max(g["views"],1),4),"verified_posts":g["verified_posts"],"verified_revenue":round(g["verified_revenue"],8),"evidence":"OBSERVED_ONLY"})
    verified=[x for x in observations if x["verified_posts"]>0]
    plan=[]
    for x in sorted(observations,key=lambda z:(z["verified_revenue"],z["engagement_per_1000_views"]),reverse=True)[:8]:
        plan.append({"test_family":x["content_family"],"format":x["format"],"hypothesis":"repeat only if fresh evidence supports the same content family","sample_rule":"minimum 3 comparable observations before changing policy","guardrail":"never infer revenue or causality from views alone"})
    state={"version":"1.0","generated_at":datetime.now(timezone.utc).isoformat(),"status":"READY","verified_observation_groups":len(verified),"observations":observations[:100],"next_experiments":plan,"verified_revenue_only":True,"unattributed_rewards_must_remain_unattributed":True}
    LIVE.mkdir(parents=True,exist_ok=True);INTEL.mkdir(parents=True,exist_ok=True);OUT.write_text(json.dumps(state,indent=2)+"\n",encoding="utf-8");REPORT.write_text(json.dumps({"status":"READY","verified_groups":len(verified),"output":str(OUT.relative_to(ROOT))},indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"status":"READY","verified_groups":len(verified),"observations":len(observations)}))
if __name__=="__main__":main()
