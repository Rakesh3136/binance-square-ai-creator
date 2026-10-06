import importlib.util
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("signal_first_router", ROOT / "src" / "signal_first_router.py")
router = importlib.util.module_from_spec(spec)
spec.loader.exec_module(router)

NOW = datetime.now(timezone.utc)

def publication(symbol, hours_ago=6, category="capital_flow_long"):
    return {
        "status": "PUBLISHED_AUTONOMOUSLY",
        "symbol": symbol,
        "category": category,
        "published_at": (NOW - timedelta(hours=hours_ago)).isoformat(),
        "post": f"Professional thesis for {symbol} with distinct evidence."
    }

# 1. Same asset must be blocked inside 72h.
rows = [publication("BTC", 6, "capital_flow_long")]
candidate = {"symbol": "BTC", "category": "capital_flow_short", "text": "New BTC short thesis."}
assert router.blocked(candidate, rows) == "same_asset_cooldown_requires_new_evidence_or_follow_up"

# 2. Direction/category changes must NOT bypass the cooldown.
candidate = {"symbol": "BTC", "category": "top_gainers", "text": "BTC is now a top gainer."}
assert router.blocked(candidate, rows) == "same_asset_cooldown_requires_new_evidence_or_follow_up"

# 3. A genuinely different asset remains eligible.
candidate = {"symbol": "ETH", "category": "capital_flow_long", "text": "ETH thesis with new evidence."}
assert router.blocked(candidate, rows) == ""

# 4. Same asset becomes eligible after the cooldown expires.
rows_old = [publication("BTC", 73, "capital_flow_long")]
candidate = {"symbol": "BTC", "category": "capital_flow_short", "text": "BTC after cooldown."}
assert router.blocked(candidate, rows_old) == ""

# 5. Explicit follow-up/outcome is the only in-window exception.
candidate = {
    "symbol": "BTC",
    "category": "follow_up",
    "follow_up": True,
    "new_evidence": "verified outcome evidence",
    "text": "BTC follow-up with verified outcome evidence."
}
# This assertion documents the intended policy; the router must implement it.
assert router.blocked(candidate, rows) == ""

print("ASSET_COOLDOWN_VERIFICATION=PASS")
print("same_asset_72h=PASS")
print("direction_change_bypass=BLOCKED")
print("different_asset=PASS")
print("post_cooldown=PASS")
print("explicit_followup_exception=PASS")
