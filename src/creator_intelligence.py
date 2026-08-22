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

def load_our_recent_results():
    rows=[]
    if not OUR_LOG.exists(): return rows
    for line in OUR_LOG.read_text(encoding="utf-8").splitlines()[-300:]:
        try:
            x=json.loads(line)
            rows.append({
                "format":str(x.get("format") or x.get("editorial_style") or "unknown").lower(),
                "category":str(x.get("content_category") or x.get("category") or "unknown").lower(),
                "views":metric(x,"views"),"likes":metric(x,"likes"),"replies":metric(x,"replies"),
                "shares":metric(x,"shares"),"followers":metric(x,"followers_gained")
            })
        except Exception: pass
    return rows

def main():
    examples=load_examples(); our_results=load_our_recent_results()
    archetype_counts=Counter(); format_counts=Counter(); length_buckets=Counter(); question_patterns=Counter(); visual_patterns=Counter()
    performance=defaultdict(lambda:{"n":0,"views":0,"likes":0,"replies":0,"shares":0,"followers":0})
    reusable=[]
    for ex in examples:
        text=clean_text(str(ex.get("text") or ex.get("post") or ""))
        if not text: continue
        archetype=ex.get("archetype") or classify(text)
        fmt=str(ex.get("format") or "general").lower()
        archetype_counts[archetype]+=1; format_counts[fmt]+=1
        n=len(text); length_buckets["short_<=300" if n<=300 else "medium_301-700" if n<=700 else "long_>700"]+=1
        if "?" in text:
            q=text.rsplit("?",2)[-2].split("\n")[-1].strip()[-120:]
            if q: question_patterns[q]+=1
        if ex.get("visual_type"): visual_patterns[str(ex["visual_type"])] += 1
        p=performance[archetype]; p["n"]+=1
        for k in ("views","likes","replies","shares","followers_gained"):
            p["followers" if k=="followers_gained" else k]+=metric(ex,k)
        reusable.append({"archetype":archetype,"format":fmt,"length":n,"has_question":"?" in text,"has_cashtag":bool(re.search(r"\$[A-Za-z][A-Za-z0-9_]*",text)),"visual_type":ex.get("visual_type")})

    ranked=[]
    for a,p in performance.items():
        n=max(1,p["n"])
        ranked.append({"archetype":a,"samples":p["n"],"avg_views":round(p["views"]/n,2),"avg_likes":round(p["likes"]/n,2),"avg_replies":round(p["replies"]/n,2),"avg_shares":round(p["shares"]/n,2),"avg_followers":round(p["followers"]/n,2),"engagement_score":round(performance_score(p),2)})
    # Do not let a one-post viral outlier decide the strategy.
    ranked.sort(key=lambda x:(x["samples"]>=3,x["engagement_score"]),reverse=True)

    our_by_format=defaultdict(lambda:{"n":0,"views":0,"likes":0,"replies":0,"followers":0})
    for r in our_results:
        p=our_by_format[r["format"]]; p["n"]+=1
        for k in ("views","likes","replies","followers"): p[k]+=r[k]
    our_ranked=[]
    for fmt,p in our_by_format.items():
        n=max(1,p["n"]); our_ranked.append({"format":fmt,"samples":p["n"],"avg_views":round(p["views"]/n,2),"avg_likes":round(p["likes"]/n,2),"avg_replies":round(p["replies"]/n,2),"avg_followers":round(p["followers"]/n,2)})
    our_ranked.sort(key=lambda x:(x["avg_replies"],x["avg_followers"],x["avg_likes"]),reverse=True)

    patterns={
        "generated_at":datetime.now(timezone.utc).isoformat(),
        "source_policy":"Public examples only; learn patterns, never copy creator wording, identities, branding or distinctive phrasing.",
        "sample_count":len(examples),"archetype_counts":dict(archetype_counts),"format_counts":dict(format_counts),
        "length_buckets":dict(length_buckets),"question_patterns":question_patterns.most_common(20),
        "visual_patterns":visual_patterns.most_common(20),"performance_by_archetype":ranked,
        "our_account_performance_by_format":our_ranked,
        "reusable_rules":[
            "Require multiple independent examples before treating a pattern as strong evidence.",
            "Use our own replies/follower conversion as the primary validation signal.",
            "Views measure distribution; they do not prove a format caused engagement.",
            "Never copy sentences, creator identities, branding, thumbnails or distinctive phrasing.",
            "Do not claim to know Binance's proprietary recommendation algorithm from public observations.",
            "Test one major variable at a time when possible: hook, format, visual, topic or question.",
            "For technical posts, real OHLCV data and honest uncertainty outrank visual hype.",
            "For monetization, include a relevant cashtag or real chart widget when discussing a tradeable asset; Binance says these enable attribution for Write to Earn.",
        ],
        "next_test":"Select a pattern supported by multiple public examples, create an original post, and compare its reply/follower rate against our baseline before adopting it permanently.",
    }
    OUTPUT.parent.mkdir(parents=True,exist_ok=True)
    OUTPUT.write_text(json.dumps(patterns,indent=2,ensure_ascii=False),encoding="utf-8")
    print(json.dumps(patterns,indent=2,ensure_ascii=False))

if __name__=="__main__": main()
