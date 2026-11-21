"""NIC market-flow and founder-opportunity intelligence; advisory only, never a publisher."""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MARKET = ROOT / "data/live/market_snapshot.json"
FLOW = ROOT / "data/live/full_universe_flow.json"
CAPITAL = ROOT / "data/live/capital_flow_intelligence.json"
PREDICTIONS = ROOT / "data/live/nic_prediction_engine.json"
OUT = ROOT / "data/live/nic_market_flow_founder_brief.json"
MAX_AGE_MINUTES = 90


def read(path):
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def parse_time(value):
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).astimezone(timezone.utc)
    except (TypeError, ValueError):
        return None


def number(value, default=0.0):
    try:
        result = float(value)
        return result if result == result and abs(result) != float("inf") else default
    except (TypeError, ValueError):
        return default


def freshness(doc, now, max_age_minutes=MAX_AGE_MINUTES):
    generated = parse_time(doc.get("generated_at"))
    if not generated:
        return {"fresh": False, "age_minutes": None, "reason": "missing_or_invalid_timestamp"}
    age = (now - generated).total_seconds() / 60
    fresh = 0 <= age <= max_age_minutes
    return {"fresh": fresh, "age_minutes": round(age, 1), "reason": "fresh" if fresh else ("future_timestamp" if age < 0 else "stale")}


def symbol_of(row):
    return str(row.get("symbol") or row.get("symbol_usdt") or "").upper().replace("USDT", "").strip()


def find_btc_move(market):
    for group in ("top_content_signals", "top_gainers", "top_losers", "highest_volume", "new_listing_market"):
        for row in market.get(group) or []:
            if isinstance(row, dict) and symbol_of(row) == "BTC":
                return number(row.get("price_change_percent"), None)
    return None


