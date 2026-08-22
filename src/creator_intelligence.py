"""Learn reusable editorial patterns from public Binance Square examples.

This is pattern research, not copying and not an attempt to infer or manipulate
Binance's proprietary recommendation algorithm. Public examples are hypotheses;
our own performance data is the final validation source.
"""
from __future__ import annotations
import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

EXAMPLES = Path("data/intelligence/public_square_examples.json")
OUTPUT = Path("data/intelligence/creator_patterns.json")
OUR_LOG = Path("analytics/publication_log.jsonl")

ARCHETYPES = {
    "news_flash": ["breaking", "news", "etf", "fed", "trump", "regulation", "headline"],
    "technical": ["breakout", "retest", "support", "resistance", "chart", "candles", "pattern"],
    "data_onchain": ["volume", "whale", "on-chain", "open interest", "liquidation", "flow"],
    "educational": ["how", "explained", "learn", "means", "guide", "beginner"],
    "community_opinion": ["agree", "choose", "bullish", "bearish", "vote", "which", "would you"],
    "macro": ["cpi", "inflation", "jobs", "fomc", "rates", "dollar", "treasury"],
    "movers": ["gainer", "loser", "surge", "pump", "dump", "volume spike", "%"],
}

FORMAT_RULES = {
    "breaking": ["news_flash"], "chart": ["technical"], "data": ["data_onchain"],
    "comparison": ["community_opinion", "movers"], "question": ["community_opinion"],
    "education": ["educational"], "news_reaction": ["news_flash", "macro"], "movers": ["movers"],
}


def read_json(path, default):
    if not path.exists(): return default
    try: return json.loads(path.read_text(encoding="utf-8"))
    except Exception: return default


def load_examples():
    data=read_json(EXAMPLES,[])
    return data if isinstance(data,list) else []


def classify(text):
    t=text.lower()
    scores={a:sum(1 for k in keys if k in t) for a,keys in ARCHETYPES.items()}
    return max(scores,key=scores.get) if max(scores.values(),default=0)>0 else "general"


def clean_text(text):
    text=re.sub(r"https?://\S+", "", text)
    text=re.sub(r"\s+", " ", text).strip()
    return text


def metric(ex,key):
    try: return float(ex.get(key) or 0)
    except Exception: return 0.0


def performance_score(p):
    n=max(1,p["n"])
    # Replies/follower conversion matter more than raw reach.
    return (p["replies"]/n)*5 + (p["followers"]/n)*4 + (p["likes"]/n)*1 + (p["shares"]/n)*2


def confidence(samples: int) -> str:
    if samples >= 10: return "high"
    if samples >= 5: return "medium"
    if samples >= 3: return "tentative"
    return "insufficient"


def load_our_recent_results():
    rows=[]
    if not OUR_LOG.exists(): return rows
    for line in OUR_LOG.read_text(encoding="utf-8").splitlines()[-500:]:
        try:
            x=json.loads(line)
            rows.append({
                "format":str(x.get("format") or x.get("editorial_style") or "unknown").lower(),
                "category":str(x.get("content_category") or x.get("category") or "unknown").lower(),
                "experiment":str(x.get("experiment_id") or x.get("editorial_experiment") or "unknown").lower(),
                "views":metric(x,"views"),"likes":metric(x,"likes"),"replies":metric(x,"replies"),
                "shares":metric(x,"shares"),"followers":metric(x,"followers_gained")
            })
        except Exception: pass
    return rows


