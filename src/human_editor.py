"""Creator 5.2 final editorial layer.
Preserves verified facts, removes unsupported cashtags, improves readability, and
keeps news stories grounded in their selected source.
"""
from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NEWS = ROOT / "data/live/news_snapshot.json"
CONTEXT = ROOT / "data/live/publication_context.json"
OUT = ROOT / "data/live/editorial_polish.json"

STYLE_QUESTIONS = {
    "NEWS": [
        "Is the market confirming this catalyst, or fading it?",
        "Would you wait for price confirmation before treating the headline as bullish?",
        "Is this a real repricing event or temporary headline noise?",
        "Which asset is giving the clearest confirmation?"
    ],
    "CHART": [
        "Breakout or fakeout?",
        "Which level would you watch first?",
        "Would you wait for confirmation on the next candle?"
    ],
    "VOLUME": [
        "Is volume confirming the move?",
        "Would you wait for follow-through?"
    ],
    "CHOICE": [
        "Chase, pullback, or wait?",
        "What would change your view?"
    ],
    "BREAKOUT": [
        "Breakout or fakeout?",
        "Would you wait for another candle?"
    ],
    "DATA": [
        "Does this data change your read?",
        "Which signal would you trust most here?"
    ],
    "UPDATE": [
        "Did this change your read?",
        "What signal would you watch next?"
    ],
}


def load(path: Path, default=None):
    if default is None:
        default = {}
    if not path.exists():
        return default
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, type(default)) else default
    except Exception:
        return default


def clean(value) -> str:
    return re.sub(r"[ \t]+", " ", str(value or "")).strip()


def normalize_symbol(value) -> str:
    symbol = str(value or "").upper().replace("$", "").replace("BINANCE:", "").strip()
    symbol = re.sub(r"USDT$", "", symbol)
    return symbol if re.fullmatch(r"[A-Z0-9]{1,15}", symbol) else ""


def get_symbol(draft: dict, text: str, context: dict) -> str:
    for value in (
        context.get("symbol"),
        draft.get("symbol"),
        draft.get("primary_symbol"),
    ):
        symbol = normalize_symbol(value)
        if symbol:
            return symbol
    match = re.search(r"\$([A-Z][A-Z0-9]{0,14})\b", text.upper())
    return match.group(1) if match else ""


def choose_style(draft: dict, selected: dict) -> str:
    raw = str(
        draft.get("experiment_format")
        or draft.get("editorial_style")
        or selected.get("category")
        or ""
    ).upper()
    if selected.get("news_title"):
        return "NEWS"
    if "NEWS" in raw or "HEADLINE" in raw:
        return "NEWS"
    if "VOLUME" in raw:
        return "VOLUME"
    if "BREAKOUT" in raw or "FAKEOUT" in raw:
        return "BREAKOUT"
    if "DATA" in raw:
        return "DATA"
    if "UPDATE" in raw or "FOLLOW" in raw:
        return "UPDATE"
    if "CHOICE" in raw:
        return "CHOICE"
    return "CHART" if "CHART" in raw else "CHOICE"


def find_selected_news(selected: dict, context: dict) -> dict:
    wanted = clean(selected.get("news_title") or context.get("news_title"))
    articles = load(NEWS, {}).get("articles") or []
    for article in articles:
        if not isinstance(article, dict):
            continue
        title = clean(article.get("title") or article.get("headline"))
        if title and (not wanted or title == wanted):
            return {
                "source": clean(article.get("source")),
                "title": title[:240],
                "url": clean(article.get("url")),
                "published_at": clean(article.get("published_at")),
                "symbols": article.get("symbols") or [],
            }
    return {}


def sanitize_cashtags(lines, allowed):
    sanitized = []
    for line in lines:
        cashtags = {
            m.upper()
            for m in re.findall(r"\$([A-Z][A-Z0-9]{0,14})\b", line.upper())
        }
        if cashtags and any(tag not in allowed for tag in cashtags):
            continue
        sanitized.append(line)
    return sanitized


