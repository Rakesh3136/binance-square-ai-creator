import importlib.util
from datetime import datetime, timezone, timedelta
from pathlib import Path
import os

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("publisher", ROOT / "src" / "binance_square_publisher.py")
publisher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(publisher)

now = datetime.now(timezone.utc)
publisher.recent_rows = lambda: [{
    "status": "PUBLISHED_AUTONOMOUSLY",
    "symbol": "BTC",
    "category": "capital_flow_long",
    "published_at": (now - timedelta(hours=6)).isoformat(),
}]

assert publisher.asset_cooldown_match("BTC", "capital_flow_short") is not None
assert publisher.asset_cooldown_match("BTC", "top_gainers") is not None

os.environ.pop("PUBLICATION_FOLLOWUP_EVIDENCE", None)
assert publisher.asset_cooldown_match("BTC", "follow_up") is not None

os.environ["PUBLICATION_FOLLOWUP_EVIDENCE"] = "verified outcome evidence"
assert publisher.asset_cooldown_match("BTC", "follow_up") is None

publisher.recent_rows = lambda: [{
    "status": "PUBLISHED_AUTONOMOUSLY",
    "symbol": "BTC",
    "category": "capital_flow_long",
    "published_at": (now - timedelta(hours=73)).isoformat(),
}]
os.environ.pop("PUBLICATION_FOLLOWUP_EVIDENCE", None)
assert publisher.asset_cooldown_match("BTC", "capital_flow_short") is None

print("PUBLISHER_ASSET_COOLDOWN_VERIFICATION=PASS")
