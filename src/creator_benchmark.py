import json
import re
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

BASE = "https://www.binance.com/bapi/composite/v3/friendly/pgc/content/article/list"
OUT = Path("data/intelligence/creator_benchmark.json")
PATTERNS = Path("data/intelligence/creator_patterns.json")


def fetch(page, feed_type, size=20):
    qs = urlencode({"pageIndex": page, "pageSize": size, "type": feed_type})
    req = Request(
        f"{BASE}?{qs}",
        headers={
            "User-Agent": "Mozilla/5.0",
            "Accept": "application/json",
            "Referer": "https://www.binance.com/en/square/trending",
        },
    )
    with urlopen(req, timeout=15) as response:
        return json.loads(response.read().decode("utf-8"))


def posts_from(payload):
    if isinstance(payload, list):
        return payload
    if not isinstance(payload, dict):
        return []
    data = payload.get("data")
    if isinstance(data, dict):
        for key in ("list", "rows", "articles", "items"):
            if isinstance(data.get(key), list):
                return data[key]
    for key in ("list", "rows", "articles", "items"):
        if isinstance(payload.get(key), list):
            return payload[key]
    return []


def num(x):
    try:
        return float(x or 0)
    except Exception:
        return 0.0


def classify(text):
    t = text.lower()
    labels = []
    if "?" in text:
        labels.append("question_hook")
    if re.search(r"\b(why|how|what|watch|bullish|bearish|breakout|fakeout)\b", t):
        labels.append("market_debate")
    if re.search(r"\b(top|gainer|loser|volume|surge|rally|crash)\b", t):
        labels.append("market_mover")
    if re.search(r"\b(news|announc|launch|listing|upgrade|etf|fed|sec)\b", t):
        labels.append("catalyst_news")
    if re.search(r"\b(data|volume|percent|%|ratio|open interest|oi)\b", t):
        labels.append("data_hook")
    if re.search(r"\b(support|resistance|breakout|pattern|rsi|ema|fib)\b", t):
        labels.append("technical")
    if "$" in text:
        labels.append("cashtag")
    if not labels:
        labels.append("general")
    return labels


def main():
    all_posts = {}
    failures = []
    for feed_type in (1, 2):
        try:
            for page in (1, 2, 3):
                rows = posts_from(fetch(page, feed_type))
                if not rows:
                    break
                for row in rows:
                    if isinstance(row, dict) and row.get("id"):
                        all_posts[str(row["id"])] = row
                time.sleep(0.5)
        except Exception as exc:
            failures.append(str(exc))

    rows = list(all_posts.values())
    ranked = sorted(rows, key=lambda x: (num(x.get("commentCount")) * 5 + num(x.get("replyCount")) * 6 + num(x.get("shareCount")) * 3 + num(x.get("likeCount"))), reverse=True)
    patterns = Counter()
    pattern_metrics = defaultdict(list)
    for row in rows:
        text = str(row.get("content") or row.get("title") or "").strip()
        for label in classify(text):
            patterns[label] += 1
            pattern_metrics[label].append(row)

    hypotheses = []
    for label, count in patterns.most_common():
        group = pattern_metrics[label]
        avg_views = sum(num(x.get("viewCount")) for x in group) / len(group)
        avg_comments = sum(num(x.get("commentCount")) for x in group) / len(group)
        avg_replies = sum(num(x.get("replyCount")) for x in group) / len(group)
        avg_shares = sum(num(x.get("shareCount")) for x in group) / len(group)
        hypotheses.append({
            "pattern": label,
            "samples": count,
            "avg_views": round(avg_views, 2),
            "avg_comments": round(avg_comments, 3),
            "avg_replies": round(avg_replies, 3),
            "avg_shares": round(avg_shares, 3),
            "hypothesis": "Test this structure on our account; do not copy wording or identity.",
        })

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": "Binance Square public article feed",
        "endpoint": BASE,
        "sample_count": len(rows),
        "failures": failures,
        "top_posts": [
            {k: x.get(k) for k in ("id", "authorName", "cardType", "content", "viewCount", "likeCount", "commentCount", "replyCount", "shareCount", "quoteCount", "webLink")}
            for x in ranked[:30]
        ],
        "patterns": hypotheses,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    existing = {}
    if PATTERNS.exists():
        try:
            existing = json.loads(PATTERNS.read_text(encoding="utf-8"))
        except Exception:
            existing = {}
    existing["generated_at"] = report["generated_at"]
    existing["source"] = "Public Binance Square feed; structural benchmarking only"
    existing["patterns"] = hypotheses[:20]
    existing["rules"] = [
        "Use public creator data as hypotheses, not as templates.",
        "Never copy another creator's wording, identity, branding or distinctive post.",
        "Prefer patterns with replies/shares, not merely high views.",
        "Do not declare causality from one post; require repeated samples.",
    ]
    PATTERNS.write_text(json.dumps(existing, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"status": "OK", "sample_count": len(rows), "patterns": hypotheses[:8], "failures": failures}, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