def polish_repetitions(text: str) -> str:
    text = re.sub(
        r"\bSpot volume is (\$[0-9][^,.\n]*?) spot volume\b",
        r"Spot volume is \1",
        text,
        flags=re.I,
    )
    text = re.sub(
        r"\b(\$[0-9][0-9.,]*[KMB]?)\s+\1\b",
        r"\1",
        text,
        flags=re.I,
    )
    text = re.sub(
        r"\b(the market market|price price|volume volume)\b",
        lambda match: match.group(1).split()[0],
        text,
        flags=re.I,
    )
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def make_post(draft: dict, report: dict):
    context = load(CONTEXT, {})
    selected = report.get("selected_editorial_lane") or report.get("selected_opportunity") or {}
    original = clean(draft.get("post") or draft.get("text") or "")
    if not original:
        raise SystemExit("Draft has no post text")

    symbol = get_symbol(draft, original, context)
    if not symbol:
        raise SystemExit("Editorial layer: primary symbol missing")

    style = choose_style(draft, selected)
    news = find_selected_news(selected, context)

    lines = [
        clean(line)
        for line in original.splitlines()
        if clean(line)
    ]
    lines = [
        line
        for line in lines
        if line.lower()
        not in {
            "key levels:",
            "key scenario levels:",
            "fresh check:",
            "quick market check:",
            "this is the crypto story i'm watching right now:",
            "this is the crypto story i’m watching right now:",
        }
    ]

    allowed = {symbol}
    for raw in selected.get("news_symbols") or []:
        normalized = normalize_symbol(raw)
        if normalized:
            allowed.add(normalized)
    for raw in context.get("news_symbols") or []:
        normalized = normalize_symbol(raw)
        if normalized:
            allowed.add(normalized)

    news_title = clean(selected.get("news_title") or context.get("news_title"))
    if "gold" in news_title.lower():
        allowed.add("XAUUSD")
    if "silver" in news_title.lower():
        allowed.add("XAGUSD")

    lines = sanitize_cashtags(lines, allowed)

    if style == "NEWS" and news:
        headline = f"🚨 {news['title']}"
        source_line = f"Source: {news['source']}" if news.get("source") else ""
        body_lines = [headline]
        if source_line:
            body_lines.append(source_line)
        for line in lines:
            if line.lower() == news["title"].lower():
                continue
            if source_line and line.lower() == source_line.lower():
                continue
            if len(line) >= 18:
                body_lines.append(line)
        body_lines = body_lines[:9]
    else:
        body_lines = (
            lines[:7]
            if lines
            else ["$" + symbol + " is giving the market a signal worth watching."]
        )

    question_pool = STYLE_QUESTIONS.get(style, STYLE_QUESTIONS["CHOICE"])
    hour_key = datetime.now(timezone.utc).strftime("%Y-%m-%d-%H")
    question_index = sum(ord(char) for char in (symbol + style + hour_key)) % len(question_pool)
    question = question_pool[question_index]

    if style == "NEWS" and "$" + symbol not in question:
        question = question.rstrip("?") + " for $" + symbol + "?"

    body = "\n\n".join(body_lines)
    body = re.sub(r"\?+", ".", body).strip(" .")
    text = polish_repetitions(body + "\n\n" + question)

    if text.count("?") != 1:
        text = re.sub(r"\?+", ".", text).rstrip(".")
        text += "\n\n" + question

    return text[:2200], style, question, news


def main():
    draft_path = Path(os.environ.get("DRAFT_PATH", ""))
    if not draft_path.exists():
        raise SystemExit("DRAFT_PATH is missing")

    report = load(draft_path, {})
    draft = report.setdefault("draft", {})
    text, style, question, news = make_post(draft, report)

    draft.update(
        {
            "post": text,
            "text": text,
            "editorial_style": style.lower(),
            "human_editor": {
                "status": "POLISHED",
                "version": "human-editor-v12",
                "style": style,
                "question": question,
                "fresh_news_used": bool(news),
                "question_count": 1,
                "fact_policy": "preserve supplied evidence only",
                "repetition_cleanup": True,
                "unsupported_cashtag_filter": True,
            },
        }
    )

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(
        json.dumps(
            {
                "status": "HUMAN_EDITOR_APPLIED",
                "version": "human-editor-v12",
                "style": style,
                "characters": len(text),
                "question": question,
                "fresh_news": bool(news),
                "repetition_cleanup": True,
                "unsupported_cashtag_filter": True,
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    draft_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print(
        json.dumps(
            {
                "status": "HUMAN_EDITOR_APPLIED",
                "version": "human-editor-v12",
                "characters": len(text),
                "style": style,
                "question": question,
                "fresh_news": bool(news),
            }
        )
    )


if __name__ == "__main__":
    main()
