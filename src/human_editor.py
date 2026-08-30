"""Human-first editorial layer for Binance Square.

This layer does not invent market facts. It turns an already researched draft into a
mobile-first, conversational post with controlled style rotation, natural emoji use,
stronger hooks and one easy conversation prompt.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

NEWS = Path("data/live/news_snapshot.json")
OUT = Path("data/live/editorial_polish.json")

STYLE_EMOJI = {
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

HOOKS = {
    "BREAKING NEWS + MARKET IMPACT": [
        "🚨 This is the crypto headline I’m watching right now.",
        "🚨 The headline matters — but the price reaction matters more.",
    ],
    "TOP GAINER/LOSER": [
        "👀 One mover is getting hard to ignore.",
        "📈 Quick market check — this move deserves a closer look.",
    ],
    "VOLUME SURGE": [
        "🔥 The volume is the part that caught my eye.",
        "🔥 Price gets attention. Volume tells me whether people are actually showing up.",
    ],
    "NEW LISTING WATCH": [
        "👀 New-market watch: here’s the part I’d keep an eye on.",
        "👀 Fresh listing, fresh volatility. Let’s see what the market does next.",
    ],
    "TRADINGVIEW CHART BREAKDOWN": [
        "📊 Forget the noise for a second — look at the chart.",
        "📊 Here’s the chart detail I think is easiest to miss.",
    ],
    "BREAKOUT/FAKEOUT": [
        "⚡ This is where the chart gets interesting.",
        "⚡ Breakouts are easy to call after the fact. The reaction here is what matters.",
    ],
    "TARGET MAP": [
        "🎯 Let’s map the levels before guessing the next move.",
        "🎯 The important part isn’t the prediction — it’s the levels.",
    ],
    "NEWS + CHART": [
        "📰 The headline caught my eye. The chart is what I checked next.",
        "📰 News first, price action second — this is the combination I’m watching.",
    ],
    "COIN VS COIN": [
        "⚔️ Two charts. One simple question: which one has the stronger setup?",
        "⚔️ A quick side-by-side check is more useful than a loud prediction.",
    ],
    "DATA SURPRISE": [
        "🔎 Here’s the number that surprised me.",
        "🔎 The headline is one thing. This data point is more interesting.",
    ],
    "LIQUIDATION STORY": [
        "💥 This move has a lot more going on than a green/red candle.",
        "💥 Volatility just changed the conversation around this coin.",
    ],
    "FOLLOW-UP/UPDATE": [
        "🔄 Quick follow-up: here’s what changed.",
        "🔄 Update time — the market has given us a little more information.",
    ],
    "MARKET CHECK": [
        "👀 Quick market check — this is the setup I’m watching.",
        "👀 Something interesting is happening here. Let’s keep it simple.",
    ],
}

QUESTION_BANK = {
    "BREAKING NEWS + MARKET IMPACT": ["Bullish catalyst or temporary headline noise?", "Did the price reaction confirm the headline for you?"],
    "TOP GAINER/LOSER": ["Would you chase this move or wait for confirmation?", "Is this strength real, or already too extended?"],
    "VOLUME SURGE": ["Would you trust the volume spike yet, or wait for another candle?", "Is volume confirming the move for you?"],
    "NEW LISTING WATCH": ["Would you watch the first pullback or the breakout?", "Too early to judge, or already interesting?"],
    "TRADINGVIEW CHART BREAKDOWN": ["Which level would you watch first?", "What would make this chart bullish for you?"],
    "BREAKOUT/FAKEOUT": ["Breakout, fakeout, or wait?", "Would you want another candle for confirmation?"],
    "TARGET MAP": ["Which level matters most to you here?", "Would you map the upside or downside first?"],
    "NEWS + CHART": ["Does the chart agree with the headline?", "Bullish reaction or headline fade?"],
    "COIN VS COIN": ["Which one would you watch next?", "Which chart looks cleaner to you?"],
    "DATA SURPRISE": ["Did you notice this number before the price move?", "Does this data change your read of the move?"],
    "LIQUIDATION STORY": ["Reversal or continuation from here?", "Would you wait for the volatility to cool down?"],
    "FOLLOW-UP/UPDATE": ["Did this change your view of the setup?", "What would you watch next?"],
    "MARKET CHECK": ["Bullish, bearish, or wait-and-see?", "Would you enter now or wait for confirmation?"],
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


def strategy_format(data: dict, draft: dict) -> str:
    strategy = data.get("engagement_strategy") or {}
    experiment = strategy.get("experiment") or {}
    raw = draft.get("experiment_format") or experiment.get("format") or draft.get("editorial_style") or "MARKET CHECK"
    raw = str(raw).upper().replace("_", " ").strip()
    aliases = {
        "BREAKOUT OR FAKEOUT": "BREAKOUT/FAKEOUT",
        "NEWS REACTION": "NEWS + CHART",
        "CHART CHALLENGE": "TRADINGVIEW CHART BREAKDOWN",
        "TOP MOVERS": "TOP GAINER/LOSER",
    }
    return aliases.get(raw, raw if raw in STYLE_EMOJI else "MARKET CHECK")


def recent_styles(data: dict) -> list[str]:
    strategy = data.get("engagement_strategy") or {}
    counts = strategy.get("recent_style_counts") or {}
    if not isinstance(counts, dict):
        return []
    return [str(k).upper().replace("_", " ") for k, _ in sorted(counts.items(), key=lambda x: x[1], reverse=True)]


def choose_style(data: dict, draft: dict) -> str:
    preferred = strategy_format(data, draft)
    recent = recent_styles(data)
    # If the chosen lane was recently dominant, deliberately rotate to another
    # valid lane instead of repeatedly emitting the same prose skeleton.
    if preferred not in recent[:2]:
        return preferred
    candidates = [
        "TRADINGVIEW CHART BREAKDOWN", "DATA SURPRISE", "COIN VS COIN",
        "BREAKOUT/FAKEOUT", "VOLUME SURGE", "NEWS + CHART", "MARKET CHECK",
    ]
    for candidate in candidates:
        if candidate != preferred and candidate not in recent[:2]:
            return candidate
    return preferred


def pick(seq, seed: str) -> str:
    if not seq:
        return ""
    return seq[sum(ord(c) for c in seed) % len(seq)]


def extract_symbol(draft: dict, text: str) -> str:
    for value in (draft.get("symbol"), draft.get("primary_symbol")):
        if value:
            return str(value).upper().replace("USDT", "")
    match = re.search(r"\$([A-Z0-9]{2,15})\b", text.upper())
    return match.group(1) if match else ""


def has_question(text: str) -> bool:
    return "?" in text


def remove_existing_question(text: str) -> str:
    lines = text.strip().splitlines()
    while lines and lines[-1].strip().endswith("?"):
        lines.pop()
    return "\n".join(lines).strip()


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

    style = choose_style(data, draft)
    symbol = extract_symbol(draft, text)
    seed = f"{symbol}:{text}:{datetime.now(timezone.utc).date().isoformat()}"
    hook = pick(HOOKS.get(style, HOOKS["MARKET CHECK"]), seed)
    emoji = STYLE_EMOJI.get(style, "👀")

    # Remove generic AI-style lead-ins when present; keep the researched body.
    generic_leads = (
        "quick market check:", "fresh check:", "this is the crypto story i’m watching right now:",
        "this is the crypto story i'm watching right now:", "quick update:",
    )
    lines = text.splitlines()
    while lines and lines[0].strip().lower() in generic_leads:
        lines.pop(0)
    body = "\n".join(lines).strip()
    body = remove_existing_question(body)

    # If the model already supplied a strong hook, do not stack another one.
    first_line = body.splitlines()[0].strip() if body else ""
    if not first_line or first_line.lower().startswith(("$" + symbol.lower(), "the latest", "current price")):
        body = hook + ("\n\n" + body if body else "")
    elif not re.search(r"[\U0001F300-\U0001FAFF]", first_line):
        body = f"{emoji} {body}"

    # Add a small conversational bridge without adding any market claim.
    if symbol and "my read" not in body.lower() and len(body) < 600:
        bridge = pick([
            "I’m not chasing the candle — I’m watching the reaction here.",
            "For me, the next reaction is more important than the headline move.",
            "That’s the part I’d keep on the radar rather than guessing ahead.",
        ], seed + ":bridge")
        body = body.rstrip() + "\n\n" + bridge

    question = pick(QUESTION_BANK.get(style, QUESTION_BANK["MARKET CHECK"]), seed + ":question")
    if has_question(body):
        body = remove_existing_question(body)
    text = body.rstrip() + "\n\n" + question

    # Mobile readability: short paragraphs, no wall of text, hard safety limit.
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    if len(text) > 850:
        shortened = text[:850]
        cut = max(shortened.rfind("\n\n"), shortened.rfind(". "))
        text = shortened[:cut if cut > 500 else 850].rstrip()
        text = remove_existing_question(text) + "\n\n" + question

    news = fresh_news(load(NEWS))
    news_used = False
    news_style = style in {"BREAKING NEWS + MARKET IMPACT", "NEWS + CHART"}
    if news and news_style:
        marker = f"📰 {news['source']}: {news['title']}"
        if marker.lower() not in text.lower() and len(text) + len(marker) + 2 <= 900:
            text = text.rstrip() + "\n\n" + marker
            # Keep exactly one interaction question at the end.
            text = remove_existing_question(text) + "\n\n" + question
            news_used = True

    draft["post"] = text
    draft["text"] = text
    draft["editorial_style"] = style.lower().replace(" ", "_")
    draft["human_editor"] = {
        "status": "POLISHED",
        "version": "human-editor-v3",
        "emoji": emoji,
        "style": style,
        "fresh_news_used": news_used,
        "conversation_question": question,
        "rotation_applied": True,
        "mobile_format": "short_paragraphs",
    }
    data["editorial_style_version"] = "human-editor-v3"
    data["news_context"] = news
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({
        "status": "HUMAN_EDITOR_APPLIED",
        "version": "human-editor-v3",
        "style": style,
        "emoji": emoji,
        "fresh_news": news_used,
        "question": question,
    }, indent=2, ensure_ascii=False), encoding="utf-8")
    draft_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({
        "status": "HUMAN_EDITOR_APPLIED",
        "characters": len(text),
        "style": style,
        "emoji": emoji,
        "fresh_news": news_used,
        "question": question,
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
