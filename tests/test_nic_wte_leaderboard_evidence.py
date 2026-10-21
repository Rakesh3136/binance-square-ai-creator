import unittest
from datetime import datetime, timezone

from src.nic_wte_leaderboard_evidence import normalize_observations


NOW = datetime(2026, 10, 21, 12, tzinfo=timezone.utc)


def row(**overrides):
    value = {
        "creator": "CreatorAlpha",
        "creator_profile_url": "https://www.binance.com/en/square/profile/CreatorAlpha",
        "rank": 1,
        "displayed_amount": 800,
        "currency": "USDC",
        "period_start": "2026-10-12T00:00:00Z",
        "period_end": "2026-10-18T23:59:00Z",
        "observed_at": "2026-10-21T10:00:00Z",
        "source_url": "https://www.binance.com/en/square/WriteToEarn",
        "evidence_ref": "capture://wte-week-2026-10-12",
    }
    value.update(overrides)
    return value


class WriteToEarnLeaderboardEvidenceTests(unittest.TestCase):
    def test_accepts_explicit_observation_but_does_not_call_it_verified_payout(self):
        result = normalize_observations({"entries": [row()]}, NOW)
        self.assertEqual(result["accepted_count"], 1)
        entry = result["entries"][0]
        self.assertEqual(entry["status"], "OBSERVED_LEADERBOARD_ENTRY_NOT_OWN_PAYOUT")
        self.assertFalse(entry["independently_verified_payment"])
        self.assertEqual(entry["displayed_amount"], 800.0)

    def test_rejects_untrusted_source_and_does_not_invent_profile_url(self):
        result = normalize_observations({"entries": [row(source_url="https://example.com/en/square/WriteToEarn", creator_profile_url=None)]}, NOW)
        self.assertEqual(result["accepted_count"], 0)
        self.assertEqual(result["rejected"][0]["reason"], "official_write_to_earn_source_url_required")

    def test_unknown_profile_is_kept_unknown_not_constructed_from_name(self):
        result = normalize_observations({"entries": [row(creator_profile_url=None)]}, NOW)
        self.assertIsNone(result["entries"][0]["creator_profile_url"])

    def test_rejects_missing_evidence_and_future_observation(self):
        missing = normalize_observations({"entries": [row(evidence_ref="")]}, NOW)
        future = normalize_observations({"entries": [row(observed_at="2026-10-22T10:00:00Z")]}, NOW)
        self.assertEqual(missing["rejected"][0]["reason"], "evidence_ref_required")
        self.assertEqual(future["rejected"][0]["reason"], "observation_time_in_future")

    def test_rejects_invalid_period_and_currency(self):
        result = normalize_observations({"entries": [row(period_start="2026-10-19T00:00:00Z", period_end="2026-10-18T00:00:00Z"), row(currency="BTC")]}, NOW)
        self.assertEqual(result["accepted_count"], 0)
        self.assertEqual(result["rejected"][0]["reason"], "period_start_after_period_end")
        self.assertEqual(result["rejected"][1]["reason"], "unsupported_or_missing_currency")


if __name__ == "__main__":
    unittest.main()
