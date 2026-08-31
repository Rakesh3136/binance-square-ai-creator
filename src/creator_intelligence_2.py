"""Creator Intelligence 3.0: human editorial layer.

Runs after draft generation and before publication. It keeps verified market facts
untouched while improving voice, rhythm, emoji use, originality and conversation.
It never fabricates engagement, news, prices, sources, outcomes or comments.
"""
from __future__ import annotations

import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORT_DIR = ROOT / "data/reports"
LOG = ROOT / "analytics/publication_log.jsonl"
OUT = ROOT / "data/live/creator_intelligence_2.json"
IDENTITY = ROOT / "data/intelligence/creator_identity.json"

GENERIC_QUESTIONS = {"what do you think?", "what do you think", "thoughts?", "any thoughts?", "agree?"}
FILLER = {"key takeaway", "notable factor", "clear shift", "market participants", "in conclusion", "it remains to be seen", "this highlights", "going forward"}
STYLE_EMOJIS = {"NEWS REACTION": "📰", "DATA SURPRISE": "📊", "CHART CHALLENGE": "👀", "BREAKOUT OR FAKEOUT": "🚨", "LIQUIDATION STORY": "⚠️", "COIN VS COIN": "⚔️", "TOP MOVERS": "🔥", "CHOICE": "🎯", "QUICK OBSERVATION": "🔎"}


def load(path: Path, default):
    if not path.exists():
        return default
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, type(default)) else default
    except Exception:
        return default


