"""Diagnose whether weak results are primarily distribution or engagement.

This deliberately avoids claiming knowledge of Binance's proprietary ranking system.
It only analyzes the account's observable publication metrics.
"""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path

LOG = Path("analytics/publication_log.jsonl")
OUT = Path("data/live/performance_diagnostics.json")


def num(row, key):
    try:
        return float(row.get(key) or 0)
    except Exception:
        return 0.0


def load_rows():
    if not LOG.exists():
        return []
    rows=[]
    for line in LOG.read_text(encoding="utf-8").splitlines()[-500:]:
        try:
            r=json.loads(line)
            if r.get("published_at") or r.get("views") is not None:
                rows.append(r)
        except Exception:
            pass
    return rows


def main():
    rows=load_rows()
    if not rows:
        result={"status":"NO_METRICS","message":"No publication metrics are available yet."}
    else:
        views=[num(r,"views") for r in rows]
        likes=[num(r,"likes") for r in rows]
        replies=[num(r,"replies") for r in rows]
        shares=[num(r,"shares") for r in rows]
        followers=[num(r,"followers_gained") for r in rows]
        n=len(rows)
        total_views=sum(views)
        total_engagement=sum(likes)+sum(replies)+sum(shares)
        reply_rate=sum(replies)/max(1,total_views)
        follower_rate=sum(followers)/max(1,total_views)
        avg_views=total_views/n
        avg_replies=sum(replies)/n
        recent=rows[-10:]
        recent_views=sum(num(r,"views") for r in recent)/max(1,len(recent))
        recent_replies=sum(num(r,"replies") for r in recent)
        recent_followers=sum(num(r,"followers_gained") for r in recent)
        if recent_views < max(50, avg_views*0.55) and recent_replies == 0:
            diagnosis="LOW_DISTRIBUTION_AND_NO_ENGAGEMENT"
        elif recent_views < max(50, avg_views*0.70):
            diagnosis="DISTRIBUTION_WEAK"
        elif recent_replies == 0 and recent_followers == 0:
            diagnosis="REACH_EXISTS_BUT_CONVERSION_WEAK"
        else:
            diagnosis="ENGAGEMENT_SIGNAL_PRESENT"
        result={
            "status":"OK","generated_at":datetime.now(timezone.utc).isoformat(),
            "sample_count":n,"diagnosis":diagnosis,
            "baseline":{"avg_views":round(avg_views,2),"avg_replies":round(avg_replies,2),"reply_rate":round(reply_rate,6),"follower_rate":round(follower_rate,6),"total_engagement":round(total_engagement,2)},
            "recent_10":{"avg_views":round(recent_views,2),"replies":round(recent_replies,2),"followers":round(recent_followers,2)},
            "next_action":(
                "Test distribution-sensitive topics and fresher event timing while keeping the post short and visual-first."
                if diagnosis in {"LOW_DISTRIBUTION_AND_NO_ENGAGEMENT","DISTRIBUTION_WEAK"}
                else "Test stronger community questions, choice formats and first-frame visuals while preserving the winning topic lane."
            ),
            "guardrail":"Do not infer Binance's proprietary algorithm from these metrics; treat this as account-level experimentation."
        }
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(result,indent=2,ensure_ascii=False),encoding="utf-8")
    print(json.dumps(result,indent=2,ensure_ascii=False))

if __name__=="__main__": main()
