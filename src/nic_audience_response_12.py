"""NIC Audience Response 12.0 — adaptive editorial brief.

Combines explicit audience observations with creative-evolution history to detect
repetition at several observable levels and emit a concrete next-post brief.
It does not infer hidden reader intent, revenue, or human identity.
"""
from __future__ import annotations
import hashlib,json,re
from collections import Counter
from datetime import datetime,timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
PUB=ROOT/"analytics/publication_log.jsonl"
OUTCOMES=ROOT/"data/live/creator_7_2_outcomes.jsonl"
CREATIVE=ROOT/"data/live/nic_creative_evolution_11.json"
OUT=ROOT/"data/live/nic_audience_response_12.json"
REPORT=ROOT/"data/intelligence/nic_audience_response_12_report.json"

STOP=set("the a an and or but if then this that with from for to of in on is are was were it its as by into about than over after before what why how can will would could should".split())

def rows(p,limit=500):
    if not p.exists(): return []
    out=[]
    for line in p.read_text(encoding="utf-8",errors="ignore").splitlines()[-limit:]:
        try:
            x=json.loads(line)
            if isinstance(x,dict): out.append(x)
        except Exception: pass
    return out

def text_of(x):
    vals=[]
    for k in ("title","headline","hook","body","content","text","draft","post_text","caption"):
        v=x.get(k)
        if isinstance(v,str): vals.append(v)
    return " ".join(vals)

def tokens(s):
    return set(re.findall(r"[a-z0-9$]{3,}",s.lower()))-STOP

def similarity(a,b):
    A,B=tokens(a),tokens(b)
    if not A or not B:return 0.0
    return len(A&B)/len(A|B)

def fp_text(s):
    grams=sorted(tokens(s))
    return "art12-"+hashlib.sha256("|".join(grams).encode()).hexdigest()[:20]

def main():
    now=datetime.now(timezone.utc)
    pubs=rows(PUB)
    outcomes=rows(OUTCOMES,1000)
    explicit=[]
    for r in outcomes:
        metrics={k:r.get(k) for k in ("views","likes","replies","shares","followers_gained")}
        if any(v is not None for v in metrics.values()):
            explicit.append({**r,**metrics})
    recent=pubs[-20:]
    texts=[text_of(x) for x in recent if text_of(x)]
    similarities=[]
    for i,t in enumerate(texts):
        prior=texts[:i]
        best=max((similarity(t,p) for p in prior),default=0.0)
        similarities.append(round(best,4))
    high_similarity=sum(x>=0.55 for x in similarities)
    observed={
        "rows":len(explicit),
        "views_observed":sum(r.get("views") is not None for r in explicit),
        "likes_observed":sum(r.get("likes") is not None for r in explicit),
        "replies_observed":sum(r.get("replies") is not None for r in explicit),
        "shares_observed":sum(r.get("shares") is not None for r in explicit),
        "followers_observed":sum(r.get("followers_gained") is not None for r in explicit),
    }
    creative={}
    try: creative=json.loads(CREATIVE.read_text(encoding="utf-8"))
    except Exception: pass
    directives=creative.get("next_directives") or []
    selected=directives[0] if directives else {}
    recent_lanes=Counter(str(x.get("content_lane") or x.get("story_lane") or "") for x in recent)
    recent_formats=Counter(str(x.get("content_format") or x.get("format") or "") for x in recent)
    recent_visuals=Counter(str(x.get("visual_type") or "") for x in recent)
    brief={
      "version":"12.0","status":"READY","generated_at":now.isoformat(),
      "audience_response":{"explicit_observation_rows":len(explicit),"observed_metrics":observed},
      "creative_collision":{"recent_posts_compared":len(texts),"max_pairwise_similarity":max(similarities,default=0.0),
                            "high_similarity_count":high_similarity,"threshold":0.55,
                            "method":"token-set Jaccard; heuristic, not semantic proof"},
      "recent_grammar":{"lanes":recent_lanes.most_common(8),"formats":recent_formats.most_common(8),
                        "visuals":recent_visuals.most_common(8)},
      "selected_directive":selected,
      "adaptive_brief":{
        "force_new_hook_family":high_similarity>=2,
        "force_new_format":high_similarity>=3,
        "force_new_visual":high_similarity>=2,
        "avoid_recent_lane":recent_lanes.most_common(1)[0][0] if high_similarity>=2 and recent_lanes else "",
        "avoid_recent_format":recent_formats.most_common(1)[0][0] if high_similarity>=3 and recent_formats else "",
        "reader_value_rule":"lead with a concrete information advantage or mechanism; no generic ticker recap",
        "monetization_rule":"optimize reader value and legitimate qualifying engagement, never fabricate clicks/trades or imply guaranteed earnings",
        "evidence_rule":"missing audience data remains UNKNOWN"
      },
      "policy":{"metrics_must_be_explicit":True,"unknown_is_neutral":True,
                "human_likeness_is_not_claimed":True,"no_hidden_reasoning":True,
                "no_engagement_manipulation":True,"no_revenue_inference":True}
    }
    OUT.parent.mkdir(parents=True,exist_ok=True); REPORT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(brief,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    REPORT.write_text(json.dumps({"version":"12.0","status":"READY","output":str(OUT.relative_to(ROOT)),
                                  "collision_count":high_similarity,"observed_rows":len(explicit)},indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"status":"READY","version":"12.0","collision_count":high_similarity,
                      "selected_directive":selected,"observed_rows":len(explicit)}))
if __name__=="__main__": main()
