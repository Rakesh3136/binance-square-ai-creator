"""Normalize AI draft aliases and enforce publication-context visual requirements."""
from __future__ import annotations
import json
import re
from datetime import datetime, timezone
from pathlib import Path

REPORT_DIR = Path("data/reports")
STATUS = Path("data/live/creator_status.json")
CONTEXT = Path("data/live/publication_context.json")


def latest_report() -> Path:
    reports = sorted(REPORT_DIR.glob("*-multi-agent.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not reports:
        raise SystemExit("No multi-agent draft report found")
    report = reports[0]
    age = datetime.now().timestamp() - report.stat().st_mtime
    if age > 1200:
        raise SystemExit("Latest draft report is stale")
    return report


def main() -> None:
    path = latest_report()
    report = json.loads(path.read_text(encoding="utf-8"))
    draft = report.get("draft")
    if not isinstance(draft, dict):
        draft = {}

    candidates = (
        draft.get("text"), draft.get("post"), draft.get("body"), draft.get("content"),
        draft.get("caption"), report.get("text"), report.get("post"),
    )
    text = next((str(x).strip() for x in candidates if isinstance(x, str) and x.strip()), "")
    if not text:
        raise SystemExit("AI draft contains no publishable text")

    context = {}
    try:
        context = json.loads(CONTEXT.read_text(encoding="utf-8"))
    except Exception:
        context = {}
    visual_decision = context.get("visual_decision") or {}
    base = str(context.get("symbol") or "").upper().replace("USDT", "").strip()

    if bool(visual_decision.get("required")):
        # Every autonomous market post is explicitly tied to the selected asset
        # and to a TradingView visual. Never substitute an AI-generated chart.
        if base and f"${base}" not in text.upper():
            text = f"${base} — " + text
        draft["visual_requested"] = True
        draft["visual_type"] = "tradingview_chart"
        report["visual_plan"] = {
            **(report.get("visual_plan") or {}),
            "use_visual": True,
            "required": True,
            "type": "tradingview_chart",
            "symbol": context.get("symbol"),
            "source": "publication_context",
        }

    # Binance Square mobile copy must have one useful conversation question.
    # Preserve an AI-written question when there is exactly one; otherwise make
    # the final line a chart-specific, non-promotional question.
    question_count = text.count("?")
    if question_count == 0:
        if base:
            text = f"{text.rstrip()}\n\nBreakout or retest — which level are you watching for confirmation on ${base}?"
        else:
            text = f"{text.rstrip()}\n\nBreakout or fakeout — which level are you watching for confirmation?"
    elif question_count > 1:
        # Keep the final question and turn earlier question marks into periods.
        last_q = text.rfind("?")
        prefix = text[:last_q].replace("?", ".")
        text = prefix + text[last_q:]

    # Avoid accidental truncation in the middle of a question.
    text = text[:740].rstrip()
    if "?" not in text:
        suffix = f" Which level confirms your setup on ${base}?" if base else " Which level confirms your setup?"
        text = (text[: 740 - len(suffix)].rstrip() + suffix)

    draft["text"] = text
    draft["post"] = text
    draft["hook"] = draft.get("hook") or (f"${base} setup:" if base else "Market setup:")
    draft["discussion_question"] = draft.get("discussion_question") or text[text.rfind("\n") + 1:].strip()
    draft.setdefault("quality_score", 0)
    draft.setdefault("editorial_style", "ai_normalized_chart_first")
    draft.setdefault("publication_status", "DRAFT_ONLY_NOT_PUBLISHED")

    report["draft"] = draft
    report["status"] = "DRAFT_ONLY_NOT_PUBLISHED"
    report["draft_normalized"] = True
    report["draft_normalized_at"] = datetime.now(timezone.utc).isoformat()
    path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    status = {}
    if STATUS.exists():
        try:
            status = json.loads(STATUS.read_text(encoding="utf-8"))
        except Exception:
            status = {}
    status.update({
        "status": "AI_SUCCESS",
        "report": str(path),
        "draft_text_ready": True,
        "normalization": "canonical_text_post_hook_question_fields",
        "visual_required_by_context": bool(visual_decision.get("required")),
    })
    STATUS.parent.mkdir(parents=True, exist_ok=True)
    STATUS.write_text(json.dumps(status, indent=2), encoding="utf-8")
    print(json.dumps({
        "status": "DRAFT_NORMALIZED",
        "report": str(path),
        "characters": len(text),
        "visual_requested": bool(draft.get("visual_requested")),
        "visual_type": draft.get("visual_type", "none"),
        "cashtag": f"${base}" if base else None,
        "question_count": text.count("?"),
        "hook": draft.get("hook"),
    }))


if __name__ == "__main__":
    main()
