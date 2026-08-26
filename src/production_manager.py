"""Bounded production manager for the Binance Square creator.

Final publication authority. AI/editorial components may fail or reject a draft,
but they must not prevent the manager from making one bounded deterministic rescue
when a fresh market opportunity exists.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORT_DIR = ROOT / "data/reports"
STATUS_PATH = ROOT / "data/live/creator_status.json"
PREFLIGHT_PATH = ROOT / "data/live/editorial_preflight.json"
INTEL_PATH = ROOT / "data/live/creator_intelligence_2.json"
GATE_PATH = ROOT / "data/live/engagement_gate.json"
AUDIT_PATH = Path("/tmp/publish_gate.json")

QUALITY_THRESHOLD = 72.0
OPPORTUNITY_THRESHOLD = 72.0
RESCUE_QUALITY_THRESHOLD = 85.0
MAX_AGE_SECONDS = 20 * 60


def load(path: Path, default=None):
    if not path.exists():
        return default if default is not None else {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value
    except Exception:
        return default if default is not None else {}


def fresh_report():
    reports = sorted(
        REPORT_DIR.glob("*-multi-agent.json"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if not reports:
        return None
    report = reports[0]
    age = datetime.now().timestamp() - report.stat().st_mtime
    return report if age <= MAX_AGE_SECONDS else None


def output(publish: bool, mode: str = "text"):
    with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as out:
        out.write(f"publish={'true' if publish else 'false'}\n")
        out.write(f"mode={mode}\n")


def set_fallback_status():
    STATUS_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATUS_PATH.write_text(
        json.dumps(
            {
                "status": "LOCAL_FALLBACK_SUCCESS",
                "generation_mode": "LOCAL_FALLBACK",
                "reason": "Production manager deterministic rescue produced a fresh publishable draft",
            },
            indent=2,
        ),
        encoding="utf-8",
    )


def opportunity_score(data):
    research = data.get("research") or {}
    critique = data.get("critique") or {}
    selected = data.get("selected_editorial_lane") or {}
    preflight = load(PREFLIGHT_PATH, {})
    preflight_selected = preflight.get("selected_opportunity") or {}

    values = []
    sources = (
        (research, ("opportunity_score", "adjusted_score", "engagement_score")),
        (critique, ("revised_opportunity_score", "opportunity_score", "adjusted_score", "engagement_score")),
        (selected, ("adjusted_score", "raw_score", "engagement_score")),
        (preflight_selected, ("adjusted_score", "raw_score", "content_signal_score", "engagement_score")),
    )
    for obj, keys in sources:
        if not isinstance(obj, dict):
            continue
        for key in keys:
            try:
                value = float(obj.get(key) or 0)
            except (TypeError, ValueError):
                value = 0.0
            if value > 0:
                values.append(value)
    return max(values, default=0.0)


def evaluate(report: Path):
    data = load(report, {})
    draft = data.get("draft") or {}
    visual = data.get("visual_plan") or {}
    post = str(draft.get("post") or draft.get("text") or "").strip()
    rescue = data.get("publish_rescue") is True

    try:
        from engagement_quality_gate import evaluate as interaction_evaluate
        interaction = interaction_evaluate(post, visual)
    except Exception as exc:
        interaction = {
            "score": 0,
            "publish": False,
            "reasons": [f"quality_gate_error:{type(exc).__name__}"],
        }

    try:
        quality = float(draft.get("quality_score") or interaction.get("score") or 0)
    except (TypeError, ValueError):
        quality = float(interaction.get("score") or 0)

    opportunity = opportunity_score(data)
    intelligence = load(INTEL_PATH, {})
    intelligence_ok = intelligence.get("publish_recommendation") is True

    if rescue:
        eligible = (
            bool(post)
            and quality >= RESCUE_QUALITY_THRESHOLD
            and opportunity >= OPPORTUNITY_THRESHOLD
            and interaction.get("publish") is True
            and data.get("status") == "DRAFT_ONLY_NOT_PUBLISHED"
        )
    else:
        eligible = (
            bool(post)
            and quality >= QUALITY_THRESHOLD
            and opportunity >= OPPORTUNITY_THRESHOLD
            and interaction.get("publish") is True
            and intelligence_ok
            and data.get("status") == "DRAFT_ONLY_NOT_PUBLISHED"
        )

    mode = "image" if visual.get("use_visual") is True else "text"
    audit = {
        "draft": str(report),
        "publish": eligible,
        "attempt": "rescue" if rescue else "normal",
        "quality_score": quality,
        "quality_threshold": RESCUE_QUALITY_THRESHOLD if rescue else QUALITY_THRESHOLD,
        "opportunity_score": opportunity,
        "opportunity_threshold": OPPORTUNITY_THRESHOLD,
        "creator_status": load(STATUS_PATH, {}).get("status"),
        "creator_intelligence_2": intelligence,
        "interaction_gate": interaction,
        "mode": mode,
        "rescue": rescue,
        "reason": "publish_eligible" if eligible else "gate_rejected",
    }
    AUDIT_PATH.write_text(json.dumps(audit, indent=2, ensure_ascii=False), encoding="utf-8")
    GATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    GATE_PATH.write_text(json.dumps(interaction, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(audit, indent=2, ensure_ascii=False))
    return eligible, mode


def main():
    report = fresh_report()
    if not report:
        output(False)
        print(json.dumps({"publish": False, "reason": "no fresh draft within 20 minutes"}))
        return 0

    # The AI self-editor already ran earlier in the workflow. Never rerun it
    # here: its failure must not block the production manager or the rescue lane.
    publish, mode = evaluate(report)
    if publish:
        output(True, mode)
        print("Production manager: normal draft passed; publication authorized.")
        return 0

    print("Production manager: normal gate rejected the draft; running one bounded rescue.")
    rescue = subprocess.run(
        [sys.executable, str(ROOT / "src/publish_rescue.py")],
        cwd=ROOT,
        check=False,
    )
    if rescue.returncode != 0:
        output(False, mode)
        print("Production manager: rescue failed; no publication.")
        return 0

    set_fallback_status()
    report = fresh_report()
    if not report:
        output(False, mode)
        print("Production manager: rescue produced no fresh report; no publication.")
        return 0

    publish, mode = evaluate(report)
    if publish:
        output(True, mode)
        print("Production manager: deterministic rescue passed; publication authorized.")
        return 0

    output(False, mode)
    print("Production manager: bounded rescue failed the final evidence checks; no publication.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
