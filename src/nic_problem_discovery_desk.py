"""NIC Problem Discovery Desk: turn cited market pain points into founder questions.

Input is a curated evidence ledger, not a language-model guess. Every opportunity
must cite source URLs and repeated, independently sourced pain. Empty evidence
produces a transparent request for evidence, never invented startup ideas.
"""
from __future__ import annotations
import json, re
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "data/intelligence/market_problem_evidence.jsonl"
OUT = ROOT / "data/live/nic_problem_discovery_brief.json"


def read_rows(path):
    rows = []
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                row = json.loads(line)
                if isinstance(row, dict):
                    rows.append(row)
            except json.JSONDecodeError:
                continue
    except OSError:
        pass
    return rows


def normalize_problem(value):
    text = re.sub(r"[^a-z0-9 ]+", " ", str(value or "").lower())
    return " ".join(text.split())


def cluster_problems(rows):
    groups = defaultdict(list)
    for row in rows:
        problem = str(row.get("problem_statement") or "").strip()
        url = str(row.get("source_url") or "").strip()
        source = str(row.get("source_name") or "").strip()
        if len(problem) < 12 or not url.startswith("https://") or not source:
            continue
        domain = urlparse(url).netloc.lower()
        if not domain:
            continue
        key = normalize_problem(row.get("problem_cluster") or problem)
        if not key:
            continue
        groups[key].append({
            "problem_statement": problem[:500],
            "source_url": url,
            "source_name": source,
            "source_domain": domain,
            "affected_user": str(row.get("affected_user") or "unspecified")[:120],
            "impact": str(row.get("impact") or "unspecified")[:240],
            "observed_at": row.get("observed_at"),
        })
    result = []
    for key, evidence in groups.items():
        domains = sorted({x["source_domain"] for x in evidence})
        users = sorted({x["affected_user"] for x in evidence if x["affected_user"] != "unspecified"})
        impact_evidence = sum(x["impact"] != "unspecified" for x in evidence)
        ready = len(domains) >= 3 and len(evidence) >= 4 and impact_evidence >= 2
        result.append({
            "problem_cluster": key,
            "problem_statement": evidence[0]["problem_statement"],
            "evidence_count": len(evidence),
            "independent_source_domains": len(domains),
            "affected_user_types": users,
            "status": "VALIDATION_CANDIDATE" if ready else "NEEDS_MORE_EVIDENCE",
            "evidence": evidence[:12],
            "founder_questions": [
                "Who experiences this problem most often, and how costly is it today?",
                "What workaround do people currently use, and why does it fail?",
                "Would the affected user pay, switch, or change behaviour for a better solution?",
                "What is the smallest test that could disprove this opportunity?",
            ],
            "impact_observations": impact_evidence,
        })
    result.sort(key=lambda x: (x["status"] == "VALIDATION_CANDIDATE", x["independent_source_domains"], x["evidence_count"]), reverse=True)
    return result


def build(rows):
    clusters = cluster_problems(rows)
    if clusters:
        lead = clusters[0]
        status = "EVIDENCE_READY_FOR_FOUNDER_DISCUSSION" if lead["status"] == "VALIDATION_CANDIDATE" else "COLLECTING_PROBLEM_EVIDENCE"
        opening = (
            f"I found a problem worth validating: {lead['problem_statement']} "
            f"It has {lead['evidence_count']} evidence records across {lead['independent_source_domains']} source domains. "
            "This is a hypothesis to test, not yet proof of a business."
        )
        next_question = lead["founder_questions"][0]
    else:
        status = "NEEDS_EVIDENCE"
        opening = (
            "I don't yet have enough cited, independent evidence to tell you honestly what major problem the market is missing. "
            "NIC should collect repeated user pain, current workarounds, impact, and willingness-to-pay signals before proposing a company."
        )
        next_question = "Which market should NIC investigate first: crypto traders, small businesses, creators, or everyday consumers?"
    return {
        "schema_version": "NIC-PROBLEM-DISCOVERY-1.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "conversation_opening": opening,
        "next_question": next_question,
        "opportunities": clusters[:10],
        "evidence_policy": [
            "Do not invent user pain, customer quotes, market size, willingness to pay, or competitors.",
            "Require at least 4 evidence records from 3 independent source domains and 2 impact observations before a validation candidate is promoted.",
            "A validation candidate is not product-market fit; interview and test with real users.",
        ],
    }


def main():
    report = build(read_rows(EVIDENCE))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"status": report["status"], "opportunities": len(report["opportunities"]), "output": str(OUT.relative_to(ROOT))}, indent=2))


if __name__ == "__main__":
    main()
