"""Seven-day Binance Square Write-to-Earn campaign controller.

This is a measurement/orchestration layer, not a revenue predictor. It tracks
verified publications and explicit performance/reward fields, assigns a varied
daily content lane, and records gaps for the next cycle. It never fabricates
reader trades, commissions, engagement, or task completion.

The exact Rewards Hub task shown to an account remains the source of truth for
eligibility, thresholds and points. This controller therefore uses configurable
defaults and exposes the assumptions in its output.
"""
from __future__ import annotations
import json, os, re
from collections import Counter
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
LIVE=ROOT/"data/live"
AN=ROOT/"analytics"
STATE=LIVE/"write_to_earn_7day_status.json"
PLAN=LIVE/"write_to_earn_7day_plan.json"
HISTORY=AN/"write_to_earn_7day.jsonl"
PUB=AN/"publication_log.jsonl"
PERF=AN/"square_performance.jsonl"

LANES=[
    ("market_setup","Market setup with one clear mechanism and invalidation."),
    ("asset_deep_dive","Single-asset research: flows, structure, catalysts and risks."),
    ("news_impact","Verified news -> mechanism -> affected asset(s), with uncertainty."),
    ("data_investigation","Data-driven comparison or anomaly with a concrete reader takeaway."),
    ("contrarian_thesis","Evidence-backed alternative interpretation with a falsification test."),
    ("outcome_accountability","Follow-up on a previous thesis using newly verified evidence."),
    ("weekly_synthesis","Seven-day synthesis: what changed, what held, what failed, next test."),
]

def load(path, default):
    try:
        if not path.exists(): return default
        value=json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value,type(default)) else default
    except Exception: return default

def rows(path, limit=500):
    if not path.exists(): return []
    out=[]
    for line in path.read_text(encoding="utf-8").splitlines()[-limit:]:
        try:
            v=json.loads(line)
            if isinstance(v,dict): out.append(v)
        except Exception: pass
    return out

def dt(value):
    try:
        x=datetime.fromisoformat(str(value).replace("Z","+00:00"))
        return x if x.tzinfo else x.replace(tzinfo=timezone.utc)
    except Exception:
        return None

def campaign_start(previous):
    env=os.getenv("WTE_7DAY_START_UTC","").strip()
    if env:
        parsed=dt(env)
        if parsed: return parsed
    existing=dt(previous.get("campaign_start_utc"))
    if existing: return existing
    # First observed run starts the campaign; no claim is made that this
    # corresponds to the user's Rewards Hub activation date.
    return datetime.now(timezone.utc)

def verified_publications(start):
    out=[]
    for row in rows(PUB):
        stamp=dt(row.get("published_at") or row.get("timestamp"))
        if not stamp or stamp < start: continue
        status=str(row.get("status") or "")
        if status.startswith("PUBLISHED_") and row.get("publication_proof") and row.get("post_id"):
            out.append(row)
    return out

def main():
    now=datetime.now(timezone.utc)
    previous=load(STATE,{})
    start=campaign_start(previous)
    elapsed=max(0,(now-start).total_seconds())
    day=min(7,int(elapsed//86400)+1)
    pubs=verified_publications(start)
    by_day=Counter()
    for p in pubs:
        stamp=dt(p.get("published_at") or p.get("timestamp"))
        if stamp:
            by_day[(stamp.date()-start.date()).days+1]+=1

    # A primary daily target is a planning heuristic only. The actual Rewards
    # Hub task may have different thresholds or regional requirements.
    daily_target=max(1,int(os.getenv("WTE_7DAY_DAILY_TARGET","1")))
    lane_name,lane_goal=LANES[day-1]
    today_count=by_day.get(day,0)
    days_completed=sum(1 for d in range(1,8) if by_day.get(d,0)>=daily_target)
    remaining_days=max(0,8-day)
    verified_rewards=[]
    for row in rows(PERF):
        stamp=dt(row.get("timestamp") or row.get("checked_at") or row.get("published_at"))
        if stamp and stamp>=start:
            for key in ("reward_amount_usdc","commission_usdc","verified_revenue_usdc"):
                value=row.get(key)
                if value is not None:
                    verified_rewards.append(value); break

    status={
        "version":"WTE-7DAY-1.0",
        "generated_at":now.isoformat(),
        "campaign_start_utc":start.isoformat(),
        "campaign_day":day,
        "campaign_days_total":7,
        "days_completed_at_daily_target":days_completed,
        "daily_target":daily_target,
        "today_verified_publications":today_count,
        "today_gap":max(0,daily_target-today_count),
        "verified_publications_total":len(pubs),
        "current_lane":{"name":lane_name,"goal":lane_goal},
        "next_action":"produce_one_qualifying_post" if today_count<daily_target and day<=7 else "measure_and_learn",
        "assumptions":{
            "source_of_truth":"Rewards Hub task shown to the account",
            "daily_target_is_configurable":True,
            "campaign_start_is_local_controller_start_unless_WTE_7DAY_START_UTC_is_set":True,
            "revenue_only_from_explicit_verified_fields":True,
        },
        "monetization_measurement":{
            "verified_reward_fields_seen":len(verified_rewards),
            "revenue_status":"verified_only" if verified_rewards else "no_verified_reward_record",
            "never_infer_from_likes_views_comments":True,
        },
        "policy":{
            "no_fake_engagement":True,
            "no_guaranteed_earnings":True,
            "no_repetitive_spam":True,
            "no_gate_bypass":True,
            "no_private_chain_of_thought_publication":True,
            "quality_and_evidence_gates_remain_authoritative":True,
        },
    }
    plan={
        "version":"WTE-7DAY-PLAN-1.0",
        "generated_at":now.isoformat(),
        "campaign_day":day,
        "lane":lane_name,
        "objective":lane_goal,
        "reader_value":"Give readers a concrete, evidence-backed reason to inspect the relevant asset rather than manufacturing urgency.",
        "attribution":"Use the verified primary coin cashtag or verified trading widget already required by the upstream WTE gate.",
        "learning":"After publication, join verified publication records to performance/outcome data and change one content variable at a time.",
        "seven_day_sequence":[{"day":i+1,"lane":name,"goal":goal} for i,(name,goal) in enumerate(LANES)],
    }
    for path,obj in ((STATE,status),(PLAN,plan)):
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(json.dumps(obj,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    HISTORY.parent.mkdir(parents=True,exist_ok=True)
    with HISTORY.open("a",encoding="utf-8") as f:
        f.write(json.dumps(status,ensure_ascii=False)+"\n")
    print(json.dumps(status,indent=2))

if __name__=="__main__":
    main()
