from pathlib import Path
import json

POLICY = json.loads(Path("config/self_engineer_policy.json").read_text(encoding="utf-8"))


def test_policy_allows_business_layer_autonomy():
    assert POLICY["max_files_per_cycle"] <= 4
    assert POLICY["max_changed_lines_per_file"] <= 300
    assert POLICY["auto_merge"] is True
    assert POLICY["autonomous_business_layer"] is True
    assert POLICY["business_autonomy"]["can_change_content_strategy"] is True
    assert POLICY["business_autonomy"]["can_change_revenue_strategy"] is True
    assert ".github/workflows/" in POLICY["blocked_prefixes"]
    assert "BINANCE_SQUARE_OPENAPI_KEY" in POLICY["blocked_tokens"]


def test_immutable_files_are_not_allowed():
    forbidden = {"config/self_engineer_policy.json", "src/self_engineer.py", "tests/test_self_engineering.py"}
    allowed = set(POLICY["allowed_prefixes"])
    assert not any(path in allowed for path in forbidden)


def test_required_creator_modules_exist():
    required = [
        "src/editorial_preflight.py",
        "src/engagement_engine.py",
        "src/creator_intelligence.py",
        "src/multi_agent_creator.py",
    ]
    assert all(Path(p).exists() for p in required)
