"""NIC Memory Graph — durable evidence graph for autonomous creator learning.

Keyless: no hosted model or API key. Stores relationships among theses,
content families, experiments, outcomes, market regimes and publication IDs.
It does not infer revenue or causality from missing data.
"""
from __future__ import annotations
import hashlib,json
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
AN=ROOT/"analytics"; LIVE=ROOT/"data/live"; INTEL=ROOT/"data/intelligence"
NIC=LIVE/"nic_core_state.json"; PORT=LIVE/"creator_portfolio_intelligence.json"; FUNNEL=LIVE/"monetization_funnel_optimizer.json"
ATTR=AN/"publication_attribution.jsonl"; OUT=LIVE/"nic_memory_graph.json"; REPORT=INTEL/"nic_memory_graph_report.json"
def load(p,d=None):
    try:
        x=json.loads(p.read_text(encoding="utf-8")) if p.exists() else d
        return x if isinstance(x,type(d)) else d
    except Exception:return d
def rows(p):
    out=[]
    if p.exists():
        for l in p.read_text(encoding="utf-8").splitlines():
            try:
                x=json.loads(l)
                if isinstance(x,dict):out.append(x)
            except Exception:pass
    return out
def sid(x):
    raw=str(x.get("canonical_post_id") or x.get("post_id") or x.get("publication_id") or "").strip()
    return raw.lower()
def main():
    nic=load(NIC,{}) or {}; port=load(PORT,{}) or {}; funnel=load(FUNNEL,{}) or {}; attrs=rows(ATTR)
    nodes=[]; edges=[]; seen=set()
    def node(kind,key,**data):
        nid=f"{kind}:{key}"
        if nid not in seen:
            seen.add(nid);nodes.append({"id":nid,"kind":kind,"key":key,**data})
        return nid
    thesis=str(nic.get("thesis_id") or "").strip()
    if thesis:
        tn=node("thesis",thesis,symbol=nic.get("symbol"),direction=nic.get("direction"),hook_family=nic.get("hook_family"))
    for o in port.get("observations",[])[:100]:
        fam=str(o.get("content_family") or "unknown"); fn=node("content_family",fam,observed_publications=o.get("publications",0),engagement_per_1000_views=o.get("engagement_per_1000_views",0),verified_revenue=o.get("verified_revenue",0))
        if thesis and fn:edges.append({"from":tn,"to":fn,"relation":"NIC_CONSIDERS"})
    for a in attrs[-500:]:
        p=sid(a)
        if not p:continue
        pn=node("publication",p,symbol=a.get("symbol"),category=a.get("category"),content_family=a.get("content_family"),revenue_verified=bool(a.get("revenue_verified")))
        if thesis:edges.append({"from":tn,"to":pn,"relation":"THESIS_PUBLICATION_CONTEXT"})
        if a.get("experiment_id"):
            en=node("experiment",str(a.get("experiment_id")));edges.append({"from":pn,"to":en,"relation":"MEASURED_BY"})
    state={"version":"1.0","generated_at":datetime.now(timezone.utc).isoformat(),"status":"READY","node_count":len(nodes),"edge_count":len(edges),"nodes":nodes,"edges":edges,"principles":["missing evidence stays missing","revenue requires explicit verification","causality is not inferred from correlation","memory informs selection but cannot override safety or publication gates"]}
    LIVE.mkdir(parents=True,exist_ok=True);INTEL.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(state,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    REPORT.write_text(json.dumps({"version":"1.0","status":"READY","node_count":len(nodes),"edge_count":len(edges),"output":str(OUT.relative_to(ROOT))},indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"status":"READY","node_count":len(nodes),"edge_count":len(edges)},ensure_ascii=False))
if __name__=="__main__":main()
