"""NIC 20 — Capability gap analyzer."""
from __future__ import annotations
import json
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; ROLE=ROOT/"data/live/nic_role_contract.json"; OUT=ROOT/"data/live/nic_capability_gap.json"
def main():
 r=json.loads(ROLE.read_text(encoding="utf-8")) if ROLE.exists() else {}; caps=r.get("capabilities",[])
 # A capability is considered available only when a matching implementation/evidence artifact exists.
 src=ROOT/"src"; existing=[]
 for c in caps:
  stem=c.replace("-","_").replace(" ","_")
  if any(p.stem.lower().find(stem.lower())>=0 for p in src.glob("*.py")): existing.append(c)
 gaps=[c for c in caps if c not in existing]
 out={"version":"20.0","generated_at":datetime.now(timezone.utc).isoformat(),"status":"READY","role":r.get("role"),"available_capabilities":existing,"capability_gaps":gaps,"policy":"gaps become research/engineering objectives; they do not justify invented capability"}
 OUT.parent.mkdir(parents=True,exist_ok=True);OUT.write_text(json.dumps(out,indent=2,ensure_ascii=False)+"\n",encoding="utf-8");print(json.dumps({"status":"READY","gaps":len(gaps)},ensure_ascii=False))
if __name__=="__main__":main()
