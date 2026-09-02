import json
import re
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from datetime import timedelta
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
MAX_NEWS_AGE_HOURS = 36

KNOWN_ASSET_NAMES={
    'bitcoin':'BTC','ethereum':'ETH','solana':'SOL','bnb':'BNB','xrp':'XRP','dogecoin':'DOGE','cardano':'ADA',
    'tron':'TRX','avalanche':'AVAX','chainlink':'LINK','sui':'SUI','toncoin':'TON','polkadot':'DOT','litecoin':'LTC',
    'shiba inu':'SHIB','pepe':'PEPE','uniswap':'UNI','aave':'AAVE','curve':'CRV','arbitrum':'ARB','optimism':'OP',
    'aptos':'APT','near protocol':'NEAR','cosmos':'ATOM','injective':'INJ','sei':'SEI','celestia':'TIA',
    'hedera':'HBAR','stellar':'XLM','secret network':'SCRT','terra classic':'LUNC','gold':'XAUUSD','silver':'XAGUSD',
    'ondo':'ONDO','hyperliquid':'HYPE','uniswap':'UNI','chainlink':'LINK','aave':'AAVE','curve finance':'CRV'
}

def extract_symbols(text: str) -> list[str]:
    found=[]
    upper=(text or '').upper()
    for m in re.findall(r'\\$([A-Z][A-Z0-9]{0,14})\\b',upper):
        if m not in found: found.append(m)
    lower=(text or '').lower()
    for name,sym in KNOWN_ASSET_NAMES.items():
        if name in lower and sym not in found: found.append(sym)
    return found[:5]

KEYWORD_WEIGHTS={
    'hack':24,'exploit':24,'breach':22,'etf':20,'sec':18,'fed':18,'rate':14,'inflation':14,
    'tariff':12,'regulation':16,'lawsuit':16,'listing':18,'delist':20,'launch':12,'upgrade':12,
    'partnership':10,'whale':12,'liquidation':16,'airdrop':14,'unlock':14,'approval':18,
    'ban':20,'reserve':12,'treasury':12,'stablecoin':12,'acquisition':12,'integration':12,
    'mainnet':12,'protocol':8,'funding':8,'institutional':10
}


def score_article(title: str, summary: str, category: str, published_at: str | None) -> float:
    text = (title + ' ' + summary).lower()
    score = 30.0
    for keyword, weight in KEYWORD_WEIGHTS.items():
        if keyword in text:
            score += weight
    if category.endswith('_official'):
        score += 8.0
    try:
        dt = datetime.fromisoformat(str(published_at).replace('Z','+00:00')) if published_at else None
        if dt:
            age = max(0.0, (datetime.now(timezone.utc)-dt.astimezone(timezone.utc)).total_seconds()/60.0)
            score += max(0.0, 20.0-age/9.0)
    except Exception:
        pass
    return round(min(100.0, score),2)


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
        dt=parse_date(pub)
        if dt:
            try:
                age=(datetime.now(timezone.utc)-datetime.fromisoformat(dt)).total_seconds()/3600
                if age < -1 or age > MAX_NEWS_AGE_HOURS:
                    continue
            except Exception:
                continue
        else:
            continue
        items.append({
            "source": source,
            "category": category,
            "title": title,
            "url": link,
            "summary": description[:1200],
            "published_at": parse_date(pub),
            "symbols": extract_symbols(title + ' ' + description),
            "news_score": score_article(title, description[:1200], category, dt),
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
        "articles": sorted(deduped[:80], key=lambda x: (float(x.get('news_score') or 0), str(x.get('published_at') or '')), reverse=True),
        "failures": failures,
        "max_age_hours": MAX_NEWS_AGE_HOURS,
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
