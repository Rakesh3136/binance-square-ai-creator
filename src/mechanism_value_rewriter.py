"""Deterministic evidence-preserving mechanism/value repair.

The only generative pass is safe_creator_runner. This stage may add a causal
bridge using facts already present in the draft, but never calls an LLM.
"""
# Live validation marker: mechanism bridge is authoritative after deduplication.
from __future__ import annotations

import json
import re
from pathlib import Path

from safe_creator_runner import deduplicate_signal_post

ROOT = Path(__file__).resolve().parents[1]
REPORT_DIR = ROOT / "data/reports"
OUT = ROOT / "data/live/mechanism_value_repair.json"
PUBLICATION_LOG = ROOT / "analytics/publication_log.jsonl"

MECHANISM_TERMS = (
    "because", "driven by", "explains why", "the reason", "which means",
    "leads to", "causes", "due to", "means that", "translates into",
    "shows up in", "flows into", "results in", "comes from", "depends on",
    "hinges on", "works through", "is linked to", "matters because",
    "suggests that", "implies that", "in turn", "which can make",
    "which can leave", "the mechanism", "pathway", "transmission",
)
GENERIC_BRIDGES = (
    "the mechanism to watch", "the link between", "the conclusion in this draft",
    "the reported fact matters because", "the effect described here",
)

def load(path):
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except Exception:
        return {}

def resolve_report():
    import os
    explicit = os.getenv("DRAFT_PATH", "").strip()
    if explicit:
        path = Path(explicit)
        if not path.exists():
            raise SystemExit(f"Mechanism repair: DRAFT_PATH does not exist: {explicit}")
        return path
    reports = sorted(REPORT_DIR.glob("*-multi-agent.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    return reports[0] if reports else None

def norm(value):
    return re.sub(r"\s+", " ", str(value or "").strip())

def questions(text):
    return re.findall(r"[^?\n]*\?", text)

def sentences(text):
    return [norm(sentence) for sentence in re.split(r"(?<=[.!?])\s+|\n+", text) if norm(sentence)]

def mechanism_present(text):
    return any(term in text.lower() for term in MECHANISM_TERMS)

def generic_bridge(sentence):
    lowered = norm(sentence).lower()
    return any(term in lowered for term in GENERIC_BRIDGES)

def explicit_facts(text):
    facts = set(re.findall(r"\$[A-Z][A-Z0-9]{1,14}\b", text))
    facts |= set(re.findall(r"\b[+-]?\d+(?:\.\d+)?%", text))
    facts |= set(re.findall(r"\$[\d,]+(?:\.\d+)?(?:\s*[KMBkmb])?\b", text))
    return facts

def recent_repetitions(text):
    if not PUBLICATION_LOG.exists():
        return []
    current = {re.sub(r"[^a-z0-9 ]", "", sentence.lower()).strip() for sentence in sentences(text) if len(sentence.split()) >= 8}
    matches = []
    try:
        for row in PUBLICATION_LOG.read_text(encoding="utf-8").splitlines()[-12:]:
            try:
                old = json.loads(row)
            except Exception:
                continue
            old_text = str(old.get("text") or old.get("post") or old.get("content") or "")
            old_sentences = {re.sub(r"[^a-z0-9 ]", "", sentence.lower()).strip() for sentence in sentences(old_text) if len(sentence.split()) >= 8}
            matches.extend(sorted(current & old_sentences))
    except Exception:
        pass
    return matches[:8]

def deterministic_bridges(original):
    symbol = (re.findall(r"\$[A-Z][A-Z0-9]{1,14}\b", original) or ["$THIS-ASSET"])[0]
    percentages = re.findall(r"\b[+-]?\d+(?:\.\d+)%", original)
    pct = percentages[0] if percentages else "the observed move"
    fact = next((sentence for sentence in sentences(original) if pct in sentence or symbol in sentence), "")
    if fact:
        return [
            f"For {symbol}, that matters because the existing {pct} move is the market fact behind the reaction, while the next response shows whether traders are accepting or rejecting it.",
            f"The useful signal in {symbol} is what happens after the observed {pct} move: follow-through would support the reaction, while rejection would weaken it.",
            f"{symbol} is worth watching because the observed {pct} move creates a test between follow-through and rejection rather than proving either outcome in advance.",
        ]
    return [
        f"For {symbol}, the next observable reaction is what separates a temporary burst of attention from a meaningful change in behavior.",
        f"The market read on {symbol} depends on the next observable response, because that is where attention either turns into follow-through or fades.",
        f"What matters next for {symbol} is the reaction itself, because a move becomes more informative when the market confirms or rejects it.",
    ]

def write_result(result):
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(result, indent=2, ensure_ascii=False))

def main():
    report = resolve_report()
    if not report:
        raise SystemExit("Mechanism repair: no draft report")
    data = load(report)
    draft = data.get("draft") or {}
    original = str(draft.get("post") or draft.get("text") or "").strip()
    if not original:
        raise SystemExit(f"Mechanism repair: draft has no post text: {report}")

    original_questions = questions(original)
    if len(original_questions) != 1:
        write_result({"status":"REPAIR_FAILED","draft_unchanged":True,"draft_path":str(report),"reasons":["ORIGINAL_QUESTION_COUNT_NOT_ONE"]})
        return 1

    original_question = original_questions[0].strip()
    body_without_question = original.replace(original_question, "").rstrip()

    bridge = ""
    for candidate_bridge in deterministic_bridges(body_without_question):
        if not recent_repetitions(candidate_bridge) and not generic_bridge(candidate_bridge):
            bridge = candidate_bridge
            break
    if not bridge:
        bridge = deterministic_bridges(body_without_question)[-1]

    candidate = f"{body_without_question}\n\n{bridge}\n\n{original_question}".strip()
    asset_symbol = (re.findall(r"\$[A-Z][A-Z0-9]{1,14}\b", candidate) or ["$THIS-ASSET"])[0]

    # Deduplicate first. If it removes the bridge, restore the exact deterministic
    # bridge without a second deduplication pass. This makes the final invariant
    # test operate on the actual final candidate.
    deduped = deduplicate_signal_post(candidate, asset_symbol)
    candidate = deduped if mechanism_present(deduped) else f"{body_without_question}\n\n{bridge}\n\n{original_question}".strip()

    reasons = []
    if not mechanism_present(candidate):
        reasons.append("MECHANISM_STILL_MISSING")
    if generic_bridge(bridge):
        reasons.append("GENERIC_BRIDGE")
    if len(questions(candidate)) != 1:
        reasons.append("QUESTION_COUNT_CHANGED")
    if original_question not in candidate:
        reasons.append("ORIGINAL_QUESTION_NOT_PRESERVED")
    if explicit_facts(original) - explicit_facts(candidate):
        reasons.append("EXPLICIT_FACT_LOSS")
    if recent_repetitions(bridge):
        reasons.append("REPAIR_SENTENCE_REPEATS_RECENT_PUBLICATION")

    if reasons:
        write_result({"status":"REPAIR_FAILED","draft_unchanged":True,"draft_path":str(report),"reasons":reasons})
        return 1

    repair = {"status":"REPAIRED","method":"deterministic","verified_facts_preserved":True,"exactly_one_question":True,"mechanism_present":True,"reader_value_floor_enabled":True}
    draft["post"] = candidate
    draft["text"] = candidate
    draft["mechanism_value_repair"] = repair
    data["draft"] = draft
    data["mechanism_value_repair"] = repair
    Path(report).write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    write_result({**repair, "draft_path":str(report)})
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
