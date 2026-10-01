"""NIC Creative Compiler 13.0 — multi-candidate diversity compiler.

Compiles the five generated candidates into a structurally and semantically
diverse shortlist, preferring information density and reader value while
penalizing near-duplicates. It selects a candidate; it does not invent facts
or expose private reasoning.
"""
from __future__ import annotations
import json,re,hashlib
from pathlib import Path
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parents[1]
PREF=ROOT/"data/live/editorial_preflight.json"
AUD=ROOT/"data/live/nic_audience_response_12.json"
OUT=ROOT/"data/live/nic_creative_compiler_13.json"
REPORT=ROOT/"data/intelligence/nic_creative_compiler_13_report.json"
STOP=set("the a an and or but if then this that with from for to of in on is are was were it its as by into about than over after before what why how can will would could should".split())
def load(p):
    try:
        x=json.loads(p.read_text(encoding="utf-8")); return x if isinstance(x,dict) else {}
    except Exception:return {}
def tokens(s):
    return set(re.findall(r"[a-z0-9$]{3,}",str(s).lower()))-STOP
def sim(a,b):
    A,B=tokens(a),tokens(b)
    return len(A&B)/len(A|B) if A and B else 0.0
def score(t):
    w=len(re.findall(r"\b[\w$%.-]+\b",t)); low=t.lower()
    facts=len(re.findall(r"\b(?:\d+(?:\.\d+)?%?|\$?\d+(?:\.\d+)?)\b",t))
    mechanisms=sum(x in low for x in ("because","why","mechanism","driven by","transmission","evidence","instead","however"))
    question=1 if t.count("?")==1 else 0
    generic=sum(x in low[:180] for x in ("fresh check","quick market check","here is what matters","what do you think"))
    return min(100,20+min(20,w/6)+min(18,facts*3)+min(18,mechanisms*4)+12*question-12*generic)
def main():
    p=load(PREF); aud=load(AUD); raw=p.get("candidate_scripts_4") or []
    candidates=[]
    for i,c in enumerate(raw):
        t=str(c.get("script") if isinstance(c,dict) else c).strip()
        if t:candidates.append({"source_index":i,"text":t})
    if not candidates: raise SystemExit("NIC 13: no generated candidates")
    threshold=float((aud.get("creative_collision") or {}).get("threshold",0.55))
    selected=[]; rejected=[]
    remaining=list(candidates)
    while remaining:
        remaining.sort(key=lambda x:(score(x["text"]),-max((sim(x["text"],y["text"]) for y in selected),default=0.0)),reverse=True)
        x=remaining.pop(0); nearest=max((sim(x["text"],y["text"]) for y in selected),default=0.0)
        x.update({"base_score":score(x["text"]),"nearest_selected_similarity":round(nearest,4)})
        if selected and nearest>=threshold:
            rejected.append({**x,"reason":"near_duplicate_of_selected_candidate"})
        else:selected.append(x)
    winner=selected[0]
    result={"version":"13.0","status":"READY","generated_at":datetime.now(timezone.utc).isoformat(),
            "input_candidates":len(candidates),"compiled_candidates":len(selected),
            "rejected_near_duplicates":len(rejected),"similarity_threshold":threshold,
            "winner":{"source_index":winner["source_index"],"score":winner["base_score"],"nearest_similarity":winner["nearest_selected_similarity"]},
            "diversity_policy":{"near_duplicate_penalty":True,"preserve_multiple_story_angles":True,
                                "reader_value_before_virality":True,"no_fact_invention":True,
                                "no_guaranteed_revenue":True},
            "candidates":selected[:5],"rejected":rejected[:10]}
    p["nic_creative_compiler_13"]=result
    OUT.parent.mkdir(parents=True,exist_ok=True);REPORT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(result,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    REPORT.write_text(json.dumps({"version":"13.0","status":"READY","input_candidates":len(candidates),
                                  "compiled_candidates":len(selected),"rejected_near_duplicates":len(rejected),
                                  "output":str(OUT.relative_to(ROOT))},indent=2)+"\n",encoding="utf-8")
    PREF.write_text(json.dumps(p,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    print(json.dumps({"status":"READY","winner_index":winner["source_index"],"compiled":len(selected),"rejected":len(rejected)}))
if __name__=="__main__":main()
