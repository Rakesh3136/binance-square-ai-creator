"""Write-to-Earn Monetization Attribution 2.1 — keyless evidence ledger."""
from __future__ import annotations
import json
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
AN=ROOT/"analytics"; LIVE=ROOT/"data/live"; INTEL=ROOT/"data/intelligence"
ATTR=AN/"publication_attribution.jsonl"; PERF=AN/"square_performance.jsonl"; EVENTS=AN/"wte_reward_events.jsonl"
OUT=LIVE/"wte_monetization_attribution.json"; REPORT=INTEL/"wte_monetization_attribution_report.json"
def jl(p):
    rows=[]
    if p.exists():
        for line in p.read_text(encoding="utf-8").splitlines():
            try:
                x=json.loads(line)
                if isinstance(x,dict): rows.append(x)
            except Exception: pass
    return rows
def pid(x):
    s=str(x.get("canonical_post_id") or x.get("post_id") or x.get("publication_id") or "").strip().rstrip("/")
    if "/square/post/" in s: s=s.split("/square/post/",1)[1].split("?",1)[0].split("#",1)[0]
    return s.lower()
def num(x,*keys):
    for k in keys:
        try:return float(x.get(k))
        except Exception: pass
    return 0.0
def main():
    attrs={pid(x):x for x in jl(ATTR) if pid(x)}; perf={pid(x):x for x in jl(PERF) if pid(x)}; events=jl(EVENTS)
    bypost={}; unattributed=[]
    for e in events:
        p=pid(e)
        if p:bypost[p]=e
        else: unattributed.append(e)
    rows=[]; now=datetime.now(timezone.utc)
    for p,a in attrs.items():
        pub=str(a.get("published_at") or a.get("created_at") or ""); age_days=None
        try: age_days=max(0,(now-datetime.fromisoformat(pub.replace("Z","+00:00"))).total_seconds()/86400)
        except Exception: pass
        ev=bypost.get(p,{}); explicit=ev.get("reward_amount_usdc")
        verified=ev.get("verified") is True and explicit is not None
        rows.append({"post_id":p,"published_at":pub,"age_days":round(age_days,3) if age_days is not None else None,"within_7_day_window":age_days is not None and age_days<=7,"symbol":a.get("symbol"),"format":a.get("format"),"category":a.get("category"),"cashtag_present":bool(a.get("cashtag_present") or a.get("coin_cashtag") or a.get("cashtag")),"widget_present":bool(a.get("widget_present") or a.get("trading_widget_present")),"views":num(perf.get(p,{}),"views","view_count","impressions"),"explicit_reward_verified":verified,"verified_reward_usdc":round(float(explicit),8) if verified else None,"reward_event_source":ev.get("source") if verified else None,"detail_status":"VERIFIED" if verified else ("NO_REWARD_EVENT" if not ev else "UNVERIFIED_EVENT")})
    post_total=round(sum(x["verified_reward_usdc"] or 0 for x in rows),8)
    unattrib_total=round(sum(num(e,"reward_amount_usdc") for e in unattributed if e.get("verified") is True),8)
    total=round(post_total+unattrib_total,8)
    summary={"tracked_posts":len(rows),"posts_within_7_day_window":sum(1 for x in rows if x["within_7_day_window"]),"posts_with_cashtag":sum(1 for x in rows if x["cashtag_present"]),"verified_post_reward_events":sum(1 for x in rows if x["explicit_reward_verified"]),"verified_unattributed_reward_events":sum(1 for e in unattributed if e.get("verified") is True),"verified_post_reward_usdc":post_total,"verified_unattributed_reward_usdc":unattrib_total,"verified_reward_total_usdc":total}
    state={"version":"2.1","generated_at":now.isoformat(),"status":"READY","posts":rows[-200:],"summary":summary,"unattributed_events":[{k:e.get(k) for k in ("event_id","observed_at","reward_amount_usdc","currency","source","detail_status")} for e in unattributed[-50:]],"rules":{"reward_requires_explicit_event":True,"hidden_trades_never_inferred":True,"views_are_not_revenue":True,"seven_day_window_is_tracking_window_not_a_guarantee":True,"unattributed_rewards_are_not_assigned_to_posts":True}}
    LIVE.mkdir(parents=True,exist_ok=True); INTEL.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(state,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    REPORT.write_text(json.dumps({"version":"2.1","status":"READY",**summary},indent=2)+"\n",encoding="utf-8")
    print(json.dumps(summary,ensure_ascii=False))
if __name__=="__main__":main()
