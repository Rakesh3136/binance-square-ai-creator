"""Fail-closed admission gate for NIC trade-mode publication.

This gate is intentionally stricter than exploratory backtest reporting. It never
turns a positive research subgroup into trade authorization.
"""
from __future__ import annotations

import json
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
PORTFOLIO = ROOT / "data/intelligence/nic_portfolio_reality.json"
PROFITABILITY = ROOT / "data/intelligence/nic_forecast_profitability.json"
OUT = ROOT / "data/live/nic_profitability_admission.json"


def evaluate(portfolio: dict, profitability: dict) -> dict:
    reasons = []
    approved = []
    if portfolio.get("mode") != "SHADOW_ONLY_NO_LIVE_ORDERS":
        reasons.append("portfolio mode is not explicitly shadow-only")
    # The portfolio engine deliberately reports NOT_PROVEN until a reviewed,
    # untouched final holdout and execution-cost stress test are passed.
    if portfolio.get("status") != "PROVEN":
        reasons.append("portfolio-level profitability is not proven")
    if portfolio.get("trade_authorization") is not True:
        reasons.append("portfolio report does not explicitly authorize trade mode")
    if profitability.get("status") != "PROVEN":
        reasons.append("forecast profitability is not proven")
    if profitability.get("publication_or_trade_authorization") is not True:
        reasons.append("profitability report does not explicitly authorize trade mode")

    groups = portfolio.get("strategies", portfolio.get("groups", {}))
    if not isinstance(groups, dict):
        reasons.append("portfolio strategy results are malformed")
        groups = {}
    for key, group in groups.items():
        if not isinstance(group, dict) or group.get("status") != "PROVEN":
            continue
        test = group.get("purged_held_out_test", {})
        if not isinstance(test, dict):
            continue
        pf = test.get("profit_factor")
        lower = test.get("mean_return_lower_bound_pct")
        if (
            isinstance(test.get("trades_closed"), int)
            and test["trades_closed"] >= 100
            and isinstance(test.get("net_pnl"), (int, float))
            and test["net_pnl"] > 0
            and isinstance(pf, (int, float))
            and pf > 1.0
            and isinstance(lower, (int, float))
            and lower > 0
        ):
            approved.append(key)
    if not approved:
        reasons.append("no strategy passed the proven held-out portfolio criteria")
    admitted = not reasons and bool(approved)
    return {
        "schema": "NIC-PROFITABILITY-ADMISSION-1.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "ADMITTED" if admitted else "BLOCKED",
        "mode": "SHADOW_ONLY",
        "approved_strategy_groups": sorted(approved) if admitted else [],
        "reasons": [] if admitted else reasons,
        "trade_authorization": False,
        "trade_mode_publication_admitted": admitted,
        "publication_or_trade_authorization": False,
        "note": "A gate pass is necessary, not sufficient, for live trading; human approval, real execution evidence, risk controls, and an untouched final holdout remain required.",
    }


def main() -> None:
    portfolio = json.loads(PORTFOLIO.read_text(encoding="utf-8"))
    profitability = json.loads(PROFITABILITY.read_text(encoding="utf-8"))
    report = evaluate(portfolio, profitability)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "status": report["status"],
        "approved_strategy_groups": report["approved_strategy_groups"],
        "reasons": report["reasons"],
        "trade_authorization": False,
    }))
    # BLOCKED is an expected safe state, not a pipeline failure.
    if report["status"] not in {"ADMITTED", "BLOCKED"}:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
