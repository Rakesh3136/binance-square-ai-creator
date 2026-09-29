"""NIC Story Discovery 5.1 — hard provenance gate before publication."""
from __future__ import annotations
import json, os
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
PREFLIGHT=ROOT/"data/live/editorial_preflight.json"
DISCOVERY=ROOT/"data/live/nic_story_discovery.json"
DRAFT=Path(os.getenv("DRAFT_PATH", ""))
OUT=ROOT/"data/live/nic_story_provenance_gate.json"

def load(p):
    try:
        x=json.loads(p.read_text(encoding="utf-8")); return x if isinstance(x,dict) else {}
    except Exception: return {}

def main():
    p=load(PREFLIGHT); d=load(DISCOVERY); draft=load(DRAFT) if DRAFT and DRAFT.exists() else {}
    ctx=load(ROOT/"data/live/publication_context.json")
    sym=str(ctx.get("symbol") or p.get("selected_opportunity",{}).get("symbol") or "").upper().replace("USDT","").replace("$","")
    reasons=[]
    if d.get("version") not in {"5.0","5.1"} or d.get("status") != "DISCOVERED": reasons.append("DISCOVERY_NOT_FRESH")
    if not d.get("selected_lane"): reasons.append("DISCOVERY_LANE_MISSING")
    if d.get("asset") and sym and str(d.get("asset")).upper()!=sym: reasons.append("DISCOVERY_ASSET_MISMATCH")
    cg=p.get("candidate_generation_4") or {}
    if str(cg.get("story_discovery_version")) not in {"5.0","5.1"}: reasons.append("CANDIDATE_GENERATION_NOT_DISCOVERY_BOUND")
    if not cg.get("story_discovery"): reasons.append("CANDIDATE_DISCOVERY_PAYLOAD_MISSING")
    if cg.get("story_discovery",{}).get("selected_lane") != d.get("selected_lane"): reasons.append("DISCOVERY_SELECTION_DRIFT")
    if draft and draft.get("draft",{}).get("story_discovery_version") not in {None,"5.0","5.1"}: reasons.append("DRAFT_DISCOVERY_VERSION_INVALID")
    result={"version":"5.1","status":"PASS" if not reasons else "BLOCK","asset":sym,"selected_lane":d.get("selected_lane"),"story_kind":d.get("story_kind"),"evidence_count":d.get("evidence_count",0),"reasons":reasons,"rules":{"discovery_required":True,"asset_lineage_required":True,"candidate_generation_bound":True,"no_stale_discovery":True}}
    OUT.parent.mkdir(parents=True,exist_ok=True); OUT.write_text(json.dumps(result,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    print(json.dumps(result,indent=2))
    if reasons: raise SystemExit("NIC Story Provenance Gate BLOCKED: "+", ".join(reasons))
if __name__=="__main__": main()
