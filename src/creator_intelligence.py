"""Learn reusable editorial patterns from public Binance Square examples.

This module intentionally learns patterns, not identities or copied wording.
It expects a JSON array of public examples in data/intelligence/public_square_examples.json.
No private data, credentialed scraping, fake engagement, or algorithm manipulation.
"""
from __future__ import annotations
import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

EXAMPLES = Path("data/intelligence/public_square_examples.json")
OUTPUT = Path("data/intelligence/creator_patterns.json")

ARCHETYPES = {
    "news_flash": ["breaking", "news", "etf", "fed", "trump", "regulation", "headline"],
    "technical": ["breakout", "retest", "support", "resistance", "chart", "candles", "pattern"],
    "data_onchain": ["volume", "whale", "on-chain", "open interest", "liquidation", "flow"],
    "educational": ["how", "explained", "learn", "means", "guide", "beginner"],
    "community_opinion": ["agree", "choose", "bullish", "bearish", "vote", "which", "would you"],
    "macro": ["cpi", "inflation", "jobs", "fomc", "rates", "dollar", "treasury"],
    "movers": ["gainer", "loser", "surge", "pump", "dump", "volume spike", "%"],
}

FORMATS = ["breaking", "chart", "data", "comparison", "question", "education", "news_reaction", "movers"]

def load_examples():
    if not EXAMPLES.exists():
        return []
    try:
        data=json.loads(EXAMPLES.read_text(encoding="utf-8"))
        return data if isinstance(data,list) else []
    except Exception:
        return []

def classify(text):
    t=text.lower()
    scores={a:sum(1 for k in keys if k in t) for a,keys in ARCHETYPES.items()}
    return max(scores,key=scores.get) if max(scores.values(),default=0)>0 else "general"

def clean_text(text):
    text=re.sub(r"https?://\S+", "", text)
    text=re.sub(r"\s+", " ", text).strip()
    return text

def main():
    examples=load_examples()
    archetype_counts=Counter(); format_counts=Counter(); length_buckets=Counter(); question_patterns=Counter(); visual_patterns=Counter()
    performance=defaultdict(lambda:{"n":0,"views":0,"likes":0,"replies":0,"shares":0,"followers":0})
    reusable=[]
    for ex in examples:
        text=clean_text(str(ex.get("text") or ex.get("post") or ""))
        if not text: continue
        archetype=ex.get("archetype") or classify(text)
        archetype_counts[archetype]+=1
        fmt=str(ex.get("format") or "general").lower()
        format_counts[fmt]+=1
        n=len(text)
        length_buckets["short_<=300" if n<=300 else "medium_301-700" if n<=700 else "long_>700"]+=1
        if "?" in text:
            q=text.split("?")[-2].split("\n")[-1].strip()[-100:]
            question_patterns[q]+=1
        if ex.get("visual_type"): visual_patterns[str(ex["visual_type"])] += 1
        p=performance[archetype]; p["n"]+=1
        for k in ("views","likes","replies","shares","followers_gained"):
            dest="followers" if k=="followers_gained" else k
            try: p[dest]+=float(ex.get(k) or 0)
            except Exception: pass
        reusable.append({"archetype":archetype,"format":fmt,"length":n,"has_question":"?" in text,"has_cashtag":"$" in text,"visual_type":ex.get("visual_type")})
    ranked=[]
    for a,p in performance.items():
        n=max(1,p["n"])
        ranked.append({"archetype":a,"samples":p["n"],"avg_views":round(p["views"]/n,2),"avg_likes":round(p["likes"]/n,2),"avg_replies":round(p["replies"]/n,2),"avg_shares":round(p["shares"]/n,2),"avg_followers":round(p["followers"]/n,2)})
    ranked.sort(key=lambda x:(x["avg_replies"],x["avg_followers"],x["avg_likes"]),reverse=True)
    patterns={
        "generated_at":datetime.now(timezone.utc).isoformat(),
        "source_policy":"Public examples only; learn patterns, never copy creator wording or identities.",
        "sample_count":len(examples),"archetype_counts":dict(archetype_counts),"format_counts":dict(format_counts),
        "length_buckets":dict(length_buckets),"question_patterns":question_patterns.most_common(20),
        "visual_patterns":visual_patterns.most_common(20),"performance_by_archetype":ranked,
        "reusable_rules":[
            "Prefer patterns supported by multiple examples, not one viral outlier.",
            "Optimize for replies and follower conversion, not views alone.",
            "Use public examples as hypotheses; validate against our own account data.",
            "Never copy sentences, creator identities, branding, or distinctive phrasing.",
            "Do not infer hidden Binance recommendation rules from correlation alone.",
            "For technical posts, real OHLCV data and honest uncertainty outrank visual hype.",
        ],
        "next_test":"Select a content format and hook pattern from the strongest archetype, then run an original controlled test on our account.",
    }
    OUTPUT.parent.mkdir(parents=True,exist_ok=True)
    OUTPUT.write_text(json.dumps(patterns,indent=2,ensure_ascii=False),encoding="utf-8")
    print(json.dumps(patterns,indent=2,ensure_ascii=False))

if __name__=="__main__": main()
