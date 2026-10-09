import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from nic_winning_post_dna import build


def row(pid, cat, rev=None, verified=True):
    return {
        "canonical_post_id": pid,
        "category": cat,
        "has_primary_cashtag": True,
        "visual_attached": True,
        "performance": {"views": 100},
        "verified_activity": {
            "revenue_verified": bool(verified and rev is not None),
            "reward_amount_usdc": rev,
        },
    }


def main():
    x = build(
        {"publication_funnel": [row("a", "setup", 2), row("b", "setup", 3), row("c", "research", 1), row("d", "false", 90, False)]},
        {},
    )
    assert x["verified_revenue_post_count"] == 3 and x["verified_revenue_total_usdc"] == 6
    assert x["editorial_contract"]["historical_best_category_candidate"] == "setup"
    assert x["editorial_contract"]["truth_policy"]["views_are_not_revenue"]

    # A verified reward event is attributed only when the event itself has an exact post ID.
    linked = build(
        {"publication_funnel": [row("p1", "setup")]},
        {},
        reward_events=[{"event_id": "e1", "verified": True, "post_id": "p1", "reward_amount_usdc": 0.25}],
    )
    assert linked["verified_revenue_post_count"] == 1
    assert linked["verified_post_ids"] == ["p1"]
    assert linked["verified_revenue_total_usdc"] == 0.25

    # Real reward notifications without IDs must remain visible, not be guessed onto posts.
    unlinked = build(
        {"publication_funnel": [row("p1", "setup")]},
        {},
        reward_events=[{"event_id": "e2", "verified": True, "reward_amount_usdc": 0.001, "detail_status": "VERIFIED_REWARD_UNATTRIBUTED_POST"}],
    )
    assert unlinked["verified_revenue_post_count"] == 0
    assert unlinked["verified_unattributed_reward_total_usdc"] == 0.001
    assert unlinked["status"] == "VERIFIED_REWARD_EVIDENCE_NEEDS_POST_LINKS"

    # An external notification without explicit verified status is observed but not counted as verified revenue.
    external = build(
        {"publication_funnel": []},
        {},
        external_events=[{"reward_amount_usdc": 0.035, "evidence_type": "user_reported_notification", "post_id": None}],
    )
    assert external["verified_revenue_post_count"] == 0
    assert external["observed_unattributed_reward_total_usdc"] == 0.035
    assert external["verified_unattributed_reward_total_usdc"] == 0

    empty = build({"publication_funnel": [row("z", "setup", 10, False)]}, {})
    assert empty["status"] == "INSUFFICIENT_VERIFIED_REVENUE" and empty["verified_revenue_post_count"] == 0
    print("NIC Winning-Post DNA attribution tests: PASS")


if __name__ == "__main__":
    main()
