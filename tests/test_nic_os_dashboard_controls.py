from pathlib import Path


def test_dashboard_exposes_owner_full_power_controls_without_persisting_tokens():
    html = (Path(__file__).resolve().parents[1] / "dashboard" / "index.html").read_text(encoding="utf-8")
    for required in (
        'id="enableFullPower"', 'id="revokeActiveGrant"', 'id="powerScopes"',
        'id="powerDuration"', 'id="grantList"', "/control/autonomy/grants",
        "autonomy_grant_id", "task_id",
    ):
        assert required in html
    assert not any(f"localStorage.{method}" in html for method in ("getItem", "setItem", "removeItem", "clear"))
    assert "Current tools remain read-only" in html
