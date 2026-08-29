"""Daily account-growth and content-learning ledger.

This module never invents followers or engagement. It records verified post metrics
and, when an externally verified account follower count is supplied, keeps a daily
follower history and calculates day-over-day change.
"""
from __future__ import annotations
import csv, json, os
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOG = ROOT / "analytics/performance_log.csv"
OUT = ROOT / "data/intelligence/growth_dashboard.json"
HISTORY = ROOT / "analytics/follower_history.jsonl"


def num(v):
    try: return float(v)
    except (TypeError, ValueError): return 0.0


def main():
    rows=[]
    if LOG.exists():
        with LOG.open("r", encoding="utf-8", newline="") as f:
            rows=list(csv.DictReader(f))

    by_day=defaultdict(lambda:{"posts":0,"views":0,"likes":0,"comments":0,"shares":0,"followers_from_posts":0})
    for r in rows:
        day=(r.get("published_at") or r.get("date") or "")[:10] or "unknown"
        if day=="unknown": continue
        d=by_day[day]; d["posts"]+=1
        d["views"]+=num(r.get("views")); d["likes"]+=num(r.get("likes")); d["comments"]+=num(r.get("comments")); d["shares"]+=num(r.get("shares")); d["followers_from_posts"]+=num(r.get("followers_gained"))

    verified_followers=os.getenv("SQUARE_FOLLOWER_COUNT", "").strip()
    now=datetime.now(timezone.utc)
    snapshot={"recorded_at":now.isoformat(),"date":now.date().isoformat()}
    if verified_followers:
        snapshot["followers"] = int(float(verified_followers))
        previous=None
        if HISTORY.exists():
            for line in HISTORY.read_text(encoding="utf-8").splitlines()[-30:]:
                try:
                    x=json.loads(line)
                    if x.get("followers") is not None: previous=x
                except Exception: pass
        snapshot["previous_followers"] = previous.get("followers") if previous else None
        snapshot["day_over_day_change"] = (snapshot["followers"]-previous["followers"]) if previous else None
        with HISTORY.open("a",encoding="utf-8") as f: f.write(json.dumps(snapshot,ensure_ascii=False)+"\n")
    else:
        snapshot["followers"] = None
        snapshot["day_over_day_change"] = None
        snapshot["note"] = "No verified account follower count was supplied; post-attributed follower gains remain separate and are never treated as total followers."

    recent_days=sorted(by_day.items())[-7:]
    totals={"posts":sum(x[1]["posts"] for x in recent_days),"views":sum(x[1]["views"] for x in recent_days),"likes":sum(x[1]["likes"] for x in recent_days),"comments":sum(x[1]["comments"] for x in recent_days),"shares":sum(x[1]["shares"] for x in recent_days),"followers_from_posts":sum(x[1]["followers_from_posts"] for x in recent_days)}
    totals["engagement_rate"]=(totals["likes"]+2*totals["comments"]+3*totals["shares"])/max(totals["views"],1)
    dashboard={"generated_at":now.isoformat(),"today":snapshot,"daily":dict(sorted(by_day.items())[-30:]),"last_7_days":totals,"objectives":{"increase_replies":True,"increase_follower_conversion":True,"increase_cashtag_and_chart_click_intent":True,"improve_style_diversity":True,"never_trade_accuracy_for_engagement":True}}
    OUT.parent.mkdir(parents=True,exist_ok=True); OUT.write_text(json.dumps(dashboard,indent=2,ensure_ascii=False),encoding="utf-8")
    print(json.dumps({"status":"OK","today":snapshot,"last_7_days":totals},ensure_ascii=False))

if __name__=="__main__": main()
