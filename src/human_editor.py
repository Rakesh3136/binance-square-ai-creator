"""Next-level editorial engine for Binance Square.

Turns a researched draft into an original, mobile-first creator post without
inventing market facts. The engine deliberately varies hook, rhythm, structure,
emoji density, evidence framing and the final conversation prompt.
"""
from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

NEWS = Path("data/live/news_snapshot.json")
OUT = Path("data/live/editorial_polish.json")

STYLE_LIBRARY = {
    "NEWS_REACTION": {
        "emoji": "📰",
        "hooks": ["📰 The headline is interesting. The price reaction is the part I care about.", "📰 News first, price action second — here’s what I’m watching."],
        "questions": ["Does the chart confirm the headline for you?", "Bullish reaction or headline fade?"],
    },
    "CHART_STORY": {
        "emoji": "📊",
        "hooks": ["📊 The candle is loud. The structure underneath it is more interesting.", "📊 Before chasing the move, I’d look at this part of the chart."],
        "questions": ["Which level would you watch first?", "Would you wait for another candle here?"],
    },
    "VOLUME_STORY": {
        "emoji": "🔥",
        "hooks": ["🔥 Price got the attention. Volume is what made me stop scrolling.", "🔥 This move has participation behind it — now comes the interesting part."],
        "questions": ["Is volume confirming the move for you?", "Would you wait for follow-through or act on this signal?"],
    },
    "CHOICE": {
        "emoji": "👀",
        "hooks": ["👀 I’m not chasing this candle. I’m watching what happens next.", "👀 This is one of those moves where confirmation matters more than excitement."],
        "questions": ["Chase the move, wait for a pullback, or stay out?", "What would make you change your view here?"],
    },
    "BREAKOUT": {
        "emoji": "⚡",
        "hooks": ["⚡ Breakouts look obvious afterwards. The reaction here is what matters now.", "⚡ This is the point where a breakout can become a real move — or a trap."],
        "questions": ["Breakout or fakeout?", "Would you want another candle for confirmation?"],
    },
    "DATA_SURPRISE": {
        "emoji": "🔎",
        "hooks": ["🔎 One number here is more interesting than the headline move.", "🔎 The first thing I noticed wasn’t price — it was the data behind it."],
        "questions": ["Does this data change your read?", "Did you notice this before looking at the percentage move?"],
    },
    "COIN_VS_COIN": {
        "emoji": "⚔️",
        "hooks": ["⚔️ Side-by-side check: which chart is actually doing the work?", "⚔️ Two coins can pump at the same time. Their structures can still tell very different stories."],
        "questions": ["Which chart would you watch next?", "Which setup looks cleaner to you?"],
    },
    "UPDATE": {
        "emoji": "🔄",
        "hooks": ["🔄 Quick update — we have a little more information now.", "🔄 The market gave us another clue. Here’s what changed."],
        "questions": ["Did this change your read?", "What signal would you watch next?"],
    },
}

BANNED_CLICHES = [
    "in conclusion", "going forward", "it remains to be seen", "this highlights",
    "key takeaway", "notable factor", "clear shift", "market participants",
    "fresh check:", "quick market check:", "as we can see", "let's dive in",
    "this is the crypto story i'm watching right now:",
    "this is the crypto story i’m watching right now:",
]
GENERIC_QUESTIONS = {"what do you think?", "what do you think", "thoughts?", "thoughts", "any thoughts?", "agree?", "agree"}


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


def seed_for(text: str, style: str) -> int:
    raw = f"{style}|{text}|{datetime.now(timezone.utc).date().isoformat()}"
    return sum((i + 1) * ord(c) for i, c in enumerate(raw))


def pick(values: list[str], seed: int, offset: int = 0) -> str:
    return values[(seed + offset) % len(values)] if values else ""


def clean(s: str) -> str:
    return re.sub(r"[ \t]+", " ", str(s or "")).strip()


def symbol_from(draft: dict, text: str) -> str:
    for key in ("symbol", "primary_symbol"):
        value = str(draft.get(key) or "").upper().replace("USDT", "").strip()
        if re.fullmatch(r"[A-Z0-9]{2,15}", value):
            return value
    m = re.search(r"\$([A-Z][A-Z0-9]{1,14})\b", text.upper())
    return m.group(1) if m else ""


