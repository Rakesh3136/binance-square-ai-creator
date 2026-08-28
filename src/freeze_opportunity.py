from __future__ import annotations
import json
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
PRE = ROOT / "data/live/editorial_preflight.json"
ENGAGEMENT = ROOT / "data/live/engagement_strategy.json"
OUT = ROOT / "data/live/authoritative_opportunity.json"


def load(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
        return value if isinstance(value, dict) else {}
    except Exception:
        return {}


def get_symbol(value: dict) -> str:
    """Accept all selector naming conventions used by the pipeline."""
    if not isinstance(value, dict):
        return ""
    for key in ("symbol", "selected_lane_symbol", "topic"):
        raw = value.get(key)
        if raw:
            return str(raw).upper().strip()
    return ""


def main():
    pre = load(PRE)
    engagement = load(ENGAGEMENT)

    # Engagement selection is authoritative.  The selector historically stores
    # the selected market pair under `topic` while preflight may use `symbol`.
    # Normalize all supported forms before freezing so a valid selection can
    # never be lost between stages.
    selected = pre.get("selected_opportunity")
    if not isinstance(selected, dict) or not get_symbol(selected):
        candidate = engagement.get("selected")
        if isinstance(candidate, dict) and get_symbol(candidate):
            selected = candidate
            pre["selected_opportunity"] = candidate
            pre["recovered_selected_opportunity"] = True
        else:
            ranked = engagement.get("ranked_candidates")
            if isinstance(ranked, list):
                selected = next((x for x in ranked if isinstance(x, dict) and get_symbol(x)), None)
            if not isinstance(selected, dict) or not get_symbol(selected):
                raise SystemExit("No selected opportunity to freeze after engagement selection")
            pre["selected_opportunity"] = selected
            pre["recovered_selected_opportunity"] = True

    symbol_usdt = get_symbol(selected)
    if not symbol_usdt.endswith("USDT"):
        symbol_usdt += "USDT"
    symbol = symbol_usdt[:-4]

    frozen = {
        "version": 3,
        "frozen_at": datetime.now(timezone.utc).isoformat(),
        "symbol": symbol,
        "symbol_usdt": symbol_usdt,
        "category": selected.get("category", ""),
        "reason": selected.get("reason", ""),
        "instruction": selected.get("instruction", ""),
        "score": selected.get("engagement_score", selected.get("adjusted_score", selected.get("raw_score", 0))),
        "run_ai": bool(pre.get("run_ai", False)),
        "selection_source": "engagement_strategy" if pre.get("recovered_selected_opportunity") else "editorial_preflight",
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(frozen, indent=2, ensure_ascii=False), encoding="utf-8")
    PRE.write_text(json.dumps(pre, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(frozen, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
