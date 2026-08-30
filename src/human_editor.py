"""Final deterministic editorial polish for Binance Square posts.

It never invents market facts. It only improves mobile readability, varies the human tone,
and uses a fresh existing news snapshot when appropriate.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

NEWS = Path("data/live/news_snapshot.json")
OUT = Path("data/live/editorial_polish.json")
EMOJIS = {
    "BREAKING NEWS + MARKET IMPACT": "🚨",
    "TOP GAINER/LOSER": "📈",
    "VOLUME SURGE": "🔥",
    "NEW LISTING WATCH": "👀",
    "TRADINGVIEW CHART BREAKDOWN": "📊",
    "BREAKOUT/FAKEOUT": "⚡",
    "TARGET MAP": "🎯",
    "NEWS + CHART": "📰",
    "COIN VS COIN": "⚔️",
    "DATA SURPRISE": "🔎",
    "LIQUIDATION STORY": "💥",
    "FOLLOW-UP/UPDATE": "🔄",
    "MARKET CHECK": "👀",
}


def load(path: Path):
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except Exception:
        return {}


def fresh_news(news: dict) -> dict:
    generated = news.get("generated_at")
    try:
        age = (datetime.now(timezone.utc) - datetime.fromisoformat(str(generated).replace("Z", "+00:00"))).total_seconds()
    except Exception:
        return {}
    if age < 0 or age > 48 * 3600:
        return {}
    for article in news.get("articles") or []:
        if not isinstance(article, dict):
            continue
        title = re.sub(r"<[^>]+>", " ", str(article.get("title") or "")).strip()
        if not title:
            continue
        image = re.search(r'<img[^>]+src=[\"\']([^\"\']+)', str(article.get("summary") or ""), re.I)
        return {
            "source": str(article.get("source") or "Unknown"),
            "title": title[:180],
            "url": str(article.get("url") or ""),
            "image_url": image.group(1) if image else "",
            "published_at": str(article.get("published_at") or ""),
        }
    return {}


def ensure_question(text: str) -> str:
    if "?" in text:
        return text
    questions = [
        "Bullish follow-through or a pullback first?",
        "Would you wait for confirmation or watch the breakout live?",
        "Which level matters most to you here?",
        "Breakout, fakeout, or wait-and-see?",
    ]
    idx = sum(ord(c) for c in text) % len(questions)
    return text.rstrip() + "\n\n" + questions[idx]


def main() -> int:
    import os

    draft_path = Path(os.environ.get("DRAFT_PATH", ""))
    if not draft_path.exists():
        raise SystemExit("DRAFT_PATH is missing")
    data = load(draft_path)
    draft = data.setdefault("draft", {})
    text = str(draft.get("post") or draft.get("text") or "").strip()
    if not text:
        raise SystemExit("Draft has no post text")

    style = str(draft.get("editorial_style") or "").upper().strip()
    if style in {"", "NORMALIZED", "LOCAL_FALLBACK"}:
        style = str(draft.get("experiment_format") or data.get("engagement_strategy", {}).get("experiment", {}).get("format") or "MARKET CHECK").upper().strip()
    if style not in EMOJIS:
        style = "MARKET CHECK"

    emoji = EMOJIS[style]
    if not re.search(r"[\U0001F300-\U0001FAFF]", text):
        text = f"{emoji} {text}"

    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = ensure_question(text)

    news = fresh_news(load(NEWS))
    news_style = style in {"BREAKING NEWS + MARKET IMPACT", "NEWS + CHART"}
    if news and news_style:
        marker = "📰 " + news["source"] + ": " + news["title"]
        if marker.lower() not in text.lower():
            text = text.rstrip() + "\n\n" + marker

    if len(text) > 900:
        shortened = text[:900]
        cut = max(shortened.rfind("\n\n"), shortened.rfind(". "))
        text = shortened[:cut if cut > 500 else 900].rstrip()
        if "?" not in text:
            text = ensure_question(text)

    draft["post"] = text
    draft["text"] = text
    draft["editorial_style"] = style.lower().replace(" ", "_")
    draft["human_editor"] = {
        "status": "POLISHED",
        "emoji": emoji,
        "fresh_news_used": bool(news and news_style),
        "style": style,
    }
    data["editorial_style_version"] = "human-editor-v2"
    data["news_context"] = news
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"status":"HUMAN_EDITOR_APPLIED","news":news,"style":style,"emoji":emoji}, indent=2, ensure_ascii=False), encoding="utf-8")
    draft_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"status":"HUMAN_EDITOR_APPLIED","characters":len(text),"style":style,"emoji":emoji,"fresh_news":bool(news and news_style)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