def normalized_style(value: str) -> str:
    return str(value or "").upper().replace("_", " ").replace("-", " ").strip()


def style_for(draft: dict, text: str, news: dict, seed: int) -> str:
    raw = normalized_style(draft.get("experiment_format") or draft.get("editorial_style") or "")
    if "NEWS" in raw or "HEADLINE" in raw:
        return "NEWS_REACTION"
    if "COIN VS" in raw or "COMPARISON" in raw:
        return "COIN_VS_COIN"
    if "VOLUME" in raw:
        return "VOLUME_STORY"
    if "BREAKOUT" in raw or "FAKEOUT" in raw:
        return "BREAKOUT"
    if "DATA" in raw:
        return "DATA_SURPRISE"
    if "UPDATE" in raw or "FOLLOW" in raw:
        return "UPDATE"
    if "CHART" in raw or "TARGET" in raw:
        return "CHART_STORY"
    visual = draft.get("visual_plan") or {}
    if isinstance(visual, dict) and str(visual.get("type") or "").lower() not in {"", "none", "text"}:
        return "CHART_STORY"
    choices = ["CHOICE", "VOLUME_STORY", "BREAKOUT", "DATA_SURPRISE"]
    return choices[seed % len(choices)]


def recent_styles(data: dict) -> set[str]:
    strategy = data.get("engagement_strategy") or {}
    counts = strategy.get("recent_style_counts") or {}
    if not isinstance(counts, dict):
        return set()
    return {normalized_style(k) for k in counts}


def choose_non_repeating_style(draft: dict, text: str, news: dict, data: dict, seed: int) -> str:
    preferred = style_for(draft, text, news, seed)
    recent = recent_styles(data)
    if normalized_style(preferred) not in recent:
        return preferred
    alternatives = ["CHOICE", "CHART_STORY", "VOLUME_STORY", "DATA_SURPRISE", "BREAKOUT", "UPDATE"]
    for i, candidate in enumerate(alternatives):
        if normalized_style(candidate) not in recent and candidate != preferred and (seed + i) % 2 == 0:
            return candidate
    return preferred


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
        title = clean(article.get("title") or article.get("headline"))
        if title:
            return {"source": clean(article.get("source") or ""), "title": title[:220], "url": clean(article.get("url") or ""), "published_at": clean(article.get("published_at") or "")}
    return {}


def strip_cliches(text: str) -> str:
    for phrase in BANNED_CLICHES:
        text = re.sub(re.escape(phrase), "", text, flags=re.I)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def remove_questions(text: str) -> str:
    lines = text.splitlines()
    while lines and lines[-1].strip().endswith("?"):
        lines.pop()
    return "\n".join(lines).strip()


def extract_fact_lines(text: str) -> list[str]:
    lines = [clean(x) for x in text.splitlines() if clean(x)]
    skip = {"key scenario levels:", "key levels:", "bullish, bearish, or wait?"}
    return [x for x in lines if x.lower() not in skip and not re.fullmatch(r"[-•*]+", x)]


def compact_levels(text: str) -> str:
    lines = text.splitlines()
    level_lines = [x for x in lines if re.search(r"\b(support|resistance|target|invalidation|sl)\b", x, re.I)]
    if len(level_lines) < 3:
        return text
    keep, inserted = [], False
    for line in lines:
        if re.search(r"\b(support|resistance|target|invalidation|sl)\b", line, re.I):
            if not inserted:
                parts = [re.sub(r"^[•*\-]\s*", "", x).rstrip(".") for x in level_lines]
                keep.append("📍 " + " • ".join(parts[:5]))
                inserted = True
        else:
            keep.append(line)
    return "\n".join(keep)


