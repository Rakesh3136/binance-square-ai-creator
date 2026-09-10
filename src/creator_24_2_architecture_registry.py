"""Creator 24.2 — active architecture registry.

The repo may retain historical numbered modules for auditability, but this registry
makes the runtime truth explicit: only modules referenced by the single orchestrator
are ACTIVE. Nothing is deleted automatically because an unreferenced module can
still be useful for historical recovery.
"""
from __future__ import annotations
import json,re
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];WF=ROOT/'.github/workflows/autonomous-market-creator.yml';SRC=ROOT/'src';OUT=ROOT/'data/intelligence/creator_24_2_architecture.json'
def main():
    workflow=WF.read_text(encoding='utf-8') if WF.exists() else ''
    refs=set(re.findall(r'python (?:-m )?src/([A-Za-z0-9_]+\.py)',workflow))
    active=[];legacy=[]
    for p in sorted(SRC.glob('creator_*.py')):
        if p.name in refs:active.append(p.name)
        else:legacy.append(p.name)
    result={'version':'24.2','generated_at':datetime.now(timezone.utc).isoformat(),'orchestrator':'.github/workflows/autonomous-market-creator.yml','active_creator_modules':active,'legacy_or_unreferenced_modules':legacy,'policy':'Do not execute numbered modules merely because they exist. The orchestrator is the runtime authority; legacy modules remain until dependency review proves deletion safe.','counts':{'active':len(active),'legacy':len(legacy)}}
    OUT.parent.mkdir(parents=True,exist_ok=True);OUT.write_text(json.dumps(result,indent=2,ensure_ascii=False),encoding='utf-8');print(json.dumps(result,indent=2,ensure_ascii=False))
if __name__=='__main__':main()
