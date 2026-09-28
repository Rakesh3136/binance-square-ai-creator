"""Focused regression checks for NIC Monetization Intelligence 2.0."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"

def main() -> int:
    result = subprocess.run(
        [sys.executable, "-m", "py_compile",
         str(SRC / "nic_monetization_os.py"),
         str(SRC / "write_to_earn_7day_controller.py"),
         str(SRC / "content_portfolio_planner.py"),
         str(SRC / "publication_context.py"),
         str(SRC / "publication_payload_builder.py"),
         str(SRC / "binance_square_publisher.py"),
         str(SRC / "safe_creator_runner.py"),
         str(SRC / "wte_monetization_attribution.py")],
        cwd=ROOT, text=True, capture_output=True,
    )
    if result.returncode:
        print(result.stdout, end="")
        print(result.stderr, end="", file=sys.stderr)
        return result.returncode

    sys.path.insert(0, str(SRC))
    import nic_monetization_os as os_layer

    expected = [
        "market_setup",
        "data_investigation",
        "news_impact",
        "asset_comparison",
        "contrarian_thesis",
        "outcome_accountability",
        "weekly_synthesis",
    ]
    actual = sorted(os_layer.LANES, key=lambda k: os_layer.LANES[k]["day"])
    assert actual == expected, f"unexpected lane sequence: {actual}"
    assert [os_layer.LANES[k]["day"] for k in actual] == list(range(1, 8))
    assert all(
        os_layer.LANES[k]["format"]
        and os_layer.LANES[k]["hook_type"]
        and os_layer.LANES[k]["visual_type"]
        and os_layer.LANES[k]["reader_payoff_type"]
        for k in expected
    )

    assert os_layer.clean_symbol("$HBARUSDT") == "HBAR"
    assert os_layer.canonical_post_id("https://www.binance.com/square/post/371581558472690") == "371581558472690"

    # Contract must remain explicit about unknown monetization stages.
    contract = os_layer.build_pre_contract()
    for key in ("reward_state", "revenue_state", "attribution_state"):
        assert key in contract, f"missing {key}"
    assert contract["reward_state"] == "UNKNOWN"
    assert contract["revenue_state"] == "UNKNOWN"

    print(json.dumps({
        "status": "PASS",
        "lane_sequence": actual,
        "lane_days": [os_layer.LANES[k]["day"] for k in actual],
        "unknown_revenue_policy": contract["revenue_state"],
    }, indent=2))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
