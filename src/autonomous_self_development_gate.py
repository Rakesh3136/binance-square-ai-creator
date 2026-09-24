"""Guard when the existing self-engineer may run autonomously.

The gate never changes production code. It only decides whether the bounded
self_engineer should be invoked, using reliability/learning evidence and a
cooldown so the creator does not churn code every 20 minutes.
"""
from __future__ import annotations
import json, os
from datetime import datetime, timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
LEARN=ROOT/"data/live/creator_self_training.json"
IMPROVE=ROOT/"data/live/creator_19_0_improvement_board.json"
OUT=ROOT/"data/live/autonomous_self_development_gate.json"
def load(p):
 try:
  x=json.loads(p.read_text(encoding="utf-8")); return x if isinstance(x,dict) else {}
 except Exception:return {}
def main():
 run=int(os.getenv("GITHUB_RUN_NUMBER","0") or 0)
 interval=max(1,int(os.getenv("AUTONOMOUS_ENGINEERING_INTERVAL","12") or 12))
 learn=load(LEARN); board=load(IMPROVE)
 policy=learn.get("policy") if isinstance(learn.get("policy"),dict) else {}
 action=str(board.get("action") or "")
 critical=action in {"FIX_HIGHEST_SEVERITY_SYSTEM_RISK","RE_EVALUATE_DECISIONS_WITH_NEW_EVIDENCE"}
 scheduled=(run>0 and run%interval==0)
 evidence=bool(policy.get("self_development",{}).get("eligible"))
 approved=bool((critical or scheduled) and evidence)
 result={"version":"1.0","generated_at":datetime.now(timezone.utc).isoformat(),"run_number":run,"interval":interval,"scheduled":scheduled,"critical_improvement":critical,"evidence_available":evidence,"run_self_engineer":approved,"reason":"critical evidence or scheduled development window" if approved else "cooldown/no sufficient evidence"}
 OUT.parent.mkdir(parents=True,exist_ok=True);OUT.write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8")
 print(json.dumps(result,indent=2))
if __name__=="__main__":main()
