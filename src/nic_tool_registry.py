"""Bounded, read-only tools exposed to NIC's owner-operated agent runtime.

This module deliberately grants no publication, account, secret, filesystem-write,
or arbitrary command authority. Every tool reads a fixed allowlisted artifact.
"""
from __future__ import annotations

import html
import json
import re
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
TOOLS: dict[str, dict[str, Any]] = {
    "get_live_market_data": {
        "description": "Fetch a live public Binance Spot ticker and recent candles for one USDT symbol. Read-only market context, not trading advice.",
        "parameters": {
            "type": "object",
            "properties": {
                "symbol": {"type": "string", "minLength": 5, "maxLength": 20},
                "interval": {"type": "string", "enum": ["1h", "4h", "1d"]}
            },
            "required": ["symbol", "interval"],
            "additionalProperties": False
        }
    },
    "search_public_news": {
        "description": "Search Google News RSS for recent public headlines. Discovery only; verify claims with primary sources before publication.",
        "parameters": {
            "type": "object",
            "properties": {"query": {"type": "string", "minLength": 2, "maxLength": 120}},
            "required": ["query"],
            "additionalProperties": False
        }
    },
    "get_verified_research_evidence": {
        "description": "Read NIC's bounded research evidence register with its recorded source class, retrieval state, freshness label and limitations.",
        "parameters": {"type": "object", "properties": {}, "additionalProperties": False}
    },
    "get_reward_pattern_insights": {
        "description": "Read content-format and hook observations from NIC's reward pattern lab, keeping verified and owner-reported reward evidence separate.",
        "parameters": {"type": "object", "properties": {}, "additionalProperties": False}
    },
    "get_agent_registry": {
        "description": "Read NIC specialist roles, their workflow wiring, and honest integration states.",
        "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    "get_creator_dashboard": {
        "description": "Read the latest creator command-center summary and evidence status.",
        "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    "list_recent_research": {
        "description": "List a small sample of locally persisted research reports and metadata.",
        "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    "get_latest_publication": {
        "description": "Read the latest exact-ID Binance Square publication record; does not publish anything.",
        "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    "get_reward_learning_status": {
        "description": "Read verified and owner-reported reward-learning totals, coverage, and blockers separately.",
        "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    "get_creator_period_coverage": {
        "description": "Read creator-week reward cohort coverage and 7/14-day post-window completeness without attributing weekly totals to posts.",
        "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    "list_creator_study_queue": {
        "description": "List a bounded sample of creator profiles NIC is studying, with public engagement clearly separated from earnings.",
        "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
    },
}


class ToolExecutionError(ValueError):
    """Raised when a tool request is invalid or its evidence is unavailable."""


def tool_catalog() -> list[dict[str, Any]]:
    """Return a JSON-serializable allowlist suitable for a model tool declaration."""
    return [{"name": name, **definition} for name, definition in TOOLS.items()]


def _read_json(relative_path: str) -> dict[str, Any]:
    path = (ROOT / relative_path).resolve()
    if ROOT not in path.parents or not path.is_file():
        raise ToolExecutionError(f"evidence_unavailable:{relative_path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ToolExecutionError(f"evidence_unreadable:{relative_path}") from exc
    if not isinstance(payload, dict):
        raise ToolExecutionError(f"evidence_invalid_shape:{relative_path}")
    return payload


def _read_jsonl_tail(relative_path: str, limit: int = 5) -> list[dict[str, Any]]:
    path = (ROOT / relative_path).resolve()
    if ROOT not in path.parents or not path.is_file():
        raise ToolExecutionError(f"evidence_unavailable:{relative_path}")
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError) as exc:
        raise ToolExecutionError(f"evidence_unreadable:{relative_path}") from exc
    rows: list[dict[str, Any]] = []
    for line in lines[-limit:]:
        try:
            row = json.loads(line)
        except (TypeError, json.JSONDecodeError):
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows


