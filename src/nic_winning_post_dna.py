"""Reconcile verified Write-to-Earn evidence without inventing post attribution."""
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load(path):
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, (dict, list)) else {}
    except (OSError, ValueError, TypeError):
        return {}


def load_jsonl(path):
    rows = []
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                try:
                    row = json.loads(line)
                    if isinstance(row, dict):
                        rows.append(row)
                except ValueError:
                    continue
    except OSError:
        pass
    return rows


def post_id(row):
    value = row.get("canonical_post_id") or row.get("post_id")
    return str(value).strip() if value is not None and str(value).strip() else None


def build(engine, contract, reward_events=None, external_events=None, attribution=None):
    """Build post-level patterns only from explicitly verified, exactly linked rewards.

    Reward notifications without a post ID remain visible as unattributed evidence. Never
    assign them to a post based on timing, coin, views, or conversational assumptions.
    """
    reward_events = reward_events or []
    external_events = external_events or []
    attribution = attribution or {}
    funnel = engine.get("publication_funnel", []) if isinstance(engine, dict) else []
    funnel = funnel if isinstance(funnel, list) else []
    attribution_posts = attribution.get("posts", []) if isinstance(attribution, dict) else []
    meta = {}
    for row in funnel + (attribution_posts if isinstance(attribution_posts, list) else []):
        if isinstance(row, dict) and post_id(row):
            meta[post_id(row)] = row

    # Build verified reward evidence by exact post identifier only.
    rewards_by_post = defaultdict(float)
    reward_event_ids = set()
    unattributed = []
    for event in reward_events + external_events:
        if not isinstance(event, dict):
            continue
        verified = event.get("verified") is True or event.get("attribution_status") == "VERIFIED"
        # External notification records are retained as observed reward evidence but are
        # not treated as verified post-level revenue unless explicit verification exists.
        amount = event.get("reward_amount_usdc")
        try:
            amount = float(amount)
        except (TypeError, ValueError):
            continue
        if amount < 0:
            continue
        eid = str(event.get("event_id") or "")
        if eid and eid in reward_event_ids:
            continue
        if eid:
            reward_event_ids.add(eid)
        pid = post_id(event)
        if verified and pid:
            rewards_by_post[pid] += amount
        else:
            unattributed.append({
                "event_id": eid or None,
                "reward_amount_usdc": amount,
                "currency": event.get("currency", "USDC"),
                "post_id": pid,
                "verified": verified,
                "detail_status": event.get("detail_status") or event.get("attribution_status") or "UNATTRIBUTED",
                "source": event.get("source"),
            })

    rows_by_id = {}
    for row in funnel:
        if not isinstance(row, dict) or not post_id(row):
            continue
        pid = post_id(row)
        activity = row.get("verified_activity") or {}
        try:
            amount = float(activity.get("reward_amount_usdc")) if activity.get("revenue_verified") is True and activity.get("reward_amount_usdc") is not None else 0.0
        except (TypeError, ValueError):
            amount = 0.0
        # Avoid double-counting a reward already recorded in the verified event ledger.
        if amount and not rewards_by_post.get(pid):
            rewards_by_post[pid] += amount
        rows_by_id[pid] = row

    for pid, amount in rewards_by_post.items():
        row = meta.get(pid, {})
        performance = row.get("performance") or {}
        rows_by_id.setdefault(pid, row)
        rows_by_id[pid] = {
            "canonical_post_id": pid,
            "category": row.get("category") or row.get("content_lane") or "unknown",
            "symbol": row.get("symbol"),
            "published_at": row.get("published_at"),
            "has_primary_cashtag": row.get("has_primary_cashtag", row.get("cashtag_present", False)),
            "visual_attached": row.get("visual_attached", False),
            "performance": performance,
            "verified_reward_usdc": round(amount, 8),
        }

    verified_rows = []
    for pid, row in rows_by_id.items():
        amount = rewards_by_post.get(pid, 0.0)
        activity = row.get("verified_activity") or {}
        if amount > 0:
            verified_rows.append({
                "post_id": pid,
                "category": str(row.get("category") or row.get("content_lane") or "unknown"),
                "revenue": amount,
                "views": float((row.get("performance") or {}).get("views") or row.get("views") or 0),
                "cashtag": bool(row.get("has_primary_cashtag", row.get("cashtag_present", False))),
                "visual": bool(row.get("visual_attached", False)),
                "symbol": row.get("symbol"),
            })

    cats = defaultdict(lambda: {"posts": 0, "revenue": 0.0, "views": 0.0, "cashtags": 0, "visuals": 0})
    for row in verified_rows:
        c = cats[row["category"]]
        c["posts"] += 1
        c["revenue"] += row["revenue"]
        c["views"] += row["views"]
        c["cashtags"] += int(row["cashtag"])
        c["visuals"] += int(row["visual"])
    ranked = sorted(cats.items(), key=lambda item: (item[1]["revenue"], item[1]["posts"]), reverse=True)

    known_unattributed_total = round(sum(item["reward_amount_usdc"] for item in unattributed if item["verified"]), 8)
    observed_unattributed_total = round(sum(item["reward_amount_usdc"] for item in unattributed), 8)
    count = len(verified_rows)
    if count >= 3:
        status = "VERIFIED_PATTERN_CANDIDATES"
    elif known_unattributed_total > 0 or observed_unattributed_total > 0:
        status = "VERIFIED_REWARD_EVIDENCE_NEEDS_POST_LINKS"
    else:
        status = "INSUFFICIENT_VERIFIED_REVENUE"

    return {
        "schema": "NIC-WINNING-POST-DNA-1.1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "verified_revenue_post_count": count,
        "verified_revenue_total_usdc": round(sum(row["revenue"] for row in verified_rows), 8),
        "verified_post_ids": [row["post_id"] for row in verified_rows],
        "verified_post_evidence": verified_rows,
        "verified_unattributed_reward_total_usdc": known_unattributed_total,
        "observed_unattributed_reward_total_usdc": observed_unattributed_total,
        "unattributed_reward_events": unattributed,
        "source_coverage": {
            "publication_funnel_rows": len(funnel),
            "attribution_post_rows": len(attribution_posts) if isinstance(attribution_posts, list) else 0,
            "verified_reward_event_rows": len(reward_events),
            "external_reward_event_rows": len(external_events),
            "attribution_policy": "Exact post IDs only; missing links are never inferred.",
        },
        "category_evidence": {
            key: {
                "posts": value["posts"],
                "revenue_usdc": round(value["revenue"], 8),
                "views": value["views"],
                "cashtag_rate": round(value["cashtags"] / value["posts"], 3),
                "visual_rate": round(value["visuals"] / value["posts"], 3),
            }
            for key, value in cats.items()
        },
        "editorial_contract": {
            "priority": "reader_value_then_evidence_then_actionability",
            "required_sequence": [
                "specific_hook", "what_changed_and_why_now", "evidence_not_hype",
                "conditional_setup_or_watch_level", "confirmation",
                "invalidation_and_risk", "reader_next_step",
            ],
            "chart_requirements": [
                "correct_asset_and_timeframe", "verified_levels_only",
                "show_confirmation_and_invalidation", "annotate_the_thesis_not_decoration",
            ],
            "variation_policy": [
                "vary_hook_and_structure_from_evidence", "one_primary_thesis_per_post",
                "repeat_asset_only_for_material_new_evidence", "never_invent_news_levels_or_revenue",
            ],
            "truth_policy": {
                "views_are_not_revenue": True,
                "likes_are_not_revenue": True,
                "prediction_success_is_not_revenue": True,
                "missing_attribution_is_not_inferred": True,
            },
            "historical_best_category_candidate": ranked[0][0] if count >= 3 and ranked else None,
            "policy": "Advisory only; existing safety, timing, cooldown, forecast, chart-truth and publication gates remain authoritative.",
        },
        "next_actions": [
            "Join verified rewards to exact canonical post IDs.",
            "Keep reward notifications without IDs visible but unattributed.",
            "Compare verified-revenue posts with comparable zero-revenue posts before changing strategy.",
        ],
    }


def main():
    root = Path(__file__).resolve().parents[1]
    engine = load(root / "analytics/creator_8_0_monetization_engine.json")
    contract = load(root / "data/live/nic_monetization_contract.json")
    reward_events = load_jsonl(root / "analytics/wte_reward_events.jsonl")
    external_events = load_jsonl(root / "analytics/external_reward_events.jsonl")
    attribution = load(root / "data/live/wte_monetization_attribution.json")
    output = build(engine, contract, reward_events, external_events, attribution)
    path = root / "data/live/nic_winning_post_dna.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "status": output["status"],
        "verified_revenue_post_count": output["verified_revenue_post_count"],
        "verified_revenue_total_usdc": output["verified_revenue_total_usdc"],
        "verified_unattributed_reward_total_usdc": output["verified_unattributed_reward_total_usdc"],
        "observed_unattributed_reward_total_usdc": output["observed_unattributed_reward_total_usdc"],
    }))
    return output


if __name__ == "__main__":
    main()
