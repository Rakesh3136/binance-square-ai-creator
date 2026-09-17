"""Deterministic monetization eligibility gate for Binance Square posts.

Write to Earn rewards qualifying reader trades. For market-analysis posts this
layer makes the attribution mechanism explicit before publication: a primary
coin cashtag must be present unless a future verified widget marker is supplied.
The gate never claims revenue and never fabricates trading activity.

A non-eligible decision is a normal control-flow outcome, not a workflow error.
The caller must inspect the explicit ``eligible`` output before publishing.
"""
from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAYLOAD = ROOT / "data/live/publication_payload.json"
CONTEXT = ROOT / "data/live/publication_context.json"
OUT = ROOT / "data/live/write_to_earn_eligibility.json"

MONETIZABLE_LANES = {
    "market", "top_gainers", "top_losers", "high_volatility", "volume_leaders",
    "technical_setup", "next_gainer_candidate", "next_loser_candidate",
    "capital_flow_long", "capital_flow_short", "flow", "creator_signal_outcome",
    "follow_up", "watchlist", "research_radar", "breaking_news", "news", "news_and_macro",
}
NON_MARKET_LANES = {"education", "commentary", "community"}


def load(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except Exception:
        return {}


def main() -> None:
    payload = load(PAYLOAD)
    context = load(CONTEXT)
    text = str(payload.get("text") or "")
    symbol = re.sub(
        r"[^A-Z0-9]",
        "",
        str(payload.get("symbol") or context.get("symbol") or "")
        .upper()
        .replace("USDT", ""),
    )
    category = str(context.get("category") or payload.get("category") or "").lower().strip()
    cashtag = f"${symbol}" if symbol else ""
    has_cashtag = bool(
        symbol
        and re.search(
            rf"(?<![A-Za-z0-9_])\${re.escape(symbol)}(?![A-Za-z0-9_])",
            text,
            flags=re.I,
        )
    )
    widget_markers = context.get("trading_widget") or payload.get("trading_widget") or payload.get("widget") or {}
    has_verified_widget = isinstance(widget_markers, dict) and bool(
        widget_markers.get("verified") is True
        and (widget_markers.get("symbol") or widget_markers.get("id"))
    )
    monetizable_lane = category in MONETIZABLE_LANES
    market_lane = monetizable_lane and category not in NON_MARKET_LANES
    eligible = not market_lane or has_cashtag or has_verified_widget
    reason = "not_market_monetization_lane"
    if market_lane:
        if has_cashtag:
            reason = "primary_coin_cashtag_present"
        elif has_verified_widget:
            reason = "verified_trading_widget_present"
        else:
            reason = "missing_primary_coin_cashtag_or_verified_trading_widget"

    result = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "version": "WTE-GATE-1.1",
        "eligible": eligible,
        "category": category,
        "symbol": symbol,
        "required_attribution": market_lane,
        "cashtag": cashtag,
        "has_primary_cashtag": has_cashtag,
        "verified_widget": has_verified_widget,
        "reason": reason,
        "policy": {
            "market_posts_require_attribution_mechanism": True,
            "revenue_is_never_inferred": True,
            "reader_trading_is_never_fabricated": True,
            "this_gate_does_not_guarantee_commission": True,
            "ineligible_publication_is_a_control_flow_skip": True,
        },
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")

    github_output = os.environ.get("GITHUB_OUTPUT")
    if github_output:
        with open(github_output, "a", encoding="utf-8") as fh:
            fh.write(f"eligible={'true' if eligible else 'false'}\n")
            fh.write(f"symbol={symbol}\n")
            fh.write(f"reason={reason}\n")

    print(json.dumps(result, indent=2, ensure_ascii=False))
    # Eligibility is a routing decision. Publication itself remains gated by the
    # workflow condition and must never run when eligible is false.
    return


if __name__ == "__main__":
    main()
