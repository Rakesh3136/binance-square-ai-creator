"""Binance Square style + monetization intelligence.

Learns platform-level patterns and public creator benchmarks without copying
creators, wording, identity, or unverifiable earnings claims.  Official
Write-to-Earn mechanics remain authoritative; observed creator claims are kept
explicitly separate from verified first-party data.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data/intelligence/square_style_intelligence.json"
MONETIZATION_OUT = ROOT / "data/intelligence/square_monetization_strategy.json"
REVENUE_REPORT = ROOT / "data/intelligence/creator_8_0_report.json"
PUBLICATION_TRUTH = ROOT / "data/live/creator_20_0_publication_truth.json"

OFFICIAL_SOURCES = [
    {
        "name": "Binance Square Write-to-Earn FAQ",
        "url": "https://www.binance.com/en/square/help/Write-to-Earn",
        "authority": "official",
    },
    {
        "name": "Binance Square Write-to-Earn page",
        "url": "https://www.binance.com/en/square/writetoearn",
        "authority": "official",
    },
    {
        "name": "Binance Square CreatorPad rewards",
        "url": "https://www.binance.com/en/square/creator",
        "authority": "official",
    },
    {
        "name": "Binance Square Skill Hub",
        "url": "https://www.binance.com/en/skills/detail/binance/square-post",
        "authority": "official",
    },
]

PUBLIC_BENCHMARK_SOURCES = [
    {
        "name": "Premium Analysis — public Write-to-Earn tips",
        "url": "https://www.binance.com/en/square/post/",
        "evidence_level": "self_reported_unverified",
        "notes": "Public creator claims about earnings/rank are treated as unverified examples, not facts about our own revenue.",
    },
    {
        "name": "Leo The Legend — public creator tips",
        "url": "https://www.binance.com/en/square/post/",
        "evidence_level": "public_creator_benchmark",
    },
    {
        "name": "BELLA BIT — public creator tips",
        "url": "https://www.binance.com/en/square/post/",
        "evidence_level": "public_creator_benchmark",
    },
    {
        "name": "blogtienso — public creator tips",
        "url": "https://www.binance.com/en/square/post/",
        "evidence_level": "public_creator_benchmark",
    },
]

BENCHMARKS = {
    "platform_guidance": {
        "hook_window": "first_3_seconds",
        "trading_formula": ["call_the_move", "own_take", "show_trade_when_relevant", "natural_cta"],
        "news_formula": ["what_is_happening", "image_or_video_when_relevant", "own_take", "show_trade_when_relevant"],
        "minimum_analysis_target_words": 50,
        "visual_principle": "Use a relevant image, chart, screenshot or original visual when it materially improves the story.",
        "human_signal": "Specific personal-style reasoning, observable decisions and concrete market context beat generic summaries.",
    },
    "observed_high_reach_patterns": [
        "Strong posts create tension before explaining it.",
        "The body adds a new fact or interpretation instead of repeating the headline.",
        "High-view examples often connect an event to a second-order market mechanism.",
        "Images and trading widgets act as proof/context rather than decoration.",
        "Conversational language and a recognizable point of view outperform sterile report language.",
        "A useful post gives the reader something to watch, compare or test next.",
        "Public creator advice repeatedly emphasizes timely topics, clear conclusions, verified trade proof, relevant cashtags and charts.",
        "Public creator advice favors actionable context over generic promotion or copy-paste summaries.",
        "Meme posts commonly use a simple immediately readable joke paired with an image rather than a synthetic infographic.",
    ],
    "anti_patterns": [
        "ticker + percentage + generic reaction sentence",
        "repeating the same support/resistance paragraph for every asset",
        "statistics dumps without interpretation",
        "generic AI transitions such as 'the mechanism to watch'",
        "generic questions appended only to manufacture comments",
        "copying a creator or reproducing a recognizable meme verbatim",
        "publishing text-only analysis when a chart or proof visual is clearly useful",
        "reusing the same meme image, four-panel cartoon or synthetic card repeatedly",
        "inventing a fake trade screenshot, fake outcome or fake earnings claim",
        "using a copyrighted reaction meme without a compatible license",
        "entirely repetitive content with no distinctive editorial judgment",
    ],
    "format_mix": {
        "technical_setup": {"visual": "verified_chart", "voice": "decision_point"},
        "capital_flow": {"visual": "verified_chart", "voice": "conditional_trade_thesis"},
        "research_radar": {"visual": "evidence_card_or_chart", "voice": "evidence_gap"},
        "news": {"visual": "event_context_or_chart", "voice": "second_order_effect"},
        "crypto_meme": {"visual": "real_world_photo_meme_or_original_scene", "voice": "recognizable_trader_humor"},
        "result_followup": {"visual": "result_card_when_supported", "voice": "accountability"},
    },
    "meme_visual_policy": {
        "preferred": "real-world human/reaction photograph from public-domain or CC0 sources, with original crypto caption tied to current market context",
        "secondary": "real market chart integrated into an original meme composition",
        "avoid": "repeated cartoon panels, generic AI-looking cards, copied famous memes, fake screenshots, fabricated statistics",
        "memory": "record recent source image and treatment so the next meme changes visual format",
        "copyright": "only public-domain or CC0 external photos are eligible for automatic use",
    },
}

WRITE_TO_EARN = {
    "attribution": {
        "required_bridge": "primary_coin_cashtag_or_verified_trading_widget",
        "direct_click_to_trade": True,
        "direct_click_window_minutes": 1,
        "own_trading_activity_earns": False,
        "max_relevant_cashtags": 3,
    },
    "commission": {
        "base_percent": 20,
        "rank_31_to_100_percent": 30,
        "rank_1_to_30_percent": 50,
    },
    "settlement": {
        "period": "Monday_to_Sunday_UTC",
        "payout_asset": "USDC",
        "payout_deadline": "following_Thursday",
        "minimum_weekly_payout": 0.1,
    },
    "content_and_reader_rules": {
        "supported_content": ["short_post", "article", "video", "live", "chat", "poll"],
        "qualified_trade_types": ["spot", "margin", "futures_except_copy_trading", "convert_instant"],
        "excluded_reader_activity": [
            "referral_user_trades",
            "API_trades",
            "fee_free_pairs",
            "market_maker_or_broker_activity",
            "stablecoin_to_stablecoin",
            "self_trading",
            "abnormal_frequent_click_behavior",
        ],
        "quality_requirement": "content must provide genuine reader value; monetization is never a reason to weaken quality or authenticity",
    },
}

MONETIZATION_CONTRACT = {
    "goal": "qualified_reader_trade_attribution_without_manipulation",
    "priority_order": [
        "signal_and_evidence_quality",
        "timeliness_and_reader_intent",
        "clear_trade_or_research_mechanism",
        "relevant_cashtag_or_verified_widget",
        "proof_visual_or_verified_trade_proof_when_available",
        "originality_and_human_editorial_judgment",
        "natural_specific_question",
        "accountability_and_outcome_follow_up",
    ],
    "market_post_requirements": {
        "primary_cashtag_required": True,
        "max_relevant_cashtags": 3,
        "chart_required_for_setup_lanes": True,
        "conditional_trade_language": True,
        "never_guarantee_outcome": True,
        "never_invent_trade_proof": True,
        "never_infer_revenue": True,
        "never_force_weak_story_for_monetization": True,
    },
    "reader_value_patterns": [
        "why_now",
        "what_market_mechanism_matters",
        "what_confirms_the_thesis",
        "what_invalidates_it",
        "what_to_watch_next",
        "one_specific_question",
    ],
    "proof_policy": {
        "verified_trade_card": "use only when first-party/system proof exists",
        "chart": "must correspond to the selected symbol and thesis",
        "outcome_post": "only after fresh verified market data confirms win/loss/mixed outcome",
    },
}

CREATORPAD_PRINCIPLES = {
    "mode": "campaign_aware_but_not_campaign_dependent",
    "rules": [
        "Monitor active CreatorPad campaigns and tasks when first-party campaign data is available.",
        "Treat campaign requirements as campaign-specific contracts, not generic publishing rules.",
        "Never claim campaign eligibility, reward amount or payout unless the campaign state is verified.",
        "Do not manufacture campaign hashtags, mentions or task completion.",
        "Historical campaigns are evidence of opportunity structure, not current offers.",
    ],
}


def load_json(path: Path, default: dict) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8")) if path.exists() else default
        return value if isinstance(value, dict) else default
    except Exception:
        return default


def observed_learning() -> dict:
    report = load_json(REVENUE_REPORT, {})
    truth = load_json(PUBLICATION_TRUTH, {})
    return {
        "revenue_engine_status": report.get("status", "UNKNOWN"),
        "verified_revenue_records": report.get("verified_revenue_records", 0),
        "attributed_records": report.get("attributed_records", 0),
        "repeated_signals": report.get("repeated_signals", 0),
        "allocated_verified_revenue": report.get("allocated_verified_revenue", 0),
        "attribution_coverage_percent": report.get("attribution_coverage_percent", 0),
        "publication_truth_state": truth.get("truth_state", "UNKNOWN"),
        "learning_policy": "verified-data-only; missing revenue or attribution stays missing",
    }


def main() -> None:
    now = datetime.now(timezone.utc).isoformat()
    learning = observed_learning()
    quality = {
        "official_mechanics_confidence": "HIGH",
        "public_creator_benchmark_confidence": "MEDIUM_OR_LOWER",
        "self_reported_earnings": "UNVERIFIED",
        "own_outcomes_priority": "HIGHEST",
    }
    payload = {
        "version": "2.0",
        "generated_at": now,
        "sources": OFFICIAL_SOURCES + PUBLIC_BENCHMARK_SOURCES,
        "benchmarks": BENCHMARKS,
        "write_to_earn": WRITE_TO_EARN,
        "monetization_contract": MONETIZATION_CONTRACT,
        "creatorpad_principles": CREATORPAD_PRINCIPLES,
        "learning_snapshot": learning,
        "research_confidence": quality,
        "training_policy": [
            "Learn patterns, not sentences.",
            "Use public creator examples as editorial benchmarks only; never clone identity, wording or signature jokes.",
            "Prefer first-party evidence and the creator system's own measured outcomes over generic internet advice.",
            "A post is monetization-ready only when it is independently publishable as useful content first.",
            "Revenue is an observed outcome, never an input that can justify fabrication or manipulation.",
        ],
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    strategy = {
        "version": "2.0",
        "generated_at": now,
        "official_write_to_earn": WRITE_TO_EARN,
        "monetization_contract": MONETIZATION_CONTRACT,
        "creatorpad_principles": CREATORPAD_PRINCIPLES,
        "selection_principles": MONETIZATION_CONTRACT["priority_order"],
        "learning_snapshot": learning,
        "research_confidence": quality,
        "sources": OFFICIAL_SOURCES + PUBLIC_BENCHMARK_SOURCES,
    }
    MONETIZATION_OUT.parent.mkdir(parents=True, exist_ok=True)
    MONETIZATION_OUT.write_text(json.dumps(strategy, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(json.dumps({
        "status": "OK",
        "version": "2.0",
        "write_to_earn_bridge": WRITE_TO_EARN["attribution"],
        "base_commission_percent": WRITE_TO_EARN["commission"]["base_percent"],
        "max_relevant_cashtags": WRITE_TO_EARN["attribution"]["max_relevant_cashtags"],
        "learning": learning,
        "outputs": [str(OUT), str(MONETIZATION_OUT)],
    }, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
