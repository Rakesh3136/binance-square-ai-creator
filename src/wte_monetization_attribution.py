"""Write-to-Earn Monetization Attribution 2.0 — keyless evidence ledger.

Turns explicit Square reward notices and post-level attribution records into a
per-post monetization ledger. It never estimates hidden reader trades or
revenue. Reward notices can be appended to analytics/wte_reward_events.jsonl
from a trusted source; missing detail remains UNKNOWN.
"""
from __future__ import annotations
import json,re
from datetime import datetime,timezone,timedelta
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
                if isinstance(x,dict):rows.append(x)
            except Exception:pass
    return rows

def pid(x):
    s=str(x.get("canonical_post_id") or x.get("post_id") or x.get("publication_id") or "").strip().rstrip("/")
    if "/square/post/" in s:s=s.split("/square/post/",1)[1].split("?",1)[0].split("#",1)[0]
    return s.lower()

def num(x,*keys):
    for k in keys:
        try:return float(x.get(k))
        except Exception:pass
    return 0.0

def main():
    attrs={pid(x):x for x in jl(ATTR) if pid(x)}
    perf={pid(x):x for x in jl(PERF) if pid(x)}
    events=jl(EVENTS)
    bypost={}
    for e in events:
        p=pid(e)
        if p:bypost[p]=e
    rows=[]
    now=datetime.now(timezone.utc)
    for p,a in attrs.items():
        pub=str(a.get("published_at") or a.get("created_at") or "")
        age_days=None
        try: age_days=max(0,(now-datetime.fromisoformat(pub.replace("Z","+00:00"))).total_seconds()/86400)
        except Exception: pass
        perfrow=perf.get(p,{})
        ev=bypost.get(p,{})
        explicit=ev.get("reward_amount_usdc")
        verified=bool(ev.get("verified") is True and explicit is not None)
        rows.append({
          "post_id":p,"published_at":pub,"age_days":round(age_days,3) if age_days is not None else None,
          "within_7_day_window":age_days is not None and age_days<=7,
          "symbol":a.get("symbol"),"format":a.get("format"),"category":a.get("category"),
          "cashtag_present":bool(a.get("cashtag_present") or a.get("coin_cashtag") or a.get("cashtag")),
          "widget_present":bool(a.get("widget_present") or a.get("trading_widget_present")),
          "views":num(perfrow,"views","view_count","impressions"),
          "explicit_reward_verified":verified,
          "verified_reward_usdc":round(float(explicit),8) if verified else None,
          "reward_event_source":ev.get("source") if verified else None,
          "detail_status":"VERIFIED" if verified else ("NO_REWARD_EVENT" if not ev else "UNVERIFIED_EVENT")
        })
    verified_total=round(sum(x["verified_reward_usdc"] or 0 for x in rows),8)
    eligible_window=sum(1 for x in rows if x["within_7_day_window"])
    with_cashtag=sum(1 for x in rows if x["cashtag_present"])
    state={"version":"2.0","generated_at":now.isoformat(),"status":"READY","posts":rows[-200:],"summary":{"tracked_posts":len(rows),"posts_within_7_day_window":eligible_window,"posts_with_cashtag":with_cashtag,"verified_reward_events":sum(1 for x in rows if x["explicit_reward_verified"]),"verified_reward_total_usdc":verified_total},"rules":{"reward_requires_explicit_event":True,"hidden_trades_never_inferred":True,"views_are_not_revenue":True,"seven_day_window_is_tracking_window_not_a_guarantee":True}}
    LIVE.mkdir(parents=True,exist_ok=True);INTEL.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(state,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    REPORT.write_text(json.dumps({"version":"2.0","status":"READY","tracked_posts":len(rows),"verified_reward_events":state["summary"]["verified_reward_events"],"verified_reward_total_usdc":verified_total},indent=2)+"\n",encoding="utf-8")
    print(json.dumps(state["summary"],ensure_ascii=False))
if __name__=="__main__":main()
