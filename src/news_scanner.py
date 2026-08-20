import json
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

OUTPUT = Path("data/live/news_snapshot.json")
FEEDS = [
    ("CoinDesk", "https://www.coindesk.com/arc/outboundfeeds/rss/", "crypto_news"),
    ("Cointelegraph", "https://cointelegraph.com/rss", "crypto_news"),
    ("BLS CPI", "https://www.bls.gov/feed/cpi.rss", "macro_official"),
    ("Federal Reserve", "https://www.federalreserve.gov/feeds/press_all.xml", "macro_official"),
    ("SEC", "https://www.sec.gov/news/pressreleases.rss", "regulation_official"),
]
MAX_ITEMS_PER_FEED = 20


def fetch(url: str) -> bytes:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "BinanceSquareAI/1.0 contact=public-research-agent"},
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        return response.read()


def text(node) -> str:
    return " ".join((node.text or "").split()) if node is not None else ""


def parse_date(value: str) -> str | None:
    if not value:
        return None
    try:
        return parsedate_to_datetime(value).astimezone(timezone.utc).isoformat()
    except (TypeError, ValueError, OverflowError):
        return None


def parse_feed(source: str, category: str, payload: bytes) -> list[dict]:
    root = ET.fromstring(payload)
    items = []
    for item in root.findall(".//item")[:MAX_ITEMS_PER_FEED]:
        title = text(item.find("title"))
        link = text(item.find("link"))
        description = text(item.find("description"))
        pub = text(item.find("pubDate")) or text(item.find("published")) or text(item.find("updated"))
        if not title or not link:
            continue
        items.append({
            "source": source,
            "category": category,
            "title": title,
            "url": link,
            "summary": description[:1200],
            "published_at": parse_date(pub),
        })
    return items


def main() -> None:
    articles: list[dict] = []
    failures: list[dict] = []

    for source, url, category in FEEDS:
        try:
            articles.extend(parse_feed(source, category, fetch(url)))
        except Exception as exc:
            failures.append({"source": source, "category": category, "error": str(exc)})

    seen = set()
    deduped = []
    for article in articles:
        if article["url"] in seen:
            continue
        seen.add(article["url"])
        deduped.append(article)

    snapshot = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "sources": [name for name, _, _ in FEEDS],
        "categories": ["crypto_news", "macro_official", "regulation_official"],
        "articles": deduped[:80],
        "failures": failures,
        "note": "RSS items are discovery leads. Official feeds are preferred for primary-source verification. The AI must verify material claims before publication and distinguish announcements from interpretation.",
    }

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(snapshot, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({
        "status": "OK",
        "articles": len(deduped),
        "failures": failures,
        "sources": snapshot["sources"],
        "output": str(OUTPUT),
    }, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
