"""Disable the visual plan safely when chart rendering fails."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

REPORT_DIR = Path("data/reports")


def main() -> None:
    reports = sorted(REPORT_DIR.glob("*-multi-agent.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not reports:
        raise SystemExit("No draft available for visual degradation")
    report = reports[0]
    data = json.loads(report.read_text(encoding="utf-8"))
    visual = data.get("visual_plan")
    if not isinstance(visual, dict):
        visual = {}
    visual.update({
        "use_visual": False,
        "type": "none",
        "degraded_from_visual": True,
        "degraded_at": datetime.now(timezone.utc).isoformat(),
    })
    data["visual_plan"] = visual
    report.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"status": "VISUAL_DEGRADED_TO_TEXT", "report": str(report)}))


if __name__ == "__main__":
    main()
