"""Anti-clone gate for Binance Square drafts.

Blocks materially repetitive posts before publication. It compares the current
finished draft with recent publication telemetry and checks both lexical overlap
and repeated sentence architecture. It does not judge profitability or predict
revenue; it protects the quality/eligibility side of the Write-to-Earn funnel.
"""
from __future__ import annotations
import json, os, re
from pathlib import Path
from collections import Counter

ROOT=Path(__file__).resolve().parents[1]
DRAFT=Path(os.getenv("DRAFT_PATH", "")) if os.getenv("DRAFT_PATH") else None
if DRAFT and not DRAFT.is_absolute(): DRAFT=ROOT/DRAFT
OUT=ROOT/"data/live/content_differentiation_gate.json"

STOP=set("the a an and or but is are was were to of in on for with from this that what how why when after before as by it its their they we our you your i be has have had will would can could should market price move moved next into about does gets get more less one two then than through not no".split())

def read_json(p, default):
    try:
        v=json.loads(p.read_text(encoding="utf-8"))
        return v if isinstance(v,type(default)) else default
    except Exception:return default

def tokens(text):
    return [x for x in re.findall(r"[a-z0-9$]+",str(text).lower()) if x not in STOP and len(x)>2]

def shingles(ts,n=3): return set(tuple(ts[i:i+n]) for i in range(max(0,len(ts)-n+1)))

def cosine(a,b):
    if not a or not b:return 0.0
    ca,cb=Counter(a),Counter(b); common=set(ca)&set(cb)
    dot=sum(ca[x]*cb[x] for x in common)
    na=sum(v*v for v in ca.values())**.5; nb=sum(v*v for v in cb.values())**.5
    return dot/(na*nb) if na and nb else 0.0

def jaccard(a,b):
    return len(a&b)/len(a|b) if a|b else 0.0

def sentence_shape(text):
    ss=[s.strip() for s in re.split(r"(?<=[.!?])\s+|\n+",str(text)) if s.strip()]
    return tuple((len(tokens(s)), s.endswith("?"), bool(re.search(r"^\$?[A-Z0-9]{2,10}\s",s))) for s in ss[:8])

def recent_posts():
    p=ROOT/"analytics/publication_log.jsonl"
    if not p.exists(): return []
    out=[]
    for line in p.read_text(encoding="utf-8").splitlines()[-30:]:
        try:
            v=json.loads(line)
            if isinstance(v,dict) and (v.get("post") or v.get("text") or v.get("draft")):
                out.append(v)
        except Exception:pass
    return out

def main():
    if not DRAFT or not DRAFT.exists(): raise SystemExit("DRAFT_PATH missing or draft does not exist")
    draft=read_json(DRAFT,{})
    text=str(draft.get("post") or draft.get("text") or draft.get("content") or "").strip()
    current=tokens(text); current_sh=shingles(current); shape=sentence_shape(text)
    comparisons=[]
    for row in recent_posts():
        old=str(row.get("post") or row.get("text") or row.get("draft") or "").strip()
        if not old: continue
        ot=tokens(old)
        comparisons.append({
            "cosine":round(cosine(current,ot),4),
            "shingle_jaccard":round(jaccard(current_sh,shingles(ot)),4),
            "shape_match":shape==sentence_shape(old),
            "symbol":row.get("symbol"),
            "post_id":row.get("post_id")
        })
    max_cos=max((x["cosine"] for x in comparisons),default=0)
    max_jac=max((x["shingle_jaccard"] for x in comparisons),default=0)
    shape_matches=sum(1 for x in comparisons if x["shape_match"])
    # Conservative thresholds: only block when overlap is strong enough to
    # indicate substantive repetition, not merely a shared crypto vocabulary.
    clone=max_cos>=0.82 or max_jac>=0.62 or (shape_matches>=2 and max_cos>=0.68)
    min_words=int(os.getenv("NIC_MIN_DISTINCT_WORDS","35"))
    distinct=len(set(current))
    too_thin=len(current)<min_words
    status="BLOCKED_CLONE" if clone else ("BLOCKED_THIN" if too_thin else "PASS")
    result={
      "version":"DIFFERENTIATION-GATE-1.0",
      "status":status,
      "passed":status=="PASS",
      "current":{"word_count":len(current),"distinct_content_tokens":distinct,"sentence_shape":shape},
      "similarity":{"max_cosine":round(max_cos,4),"max_shingle_jaccard":round(max_jac,4),"shape_matches":shape_matches},
      "comparison_count":len(comparisons),
      "rules":{"cosine_block":0.82,"shingle_block":0.62,"shape_plus_cosine_block":{"shape_matches":2,"cosine":0.68},"min_distinct_words":min_words},
      "reason":"Recent-post structure/content is materially repetitive; do not publish another clone." if clone else ("Draft is too thin to provide differentiated reader value." if too_thin else "Draft is sufficiently differentiated from recent publication telemetry."),
      "hard_invariants":["no_duplicate_content","no_fake_engagement","no_revenue_guarantee","quality_gates_remain_authoritative"]
    }
    OUT.parent.mkdir(parents=True,exist_ok=True); OUT.write_text(json.dumps(result,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    print(json.dumps(result,indent=2))
    if not result["passed"]: raise SystemExit(2)

if __name__=="__main__": main()