def make_body(original: str, style: str, symbol: str, news: dict, seed: int) -> tuple[str, bool]:
    text = compact_levels(strip_cliches(original))
    text = remove_questions(text)
    lines = extract_fact_lines(text)
    if not lines:
        return "", False
    first = lines[0]
    if first.lower().startswith(("$" + symbol.lower(), "current price", "fresh check", "quick market check")):
        lines = lines[1:] or lines

    profile = STYLE_LIBRARY[style]
    hook = pick(profile["hooks"], seed)
    facts = [line for line in lines if len(line) < 260][:3]
    body = hook + (("\n\n" + "\n".join(facts)) if facts else "")

    news_used = False
    if news and style == "NEWS_REACTION":
        marker = f"📰 {news['source']}: {news['title']}" if news.get("source") else f"📰 {news['title']}"
        if len(body) + len(marker) + 2 <= 720:
            body += "\n\n" + marker
            news_used = True

    if symbol and len(body) < 620:
        pov = pick([
            f"My focus here is the reaction, not the first spike on ${symbol}.",
            f"I’d rather see confirmation on ${symbol} than guess the next candle.",
            f"For ${symbol}, the next reaction matters more to me than the headline percentage.",
        ], seed, 7)
        if pov.lower() not in body.lower():
            body += "\n\n" + pov
    return body, news_used


def final_question(style: str, symbol: str, seed: int) -> str:
    question = pick(STYLE_LIBRARY[style]["questions"], seed, 13)
    if symbol and question.lower() in {"which level would you watch first?", "which chart would you watch next?"}:
        return question[:-1] + f" on ${symbol}?"
    return question


def enforce_one_question(text: str, question: str) -> str:
    return remove_questions(text).rstrip(" .") + "\n\n" + question


def mobile_trim(text: str, question: str, limit: int = 820) -> str:
    if len(text) <= limit:
        return text
    base = remove_questions(text)
    room = max(350, limit - len(question) - 2)
    base = base[:room]
    cut = max(base.rfind("\n\n"), base.rfind(". "))
    if cut >= 300:
        base = base[:cut + (2 if base[cut:cut + 2] == ". " else 0)]
    else:
        base = base.rsplit(" ", 1)[0]
    return enforce_one_question(base.strip(), question)


def main() -> int:
    draft_path = Path(os.environ.get("DRAFT_PATH", ""))
    if not draft_path.exists():
        raise SystemExit("DRAFT_PATH is missing")

    data = load(draft_path, {})
    draft = data.setdefault("draft", {})
    original = clean(draft.get("post") or draft.get("text") or "")
    if not original:
        raise SystemExit("Draft has no post text")

    news = fresh_news(load(NEWS, {}))
    symbol = symbol_from(draft, original)
    seed = seed_for(original, str(draft.get("editorial_style") or ""))
    style = choose_non_repeating_style(draft, original, news, data, seed)
    body, news_used = make_body(original, style, symbol, news, seed)
    if not body:
        raise SystemExit("Editorial engine produced empty body")

    question = final_question(style, symbol, seed)
    text = mobile_trim(enforce_one_question(body, question), question)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()

    if text.count("?") != 1 or any(q in text.lower() for q in GENERIC_QUESTIONS):
        text = enforce_one_question(text, question)

    emoji = STYLE_LIBRARY[style]["emoji"]
    draft["post"] = text
    draft["text"] = text
    draft["editorial_style"] = style.lower()
    draft["human_editor"] = {
        "status": "POLISHED",
        "version": "human-editor-v5-next-level",
        "style": style,
        "emoji": emoji,
        "emoji_policy": "light_contextual_use",
        "fresh_news_used": news_used,
        "conversation_question": question,
        "mobile_format": "hook_story_evidence_pov_question",
        "question_count": 1,
        "anti_template": True,
        "fact_policy": "preserve_researched_facts; no new market claims",
    }
    data["editorial_style_version"] = "human-editor-v5-next-level"
    data["news_context"] = news

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"status": "HUMAN_EDITOR_APPLIED", "version": "human-editor-v5-next-level", "style": style, "emoji": emoji, "fresh_news": news_used, "question": question, "characters": len(text), "question_count": text.count("?")}, indent=2, ensure_ascii=False), encoding="utf-8")
    draft_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"status": "HUMAN_EDITOR_APPLIED", "characters": len(text), "style": style, "emoji": emoji, "fresh_news": news_used, "question": question, "question_count": text.count("?")}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
