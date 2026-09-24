"""Creator Series Engine — turns verified stories into accountable multi-post arcs.

It plans continuity; it does not force publication. Every episode must be backed
by the appropriate fresh evidence and the existing publication gates.
"""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
AN=ROOT/"analytics"; LIVE=ROOT/"data/live"; INTEL=ROOT/"data/intelligence"
ATTR=AN/"publication_attribution.jsonl"; OUTCOMES=AN/"creator_7_2_outcomes.jsonl"
FROZEN=LIVE/"authoritative_opportunity.json"; CONTEXT=LIVE/"publication_context.json"
OUT=LIVE/"creator_series_plan.json"; REPORT=INTEL/"creator_series_report.json"

def jl(p):
    rows=[]
    if p.exists():
        for l in p.read_text(encoding="utf-8").splitlines():
            try:
                x=json.loads(l)
                if isinstance(x,dict):rows.append(x)
            except:pass
    return rows
def j(p):
    try:
        x=json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
        return x if isinstance(x,dict) else {}
    except:return {}
def pid(x):
    s=str(x.get("canonical_post_id") or x.get("post_id") or "").strip().rstrip("/")
    if "/square/post/" in s:s=s.split("/square/post/",1)[1].split("?",1)[0]
    return s.lower()

def main():
    attrs=jl(ATTR); outs=jl(OUTCOMES); frozen=j(FROZEN); ctx=j(CONTEXT)
    histories={}
    for a in attrs:
        p=pid(a)
        if not p:continue
        sym=str(a.get("symbol") or "").upper().replace("USDT","").replace("$","")
        if not sym:continue
        histories.setdefault(sym,[]).append({
          "post_id":p,"category":a.get("category"),"format":a.get("format"),
          "published_at":a.get("published_at"),"experiment_id":a.get("experiment_id")
        })
    symbol=str(frozen.get("symbol") or ctx.get("symbol") or "").upper().replace("USDT","").replace("$","")
    prior=histories.get(symbol,[])
    direction=str(frozen.get("direction") or "").upper()
    active=[]
    if symbol and direction:
        active=[{
          "series_id":f"{symbol}-{datetime.now(timezone.utc).strftime('%Y%m%d')}-{direction}",
          "symbol":symbol,"thesis_direction":direction,
          "episodes":[
            {"episode":1,"type":"SETUP","condition":"fresh verified setup","required_evidence":["trigger","tp1","tp2","sl"]},
            {"episode":2,"type":"CONFIRMATION","condition":"only if fresh evidence changes or confirms the thesis","required_evidence":["new market evidence"]},
            {"episode":3,"type":"OUTCOME","condition":"only after the defined outcome window closes","required_evidence":["timestamped outcome"]},
            {"episode":4,"type":"LESSON","condition":"only if outcome is verified","required_evidence":["outcome","what_changed"]},
            {"episode":5,"type":"NEXT_TEST","condition":"only if a new eligible opportunity exists","required_evidence":["new opportunity contract"]}
          ],
          "publication_policy":"Episodes are opportunities, not obligations. Never publish a follow-up solely to continue a series.",
          "prior_series_posts":prior[-10:],
          "accountability_policy":"Never rewrite history; preserve original call, timestamp and outcome."
        }]
    plan={
      "version":"1.0","generated_at":datetime.now(timezone.utc).isoformat(),
      "status":"READY" if active else "NO_ACTIVE_SERIES",
      "active_series":active,
      "templates":[
        "3-Minute Market Radar","Breakout or Fakeout?","Yesterday's Call: Result","One Chart, One Lesson"
      ],
      "rules":{
        "no_forced_followup":True,
        "outcome_must_be_timestamped":True,
        "prediction_lineage_immutable":True,
        "series_does_not_override_signal_first":True,
        "series_does_not_override_editorial_quality":True
      }
    }
    LIVE.mkdir(parents=True,exist_ok=True);INTEL.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(plan,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    REPORT.write_text(json.dumps({"version":"1.0","status":plan["status"],"active_series":len(active),"output":str(OUT.relative_to(ROOT))},indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"status":plan["status"],"active_series":len(active),"symbol":symbol},ensure_ascii=False))
if __name__=="__main__":main()
