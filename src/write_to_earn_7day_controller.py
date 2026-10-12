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
PERF=AN/"square_performance.jsonl"; REWARD_EVENTS=AN/"wte_reward_events.jsonl"

LANES=[
    ("market_setup","Chart-first market setup with one clear mechanism, confirmation and invalidation."),
    ("data_investigation","Investigate one unusual relationship or anomaly and explain why it matters."),
    ("news_impact","Verified fresh event -> market mechanism -> observable response, with uncertainty."),
    ("asset_comparison","Compare two evidence-supported assets or market paths and expose the trade-off."),
    ("contrarian_thesis","Test the obvious interpretation against contrary evidence with a falsification condition."),
    ("outcome_accountability","Revisit a prior thesis only with fresh evidence and state exactly what changed."),
    ("weekly_synthesis","Synthesize verified weekly observations and define the next measurable test."),
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

def verified_row(row):
    status=str(row.get("status") or "")
    return status in {"PUBLISHED_VERIFIED_BY_API_RESPONSE","PUBLISHED_AUTONOMOUSLY","VERIFIED_PUBLISHED"} and bool(row.get("publication_proof") and (row.get("canonical_post_id") or row.get("post_id")))

def current_run_publication_time(publications, result, run_id):
    """Return timestamp only for a current-run API-confirmed post in the durable log."""
    if not run_id or str(result.get("github_run_id") or "") != str(run_id):
        return None
    if str(result.get("status") or "").upper() != "PUBLISHED_VERIFIED_BY_API_RESPONSE":
        return None
    wanted=str(result.get("canonical_post_id") or result.get("post_id") or "").strip()
    if not wanted:
        return None
    for row in reversed(publications):
        got=str(row.get("canonical_post_id") or row.get("post_id") or "").strip()
        if got == wanted and verified_row(row):
            return dt(row.get("published_at") or row.get("timestamp"))
    return None

def campaign_start(previous, publications=None, result=None, run_id=None, now=None):
    env=os.getenv("WTE_7DAY_START_UTC","").strip()
    if env:
        parsed=dt(env)
        if parsed: return parsed
    now=now or datetime.now(timezone.utc)
    publications=publications or []
    existing=dt(previous.get("campaign_start_utc"))
    current_post=current_run_publication_time(publications, result or {}, run_id)
    if existing:
        # Repair the old first-run race only when this run proves the exact post
        # was published just before the previous controller initialized, and
        # the old controller counted zero posts. Never reset an established campaign.
        if current_post and int(previous.get("verified_publications_total") or 0)==0 and existing>current_post:
            age=(existing-current_post).total_seconds()
            if 0 <= age <= 30*60:
                return current_post
        return existing
    if current_post:
        return current_post
    # No verified current-run post: start observation now. Do not backdate to
    # unrelated historical posts or claim this equals Rewards Hub activation.
    return now

def verified_publications(start):
    out=[]
    for row in rows(PUB):
        stamp=dt(row.get("published_at") or row.get("timestamp"))
        if not stamp or stamp < start: continue
        status=str(row.get("status") or "")
        if verified_row(row):
            out.append(row)
    return out

def main():
    now=datetime.now(timezone.utc)
    previous=load(STATE,{})
    publication_rows=rows(PUB)
    publication_result=load(LIVE/"publication_result.json",{})
    run_id=os.getenv("GITHUB_RUN_ID","")
    start=campaign_start(previous,publication_rows,publication_result,run_id,now)
    elapsed=max(0,(now-start).total_seconds())
    day=min(7,int(elapsed//86400)+1)
    pubs=verified_publications(start)
    by_day=Counter()
    for p in pubs:
        stamp=dt(p.get("published_at") or p.get("timestamp"))
        if stamp:
            # Campaign days are elapsed 24-hour windows, not calendar-date labels.
            # This prevents a post at 23:59 from being counted on day 2 at 00:01.
            bucket=max(1,int((stamp-start).total_seconds()//86400)+1)
            by_day[bucket]+=1

    # A primary daily target is a planning heuristic only. The actual Rewards
    # Hub task may have different thresholds or regional requirements.
    daily_target=max(1,int(os.getenv("WTE_7DAY_DAILY_TARGET","1")))
    lane_name,lane_goal=LANES[day-1]
    today_count=by_day.get(day,0)
    days_completed=sum(1 for d in range(1,8) if by_day.get(d,0)>=daily_target)
    remaining_days=max(0,8-day)
    verified_rewards=[]
    for row in rows(REWARD_EVENTS):
        stamp=dt(row.get("observed_at") or row.get("timestamp") or row.get("checked_at"))
        if stamp and stamp>=start and row.get("verified") is True and row.get("reward_amount_usdc") is not None:
            verified_rewards.append(row.get("reward_amount_usdc"))

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
            "campaign_start_is_explicit_env_or_first_current_run_verified_publication_else_controller_start":True,
            "current_run_post_must_match_run_id_and_canonical_post_id":True,
            "campaign_day_uses_elapsed_24_hour_windows":True,
            "revenue_only_from_explicit_verified_fields":True,"reward_source":"analytics/wte_reward_events.jsonl","performance_reward_fields_are_not_trusted":True,
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