def build(market, flow, capital, predictions, now=None):
    now = now or datetime.now(timezone.utc)
    source_docs = {"market_snapshot": market, "full_universe_flow": flow, "capital_flow_intelligence": capital}
    freshness_report = {name: freshness(doc, now) for name, doc in source_docs.items()}
    fresh_market = all(item["fresh"] for item in freshness_report.values())
    btc_move = find_btc_move(market)
    rotation = (capital.get("market_rotation") or {})
    regime = str(rotation.get("market_regime") or "UNKNOWN").upper()
    flow_rows = [x for x in (flow.get("top_flow_candidates") or []) if isinstance(x, dict)]
    early = []
    if fresh_market:
        for row in flow_rows:
            move = abs(number(row.get("price_change_percent")))
            relative = number(row.get("relative_strength_24h"))
            oi = number(row.get("oi_change_3h_pct"))
            volume = number(row.get("quote_volume_usdt"))
            state = str(row.get("flow_state") or "UNKNOWN").upper()
            # Avoid chasing extended assets. These are screening conditions, not a prediction.
            if state in {"LATE", "EXHAUSTED"} or move >= 6 or relative < 2 or oi <= 0 or volume < 500000:
                continue
            early.append({
                "symbol": symbol_of(row), "last_price": row.get("last_price"),
                "price_change_24h_pct": row.get("price_change_percent"),
                "relative_strength_to_btc_pct": row.get("relative_strength_24h"),
                "open_interest_change_3h_pct": row.get("oi_change_3h_pct"),
                "quote_volume_usdt": row.get("quote_volume_usdt"),
                "flow_state": state, "evidence_fields": row.get("evidence") or [],
                "interpretation": "early-screen candidate; requires independent confirmation, not a buy call"
            })
        early.sort(key=lambda x: (number(x.get("relative_strength_to_btc_pct")), number(x.get("open_interest_change_3h_pct")), number(x.get("quote_volume_usdt"))), reverse=True)
    if not fresh_market:
        flow_conclusion = "WAIT_STALE_MARKET_DATA"
        capital_claim = "No current rotation conclusion: one or more source snapshots are stale or timestamp-invalid."
    elif btc_move is not None and btc_move < 0:
        flow_conclusion = "BTC_WEAKNESS_ROTATION_SCREEN"
        capital_claim = ("Relative-strength candidates may be resilient while BTC falls. Price/OI/funding proxies do not prove that whales moved funds into them; direct exchange netflows or labelled wallet flows are missing.")
    else:
        flow_conclusion = "NO_BTC_DRAWDOWN_ROTATION_TRIGGER"
        capital_claim = ("No current BTC-down rotation setup is established. Relative strength and derivatives metrics are screening proxies, not proof of capital transfer.")
    long_term = {
        "status": "FUNDAMENTAL_EVIDENCE_REQUIRED",
        "policy": "Do not call a token a good long-term project from price, volume, OI, or creator engagement alone.",
        "required_evidence": [
            "primary project documentation and product shipped",
            "active users and retention over time",
            "developer activity and release cadence",
            "token utility, emissions, unlock schedule and concentration",
            "revenue/fees or other measurable demand",
            "security audits, incident history and governance risks",
            "competitors, valuation assumptions and explicit thesis invalidation"
        ]
    }
    founder = {
        "status": "HYPOTHESES_TO_VALIDATE_NOT_MARKET_FACTS",
        "conversation_prompt": "Which painful problem have you personally seen repeatedly, who experiences it, how do they solve it today, and what evidence would make them pay for a better solution?",
        "opportunity_hypotheses": [
            {"name": "Transparent crypto capital-flow monitor", "problem_hypothesis": "Traders confuse price strength and futures OI with actual wallet/exchange inflows.", "small_test": "Compare public exchange netflows, labelled-wallet transfers, spot CVD, OI/funding and subsequent returns; publish uncertainty and source timestamps.", "validation_needed": "Data licensing/coverage, false-positive rate, user interviews, willingness to pay."},
            {"name": "Token unlock and supply-risk explainer", "problem_hypothesis": "Retail readers struggle to connect unlock schedules, circulating supply and liquidity.", "small_test": "Build a source-cited calendar with float impact, liquidity context, and historical post-event outcomes.", "validation_needed": "Schedule accuracy, market impact study, target-user interviews."},
            {"name": "Long-term project evidence tracker", "problem_hypothesis": "Project promotion often omits adoption, token value capture, security and thesis invalidation.", "small_test": "Create an evidence scorecard with dated primary sources and quarterly changes; no price target without a valuation model.", "validation_needed": "Primary-source coverage, analyst usefulness, recurring user demand."}
        ],
        "next_questions_for_user": [
            "Which group do you most want to help first: retail crypto traders, long-term investors, or builders/founders?",
            "What problem have you personally faced enough times that you would pay to make it disappear?",
            "Would you prefer to start with a small research/data product or a larger software company?"
        ]
    }
    return {
        "schema": "NIC-MARKET-FLOW-FOUNDER-BRIEF-1.0",
        "generated_at": now.astimezone(timezone.utc).isoformat(),
        "status": "READY" if fresh_market else "MARKET_ANALYSIS_BLOCKED_STALE_INPUTS",
        "publication_authorized": False, "trade_authorized": False,
        "freshness": freshness_report,
        "market_regime": regime, "btc_change_24h_pct": btc_move,
        "flow_conclusion": flow_conclusion, "capital_flow_interpretation": capital_claim,
        "early_screen_candidates": early[:10],
        "early_screen_note": "Candidates are filtered to avoid already-extended movers. Screening does not prove predictive edge; every candidate must be frozen as a forecast and resolved out of sample.",
        "long_term_project_research": long_term,
        "founder_opportunity_brief": founder,
        "missing_capabilities": [
            "labelled-wallet and exchange netflow data with source provenance",
            "spot order-flow/CVD and depth/liquidity changes, separated from derivatives positioning",
            "historical event study: BTC down moves versus altcoin flows and forward returns after fees",
            "independent long-term fundamentals research and token unlock tracking",
            "user interviews and willingness-to-pay evidence before selecting a startup idea"
        ]
    }


def main():
    result = build(read(MARKET), read(FLOW), read(CAPITAL), read(PREDICTIONS))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"status": result["status"], "flow_conclusion": result["flow_conclusion"],
                      "early_candidates": len(result["early_screen_candidates"]),
                      "founder_hypotheses": len(result["founder_opportunity_brief"]["opportunity_hypotheses"]),
                      "report": str(OUT.relative_to(ROOT)), "publication_authorized": False}, indent=2))


if __name__ == "__main__":
    main()
