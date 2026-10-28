import unittest

from src.bounded_editorial_improvement import (
    generate_and_select, score_candidate, MAX_CANDIDATES,
)


def draft(text, symbol="ETH"):
    return {
        "draft": {"post": text, "text": text, "symbol": symbol},
        "research": {"summary": "test"},
    }


class BoundedEditorialImprovementTests(unittest.TestCase):
    def test_selects_one_from_bounded_candidates_and_records_no_reward_claim(self):
        base = (
            "$ETH is the market question worth watching today. Price is around "
            "$2,500, and the recent range spans $2,420 to $2,560. The useful "
            "test is whether the next reaction holds that structure rather than "
            "reversing it immediately. These are observed levels, not a forecast "
            "or promise, and fresh evidence could change the read. What would "
            "make you reconsider this setup?"
        )
        context = {"frozen_symbol": "ETH"}
        calls = []

        def build(ctx):
            calls.append(ctx["iteration_seed"])
            text = base + ("\n\nThe evidence remains conditional." if ctx["iteration_seed"] % 2 else "")
            return draft(text)

        selected = generate_and_select(context, build, max_candidates=MAX_CANDIDATES)
        self.assertLessEqual(len(calls), MAX_CANDIDATES)
        self.assertEqual(selected["editorial_iteration"]["status"], "SELECTED_FROM_BOUNDED_CANDIDATES")
        self.assertFalse(selected["editorial_iteration"]["selection_is_reward_prediction"])
        self.assertEqual(selected["editorial_iteration"]["reward_claim"], "NOT_CLAIMED")
        self.assertTrue(selected["editorial_iteration"]["quality_and_publication_gates_remain_authoritative"])


    def test_recent_publication_similarity_blocks_duplicate_and_selects_different_candidate(self):
        repeated = (
            "$ETH is the market question worth watching today. Price is around "
            "$2,500, and the recent range spans $2,420 to $2,560. The useful "
            "test is whether the next reaction holds that structure rather than "
            "reversing it immediately. These are observed levels, not a forecast "
            "or promise, and fresh evidence could change the read. What would "
            "make you reconsider this setup?"
        )
        alternative = (
            "$ETH's funding basis deserves attention because positioning can "
            "change before spot price makes the shift obvious. The key evidence "
            "is whether participation expands alongside the move or fades while "
            "price keeps drifting. That distinction separates a durable change "
            "in demand from a short-lived squeeze, without assuming either outcome. "
            "A single snapshot is not enough to prove the mechanism. Which new "
            "data point would change your interpretation first?"
        )
        context = {"recent_publication_texts": [repeated]}

        blocked = score_candidate(draft(repeated), context)
        self.assertIn("near_duplicate_of_recent_publication", blocked["issues"])
        self.assertFalse(blocked["eligible"])

        def build(ctx):
            return draft(repeated if ctx["iteration_seed"] == 0 else alternative)

        selected = generate_and_select(context, build, max_candidates=2)
        selected_text = selected["draft"]["post"]
        self.assertEqual(selected_text, alternative)
        selected_score = next(
            row for row in selected["editorial_iteration"]["candidates"]
            if row["presentation_strategy"] == "evidence_led_research"
        )
        self.assertNotIn("near_duplicate_of_recent_publication", selected_score["issues"])
        self.assertLess(selected_score["max_similarity_to_recent_publication"], 0.88)


    def test_rejects_one_reused_sentence_even_when_the_full_post_is_original(self):
        repeated_sentence = (
            "The useful test is whether the next reaction holds that structure "
            "rather than reversing it immediately."
        )
        repeated_post = (
            "$ETH's current funding basis tells a different story from spot price. "
            + repeated_sentence + " "
            "That difference can reveal positioning pressure, but it cannot prove "
            "which side will win. The next confirmation should come from fresh "
            "participation data rather than a recycled narrative. What evidence "
            "would change your read first?"
        )
        fresh_post = (
            "$ETH is showing a divergence between spot movement and derivatives "
            "positioning. A funding shift can matter when it persists across more "
            "than one observation, especially if open interest changes alongside "
            "price. That is a hypothesis to test, not proof of a coming move. "
            "Watch whether the next data point confirms the divergence or erases it. "
            "Which metric would you check first?"
        )
        context = {"recent_publication_texts": [repeated_sentence]}
        blocked = score_candidate(draft(repeated_post), context)
        self.assertIn("repeats_recent_published_sentence", blocked["issues"])
        self.assertEqual(blocked["repeated_recent_published_sentence_count"], 1)
        self.assertFalse(blocked["eligible"])

        def build(ctx):
            return draft(repeated_post if ctx["iteration_seed"] == 0 else fresh_post)

        selected = generate_and_select(context, build, max_candidates=2)
        self.assertEqual(selected["draft"]["post"], fresh_post)
        self.assertEqual(selected["editorial_iteration"]["eligible_candidates"], 1)

    def test_rejects_guaranteed_earnings_language(self):
        result = draft(
            "$ETH is a guaranteed profit opportunity. Price is around $2,500, "
            "with a recent range from $2,400 to $2,600. The evidence can change "
            "and this scenario needs confirmation. What do you think?"
        )
        report = score_candidate(result, {})
        self.assertIn("unsupported_earnings_or_certainty_claim", report["issues"])
        self.assertFalse(report["eligible"])

    def test_fails_closed_when_all_candidates_are_invalid(self):
        def build(_ctx):
            return draft("ETH will definitely pump. Guaranteed profit. What now?")
        with self.assertRaises(RuntimeError):
            generate_and_select({}, build, max_candidates=2)


if __name__ == "__main__":
    unittest.main()
