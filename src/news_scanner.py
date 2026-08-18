import json
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

OUTPUT = Path("data/live/news_snapshot.json")
FEEDS = [
    ("CoinDesk", "https://www.coindesk.com/arc/outboundfeeds/rss/"),
    ("Cointelegraph", "https://cointelegraph.com/rss"),
]
MAX_ITEMS_PER_FEED = 20


def fetch(url: str) -> bytes:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0 (compatible; BinanceSquareAI/1.0)"},
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


def parse_feed(source: str, payload: bytes) -> list[dict]:
    root = ET.fromstring(payload)
    items = []
    for item in root.findall(".//item")[:MAX_ITEMS_PER_FEED]:
        title = text(item.find("title"))
        link = text(item.find("link"))
        description = text(item.find("description"))
        pub = text(item.find("pubDate"))
        if not title or not link:
            continue
        items.append({
            "source": source,
            "title": title,
            "url": link,
            "summary": description[:1200],
            "published_at": parse_date(pub),
        })
    return items


def main() -> None:
    articles: list[dict] = []
    failures: list[dict] = []

    for source, url in FEEDS:
        try:
            articles.extend(parse_feed(source, fetch(url)))
        except Exception as exc:
            failures.append({"source": source, "error": str(exc)})

    # De-duplicate by canonical URL while keeping source metadata.
    seen = set()
    deduped = []
    for article in articles:
        if article["url"] in seen:
            continue
        seen.add(article["url"])
        deduped.append(article)

    snapshot = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "sources": [name for name, _ in FEEDS],
        "articles": deduped[:40],
        "failures": failures,
        "note": "RSS items are discovery leads. The AI must verify material claims against primary sources before publication.",
    }

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(snapshot, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({
        "status": "OK",
        "articles": len(deduped),
        "failures": failures,
        "output": str(OUTPUT),
    }, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