def execute_tool(name: str, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
    """Execute one allowlisted read-only tool; reject unknown or extra arguments."""
    if name not in TOOLS:
        raise ToolExecutionError("tool_not_allowed")
    args = {} if arguments is None else arguments
    if not isinstance(args, dict):
        raise ToolExecutionError("tool_arguments_invalid")

    if name == "get_live_market_data":
        if set(args) != {"symbol", "interval"}:
            raise ToolExecutionError("market_arguments_invalid")
        symbol = str(args.get("symbol", "")).strip().upper()
        interval = str(args.get("interval", "")).strip()
        if not re.fullmatch(r"[A-Z0-9]{2,16}USDT", symbol) or interval not in {"1h", "4h", "1d"}:
            raise ToolExecutionError("market_symbol_or_interval_invalid")
        base = "https://api.binance.com/api/v3"
        headers = {"User-Agent": "NIC-creator-research/1.0", "Accept": "application/json"}
        try:
            ticker_request = urllib.request.Request(f"{base}/ticker/24hr?{urllib.parse.urlencode({'symbol': symbol})}", headers=headers)
            with urllib.request.urlopen(ticker_request, timeout=8) as response:
                ticker = json.loads(response.read().decode("utf-8"))
            candle_request = urllib.request.Request(f"{base}/klines?{urllib.parse.urlencode({'symbol': symbol, 'interval': interval, 'limit': 12})}", headers=headers)
            with urllib.request.urlopen(candle_request, timeout=8) as response:
                candles_raw = json.loads(response.read().decode("utf-8"))
        except (OSError, urllib.error.URLError, TimeoutError, UnicodeError, json.JSONDecodeError) as exc:
            raise ToolExecutionError("binance_public_market_data_unavailable") from exc
        if not isinstance(ticker, dict) or not isinstance(candles_raw, list):
            raise ToolExecutionError("binance_public_market_data_invalid")
        candles = []
        for row in candles_raw[-12:]:
            if isinstance(row, list) and len(row) >= 8:
                candles.append({
                    "open_time_ms": row[0], "open": row[1], "high": row[2],
                    "low": row[3], "close": row[4], "volume": row[5],
                    "close_time_ms": row[6], "quote_volume": row[7],
                })
        return {
            "source": "Binance public Spot REST API",
            "observed_at": datetime.now(timezone.utc).isoformat(),
            "symbol": symbol,
            "interval": interval,
            "ticker_24h": {
                key: ticker.get(key) for key in (
                    "lastPrice", "priceChange", "priceChangePercent", "weightedAvgPrice",
                    "highPrice", "lowPrice", "volume", "quoteVolume", "count"
                )
            },
            "recent_candles": candles,
            "evidence_class": "LIVE_PUBLIC_MARKET_OBSERVATION",
            "limitations": ["Market observations are not forecasts or trade instructions.", "Confirm data freshness and symbol context before publication."]
        }

    if name == "search_public_news":
        if set(args) != {"query"}:
            raise ToolExecutionError("news_arguments_invalid")
        query = str(args.get("query", "")).strip()
        if not 2 <= len(query) <= 120 or any(ord(char) < 32 for char in query):
            raise ToolExecutionError("news_query_invalid")
        params = urllib.parse.urlencode({"q": query, "hl": "en-US", "gl": "US", "ceid": "US:en"})
        request = urllib.request.Request(
            f"https://news.google.com/rss/search?{params}",
            headers={"User-Agent": "NIC-creator-research/1.0", "Accept": "application/rss+xml, application/xml"}
        )
        try:
            with urllib.request.urlopen(request, timeout=8) as response:
                root = ET.fromstring(response.read())
        except (OSError, urllib.error.URLError, TimeoutError, UnicodeError, ET.ParseError) as exc:
            raise ToolExecutionError("public_news_search_unavailable") from exc
        items = []
        for item in root.findall("./channel/item")[:8]:
            title = item.findtext("title") or ""
            description = item.findtext("description") or ""
            description = re.sub(r"<[^>]+>", " ", html.unescape(description))
            description = re.sub(r"\s+", " ", description).strip()
            items.append({
                "title": html.unescape(title)[:300],
                "url": item.findtext("link"),
                "published_at": item.findtext("pubDate"),
                "publisher": item.findtext("source"),
                "snippet": description[:360],
                "evidence_class": "DISCOVERY_ONLY_REQUIRES_PRIMARY_SOURCE_VERIFICATION"
            })
        return {
            "source": "Google News RSS",
            "query": query,
            "retrieved_at": datetime.now(timezone.utc).isoformat(),
            "result_count": len(items),
            "results": items,
            "policy": "Headlines are discovery leads, not verified facts. Open and verify primary sources before publication."
        }

    if name == "get_verified_research_evidence":
        if args:
            raise ToolExecutionError("tool_arguments_not_supported")
        data = _read_json("data/live/nic_verified_evidence.json")
        records = []
        for item in (data.get("records") or [])[:12]:
            if not isinstance(item, dict):
                continue
            records.append({
                "title": item.get("title"),
                "url": item.get("final_url") or item.get("url"),
                "source_class": item.get("source_class"),
                "retrieval_status": item.get("retrieval_status"),
                "freshness": item.get("freshness", "UNKNOWN"),
                "limitations": item.get("limitations", []),
                "evidence_class": "DISCOVERY_OR_RETRIEVAL_RECORD_NOT_AUTOMATICALLY_A_VERIFIED_CLAIM"
            })
        return {
            "source": "data/live/nic_verified_evidence.json",
            "generated_at": data.get("generated_at"),
            "status": data.get("status"),
            "record_count": data.get("count", len(records)),
            "records_returned": len(records),
            "records": records,
            "policy": "A retrieved URL or headline is not proof that its claim is true; verify primary source content."
        }

    if name == "get_reward_pattern_insights":
        if args:
            raise ToolExecutionError("tool_arguments_not_supported")
        data = _read_json("data/live/nic_revenue_pattern_lab.json")
        observations = []
        for item in (data.get("observations") or [])[:12]:
            if not isinstance(item, dict):
                continue
            examples = []
            for example in (item.get("owner_reported_examples") or [])[:5]:
                if isinstance(example, dict):
                    examples.append({
                        "post_id": example.get("post_id"),
                        "post_url": example.get("public_post_url"),
                        "summary": example.get("summary"),
                        "evidence": example.get("evidence", "OWNER_REPORTED_NOT_INDEPENDENTLY_VERIFIED")
                    })
            observations.append({
                "content_lane": item.get("content_lane") or item.get("category"),
                "content_format": item.get("content_format") or item.get("format"),
                "hook_type": item.get("hook_type"),
                "posts_observed": item.get("posts"),
                "views_observed": item.get("views"),
                "verified_posts": item.get("verified_posts"),
                "verified_reward_usdc": item.get("verified_revenue"),
                "owner_reported_posts": item.get("owner_reported_posts"),
                "owner_reported_reward_usdc": item.get("owner_reported_revenue_usdc"),
                "owner_reported_examples": examples,
                "evidence": item.get("evidence")
            })
        return {
            "source": "data/live/nic_revenue_pattern_lab.json",
            "generated_at": data.get("generated_at"),
            "status": data.get("status"),
            "verified_reward_event_count": data.get("accepted_verified_reward_events"),
            "rejected_reward_event_count": data.get("rejected_reward_events"),
            "observations": observations,
            "next_experiments": (data.get("next_experiments") or [])[:8],
            "evidence_policy": {
                "owner_reported_is_independently_verified": False,
                "public_views_are_earnings_evidence": False,
                "creator_period_totals_are_individual_post_rewards": False,
                "patterns_are_hypotheses_not_causal_proof": True
            }
        }

    if args:
        raise ToolExecutionError("tool_arguments_not_supported")

    if name == "get_agent_registry":
        data = _read_json("data/live/nic_agent_registry.json")
        agents = data.get("agents", [])
        return {
            "source": "data/live/nic_agent_registry.json",
            "generated_at": data.get("generated_at"),
            "mission": data.get("mission"),
            "agent_count": data.get("agent_count", len(agents) if isinstance(agents, list) else None),
            "operational_agent_count": data.get("operational_agent_count"),
            "agents": [
                {"agent_id": a.get("agent_id"), "name": a.get("name"),
                 "state": a.get("state"), "skills": a.get("skills", []),
                 "limitations": a.get("limitations", [])}
                for a in agents if isinstance(a, dict)
            ] if isinstance(agents, list) else [],
            "policy": data.get("policy", {}),
            "specialist_runtime": data.get("specialist_runtime", {}),
        }

    if name == "get_creator_dashboard":
        if args:
            raise ToolExecutionError("tool_arguments_not_supported")
        data = _read_json("data/live/nic_dashboard.json")
        return {
            "source": "data/live/nic_dashboard.json",
            "generated_at": data.get("generated_at"),
            "symbol": (data.get("current_decision") or {}).get("symbol"),
            "last_run_id": (data.get("transparent_trace") or {}).get("run_id"),
            "publication": (data.get("transparent_trace") or {}).get("outcome", {}),
            "keys": sorted(data.keys())[:60],
            "summary": {
                key: data[key] for key in (
                    "status", "publication_status", "last_publication",
                    "reward_learning_status", "verified_reward_events",
                    "quality_gate_status",
                ) if key in data and isinstance(data[key], (str, int, float, bool, type(None)))
            },
        }

    if name == "list_recent_research":
        if args:
            raise ToolExecutionError("tool_arguments_not_supported")
        directory = ROOT / "data" / "reports"
        if not directory.is_dir():
            raise ToolExecutionError("evidence_unavailable:data/reports")
        reports = []
        for path in sorted(directory.glob("*.json"), key=lambda item: item.name, reverse=True)[:8]:
            try:
                item = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, UnicodeError, json.JSONDecodeError):
                continue
            if isinstance(item, dict):
                reports.append({
                    "file": path.name,
                    "title": str(item.get("title") or item.get("headline") or path.stem)[:240],
                    "keys": sorted(item.keys())[:24],
                })
        return {"source": "data/reports/*.json", "sample_count": len(reports), "reports": reports}

    if name == "get_latest_publication":
        if args:
            raise ToolExecutionError("tool_arguments_not_supported")
        rows = _read_jsonl_tail("analytics/publication_log.jsonl", limit=5)
        if not rows:
            raise ToolExecutionError("publication_history_empty")
        row = rows[-1]
        post_id = str(row.get("canonical_post_id") or row.get("post_id") or "").strip()
        proof = str(row.get("publication_proof") or "")
        verified = row.get("publication_id_verified") is True and bool(post_id) and proof == "binance_openapi_response_post_id"
        return {
            "source": "analytics/publication_log.jsonl",
            "timestamp": row.get("published_at") or row.get("timestamp"),
            "status": row.get("status"),
            "post_id": post_id or None,
            "link": row.get("link"),
            "symbol": row.get("symbol"),
            "category": row.get("category"),
            "content_format": row.get("content_format"),
            "visual_attached": row.get("visual_attached") is True,
            "publication_id_verified": verified,
            "publication_proof": proof or None,
            "monetization_status": (row.get("monetization") or {}).get("status"),
            "reward_amount_usdc": (row.get("monetization") or {}).get("reward_amount_usdc"),
            "reward_is_verified": (row.get("monetization") or {}).get("revenue_verified") is True,
        }

    if name == "get_reward_learning_status":
        if args:
            raise ToolExecutionError("tool_arguments_not_supported")
        data = _read_json("data/intelligence/nic_square_earnings_learning_report.json")
        learning = _read_json("data/live/nic_square_earnings_learning.json")
        feedback = learning.get("owner_reported_reward_feedback")
        feedback = feedback if isinstance(feedback, dict) else {}
        raw_entries = feedback.get("entries")
        entries = []
        if isinstance(raw_entries, list):
            for item in raw_entries[:20]:
                if not isinstance(item, dict):
                    continue
                entries.append({
                    "post_id": item.get("post_id"),
                    "post_url": item.get("public_post_url"),
                    "reported_reward_usdc": item.get("reported_reward_usdc"),
                    "currency": item.get("currency"),
                    "reported_at": item.get("reported_at"),
                    "content_lane": item.get("content_lane"),
                    "content_format": item.get("content_format"),
                    "hook_type": item.get("hook_type"),
                    "summary": item.get("summary"),
                    "owner_reported_views": item.get("owner_reported_views"),
                    "verification_status": item.get("verification_status"),
                    "evidence_type": item.get("evidence_type"),
                })
        fields = (
            "generated_at", "status", "weekly_goal_usdc",
            "verified_reward_events_7d", "verified_usdc_7d",
            "owner_reported_usdc_7d", "owner_reported_events_7d",
            "owner_reported_usdc_14d", "owner_reported_events_14d",
            "owner_reported_posts_14d", "owner_reported_feedback_status",
            "coverage_status", "creator_profiles_resolved",
            "profile_posts_collected_14d", "profile_research_status",
            "autonomy_status", "autonomy_critical_blockers",
            "autonomy_blocker_ids", "autopublish_enabled",
        )
        return {
            "source": "data/intelligence/nic_square_earnings_learning_report.json",
            "summary": {key: data[key] for key in fields if key in data},
            "owner_reported_reward_feedback": {
                "status": feedback.get("status"),
                "accepted_report_count": feedback.get("accepted_report_count"),
                "rejected_report_count": feedback.get("rejected_report_count"),
                "7_day": feedback.get("7_day", {}),
                "14_day": feedback.get("14_day", {}),
                "entries_returned": len(entries),
                "entries": entries,
            },
            "evidence_policy": {
                "owner_reported_is_independent_verification": False,
                "owner_reported_entries_are_post_level_learning_feedback": True,
                "public_views_or_engagement_are_earnings": False,
                "creator_period_totals_attribute_to_individual_posts": False,
            },
        }

    if name == "get_creator_period_coverage":
        if args:
            raise ToolExecutionError("tool_arguments_not_supported")
        data = _read_json("data/intelligence/creator_period_learning.json")
        coverage = data.get("coverage", {})
        periods = data.get("creator_periods", [])
        summaries = []
        if isinstance(periods, list):
            for item in periods[:12]:
                if not isinstance(item, dict):
                    continue
                profile = item.get("profile") or {}
                reward = item.get("creator_period_reward") or {}
                summaries.append({
                    "creator": item.get("creator"),
                    "identity_match": profile.get("identity_match"),
                    "collection_status": profile.get("collection_status"),
                    "window_7d_complete": profile.get("window_7d_complete") is True,
                    "window_14d_complete": profile.get("window_14d_complete") is True,
                    "window_pre_period_14d_complete": profile.get("window_pre_period_14d_complete") is True,
                    "reward_amount": reward.get("amount"),
                    "reward_currency": reward.get("currency"),
                    "reward_period_start": reward.get("period_start"),
                    "reward_period_end": reward.get("period_end"),
                    "posts_7d": (item.get("post_cohort_7d") or {}).get("post_count"),
                    "posts_14d": (item.get("post_cohort_14d") or {}).get("post_count"),
                })
        return {
            "source": "data/intelligence/creator_period_learning.json",
            "learning_status": data.get("learning_status"),
            "coverage_status": data.get("coverage_status"),
            "reward_granularity": data.get("reward_granularity"),
            "coverage": coverage,
            "creators": summaries,
            "attribution_policy": "Creator-period rewards are cohort-level evidence and are never assigned to individual posts.",
        }

    if name == "list_creator_study_queue":
        if args:
            raise ToolExecutionError("tool_arguments_not_supported")
        data = _read_json("data/live/nic_square_earnings_learning.json")
        queue = data.get("creator_study_queue", [])
        creators = []
        if isinstance(queue, list):
            for item in queue[:10]:
                if not isinstance(item, dict):
                    continue
                creators.append({
                    "creator": item.get("creator"),
                    "discovery_window_days": item.get("discovery_window"),
                    "posts_observed": item.get("posts_observed"),
                    "dominant_archetypes": item.get("dominant_archetypes", []),
                    "public_engagement_rate": item.get("public_engagement_rate"),
                    "median_views": item.get("median_views"),
                    "earnings_status": item.get("earnings_status"),
                    "discovery_signal": item.get("discovery_signal"),
                    "sample_urls": item.get("sample_urls", [])[:5],
                })
        return {
            "source": "data/live/nic_square_earnings_learning.json",
            "research_coverage": data.get("research_coverage", {}),
            "creator_count_returned": len(creators),
            "creators": creators,
            "policy": "Public engagement is a research signal, not evidence of earnings.",
        }

    raise ToolExecutionError("tool_not_allowed")
