"""Creator Intelligence 2.0: taste, originality, audience conversion and self-rejection.

This layer sits after draft generation and before publication. It learns from our
own publication history, uses public creator research only as structural
hypotheses, and refuses to publish content that feels repetitive, generic or
conversation-poor. It never fabricates metrics or copies creators.
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
PATTERNS = ROOT / "data/intelligence/creator_patterns.json"

GENERIC_QUESTIONS = {
    "what do you think?",
    "what do you think",
    "thoughts?",
    "any thoughts?",
    "agree?",
}
FILLER = [
    "key takeaway", "notable factor", "clear shift", "market participants",
    "in conclusion", "it remains to be seen", "this highlights", "going forward",
]


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


def recent_publications(limit=40):
    rows = []
    if not LOG.exists():
        return rows
    for line in LOG.read_text(encoding="utf-8").splitlines()[-500:]:
        try:
            x = json.loads(line)
            if isinstance(x, dict):
                rows.append(x)
        except Exception:
            continue
    return rows[-limit:]


def words(text):
    return re.findall(r"[a-z0-9$%']+", str(text).lower())


def fingerprint(text):
    return " ".join(words(text))


def shingles(text, n=4):
    w = words(text)
    return {" ".join(w[i:i+n]) for i in range(max(0, len(w)-n+1))}


def overlap(a, b):
    sa, sb = shingles(a), shingles(b)
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / max(1, min(len(sa), len(sb)))


def get_post(report):
    draft = report.get("draft") or {}
    if not isinstance(draft, dict):
        draft = {}
    post = str(draft.get("post") or draft.get("text") or "").strip()
    return draft, post


def infer_symbol(report, post):
    selected = report.get("selected_editorial_lane") or {}
    raw = str(selected.get("symbol") or "")
    m = re.search(r"\b([A-Z0-9]{2,12})USDT\b", raw.upper())
    if m:
        return m.group(1)
    m = re.search(r"\$([A-Z][A-Z0-9]{1,11})\b", post.upper())
    return m.group(1) if m else ""


def score_post(post, report, recent):
    text = post.strip()
    low = text.lower()
    lines = [x.strip() for x in text.splitlines() if x.strip()]
    symbol = infer_symbol(report, text)
    scores = {}
    reasons = []

    # Taste / human voice.
    human = 100
    if any(p in low for p in FILLER):
        human -= 18; reasons.append("analyst_filler")
    if len(lines) > 9:
        human -= 10; reasons.append("too_many_lines")
    if len(text) > 650:
        human -= 8; reasons.append("dense_for_mobile")
    if re.search(r"\b(i would|i'm watching|i'm looking|my read|quick read|here's what)\b", low):
        human += 3
    scores["human_voice"] = max(0, min(100, human))

    # Thesis: a real post should say what the observation means, not only quote numbers.
    thesis = 45
    if re.search(r"\b(because|means|suggests|but|while|instead|the interesting|the catch|why)\b", low):
        thesis += 25
    if re.search(r"\b(confirmed|unconfirmed|watch|wait|follow-through|fakeout|retest|contrast|difference)\b", low):
        thesis += 15
    if re.search(r"\d+(?:\.\d+)?%|\$\d", text):
        thesis += 10
    scores["thesis"] = min(100, thesis)

    # Specificity/evidence.
    specificity = 35
    if symbol:
        specificity += 20
    if re.search(r"\d+(?:\.\d+)?%", text):
        specificity += 15
    if re.search(r"\$\d", text):
        specificity += 10
    if re.search(r"\b(volume|range|price|candle|inflow|outflow|liquidation|support|resistance|ETF|BTC|ETH)\b", text, re.I):
        specificity += 10
    scores["specificity"] = min(100, specificity)

    # Conversation: exactly one concrete, low-friction question.
    questions = re.findall(r"[^?]{3,}\?", text)
    conversation = 25
    if len(questions) == 1:
        conversation += 35
        q = questions[0].strip().lower()
        if q in GENERIC_QUESTIONS:
            conversation -= 25; reasons.append("generic_question")
        elif symbol and symbol.lower() in q:
            conversation += 20
        elif any(x in q for x in ("which", "would", "watch", "choose", "breakout", "fakeout", "bullish", "bearish", "wait")):
            conversation += 15
    elif len(questions) == 0:
        reasons.append("missing_question")
    else:
        reasons.append("multiple_questions")
    scores["conversation"] = max(0, min(100, conversation))

    # Originality: compare against our recent hooks/topics, not public creators.
    max_overlap = 0.0
    for row in recent[-20:]:
        prior = str(row.get("hook") or row.get("topic") or "").strip()
        if prior:
            max_overlap = max(max_overlap, overlap(text, prior))
    originality = 100 - int(max_overlap * 100)
    if len(set(words(text))) < max(12, len(words(text)) * 0.55):
        originality -= 5
    scores["originality"] = max(0, min(100, originality))
    if max_overlap >= 0.55:
        reasons.append("too_similar_to_recent_content")

    # Audience conversion. Metrics may not yet be synced; never invent them.
    measured = [r for r in recent if any(k in r for k in ("views", "replies", "followers_gained"))]
    if measured:
        views = sum(float(r.get("views") or 0) for r in measured)
        replies = sum(float(r.get("replies") or 0) for r in measured)
        followers = sum(float(r.get("followers_gained") or 0) for r in measured)
        reply_rate = replies / max(1.0, views)
        follower_rate = followers / max(1.0, views)
        conversion = 70 + min(15, reply_rate * 10000) + min(15, follower_rate * 10000)
    else:
        conversion = 70
    scores["audience_conversion"] = round(min(100, conversion), 2)

    # Distinctive creator identity: favor repeatable editorial strengths without cloning anyone.
    identity = load(IDENTITY, {})
    identity_score = 60
    if identity.get("voice_principles"):
        identity_score += 15
    if report.get("selected_editorial_lane"):
        identity_score += 10
    if report.get("visual_plan"):
        identity_score += 10
    scores["creator_identity"] = min(100, identity_score)

    total = round(
        scores["human_voice"] * 0.18 +
        scores["thesis"] * 0.18 +
        scores["specificity"] * 0.16 +
        scores["conversation"] * 0.18 +
        scores["originality"] * 0.18 +
        scores["audience_conversion"] * 0.07 +
        scores["creator_identity"] * 0.05,
        2,
    )
    reject = total < 72 or scores["originality"] < 55 or scores["conversation"] < 55 or scores["thesis"] < 55
    return scores, total, reject, reasons, max_overlap


def edit_post(post, report):
    """Apply only safe editorial repairs; never invent market facts."""
    draft, text = get_post(report)
    symbol = infer_symbol(report, text)
    lines = [x.strip() for x in text.splitlines() if x.strip()]
    if not text:
        return text, []
    changes = []
    # Remove canned analyst filler.
    for phrase in FILLER:
        if phrase in text.lower():
            text = re.sub(re.escape(phrase), "", text, flags=re.I)
            changes.append("removed_filler")
    # Replace a generic final question with a concrete question anchored to the asset.
    if symbol:
        generic_re = r"(?:what do you think\?|thoughts\?|any thoughts\?|agree\?)"
        if re.search(generic_re, text, re.I):
            text = re.sub(generic_re, f"Would you watch ${symbol} here or wait for confirmation?", text, flags=re.I)
            changes.append("upgraded_question")
    # Guarantee one question if the draft has none.
    if "?" not in text and symbol:
        text = text.rstrip(" .") + f" — would you watch ${symbol} here or wait for confirmation?"
        changes.append("added_question")
    # Collapse excessive whitespace and keep mobile length.
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    if len(text) > 740:
        text = text[:737].rsplit(" ", 1)[0] + "..."
        changes.append("trimmed_length")
    return text, changes


def update_identity(recent):
    formats = Counter()
    styles = Counter()
    categories = Counter()
    for row in recent:
        formats[str(row.get("format") or "unknown").lower()] += 1
        styles[str(row.get("editorial_style") or "unknown").upper()] += 1
        categories[str(row.get("content_category") or "unknown").lower()] += 1
    identity = load(IDENTITY, {})
    identity.update({
        "version": 1,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "name": "Market Signal Storyteller",
        "positioning": "A data-first crypto creator that turns verified market moves into concise, human conversation.",
        "voice_principles": [
            "curious before certain",
            "specific before sensational",
            "conversational before corporate",
            "original before optimized",
            "useful before promotional",
        ],
        "content_pillars": ["market structure", "data surprises", "news reactions", "comparisons", "education"],
        "recent_format_mix": formats.most_common(10),
        "recent_style_mix": styles.most_common(10),
        "recent_category_mix": categories.most_common(10),
        "identity_rule": "Never imitate a creator. Borrow only validated structural patterns and develop a recognizable voice from our own results.",
    })
    IDENTITY.parent.mkdir(parents=True, exist_ok=True)
    IDENTITY.write_text(json.dumps(identity, indent=2, ensure_ascii=False), encoding="utf-8")
    return identity


def main():
    report_path = latest_report()
    if not report_path:
        raise SystemExit("No draft report available")
    report = load(report_path, {})
    recent = recent_publications()
    identity = update_identity(recent)
    draft, post = get_post(report)
    if not post:
        raise SystemExit("Creator Intelligence 2.0: draft has no text")

    scores, total, reject, reasons, max_overlap = score_post(post, report, recent)
    edited_post, changes = edit_post(post, report)
    if edited_post != post:
        report.setdefault("draft", {})["post"] = edited_post
        report["draft"]["text"] = edited_post
        post = edited_post
        scores, total, reject, reasons, max_overlap = score_post(post, report, recent)

    result = {
        "version": 2,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "report": str(report_path),
        "decision": "REJECT_AND_REWORK" if reject else "READY_FOR_PUBLICATION_REVIEW",
        "publish_recommendation": not reject,
        "self_rejection_enabled": True,
        "score": total,
        "dimensions": scores,
        "reasons": sorted(set(reasons)),
        "max_recent_content_overlap": round(max_overlap, 3),
        "editorial_repairs": changes,
        "creator_identity": identity,
        "rules": [
            "Reject generic or repetitive drafts instead of publishing them.",
            "One concrete question per post; no engagement begging.",
            "A thesis must explain why the data matters.",
            "Public creator research is structural inspiration only; never copy wording or identity.",
            "Verified performance outranks raw views when deciding what to repeat.",
            "Do not invent metrics, revenue, sources, prices or market facts.",
        ],
    }
    report["creator_intelligence_2"] = result
    report["status"] = "DRAFT_ONLY_NOT_PUBLISHED"
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    if reject:
        raise SystemExit(3)


if __name__ == "__main__":
    main()
