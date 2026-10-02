"""NIC Monetization Intelligence 2.0 — editorial contract and attribution ledger.

This module makes monetization experimentation a first-class, durable contract.
It never predicts revenue, fabricates reader activity, or overrides market,
quality, originality, safety, visual, WTE, or publication gates.

Usage:
    python src/nic_monetization_os.py pre
    python src/nic_monetization_os.py post
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LIVE = ROOT / "data" / "live"
ANALYTICS = ROOT / "analytics"
INTEL = ROOT / "data" / "intelligence"

WTE_PLAN = LIVE / "write_to_earn_7day_plan.json"
WTE_STATUS = LIVE / "write_to_earn_7day_status.json"
WTE_ELIGIBILITY = LIVE / "write_to_earn_eligibility.json"
EXPERIMENT_PLAN = ANALYTICS / "creator_7_4_experiment_plan.json"
EXPERIMENT_GOVERNOR = LIVE / "nic_experiment_governor.json"
REVENUE_DIRECTOR = LIVE / "revenue_content_director.json"
ATTRIBUTION = ANALYTICS / "publication_attribution.jsonl"
PERFORMANCE = ANALYTICS / "square_performance.jsonl"
REWARD_EVENTS = ANALYTICS / "wte_reward_events.jsonl"
PUBLICATION_LOG = ANALYTICS / "publication_log.jsonl"
PUBLICATION_RESULT = LIVE / "publication_result.json"
CONTRACT = LIVE / "nic_monetization_contract.json"
LEDGER = ANALYTICS / "nic_monetization_os.jsonl"
DASHBOARD = LIVE / "nic_monetization_dashboard.json"
REPORT = INTEL / "nic_monetization_os_report.json"

LANES = {
    "market_setup": {
        "day": 1,
        "goal": "Build a chart-first market setup around one verified decision point.",
        "format": "decision_chart",
        "hook_type": "decision_point",
        "visual_type": "decision_map",
        "reader_payoff_type": "confirmation_rule",
    },
    "data_investigation": {
        "day": 2,
        "goal": "Investigate one unusual market relationship or data anomaly and explain why it matters.",
        "format": "data_investigation",
        "hook_type": "data_contradiction",
        "visual_type": "relationship_chart",
        "reader_payoff_type": "data_relationship",
    },
    "news_impact": {
        "day": 3,
        "goal": "Connect one fresh verified event to a supplied market mechanism and observable response.",
        "format": "news_mechanism",
        "hook_type": "verified_event",
        "visual_type": "event_to_market_map",
        "reader_payoff_type": "mechanism_explanation",
    },
    "asset_comparison": {
        "day": 4,
        "goal": "Compare two evidence-supported assets or market paths and expose the trade-off.",
        "format": "asset_comparison",
        "hook_type": "relative_strength_gap",
        "visual_type": "comparison_chart",
        "reader_payoff_type": "tradeoff_framework",
    },
    "contrarian_thesis": {
        "day": 5,
        "goal": "Test the obvious interpretation against contrary evidence and define what would falsify it.",
        "format": "contrarian_analysis",
        "hook_type": "obvious_trade_problem",
        "visual_type": "failure_map",
        "reader_payoff_type": "falsification_test",
    },
    "outcome_accountability": {
        "day": 6,
        "goal": "Revisit a prior thesis only when fresh evidence exists and state exactly what changed.",
        "format": "accountability_followup",
        "hook_type": "thesis_result",
        "visual_type": "before_after",
        "reader_payoff_type": "what_changed",
    },
    "weekly_synthesis": {
        "day": 7,
        "goal": "Synthesize the week's verified observations and define the next measurable test.",
        "format": "weekly_synthesis",
        "hook_type": "pattern_summary",
        "visual_type": "multi_asset_summary",
        "reader_payoff_type": "next_test",
    },
}

def load_json(path: Path, default: dict) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else default
    except Exception:
        return default

def load_jsonl(path: Path, limit: int = 1000) -> list[dict]:
    if not path.exists():
        return []
    rows: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines()[-limit:]:
        try:
            value = json.loads(line)
            if isinstance(value, dict):
                rows.append(value)
        except Exception:
            continue
    return rows

def clean_symbol(value: object) -> str:
    symbol = re.sub(r"USDT$", "", str(value or "").upper().replace("$", "").strip())
    return symbol if re.fullmatch(r"[A-Z0-9]{1,15}", symbol) else ""

def canonical_post_id(value: object) -> str:
    raw = str(value or "").strip().rstrip("/")
    if "/square/post/" in raw:
        raw = raw.split("/square/post/", 1)[1].split("?", 1)[0].split("#", 1)[0]
    return raw if re.fullmatch(r"[A-Za-z0-9_-]{1,128}", raw) else ""

def active_experiment() -> dict:
    plan = load_json(EXPERIMENT_PLAN, {})
    current = plan.get("current_experiment") if isinstance(plan, dict) else {}
    return current if isinstance(current, dict) else {}

def infer_lane(status: dict, plan: dict) -> tuple[str, dict]:
    lane = str((status.get("current_lane") or {}).get("name") or plan.get("lane") or "").strip().lower()
    if lane in LANES:
        return lane, LANES[lane]
    return "market_setup", LANES["market_setup"]

def known_asset() -> str:
    for path, keys in (
        (LIVE / "authoritative_opportunity.json", ("symbol",)),
        (LIVE / "editorial_preflight.json", ("selected_opportunity", "symbol")),
        (LIVE / "creator_brain_decision.json", ("symbol",)),
    ):
        data = load_json(path, {})
        if path.name == "editorial_preflight.json":
            data = data.get("selected_opportunity") if isinstance(data.get("selected_opportunity"), dict) else {}
        for key in keys:
            symbol = clean_symbol(data.get(key))
            if symbol:
                return symbol
    return ""

def experiment_metadata() -> tuple[str, str, str]:
    current = active_experiment()
    experiment_id = str(current.get("experiment_id") or "").strip()
    variable = str(current.get("primary_variable") or "").strip()
    treatment = str(current.get("treatment_value") or "").strip()
    if not experiment_id:
        run_id = os.getenv("GITHUB_RUN_ID", "").strip() or "manual"
        seed = f"{run_id}:{datetime.now(timezone.utc).strftime('%Y%m%d%H%M')}"
        experiment_id = "nic-" + hashlib.sha256(seed.encode()).hexdigest()[:16]
    return experiment_id, variable or "content_lane", treatment or "lane_native"

def cycle_id(campaign_day: int, lane: str, experiment_id: str) -> str:
    run_id = os.getenv("GITHUB_RUN_ID", "").strip() or "manual"
    seed = f"{run_id}:{campaign_day}:{lane}:{experiment_id}"
    return "nic-" + hashlib.sha256(seed.encode()).hexdigest()[:20]

def append_event(event: dict) -> bool:
    event_id = str(event.get("event_id") or "").strip()
    if not event_id:
        return False
    existing = {str(x.get("event_id")) for x in load_jsonl(LEDGER, 5000)}
    if event_id in existing:
        return False
    ANALYTICS.mkdir(parents=True, exist_ok=True)
    with LEDGER.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, ensure_ascii=False) + "\n")
    return True

def read_matching_publication(post_id: str) -> dict:
    if not post_id:
        return {}
    for row in reversed(load_jsonl(PUBLICATION_LOG, 1000)):
        candidate = canonical_post_id(row.get("canonical_post_id") or row.get("post_id") or row.get("link"))
        if candidate == post_id:
            return row
    return {}

def verified_reward(post_id: str) -> tuple[float | None, str | None]:
    for event in reversed(load_jsonl(REWARD_EVENTS, 5000)):
        candidate = canonical_post_id(event.get("canonical_post_id") or event.get("post_id") or event.get("publication_id"))
        amount = event.get("reward_amount_usdc")
        if candidate == post_id and event.get("verified") is True and amount is not None:
            try:
                return round(float(amount), 8), str(event.get("source") or "explicit_reward_event")
            except Exception:
                pass
    return None, None

def performance_snapshot(post_id: str) -> dict:
    if not post_id:
        return {}
    for row in reversed(load_jsonl(PERFORMANCE, 5000)):
        candidate = canonical_post_id(row.get("canonical_post_id") or row.get("post_id") or row.get("publication_id"))
        if candidate == post_id:
            return row
    return {}

def build_pre_contract() -> dict:
    status = load_json(WTE_STATUS, {})
    plan = load_json(WTE_PLAN, {})
    eligibility = load_json(WTE_ELIGIBILITY, {})
    governor = load_json(EXPERIMENT_GOVERNOR, {})
    revenue_director = load_json(REVENUE_DIRECTOR, {})
    lane, lane_meta = infer_lane(status, plan)
    experiment_id, variable, treatment = experiment_metadata()
    asset = known_asset()
    run_id = os.getenv("GITHUB_RUN_ID", "").strip() or None
    day = int(status.get("campaign_day") or lane_meta["day"])
    contract = {
        "version": "2.0",
        "status": "PREPUBLICATION",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "cycle_id": cycle_id(day, lane, experiment_id),
        "run_id": run_id,
        "campaign_day": day,
        "content_lane": lane,
        "lane_goal": lane_meta["goal"],
        "content_format": lane_meta["format"],
        "hook_type": lane_meta["hook_type"],
        "visual_type": lane_meta["visual_type"],
        "reader_payoff_type": lane_meta["reader_payoff_type"],
        "asset": asset or None,
        "cashtag": "$" + asset if asset else None,
        "planned_publication_time": os.getenv("NIC_PLANNED_PUBLICATION_TIME") or None,
        "publication_time": None,
        "experiment_id": experiment_id,
        "experiment_variable": variable,
        "experiment_treatment": treatment,
        "experiment_source": "creator_7_4_adaptive_experiment_controller" if active_experiment().get("experiment_id") else "NIC_cold_start",
        "experiment_governor_decision": governor.get("decision"),
        "reader_action": "Inspect the supplied asset/evidence through the exact supported Binance Square asset surface; never pressure a trade.",
        "reward_state": "UNKNOWN",
        "revenue_state": "UNKNOWN",
        "attribution_state": "AWAITING_PUBLICATION",
        "evidence_policy": {
            "reader_trades_must_be_explicitly_verified": True,
            "revenue_must_be_explicitly_verified": True,
            "views_are_not_revenue": True,
            "prediction_success_is_not_revenue": True,
            "missing_attribution_stays_unknown": True,
        },
        "inputs": {
            "wte_status_version": status.get("version"),
            "wte_plan_version": plan.get("version"),
            "wte_eligibility": eligibility.get("eligible"),
            "active_experiment_id": active_experiment().get("experiment_id"),
            "revenue_director_status": revenue_director.get("status"),
        },
        "handoff": {
            "preserve_selected_asset": True,
            "preserve_lane_when_fallback": True,
            "preserve_experiment_lineage_when_fallback": True,
            "publish_only_through_existing_gates": True,
        },
    }
    return contract

def dashboard_post_phase(contract: dict) -> dict:
    result = load_json(PUBLICATION_RESULT, {})
    contract_created = contract.get("created_at")
    result_checked = result.get("checked_at")
    if contract_created and result_checked:
        try:
            created_dt = datetime.fromisoformat(str(contract_created).replace("Z", "+00:00"))
            checked_dt = datetime.fromisoformat(str(result_checked).replace("Z", "+00:00"))
            if checked_dt < created_dt:
                result = {}
        except Exception:
            pass
    post_id = canonical_post_id(result.get("canonical_post_id") or result.get("post_id"))
    publication = read_matching_publication(post_id)
    reward, reward_source = verified_reward(post_id)
    performance = performance_snapshot(post_id)
    monetization = publication.get("monetization") if isinstance(publication.get("monetization"), dict) else {}
    cashtag_present = bool(monetization.get("has_primary_cashtag") or publication.get("has_primary_cashtag") or publication.get("cashtag"))
    pub_status = str(result.get("status") or publication.get("status") or "NO_PUBLICATION")
    verified_publication = bool(post_id and publication.get("publication_id_verified") is not False and str(publication.get("publication_proof") or "").strip())
    stages = {
        "eligible_topic": {"status": "OBSERVED" if contract.get("asset") else "UNKNOWN"},
        "publication": {"status": "VERIFIED" if verified_publication else ("SUBMITTED_UNKNOWN" if pub_status == "PUBLISHED_SUBMITTED_504" else "UNKNOWN")},
        "reach": {"status": "OBSERVED" if performance else "UNKNOWN", "views": performance.get("views") if performance else None},
        "engagement": {"status": "OBSERVED" if performance else "UNKNOWN", "likes": performance.get("likes") if performance else None, "comments": performance.get("comments") if performance else None, "shares": performance.get("shares") if performance else None},
        "asset_interaction": {"status": "UNKNOWN" if not cashtag_present else "ATTRIBUTION_READY", "evidence": "Primary cashtag/widget presence is known; reader interaction itself is not inferred."},
        "qualifying_reader_activity": {"status": "VERIFIED" if reward is not None else "UNKNOWN"},
        "verified_wte_commission": {"status": "VERIFIED" if reward is not None else "UNKNOWN", "amount_usdc": reward},
    }
    revenue_state = "VERIFIED" if reward is not None else "UNKNOWN"
    contract.update({
        "status": "POSTPUBLICATION",
        "publication_time": publication.get("published_at") or result.get("checked_at"),
        "post_id": post_id or None,
        "canonical_post_id": post_id or None,
        "cashtag_present": cashtag_present,
        "attribution_state": "VERIFIED_POST_ID" if verified_publication else "UNKNOWN",
        "reward_state": revenue_state,
        "revenue_state": revenue_state,
        "performance_observed": bool(performance),
        "stages": stages,
        "reward_source": reward_source,
        "publication_status": pub_status,
    })
    return contract

def post_events(contract: dict) -> int:
    count = 0
    post_id = canonical_post_id(contract.get("post_id") or contract.get("canonical_post_id"))
    cycle = str(contract.get("cycle_id") or "unknown")
    if post_id:
        pub = read_matching_publication(post_id)
        event_id = f"{cycle}:publication:{post_id}"
        count += int(append_event({
            "event_id": event_id,
            "event_type": "PUBLICATION_VERIFIED" if pub.get("publication_id_verified") is not False else "PUBLICATION_OBSERVED",
            "observed_at": datetime.now(timezone.utc).isoformat(),
            "cycle_id": cycle,
            "post_id": post_id,
            "experiment_id": contract.get("experiment_id"),
            "campaign_day": contract.get("campaign_day"),
            "content_lane": contract.get("content_lane"),
            "content_format": contract.get("content_format"),
            "hook_type": contract.get("hook_type"),
            "visual_type": contract.get("visual_type"),
            "reader_payoff_type": contract.get("reader_payoff_type"),
            "asset": contract.get("asset"),
            "source": "publication_log",
        }))
        perf = performance_snapshot(post_id)
        if perf:
            digest = hashlib.sha256(json.dumps(perf, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:16]
            count += int(append_event({
                "event_id": f"{cycle}:performance:{digest}",
                "event_type": "PERFORMANCE_OBSERVED",
                "observed_at": datetime.now(timezone.utc).isoformat(),
                "cycle_id": cycle,
                "post_id": post_id,
                "experiment_id": contract.get("experiment_id"),
                "campaign_day": contract.get("campaign_day"),
                "content_lane": contract.get("content_lane"),
                "content_format": contract.get("content_format"),
                "hook_type": contract.get("hook_type"),
                "visual_type": contract.get("visual_type"),
                "reader_payoff_type": contract.get("reader_payoff_type"),
                "asset": contract.get("asset"),
                "metrics": {k: perf.get(k) for k in ("views", "likes", "comments", "shares", "quotes", "follower_growth") if k in perf},
                "source": "square_performance",
            }))
        reward, source = verified_reward(post_id)
        if reward is not None:
            count += int(append_event({
                "event_id": f"{cycle}:reward:{post_id}:{reward:.8f}",
                "event_type": "WTE_REWARD_VERIFIED",
                "observed_at": datetime.now(timezone.utc).isoformat(),
                "cycle_id": cycle,
                "post_id": post_id,
                "experiment_id": contract.get("experiment_id"),
                "campaign_day": contract.get("campaign_day"),
                "content_lane": contract.get("content_lane"),
                "content_format": contract.get("content_format"),
                "hook_type": contract.get("hook_type"),
                "visual_type": contract.get("visual_type"),
                "reader_payoff_type": contract.get("reader_payoff_type"),
                "asset": contract.get("asset"),
                "reward_amount_usdc": reward,
                "source": source,
                "verified": True,
            }))
    return count

def build_learning_summary() -> dict:
    groups: dict[tuple[str, str, str], dict] = defaultdict(lambda: {"posts": 0, "views": 0.0, "engagement": 0.0, "verified_revenue": 0.0, "rewarded_posts": 0})
    for row in load_jsonl(ATTRIBUTION, 5000):
        post_id = canonical_post_id(row.get("canonical_post_id") or row.get("post_id"))
        if not post_id:
            continue
        lane = str(row.get("content_lane") or row.get("story_lane") or "unknown")
        fmt = str(row.get("content_format") or row.get("format") or "unknown")
        hook = str(row.get("hook_type") or "unknown")
        key = (lane, fmt, hook)
        g = groups[key]
        g["posts"] += 1
        perf = performance_snapshot(post_id)
        try:
            g["views"] += float(perf.get("views") or 0)
        except Exception:
            pass
        for k in ("likes", "comments", "shares"):
            try:
                g["engagement"] += float(perf.get(k) or 0)
            except Exception:
                pass
        reward, _ = verified_reward(post_id)
        if reward is not None:
            g["rewarded_posts"] += 1
            g["verified_revenue"] += reward
    observations = []
    for (lane, fmt, hook), g in sorted(groups.items(), key=lambda item: (item[1]["verified_revenue"], item[1]["engagement"]), reverse=True):
        observations.append({
            "content_lane": lane,
            "content_format": fmt,
            "hook_type": hook,
            **{k: round(v, 8) if isinstance(v, float) else v for k, v in g.items()},
            "evidence": "VERIFIED_REWARD_PLUS_OBSERVATION" if g["rewarded_posts"] else "OBSERVATIONAL_ONLY",
        })
    return {
        "observations": observations[:100],
        "sample_groups": len(observations),
        "verified_reward_groups": sum(1 for x in observations if x["rewarded_posts"]),
        "learning_policy": "Observations are hypotheses. Do not infer causality from views/engagement and do not infer revenue without explicit verified reward events.",
    }

def main() -> int:
    phase = str(sys.argv[1] if len(sys.argv) > 1 else os.getenv("NIC_MONETIZATION_PHASE", "pre")).strip().lower()
    if phase not in {"pre", "post"}:
        print("Usage: python src/nic_monetization_os.py [pre|post]", file=sys.stderr)
        return 2
    LIVE.mkdir(parents=True, exist_ok=True)
    INTEL.mkdir(parents=True, exist_ok=True)
    if phase == "pre":
        contract = build_pre_contract()
        CONTRACT.write_text(json.dumps(contract, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        append_event({
            "event_id": f"{contract['cycle_id']}:contract",
            "event_type": "CONTRACT_CREATED",
            "observed_at": contract["created_at"],
            "cycle_id": contract["cycle_id"],
            "campaign_day": contract["campaign_day"],
            "content_lane": contract["content_lane"],
            "content_format": contract["content_format"],
            "hook_type": contract["hook_type"],
            "visual_type": contract["visual_type"],
            "reader_payoff_type": contract["reader_payoff_type"],
            "asset": contract["asset"],
            "experiment_id": contract["experiment_id"],
            "experiment_variable": contract["experiment_variable"],
            "experiment_treatment": contract["experiment_treatment"],
            "source": "nic_monetization_os_pre",
        })
        print(json.dumps({"status": "READY", "phase": "pre", "cycle_id": contract["cycle_id"], "campaign_day": contract["campaign_day"], "content_lane": contract["content_lane"], "experiment_id": contract["experiment_id"]}, ensure_ascii=False))
        return 0

    current = load_json(CONTRACT, {})
    if not current:
        # Post-publication intelligence can run independently of a current
        # prepublication contract. Always emit the canonical dashboard/report
        # so the workflow's artifact contract remains valid.
        now = datetime.now(timezone.utc).isoformat()
        dashboard = {
            "version": "2.1",
            "generated_at": now,
            "status": "NO_PREPUBLICATION_CONTRACT",
            "cycle_id": None,
            "post_id": None,
            "verified_reward_usdc": None,
            "learning": build_learning_summary(),
            "events_added_this_refresh": 0,
            "explicit_unknowns": [
                "No active prepublication contract was available for this refresh.",
                "Reader trade activity is UNKNOWN unless an explicit verified reward event is present.",
                "Revenue is UNKNOWN unless an explicit verified reward amount is present.",
            ],
        }
        DASHBOARD.write_text(json.dumps(dashboard, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        REPORT.write_text(json.dumps({
            "version": "2.1",
            "status": dashboard["status"],
            "generated_at": now,
            "post_id": None,
            "verified_reward_usdc": None,
        }, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print("NIC Monetization OS: no prepublication contract; emitted empty postpublication intelligence snapshot.")
        return 0
    updated = dashboard_post_phase(current)
    events_added = post_events(updated)
    learning = build_learning_summary()
    CONTRACT.write_text(json.dumps(updated, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    dashboard = {
        "version": "2.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "cycle_id": updated.get("cycle_id"),
        "campaign_day": updated.get("campaign_day"),
        "content_lane": updated.get("content_lane"),
        "content_format": updated.get("content_format"),
        "hook_type": updated.get("hook_type"),
        "visual_type": updated.get("visual_type"),
        "reader_payoff_type": updated.get("reader_payoff_type"),
        "experiment_id": updated.get("experiment_id"),
        "post_id": updated.get("post_id"),
        "funnel": updated.get("stages", {}),
        "verified_reward_usdc": next((x["amount_usdc"] for x in updated.get("stages", {}).values() if isinstance(x, dict) and x.get("amount_usdc") is not None), None),
        "learning": learning,
        "explicit_unknowns": [
            "Asset interaction is UNKNOWN unless explicit telemetry is present.",
            "Reader trade activity is UNKNOWN unless an explicit verified reward event is present.",
            "Revenue is UNKNOWN unless an explicit verified reward amount is present.",
        ],
        "events_added_this_refresh": events_added,
    }
    DASHBOARD.write_text(json.dumps(dashboard, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    REPORT.write_text(json.dumps({
        "version": "2.0",
        "status": "READY",
        "generated_at": dashboard["generated_at"],
        "cycle_id": updated.get("cycle_id"),
        "post_id": updated.get("post_id"),
        "content_lane": updated.get("content_lane"),
        "experiment_id": updated.get("experiment_id"),
        "reward_state": updated.get("reward_state"),
        "revenue_state": updated.get("revenue_state"),
        "sample_groups": learning["sample_groups"],
        "verified_reward_groups": learning["verified_reward_groups"],
        "events_added": events_added,
    }, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "READY", "phase": "post", "post_id": updated.get("post_id"), "reward_state": updated.get("reward_state"), "events_added": events_added, "sample_groups": learning["sample_groups"]}, ensure_ascii=False))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
