from __future__ import annotations
import json,os,re
from pathlib import Path
from collections import Counter
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/"data/live/content_differentiation_gate.json"
STOP=set("the a an and or but is are was were to of in on for with from this that what how why when after before as by it its their they we our you your i be has have had will would can could should market price move moved next into about does gets get more less one two then than through not no".split())
def toks(t): return [x for x in re.findall(r"[a-z0-9$]+",str(t).lower()) if x not in STOP and len(x)>2]
def shingles(t,n=3): return set(tuple(t[i:i+n]) for i in range(max(0,len(t)-n+1)))
def cosine(a,b):
 c,d=Counter(a),Counter(b); common=set(c)&set(d); dot=sum(c[x]*d[x] for x in common); na=sum(v*v for v in c.values())**.5; nb=sum(v*v for v in d.values())**.5
 return dot/(na*nb) if na and nb else 0.0
def jac(a,b): return len(a&b)/len(a|b) if a|b else 0.0
def shape(t):
 ss=[s.strip() for s in re.split(r"(?<=[.!?])\s+|\n+",str(t)) if s.strip()]
 return tuple((len(toks(s)),s.endswith("?")) for s in ss[:8])
def main():
 dp=os.getenv("DRAFT_PATH")
 if not dp or not Path(dp).exists(): raise SystemExit("DRAFT_PATH missing")
 try:d=json.loads(Path(dp).read_text(encoding="utf-8"))
 except Exception: d={}
 text=str(d.get("post") or d.get("text") or d.get("content") or "").strip(); cur=toks(text); sh=shingles(cur); shp=shape(text); rows=[]
 p=ROOT/"analytics/publication_log.jsonl"
 if p.exists():
  for line in p.read_text(encoding="utf-8").splitlines()[-40:]:
   try:
    v=json.loads(line); old=str(v.get("post") or v.get("text") or v.get("draft") or "").strip()
    if old: rows.append(v)
   except Exception: pass
 comps=[]
 for r in rows:
  ot=toks(r.get("post") or r.get("text") or r.get("draft") or ""); comps.append({"cosine":cosine(cur,ot),"jaccard":jac(sh,shingles(ot)),"shape":shp==shape(r.get("post") or r.get("text") or r.get("draft") or ""),"post_id":r.get("post_id")})
 mc=max((x["cosine"] for x in comps),default=0); mj=max((x["jaccard"] for x in comps),default=0); sm=sum(x["shape"] for x in comps); clone=mc>=.82 or mj>=.62 or (sm>=2 and mc>=.68); thin=len(cur)<35; status="BLOCKED_CLONE" if clone else ("BLOCKED_THIN" if thin else "PASS")
 result={"version":"DIFFERENTIATION-GATE-1.1","status":status,"passed":status=="PASS","word_count":len(cur),"max_cosine":round(mc,4),"max_shingle_jaccard":round(mj,4),"shape_matches":sm,"rules":{"cosine":.82,"jaccard":.62,"shape_plus_cosine":[2,.68],"min_content_tokens":35}}
 OUT.parent.mkdir(parents=True,exist_ok=True); OUT.write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8"); print(json.dumps(result,indent=2))
 if not result["passed"]: raise SystemExit(2)
if __name__=="__main__": main()
