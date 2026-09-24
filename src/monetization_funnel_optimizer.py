"""Monetization Funnel Optimizer — evidence-only planning layer.

Optimizes the *measurement and testing plan* for legitimate Square monetization.
It never invents clicks, trades, revenue, or causal winners.
"""
from __future__ import annotations
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
AN=ROOT/"analytics"; LIVE=ROOT/"data/live"; INTEL=ROOT/"data/intelligence"
PERF=AN/"square_performance.jsonl"; ATTR=AN/"publication_attribution.jsonl"
REV=AN/"creator_8_0_monetization_engine.json"; FEEDBACK=LIVE/"creator_8_4_monetization_feedback.json"
OUT=LIVE/"monetization_funnel_optimizer.json"; REPORT=INTEL/"monetization_funnel_optimizer_report.json"

def j(path,default):
    try:
        x=json.loads(path.read_text(encoding="utf-8")) if path.exists() else default
        return x if isinstance(x,type(default)) else default
    except Exception:return default
def jl(path):
    rows=[]
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                x=json.loads(line)
                if isinstance(x,dict): rows.append(x)
            except Exception: pass
    return rows
def pid(x):
    s=str(x.get("canonical_post_id") or x.get("post_id") or x.get("publication_id") or "").strip().rstrip("/")
    if "/square/post/" in s:s=s.split("/square/post/",1)[1].split("?",1)[0].split("#",1)[0]
    return s.lower()
def num(x,*keys):
    for k in keys:
        try:return float(x.get(k))
        except:pass
    return 0.0

def main():
    perf=jl(PERF); attr={pid(x):x for x in jl(ATTR) if pid(x)}
    fb=j(FEEDBACK,{}); rev=j(REV,{})
    stages=defaultdict(lambda:{"posts":0,"views":0.0,"engagement":0.0,"attributed":0,"verified_revenue":0.0})
    for row in perf:
        p=pid(row)
        if not p: continue
        a=attr.get(p,{})
        category=str(a.get("category") or row.get("category") or "unknown")
        fmt=str(a.get("format") or row.get("format") or "unknown")
        key=(category,fmt)
        g=stages[key]; g["posts"]+=1
        g["views"]+=num(row,"views","view_count","reach","impressions")
        g["engagement"]+=num(row,"likes","like_count")+2*num(row,"comments","replies","reply_count")+3*num(row,"shares","share_count")
        if a.get("canonical_post_id") or a.get("post_id"): g["attributed"]+=1
        if a.get("revenue_verified") is True:
            g["verified_revenue"]+=max(0,num(a,"revenue_amount","verified_revenue_amount","earnings_amount","earnings"))

    observed=[]
    for (cat,fmt),g in stages.items():
        observed.append({
            "category":cat,"format":fmt,"publications":g["posts"],
            "views":round(g["views"],2),
            "engagement_per_1000_views":round(g["engagement"]/max(g["views"],1)*1000,4),
            "attributed_publications":g["attributed"],
            "verified_revenue":round(g["verified_revenue"],8),
            "evidence":"OBSERVATIONAL_ONLY"
        })
    observed.sort(key=lambda x:(x["verified_revenue"],x["engagement_per_1000_views"]),reverse=True)

    funnel={
      "version":"1.0","generated_at":datetime.now(timezone.utc).isoformat(),
      "objective":"maximize legitimate, attributable learning across the Square reader journey",
      "stages":["eligible_topic","publication","reader_engagement","cashtag_or_widget_interaction","eligible_trade","verified_commission"],
      "observations":observed[:100],
      "current_evidence":{
        "verified_revenue_status":rev.get("status"),
        "verified_revenue":rev.get("lineage",{}).get("allocated_verified_revenue",0),
        "feedback_repeated_observations":fb.get("repeated_observations",0)
      },
      "next_tests":[
        {"variable":"content_series","treatment":"series_followup_after_verified_setup","guardrail":"only when a real setup/outcome exists"},
        {"variable":"reader_cta","treatment":"evidence_review_question","guardrail":"no profit promise or trading pressure"},
        {"variable":"cashtag_surface","treatment":"exact_supported_asset_surface","guardrail":"never fabricate widget/link"},
        {"variable":"format","treatment":"alternate_format_for_same_evidence","guardrail":"one variable per experiment; no story forcing"},
      ],
      "policy":{
        "revenue_requires_explicit_verification":True,
        "reader_trades_never_inferred":True,
        "views_are_not_revenue":True,
        "prediction_success_is_not_revenue":True,
        "quality_gates_authoritative":True,
        "minimum_repeated_observations":3,
        "optimize_for_verified_value_not_raw_views":True
      }
    }
    LIVE.mkdir(parents=True,exist_ok=True); INTEL.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(funnel,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    REPORT.write_text(json.dumps({"version":"1.0","status":"READY","observed_groups":len(observed),"output":str(OUT.relative_to(ROOT))},indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"status":"READY","observed_groups":len(observed),"verified_revenue":funnel["current_evidence"]["verified_revenue"]},ensure_ascii=False))
if __name__=="__main__":main()