def latest_report():
    reports = sorted(REPORT_DIR.glob("*-multi-agent.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    return reports[0] if reports else None


def recent_publications(limit=50):
    rows = []
    if not LOG.exists():
        return rows
    for line in LOG.read_text(encoding="utf-8").splitlines()[-600:]:
        try:
            row = json.loads(line)
            if isinstance(row, dict):
                rows.append(row)
        except Exception:
            pass
    return rows[-limit:]


def words(text):
    return re.findall(r"[a-z0-9$%']+", str(text).lower())


def shingles(text, n=4):
    w = words(text)
    return {" ".join(w[i:i+n]) for i in range(max(0, len(w)-n+1))}


def overlap(a, b):
    sa, sb = shingles(a), shingles(b)
    return len(sa & sb) / max(1, min(len(sa), len(sb))) if sa and sb else 0.0


def get_post(report):
    draft = report.get("draft") or {}
    if not isinstance(draft, dict):
        draft = {}
    return draft, str(draft.get("post") or draft.get("text") or "").strip()


def infer_symbol(report, post):
    selected = report.get("selected_editorial_lane") or {}
    raw = str(selected.get("symbol") or "")
    m = re.search(r"\b([A-Z0-9]{2,12})USDT\b", raw.upper())
    if m:
        return m.group(1)
    m = re.search(r"\$([A-Z][A-Z0-9]{1,11})\b", post.upper())
    return m.group(1) if m else ""


def style_of(report):
    draft = report.get("draft") or {}
    raw = str(draft.get("experiment_format") or draft.get("editorial_style") or "").upper()
    if "NEWS" in raw: return "NEWS REACTION"
    if "CHART" in raw: return "CHART CHALLENGE"
    if "BREAKOUT" in raw or "FAKEOUT" in raw: return "BREAKOUT OR FAKEOUT"
    if "LIQUID" in raw: return "LIQUIDATION STORY"
    if "DATA" in raw: return "DATA SURPRISE"
    if "COIN" in raw: return "COIN VS COIN"
    if "TOP" in raw or "GAIN" in raw or "MOVER" in raw: return "TOP MOVERS"
    return "CHOICE"


def clean_filler(text):
    for phrase in FILLER:
        text = re.sub(r"\b" + re.escape(phrase) + r"\b[:,]?", "", text, flags=re.I)
    return re.sub(r"[ \t]{2,}", " ", text)


def add_human_rhythm(text):
    text = text.replace("\r", "").strip()
    lines = [re.sub(r"\s+", " ", x.strip()) for x in text.splitlines() if x.strip()]
    out = []
    for line in lines:
        if len(line) > 190 and ". " in line:
            out.extend([p.strip() for p in re.split(r"(?<=[.!?])\s+", line) if p.strip()])
        else:
            out.append(line)
    return "\n\n".join(out)


def humanize(post, report):
    symbol = infer_symbol(report, post)
    style = style_of(report)
    text = add_human_rhythm(clean_filler(post))
    changes = []
    emoji = STYLE_EMOJIS.get(style, "👀")
    emoji_chars = re.findall(r"[\U0001F300-\U0001FAFF]", text)
    if not emoji_chars:
        first = text.split("\n\n", 1)[0].strip()
        text = text.replace(first, f"{emoji} {first}", 1)
        changes.append("added_contextual_emoji")
    elif len(emoji_chars) > 3:
        kept, buf = 0, []
        for ch in text:
            if re.match(r"[\U0001F300-\U0001FAFF]", ch):
                kept += 1
                if kept > 3:
                    continue
            buf.append(ch)
        text = "".join(buf)
        changes.append("reduced_emoji_noise")

    if symbol and any(q.strip().lower() in GENERIC_QUESTIONS for q in re.findall(r"[^?]{3,}\?", text)):
        text = re.sub(r"(?:What do you think\?|Thoughts\?|Any thoughts\?|Agree\?)", f"Would you watch ${symbol} here or wait for confirmation?", text, flags=re.I)
        changes.append("replaced_generic_question")

    questions = re.findall(r"[^?]{3,}\?", text)
    if len(questions) == 0 and symbol:
        text = text.rstrip(" .") + f"\n\nWould you watch ${symbol} here, or wait?"
        changes.append("added_conversation_question")
    elif len(questions) > 1:
        first_q, last_q = text.find("?"), text.rfind("?")
        if first_q != last_q:
            text = text[:first_q] + "." + text[first_q + 1:]
            changes.append("reduced_to_one_question")

    text = re.sub(r"\b(follow for more|like and follow|smash the like|drop a like)\b[.!]*", "", text, flags=re.I)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    if len(text) > 900:
        sentences = re.split(r"(?<=[.!?])\s+", text)
        compact = ""
        for sentence in sentences:
            candidate = (compact + " " + sentence).strip()
            if len(candidate) > 880:
                break
            compact = candidate
        if compact:
            text = compact
            changes.append("trimmed_mobile_length")
    return text, changes


def score_post(post, report, recent):
    low = post.lower(); symbol = infer_symbol(report, post); scores = {}; reasons = []
    human = 70
    if len(post) > 900: human -= 15; reasons.append("too_long")
    if any(x in low for x in ("in conclusion", "it remains to be seen", "going forward")): human -= 15; reasons.append("analyst_filler")
    if re.search(r"\b(i'm watching|my read|here's|here is|the part i)\b", low): human += 10
    if re.search(r"[\U0001F300-\U0001FAFF]", post): human += 5
    scores["human_voice"] = max(0, min(100, human))

    thesis = 45
    if re.search(r"\b(because|means|suggests|but|while|instead|catch|why|unless|if)\b", low): thesis += 25
    if re.search(r"\b(retest|follow-through|fakeout|breakout|reaction|confirmation|range|volume)\b", low): thesis += 15
    if symbol and symbol.lower() in low: thesis += 10
    scores["thesis"] = min(100, thesis)

    specificity = 40 + (20 if symbol else 0) + (15 if re.search(r"\d+(?:\.\d+)?%", post) else 0) + (10 if re.search(r"\$\d", post) else 0) + (10 if re.search(r"\b(volume|range|price|support|resistance|candle|inflow|outflow)\b", post, re.I) else 0)
    scores["specificity"] = min(100, specificity)

    questions = re.findall(r"[^?]{3,}\?", post); conversation = 25
    if len(questions) == 1:
        conversation += 40
        q = questions[0].lower()
        if q.strip() in GENERIC_QUESTIONS: conversation -= 30
        if symbol and symbol.lower() in q: conversation += 15
    elif len(questions) == 0: reasons.append("missing_question")
    else: reasons.append("multiple_questions")
    scores["conversation"] = max(0, min(100, conversation))

    max_overlap = 0.0
    for row in recent[-25:]:
        prior = str(row.get("hook") or row.get("topic") or row.get("text") or "").strip()
        if prior: max_overlap = max(max_overlap, overlap(post, prior))
    scores["originality"] = max(0, min(100, 100 - int(max_overlap * 100)))
    if max_overlap >= 0.55: reasons.append("too_similar_to_recent_content")

    measured = [r for r in recent if any(k in r for k in ("views", "replies", "followers_gained"))]
    if measured:
        views = sum(float(r.get("views") or 0) for r in measured); replies = sum(float(r.get("replies") or 0) for r in measured); followers = sum(float(r.get("followers_gained") or 0) for r in measured)
        conversion = 65 + min(20, replies / max(1, views) * 10000) + min(15, followers / max(1, views) * 10000)
    else: conversion = 65
    scores["audience_conversion"] = round(min(100, conversion), 2)
    scores["creator_identity"] = 90
    total = round(scores["human_voice"]*.20 + scores["thesis"]*.18 + scores["specificity"]*.16 + scores["conversation"]*.18 + scores["originality"]*.18 + scores["audience_conversion"]*.06 + scores["creator_identity"]*.04, 2)
    reject = total < 70 or scores["originality"] < 50 or scores["conversation"] < 55 or scores["thesis"] < 55
    return scores, total, reject, reasons, max_overlap


def update_identity(recent):
    identity = load(IDENTITY, {}); formats, styles, categories = Counter(), Counter(), Counter()
    for row in recent:
        formats[str(row.get("format") or "unknown").lower()] += 1; styles[str(row.get("editorial_style") or "unknown").upper()] += 1; categories[str(row.get("content_category") or "unknown").lower()] += 1
    identity.update({
        "version": 3, "updated_at": datetime.now(timezone.utc).isoformat(), "name": "Market Signal Storyteller",
        "positioning": "A data-first crypto creator with a recognizable human voice: curious, specific, visual and conversational.",
        "voice_principles": ["headline creates curiosity, not hype for hype's sake", "one sharp observation beats a list of numbers", "write like a trader explaining the chart to a friend", "use emojis as visual punctuation, never decoration spam", "ask one real question that invites a choice", "news is useful only when connected to verified market action", "never invent facts, sources, engagement or outcomes"],
        "content_pillars": ["market structure", "data surprises", "news reactions", "comparisons", "education", "chart challenges"],
        "recent_format_mix": formats.most_common(10), "recent_style_mix": styles.most_common(10), "recent_category_mix": categories.most_common(10),
        "identity_rule": "Develop a recognizable voice from our own results; never imitate another creator.",
    })
    IDENTITY.parent.mkdir(parents=True, exist_ok=True); IDENTITY.write_text(json.dumps(identity, indent=2, ensure_ascii=False), encoding="utf-8")
    return identity


def main():
    report_path = latest_report()
    if not report_path: raise SystemExit("No draft report available")
    report = load(report_path, {}); recent = recent_publications(); identity = update_identity(recent); _, original = get_post(report)
    if not original: raise SystemExit("Creator Intelligence 3.0: draft has no text")
    edited, changes = humanize(original, report)
    report.setdefault("draft", {})["post"] = edited; report["draft"]["text"] = edited; report["draft"]["human_editorial_version"] = 3
    report["draft"]["emoji_policy"] = "1-3 contextual emojis maximum"; report["draft"]["engagement_policy"] = "one genuine question; no engagement bait; reply only to real user comments"
    scores, total, reject, reasons, max_overlap = score_post(edited, report, recent)
    result = {"version": 3, "generated_at": datetime.now(timezone.utc).isoformat(), "report": str(report_path), "decision": "REJECT_AND_REWORK" if reject else "READY_FOR_PUBLICATION_REVIEW", "publish_recommendation": not reject, "score": total, "dimensions": scores, "reasons": sorted(set(reasons)), "max_recent_content_overlap": round(max_overlap, 3), "editorial_repairs": changes, "creator_identity": identity, "rules": ["Use a distinct opening and structure; never mechanically repeat the previous post.", "Use 1-3 contextual emojis only when they improve scanning.", "Keep one concrete question and never beg for likes or follows.", "Connect a news claim to verified market data; never invent context or imagery.", "Only real user comments may trigger automated replies; never manufacture conversations.", "Do not invent metrics, revenue, sources, prices, targets or market facts."]}
    report["creator_intelligence_3"] = result; report["status"] = "DRAFT_ONLY_NOT_PUBLISHED"
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"); OUT.parent.mkdir(parents=True, exist_ok=True); OUT.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    if reject: raise SystemExit(3)


if __name__ == "__main__": main()