def main():
    examples=load_examples(); our_results=load_our_recent_results()
    archetype_counts=Counter(); format_counts=Counter(); length_buckets=Counter(); question_patterns=Counter(); visual_patterns=Counter()
    creator_counts=Counter(); source_counts=Counter(); performance=defaultdict(lambda:{"n":0,"views":0,"likes":0,"replies":0,"shares":0,"followers":0})
    creator_performance=defaultdict(lambda:{"n":0,"replies":0,"followers":0,"likes":0,"shares":0,"views":0})
    reusable=[]; rejected=[]
    seen=set()

    for ex in examples:
        text=clean_text(str(ex.get("text") or ex.get("post") or ""))
        if not text:
            rejected.append({"reason":"missing_text"}); continue
        fingerprint=re.sub(r"[^a-z0-9]+"," ",text.lower()).strip()
        if fingerprint in seen:
            rejected.append({"reason":"duplicate_text"}); continue
        seen.add(fingerprint)
        if len(text)<20:
            rejected.append({"reason":"too_short"}); continue
        archetype=ex.get("archetype") or classify(text)
        fmt=str(ex.get("format") or "general").lower()
        creator=str(ex.get("creator") or ex.get("creator_id") or "unknown")
        source=str(ex.get("source") or ex.get("source_url") or "unknown")
        archetype_counts[archetype]+=1; format_counts[fmt]+=1; creator_counts[creator]+=1; source_counts[source]+=1
        n=len(text); length_buckets["short_<=300" if n<=300 else "medium_301-700" if n<=700 else "long_>700"]+=1
        if "?" in text:
            q=text.rsplit("?",2)[-2].split("\n")[-1].strip()[-120:]
            if q: question_patterns[q]+=1
        if ex.get("visual_type"): visual_patterns[str(ex["visual_type"])] += 1
        p=performance[archetype]; p["n"]+=1
        cp=creator_performance[creator]; cp["n"]+=1
        for k in ("views","likes","replies","shares","followers_gained"):
            value=metric(ex,k)
            p["followers" if k=="followers_gained" else k]+=value
            cp["followers" if k=="followers_gained" else k]+=value
        reusable.append({"archetype":archetype,"format":fmt,"creator":creator,"length":n,"has_question":"?" in text,"has_cashtag":bool(re.search(r"\$[A-Za-z][A-Za-z0-9_]*",text)),"visual_type":ex.get("visual_type"),"views":metric(ex,"views"),"replies":metric(ex,"replies"),"followers":metric(ex,"followers_gained")})

    ranked=[]
    for a,p in performance.items():
        n=max(1,p["n"])
        ranked.append({"archetype":a,"samples":p["n"],"confidence":confidence(p["n"]),"avg_views":round(p["views"]/n,2),"avg_likes":round(p["likes"]/n,2),"avg_replies":round(p["replies"]/n,2),"avg_shares":round(p["shares"]/n,2),"avg_followers":round(p["followers"]/n,2),"reply_rate":round(p["replies"]/max(1,p["views"]),5),"follower_rate":round(p["followers"]/max(1,p["views"]),5),"engagement_score":round(performance_score(p),2)})
    ranked.sort(key=lambda x:(x["samples"]>=3,x["engagement_score"]),reverse=True)

    creator_ranked=[]
    for creator,p in creator_performance.items():
        n=max(1,p["n"])
        creator_ranked.append({"creator":creator,"samples":p["n"],"confidence":confidence(p["n"]),"avg_views":round(p["views"]/n,2),"avg_replies":round(p["replies"]/n,2),"avg_followers":round(p["followers"]/n,2),"reply_rate":round(p["replies"]/max(1,p["views"]),5),"follower_rate":round(p["followers"]/max(1,p["views"]),5)})
    creator_ranked.sort(key=lambda x:(x["samples"]>=5,x["reply_rate"],x["follower_rate"]),reverse=True)

    our_by_format=defaultdict(lambda:{"n":0,"views":0,"likes":0,"replies":0,"followers":0})
    our_by_experiment=defaultdict(lambda:{"n":0,"views":0,"likes":0,"replies":0,"followers":0})
    for r in our_results:
        p=our_by_format[r["format"]]; p["n"]+=1
        e=our_by_experiment[r["experiment"]]; e["n"]+=1
        for k in ("views","likes","replies","followers"):
            p[k]+=r[k]; e[k]+=r[k]

    def summarize(group):
        out=[]
        for name,p in group.items():
            n=max(1,p["n"])
            out.append({"name":name,"samples":p["n"],"avg_views":round(p["views"]/n,2),"avg_likes":round(p["likes"]/n,2),"avg_replies":round(p["replies"]/n,2),"avg_followers":round(p["followers"]/n,2),"reply_rate":round(p["replies"]/max(1,p["views"]),5),"follower_rate":round(p["followers"]/max(1,p["views"]),5)})
        return sorted(out,key=lambda x:(x["samples"],x["reply_rate"],x["follower_rate"]),reverse=True)

    our_ranked=summarize(our_by_format); our_experiment_ranked=summarize(our_by_experiment)
    baseline_views=sum(r["views"] for r in our_results)/max(1,len(our_results))
    baseline_replies=sum(r["replies"] for r in our_results)/max(1,len(our_results))
    baseline_followers=sum(r["followers"] for r in our_results)/max(1,len(our_results))

    patterns={
        "generated_at":datetime.now(timezone.utc).isoformat(),
        "source_policy":"Public examples only; learn patterns, never copy creator wording, identities, branding or distinctive phrasing.",
        "sample_count":len(examples)-len(rejected),"rejected_examples":rejected[:50],
        "creator_count":len([x for x in creator_counts if x!="unknown"]),"source_count":len([x for x in source_counts if x!="unknown"]),
        "archetype_counts":dict(archetype_counts),"format_counts":dict(format_counts),"length_buckets":dict(length_buckets),
        "question_patterns":question_patterns.most_common(20),"visual_patterns":visual_patterns.most_common(20),
        "performance_by_archetype":ranked,"creator_benchmarks":creator_ranked[:30],
        "our_account_performance_by_format":our_ranked,"our_account_performance_by_experiment":our_experiment_ranked,
        "our_baseline":{"samples":len(our_results),"avg_views":round(baseline_views,2),"avg_replies":round(baseline_replies,2),"avg_followers":round(baseline_followers,2)},
        "reusable_rules":[
            "Require multiple independent examples before treating a pattern as strong evidence.",
            "Treat creator benchmarks as directional evidence, not proof of causation.",
            "Use our own replies and follower conversion as the primary validation signal.",
            "Views measure distribution; they do not prove a format caused engagement.",
            "Never copy sentences, creator identities, branding, thumbnails or distinctive phrasing.",
            "Do not claim to know Binance's proprietary recommendation algorithm from public observations.",
            "Test one major variable at a time when possible: hook, format, visual, topic or question.",
            "For technical posts, real OHLCV data and honest uncertainty outrank visual hype.",
            "For monetization, include a relevant cashtag or real chart widget when discussing a tradeable asset; Binance says these enable attribution for Write to Earn.",
        ],
        "next_test":"Choose a pattern with at least 3 independent examples, adapt it into an original post, and compare reply/follower rate against our baseline. Do not permanently adopt a pattern from one viral outlier.",
    }
    OUTPUT.parent.mkdir(parents=True,exist_ok=True)
    OUTPUT.write_text(json.dumps(patterns,indent=2,ensure_ascii=False),encoding="utf-8")
    print(json.dumps(patterns,indent=2,ensure_ascii=False))

if __name__=="__main__": main()
