"""Creator Portfolio Intelligence — evidence-based content allocation.

Ranks content families by observed evidence across market regimes. It never
predicts revenue and never overrides publication/evidence gates.
"""
from __future__ import annotations
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
AN=ROOT/"analytics"; LIVE=ROOT/"data/live"; INTEL=ROOT/"data/intelligence"
PERF=AN/"square_performance.jsonl"; ATTR=AN/"publication_attribution.jsonl"
REG=LIVE/"market_regime_intelligence.json"; OUT=LIVE/"creator_portfolio_intelligence.json"; REPORT=INTEL/"creator_portfolio_intelligence_report.json"

def rows(p):
    out=[]
    if p.exists():
        for line in p.read_text(encoding="utf-8").splitlines():
            try:
                x=json.loads(line)
                if isinstance(x,dict):out.append(x)
            except Exception: pass
    return out

def load(p,default=None):
    try:
        x=json.loads(p.read_text(encoding="utf-8")) if p.exists() else default
        return x if isinstance(x,dict) else default
    except Exception:return default

def num(x,*keys):
    for k in keys:
        try:return float(x.get(k))
        except Exception:pass
    return 0.0

def main():
    perf=rows(PERF); attrs=rows(ATTR); regime=load(REG,{}) or {}
    amap={str(a.get("canonical_post_id") or a.get("post_id") or "").strip():a for a in attrs}
    groups=defaultdict(lambda:{"posts":0,"views":0.0,"engagement":0.0,"verified_revenue":0.0})
    for p in perf:
        pid=str(p.get("canonical_post_id") or p.get("post_id") or "").strip()
        a=amap.get(pid,{})
        family=str(a.get("content_family") or a.get("category") or p.get("category") or "unknown")
        g=groups[family]; g["posts"]+=1; g["views"]+=num(p,"views","view_count","reach","impressions")
        g["engagement"]+=num(p,"likes","like_count")+2*num(p,"comments","replies")+3*num(p,"shares","share_count")
        if a.get("revenue_verified") is True:g["verified_revenue"]+=max(0,num(a,"revenue_amount","verified_revenue_amount","earnings_amount"))
    observed=[]
    for family,g in groups.items():
        observed.append({"content_family":family,"publications":g["posts"],"views":round(g["views"],2),"engagement_per_1000_views":round(g["engagement"]/max(g["views"],1)*1000,4),"verified_revenue":round(g["verified_revenue"],8),"evidence":"OBSERVATIONAL_ONLY"})
    observed.sort(key=lambda x:(x["verified_revenue"],x["engagement_per_1000_views"],x["publications"]),reverse=True)
    plan={"version":"1.0","generated_at":datetime.now(timezone.utc).isoformat(),"status":"READY","objective":"allocate research and experimentation attention using observed evidence, not predicted earnings","current_regime":regime.get("regime") or regime.get("label") or "UNKNOWN","observations":observed[:100],"allocation_rules":{"never_force_publish":True,"verified_revenue_over_views":True,"exploration_preserved":True,"minimum_observations":3,"no_revenue_prediction":True},"next_actions":["repeat families with sufficient evidence only when a fresh eligible opportunity exists","reserve controlled exploration for under-observed families","compare families across regimes before changing long-term allocation","feed observed results into NIC and self-training"]}
    LIVE.mkdir(parents=True,exist_ok=True);INTEL.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(plan,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    REPORT.write_text(json.dumps({"version":"1.0","status":"READY","observed_families":len(observed),"output":str(OUT.relative_to(ROOT))},indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"status":"READY","observed_families":len(observed),"regime":plan["current_regime"]},ensure_ascii=False))
if __name__=="__main__":main()
