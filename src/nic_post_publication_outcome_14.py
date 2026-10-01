"""NIC 14 — Post-Publication Outcome Loop.

Joins exact publication IDs to explicit audience/performance/reward evidence,
classifies each publication by observation maturity, and emits bounded next-cycle
adaptation signals. Unknown data stays unknown; no revenue or causality is inferred.
"""
from __future__ import annotations
import json,re
from collections import Counter
from datetime import datetime,timezone,timedelta
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
AN=ROOT/"analytics"; LIVE=ROOT/"data/live"; INTEL=ROOT/"data/intelligence"
PUB=AN/"publication_log.jsonl"; ATTR=AN/"publication_attribution.jsonl"
REW=AN/"wte_reward_events.jsonl"; EXT=AN/"external_reward_events.jsonl"
PERF=AN/"square_performance.jsonl"; OUT=LIVE/"nic_post_publication_outcome_14.json"
REPORT=INTEL/"nic_post_publication_outcome_14_report.json"
WINDOW=7

def rows(path):
    if not path.exists(): return []
    out=[]
    for line in path.read_text(encoding="utf-8",errors="ignore").splitlines():
        try:
            x=json.loads(line)
            if isinstance(x,dict): out.append(x)
        except Exception: pass
    return out

def pid(x):
    raw=str(x.get("canonical_post_id") or x.get("post_id") or x.get("publication_id") or "").strip()
    if "/square/post/" in raw: raw=raw.split("/square/post/",1)[1].split("?",1)[0]
    return raw.lower() if re.fullmatch(r"[a-z0-9_-]{1,128}",raw.lower()) else ""

def dt(v):
    try:
        x=datetime.fromisoformat(str(v).replace("Z","+00:00"))
        return x if x.tzinfo else x.replace(tzinfo=timezone.utc)
    except Exception: return None

def num(x):
    try: return float(x)
    except Exception: return None

def main():
    now=datetime.now(timezone.utc)
    pubs={}
    for x in rows(PUB):
        p=pid(x)
        if p: pubs[p]=x
    for x in rows(ATTR):
        p=pid(x)
        if p: pubs[p]={**pubs.get(p,{}),**x}

    rewards={}; unattributed=[]
    for source in (REW,EXT):
        for x in rows(source):
            if x.get("verified") is not True and source==REW: continue
            p=pid(x)
            amount=num(x.get("reward_amount_usdc"))
            if p and amount is not None:
                rewards[p]=rewards.get(p,0.0)+max(0,amount)
            elif amount is not None and x.get("verified") is True:
                unattributed.append({"event_id":x.get("event_id"),"amount_usdc":amount,"observed_at":x.get("observed_at")})

    performance={}
    for x in rows(PERF):
        p=pid(x)
        if p: performance[p]=x

    outcomes=[]; maturity=Counter(); reward_posts=[]
    for p,x in pubs.items():
        published=dt(x.get("published_at") or x.get("recorded_at") or x.get("timestamp"))
        age=(now-published).total_seconds()/86400 if published else None
        reward=rewards.get(p)
        perf=performance.get(p,{})
        explicit_metrics={k:perf[k] for k in ("views","likes","replies","shares","followers_gained") if k in perf and num(perf[k]) is not None}
        if reward is not None:
            state="VERIFIED_REWARD"; reward_posts.append(p)
        elif age is not None and age>=WINDOW:
            state="CLOSED_NO_VERIFIED_REWARD"
        else:
            state="OPEN_OBSERVATION"
        maturity[state]+=1
        outcomes.append({
            "post_id":p,"published_at":x.get("published_at") or x.get("recorded_at"),
            "symbol":x.get("symbol"),"category":x.get("category"),
            "content_lane":x.get("content_lane") or x.get("story_lane"),
            "content_format":x.get("content_format") or x.get("format"),
            "visual_type":x.get("visual_type"),"cashtag":x.get("cashtag"),
            "age_days":round(age,3) if age is not None else None,
            "observation_closes_at":(published+timedelta(days=WINDOW)).isoformat() if published else None,
            "outcome_state":state,"verified_reward_usdc":round(reward,8) if reward is not None else None,
            "explicit_audience_metrics":explicit_metrics,
            "performance_evidence_status":"EXPLICIT" if explicit_metrics else "UNKNOWN",
            "causality_claim_allowed":False
        })

    recent=sorted(outcomes,key=lambda x:x.get("published_at") or "")[-12:]
    lane_counts=Counter(x.get("content_lane") for x in recent if x.get("content_lane"))
    format_counts=Counter(x.get("content_format") for x in recent if x.get("content_format"))
    visual_counts=Counter(x.get("visual_type") for x in recent if x.get("visual_type"))
    adaptation={
        "force_new_lane":lane_counts.most_common(1)[0][0] if lane_counts and lane_counts.most_common(1)[0][1]>=4 else None,
        "force_new_format":format_counts.most_common(1)[0][0] if format_counts and format_counts.most_common(1)[0][1]>=4 else None,
        "force_new_visual":visual_counts.most_common(1)[0][0] if visual_counts and visual_counts.most_common(1)[0][1]>=4 else None,
        "rules":["Use explicit verified reward evidence only for monetization learning.",
                 "Treat missing audience metrics as UNKNOWN, not failure.",
                 "Do not infer causality from a single post.",
                 "Change creative variables only when evidence supports an adaptation.",
                 "Keep exact post-ID lineage; never assign an unattributed reward."]
    }
    result={"version":"14.0","status":"READY","generated_at":now.isoformat(),
            "policy":{"seven_day_observation_window":WINDOW,"exact_post_id_lineage":True,
                      "explicit_reward_only":True,"unknown_is_neutral":True,
                      "no_causality_from_single_post":True,"no_private_reasoning":True},
            "summary":{"publication_records":len(outcomes),"maturity":dict(maturity),
                       "verified_reward_posts":len(reward_posts),
                       "unattributed_verified_rewards":len(unattributed)},
            "outcomes":outcomes[-500:],"adaptation":adaptation,
            "unattributed_rewards":unattributed[-50:],
            "next_cycle":{"consume_with":"nic_creative_evolution_11 / nic_audience_response_12 / nic_creative_compiler_13",
                          "goal":"turn closed, explicit outcomes into bounded creative adaptation"}}
    LIVE.mkdir(parents=True,exist_ok=True); INTEL.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(result,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    REPORT.write_text(json.dumps({"version":"14.0","status":"READY","summary":result["summary"],
                                  "adaptation":adaptation,"output":str(OUT.relative_to(ROOT))},indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"status":"READY",**result["summary"]}))

if __name__=="__main__": main()
