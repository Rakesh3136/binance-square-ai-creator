"""Creator 17.0 — Active Knowledge Acquisition.

Turns the 14.0 knowledge-gap plan into bounded, evidence-led research using
fresh repository snapshots and the existing RSS discovery layer. It separates
observed facts from inference, detects contradictions, and reports whether
new evidence should change the 15.0 opportunity ranking or 16.0 decisions.

No fabricated sources/claims, no inferred revenue, and no quality-gate bypass.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ANALYTICS = ROOT / "analytics"
LIVE = ROOT / "data" / "live"
INTEL = ROOT / "data" / "intelligence"
STATE = LIVE / "creator_17_0_research_state.json"
MEMORY = ANALYTICS / "creator_17_0_knowledge_memory.json"
STRATEGY = ANALYTICS / "strategy_memory.json"


def read_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return default


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def rid(value: Any) -> str:
    return "research17_" + hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()[:12]


def articles(news: dict) -> list[dict]:
    rows = news.get("articles", []) if isinstance(news, dict) else []
    return [x for x in rows if isinstance(x, dict) and x.get("title") and x.get("url")]


def research_gaps(plan: dict, decision: dict, board: dict) -> list[dict]:
    gaps = plan.get("priority_research", []) if isinstance(plan, dict) else []
    if gaps:
        return gaps[:3]
    opportunities = board.get("opportunities", []) if isinstance(board, dict) else []
    top = opportunities[:2] if isinstance(opportunities, list) else []
    if top:
        return [{"priority": 2, "gap": "opportunity_evidence", "research": "verify the strongest current opportunity with fresh evidence", "opportunity_id": x.get("opportunity_id")} for x in top]
    if str(decision.get("action", "")).startswith("RESEARCH"):
        return [{"priority": 1, "gap": "decision_uncertainty", "research": "refresh evidence before committing to a major action"}]
    return []


def build_evidence(news: dict, gaps: list[dict]) -> list[dict]:
    rows = articles(news)
    evidence = []
    for gap in gaps:
        terms = set(str(gap.get("gap", "")).lower().replace("_", " ").split())
        research = str(gap.get("research", "")).lower()
        terms.update(w for w in research.replace("_", " ").split() if len(w) >= 5)
        ranked = []
        for item in rows:
            text = (str(item.get("title", "")) + " " + str(item.get("summary", ""))).lower()
            overlap = sum(1 for t in terms if t in text)
            score = float(item.get("news_score") or 0) + overlap * 5
            ranked.append((score, item))
        for score, item in sorted(ranked, key=lambda x: x[0], reverse=True)[:3]:
            support = "strong" if str(item.get("category", "")).endswith("_official") else "discovery"
            evidence.append({
                "research_gap": gap.get("gap"),
                "source": item.get("source"),
                "url": item.get("url"),
                "published_at": item.get("published_at"),
                "claim_lead": item.get("title"),
                "support_level": support,
                "freshness_hours": _age_hours(item.get("published_at")),
                "relevance_score": round(score, 2),
                "epistemic_status": "observed_discovery_lead" if support == "discovery" else "observed_primary_feed",
                "requires_verification_before_publication": True,
            })
    return evidence


def _age_hours(value: Any) -> float | None:
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return round(max(0.0, (datetime.now(timezone.utc) - dt.astimezone(timezone.utc)).total_seconds() / 3600), 2)
    except Exception:
        return None


def main() -> int:
    plan = read_json(LIVE / "creator_14_0_knowledge_plan.json", {})
    world = read_json(ANALYTICS / "creator_14_0_world_model.json", {})
    decision = read_json(LIVE / "creator_16_0_decision_board.json", {})
    board = read_json(LIVE / "creator_15_0_opportunity_board.json", {})
    news = read_json(LIVE / "news_snapshot.json", {})
    market = read_json(LIVE / "market_snapshot.json", {})
    strategy = read_json(STRATEGY, {})
    memory = read_json(MEMORY, {"research_history": []})

    gaps = research_gaps(plan, decision, board)
    evidence = build_evidence(news, gaps)
    official = [x for x in evidence if x.get("support_level") == "strong"]
    discovery = [x for x in evidence if x.get("support_level") == "discovery"]

    contradictions = []
    for gap in gaps:
        related = [x for x in evidence if x.get("research_gap") == gap.get("gap")]
        symbols = {}
        for x in related:
            claim = str(x.get("claim_lead", "")).lower()
            for sym in ("btc", "eth", "sol", "bnb", "xrp"):
                if sym in claim:
                    symbols.setdefault(sym, 0)
                    symbols[sym] += 1
        if len(symbols) > 1 and len(related) >= 2:
            contradictions.append({"gap": gap.get("gap"), "status": "possible_narrative_conflict", "requires_manual_or_primary_verification": True})

    if not gaps:
        status = "NO_KNOWLEDGE_GAP"
        impact = "NO_CHANGE"
    elif not evidence:
        status = "WAITING_FOR_SOURCE"
        impact = "BLOCK_UNTIL_VERIFIED"
    elif official:
        status = "RESEARCH_COMPLETE"
        impact = "RE_EVALUATE_COUNTERFACTUALS" if decision else "RE_RANK_OPPORTUNITIES"
    else:
        status = "PARTIAL_RESEARCH"
        impact = "BLOCK_UNTIL_VERIFIED"

    research_id = rid({"gaps": gaps, "evidence": evidence, "impact": impact})
    state = {
        "schema_version": "17.0",
        "research_id": research_id,
        "updated_at": now(),
        "status": status,
        "research_tasks": gaps,
        "evidence_ledger": evidence,
        "evidence_summary": {"total": len(evidence), "official_feed": len(official), "discovery_leads": len(discovery)},
        "contradictions": contradictions,
        "decision_impact": impact,
        "market_available": bool(market),
        "world_model_id": world.get("world_model_id"),
        "epistemic_policy": "discovery leads are not publication facts; material claims require verification",
        "hard_constraints": [
            "no fabricated sources or claims",
            "no inferred revenue",
            "no fake engagement",
            "no guaranteed returns",
            "no quality_gate_bypass",
            "no credential changes",
            "no blind production code modification",
        ],
    }
    write_json(STATE, state)
    history = memory if isinstance(memory, dict) else {"research_history": []}
    history.setdefault("research_history", []).append({"research_id": research_id, "at": state["updated_at"], "status": status, "impact": impact, "evidence_count": len(evidence)})
    history["research_history"] = history["research_history"][-50:]
    history["latest"] = state
    write_json(MEMORY, history)

    strategy.setdefault("creator_17_0", {})
    strategy["creator_17_0"] = {"research_id": research_id, "status": status, "decision_impact": impact, "evidence_count": len(evidence), "official_evidence_count": len(official)}
    strategy.setdefault("learning_overlay", {})["active_research"] = strategy["creator_17_0"]
    write_json(STRATEGY, strategy)
    write_json(INTEL / "creator_17_0_report.json", {"module": "creator_17_0_active_research", "generated_at": now(), "status": status, "decision_impact": impact, "research_id": research_id, "knowledge_gap_count": len(gaps), "evidence_count": len(evidence), "official_evidence_count": len(official), "contradiction_count": len(contradictions)})
    print(json.dumps({"status": status, "decision_impact": impact, "knowledge_gap_count": len(gaps), "evidence_count": len(evidence), "official_evidence_count": len(official)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
