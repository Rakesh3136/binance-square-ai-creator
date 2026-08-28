"""Normalize AI draft aliases and enforce publication-context visual requirements."""
from __future__ import annotations
import json
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

    if bool(visual_decision.get("required")):
        # The production contract requires the selected asset to be explicitly
        # tagged in the post so the TradingView image and post are unambiguous.
        base = str(context.get("symbol") or "").upper().replace("USDT", "").strip()
        if base and f"${base}" not in text.upper():
            text = f"${base} " + text
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

    text = text[:740]
    draft["text"] = text
    draft["post"] = text
    draft.setdefault("quality_score", 0)
    draft.setdefault("editorial_style", "ai_normalized")
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
        "normalization": "canonical_text_and_post_fields",
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
        "cashtag": f"${str(context.get('symbol') or '').upper().replace('USDT', '')}" if context.get('symbol') else None,
    }))


if __name__ == "__main__":
    main()
