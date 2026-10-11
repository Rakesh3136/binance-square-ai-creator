import importlib.util
from pathlib import Path

SPEC = importlib.util.spec_from_file_location(
    "nic_profitability_admission_gate",
    Path(__file__).resolve().parents[1] / "src/nic_profitability_admission_gate.py",
)
gate = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(gate)


def test_exploratory_positive_subgroup_is_never_trade_authorized():
    portfolio = {
        "status": "NOT_PROVEN",
        "mode": "SHADOW_ONLY_NO_LIVE_ORDERS",
        "groups": {
            "BULLISH|12h": {
                "status": "EXPLORATORY_SHADOW_CANDIDATE_NOT_PROOF",
                "purged_held_out_test": {
                    "trades_closed": 200, "net_pnl": 100, "profit_factor": 1.5,
                    "mean_return_lower_bound_pct": 0.1,
                },
            }
        },
    }
    profitability = {
        "status": "NOT_PROVEN",
        "publication_or_trade_authorization": False,
    }
    result = gate.evaluate(portfolio, profitability)
    assert result["status"] == "BLOCKED"
    assert result["approved_strategy_groups"] == []
    assert result["trade_authorization"] is False


def test_missing_reports_fail_closed():
    result = gate.evaluate({}, {})
    assert result["status"] == "BLOCKED"
    assert result["trade_authorization"] is False
    assert result["reasons"]


def test_proven_claim_requires_explicit_authorization_and_heldout_metrics():
    portfolio = {
        "status": "PROVEN",
        "mode": "SHADOW_ONLY_NO_LIVE_ORDERS",
        "trade_authorization": True,
        "groups": {
            "BULLISH|12h": {
                "status": "PROVEN",
                "purged_held_out_test": {
                    "trades_closed": 120, "net_pnl": 250.0, "profit_factor": 1.4,
                    "mean_return_lower_bound_pct": 0.08,
                },
            }
        },
    }
    profitability = {
        "status": "PROVEN",
        "publication_or_trade_authorization": True,
    }
    result = gate.evaluate(portfolio, profitability)
    assert result["status"] == "ADMITTED"
    assert result["approved_strategy_groups"] == ["BULLISH|12h"]


if __name__ == "__main__":
    test_exploratory_positive_subgroup_is_never_trade_authorized()
    test_missing_reports_fail_closed()
    test_proven_claim_requires_explicit_authorization_and_heldout_metrics()
    print("NIC profitability admission gate tests: PASS")
