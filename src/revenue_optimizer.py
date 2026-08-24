"""Revenue and Write to Earn Monetization Optimizer.

Ensures posts discussing tradeable assets include valid cashtags,
attribution metadata, and strictly comply with Binance Square's Write to Earn
guidelines to optimize monetization attribution without compromising quality.
"""
import json
import re
from datetime import datetime, timezone
from pathlib import Path

INPUT_PREFLIGHT = Path("data/live/editorial_preflight.json")
OUTPUT_REVENUE = Path("data/live/revenue_strategy.json")

CATEGORY_BENCHMARKS = {
    "top_gainers": "BTC",
    "top_losers": "BTC",
    "volume_leaders": "ETH",
    "high_volatility": "BTC",
    "new_listings": "USDT",
    "comparison": "BTC",
    "technical_setup": "BTC"
}

DISALLOWED_PROMO_PATTERNS = [
    r"100x", r"1000x", r"guaranteed", r"risk-free", r"free money",
    r"join my (telegram|discord|group|channel)", r"pm me for signals",
    r"buy now before it's too late", r"financial advice"
]


def clean_symbol(raw_symbol: str) -> str:
    """Normalize raw ticker symbol into a clean base asset (e.g., NFPUSDT -> NFP)."""
    if not raw_symbol:
        return ""
    clean = str(raw_symbol).strip().upper().replace("$", "")
    if clean.endswith("USDT") and len(clean) > 4:
        clean = clean[:-4]
    elif clean.endswith("BUSD") and len(clean) > 4:
        clean = clean[:-4]
    return clean


def extract_cashtags(text: str) -> list[str]:
    """Find all $CASHTAG tokens in post text."""
    if not text:
        return []
    matches = re.findall(r"\$([A-Z0-9]{2,10})\b", text.upper())
    return sorted(list(set(matches)))


def audit_compliance(text: str) -> dict:
    """Check draft text against Binance Square Write to Earn promotional compliance rules."""
    text_lower = text.lower() if text else ""
    violations = []
    for pattern in DISALLOWED_PROMO_PATTERNS:
        if re.search(pattern, text_lower):
            violations.append(pattern)
    
    return {
        "compliant": len(violations) == 0,
        "violations": violations,
        "checked_at": datetime.now(timezone.utc).isoformat()
    }


def optimize_monetization(draft_text: str, primary_symbol: str, category: str = "", format_type: str = "") -> dict:
    """Optimize draft text for Binance Write to Earn revenue attribution.
    
    Ensures primary cashtag is embedded, suggests secondary tradeable asset cashtag for
    comparison formats, attaches widget recommendations, and verifies compliance.
    """
    base_symbol = clean_symbol(primary_symbol)
    existing_tags = extract_cashtags(draft_text)
    
    updated_text = draft_text or ""
    
    if base_symbol and base_symbol not in existing_tags:
        if updated_text.strip():
            updated_text = f"${base_symbol} {updated_text}"
        else:
            updated_text = f"${base_symbol}"
        existing_tags.append(base_symbol)
        existing_tags = sorted(list(set(existing_tags)))

    if format_type in {"COIN VS COIN", "CHOICE", "COMPARISON"}:
        suggested_widget = "comparison_chart_widget"
    elif format_type in {"CHART CHALLENGE", "BREAKOUT OR FAKEOUT", "TECHNICAL"}:
        suggested_widget = "candlestick_chart_widget"
    else:
        suggested_widget = "spot_price_widget"

    compliance = audit_compliance(updated_text)

    eligible = bool(base_symbol and compliance["compliant"] and len(updated_text) >= 50)
    attribution_score = 1.0 if eligible and len(existing_tags) >= 1 else 0.5 if eligible else 0.0

    return {
        "optimized_text": updated_text,
        "primary_symbol": base_symbol,
        "cashtags": existing_tags,
        "suggested_widget": suggested_widget,
        "write_to_earn_eligible": eligible,
        "attribution_score": attribution_score,
        "compliance": compliance
    }


def main():
    """Run revenue strategy analysis on current editorial preflight data."""
    if not INPUT_PREFLIGHT.exists():
        return

    try:
        preflight_data = json.loads(INPUT_PREFLIGHT.read_text(encoding="utf-8"))
    except Exception:
        return

    selected = preflight_data.get("selected_opportunity") or {}
    symbol = selected.get("symbol") or selected.get("topic") or "BTCUSDT"
    category = selected.get("category") or "top_losers"
    engagement = preflight_data.get("engagement_strategy") or {}
    experiment = engagement.get("experiment") or {}
    format_type = experiment.get("format") or "CHOICE"

    base_symbol = clean_symbol(symbol)

    result = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "primary_monetization_symbol": base_symbol,
        "suggested_cashtag": f"${base_symbol}",
        "write_to_earn_enabled": True,
        "category": category,
        "format_type": format_type,
        "monetization_rules": [
            "Always include at least one valid $CASHTAG for tradeable Binance spot/futures pairs.",
            "Use candlestick chart widget for technical analysis and price widget for movers.",
            "Never use fake urgency, guaranteed returns, or external referral links."
        ]
    }

    OUTPUT_REVENUE.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_REVENUE.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
