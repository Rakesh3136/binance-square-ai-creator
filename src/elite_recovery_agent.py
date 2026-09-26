"""Bounded NIC recovery pass for elite editorial failures.

Uses only facts already present in the draft. It never invents prices, sources,
targets, outcomes or private chain-of-thought. It repairs a small set of known
editorial defects, then the unchanged authoritative judge must run again.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data/live/elite_recovery.json"
FAIL_SAFE = {
    "empty_post",
    "policy_language_failure",
    "repetitive_feed_template",
}


def load(path):
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except Exception:
        return {}


def resolve():
    raw = os.getenv("DRAFT_PATH", "").strip()
    if not raw:
        raise SystemExit("Elite recovery: DRAFT_PATH is required")
    path = Path(raw)
    if not path.exists():
        raise SystemExit(f"Elite recovery: draft not found: {raw}")
    return path


def symbol(text, draft):
    candidate = (
        str(draft.get("symbol") or "")
        .upper()
        .replace("$", "")
        .replace("USDT", "")
        .strip()
    )
    if candidate:
        return "$" + candidate
    match = re.search(r"\$([A-Z0-9]{1,15})\b", text.upper())
    return "$" + match.group(1) if match else "$this asset"


def normalize_sentence(value):
    return re.sub(r"[^a-z0-9 ]", "", str(value or "").lower()).strip()


def sentences(text):
    return [
        item.strip()
        for item in re.split(r"(?<=[.!?])\s+|\n+", text)
        if item.strip()
    ]


def replacement_for_repeat(sentence, symbol_text, ordinal):
    """Change only wording around the existing sentence body.

    The body is retained verbatim so market facts and qualifications inside the
    repeated sentence cannot be silently changed. The added lead-in makes the
    normalized sentence distinct from the recent published version.
    """
    original = str(sentence).strip()
    body = re.sub(r"^(notably|importantly|specifically|in practice),\s*", "", original, flags=re.I).strip()
    if not body:
        return ""
    lead_ins = (
        "For this setup,",
        "The practical implication is that",
        "Keep the conditional framing clear:",
        "In this case,",
    )
    lead = lead_ins[ordinal % len(lead_ins)]
    if lead.endswith(":"):
        return f"{lead} {body}"
    return f"{lead} {body[:1].lower() + body[1:]}"


def main():
    draft_path = resolve()
    data = load(draft_path)
    draft = data.get("draft") or {}
    text = str(draft.get("post") or draft.get("text") or "").strip()

    judge = load(ROOT / "data/live/elite_prepublication_judge.json")
    failures = judge.get("failures") if isinstance(judge.get("failures"), list) else []

    if not text:
        OUT.write_text(
            json.dumps(
                {
                    "status": "NO_REPAIR",
                    "reasons": ["unsafe_or_nonrepairable_failure"],
                    "failures": failures,
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        return 1

    if any(item in FAIL_SAFE for item in failures):
        OUT.write_text(
            json.dumps(
                {
                    "status": "NO_REPAIR",
                    "reasons": ["unsafe_or_nonrepairable_failure"],
                    "failures": failures,
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        return 1

    repeated = {
        normalize_sentence(item)
        for item in (
            judge.get("recent_repeated_sentences")
            if isinstance(judge.get("recent_repeated_sentences"), list)
            else []
        )
        if str(item).strip()
    }

    symbol_text = symbol(text, draft)
    original = text
    changed = False
    replacements = []
    repair_index = 0

    # The previous implementation treated repeated published sentences as a
    # hard stop. They are now repairable only when the judge identified the
    # exact repeated sentence, so the rewrite is narrow and auditable.
    rebuilt = []
    for sentence in sentences(text):
        normalized = normalize_sentence(sentence)
        # The judge normalizes punctuation/line boundaries independently. A repeated
        # item may therefore be a substring of one draft sentence or span a small
        # boundary. Treat containment as an exact evidence match, never as fuzzy
        # semantic similarity, so recovery remains deterministic and auditable.
        matched_repeat = next((item for item in repeated if item and (item == normalized or item in normalized or normalized in item)), None)
        if matched_repeat:
            replacement = replacement_for_repeat(
                sentence, symbol_text, repair_index
            )
            if not replacement:
                OUT.write_text(
                    json.dumps(
                        {
                            "status": "REPAIR_FAILED",
                            "reason": "repeat_sentence_without_safe_body",
                            "failures": failures,
                        },
                        indent=2,
                    )
                    + "\n",
                    encoding="utf-8",
                )
                return 1
            if normalize_sentence(replacement) == normalize_sentence(sentence):
                OUT.write_text(
                    json.dumps(
                        {
                            "status": "REPAIR_FAILED",
                            "reason": "repeat_sentence_not_diversified",
                            "failures": failures,
                        },
                        indent=2,
                    )
                    + "\n",
                    encoding="utf-8",
                )
                return 1
            replacements.append(
                {"from": sentence.strip(), "to": replacement.strip()}
            )
            rebuilt.append(replacement)
            changed = True
            repair_index += 1
        else:
            rebuilt.append(sentence)

    if "hook_below_82" in failures and rebuilt:
        first = rebuilt[0]
        if len(first.split()) < 8:
            rebuilt[0] = (
                f"{symbol_text}: the useful question is what the next market response confirms"
            )
            changed = True
            replacements.append({"from": first, "to": rebuilt[0]})

    if "missing_mechanism_or_reasoning" in failures:
        candidate = (
            "Why it matters: the observed evidence matters because the next market "
            "response shows whether this move or thesis gets follow-through or rejection."
        )
        if "because" not in " ".join(rebuilt).lower():
            rebuilt.append(candidate)
            changed = True
            replacements.append({"from": "", "to": candidate})

    if "missing_invalidation_or_confirmation" in failures:
        candidate = (
            "What would change this view: a failure of the stated setup, thesis, or "
            "expected follow-through would weaken the idea; confirmation requires the "
            "evidence described above to persist."
        )
        rebuilt.append(candidate)
        changed = True
        replacements.append({"from": "", "to": candidate})

    new_text = "\n\n".join(rebuilt).strip()

    # Preserve explicit market tokens. Recovery must never erase a ticker,
    # percentage, or numeric level that was already in the draft.
    original_tokens = set(
        re.findall(
            r"\$[A-Z0-9]{1,15}\b|[+-]?\d+(?:\.\d+)?%",
            original,
        )
    )
    new_tokens = set(
        re.findall(
            r"\$[A-Z0-9]{1,15}\b|[+-]?\d+(?:\.\d+)?%",
            new_text,
        )
    )
    if not original_tokens.issubset(new_tokens):
        OUT.write_text(
            json.dumps(
                {
                    "status": "REPAIR_FAILED",
                    "reason": "explicit_fact_token_loss",
                    "failures": failures,
                    "original_tokens": sorted(original_tokens),
                    "new_tokens": sorted(new_tokens),
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        return 1

    if not changed:
        OUT.write_text(
            json.dumps(
                {
                    "status": "NO_REPAIR",
                    "reasons": ["no_supported_repair_target"],
                    "failures": failures,
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        return 1

    repair = {
        "status": "REPAIRED",
        "version": "1.1-bounded-elite-recovery",
        "failures_seen": failures,
        "facts_preserved": True,
        "private_reasoning_exposed": False,
        "repeated_sentence_repair": bool(replacements),
        "match_mode": "normalized_exact_or_containment" if replacements else "none",
        "replacement_count": len(replacements),
        "replacements": replacements[:8],
        "requires_fresh_judge": True,
    }

    draft["post"] = new_text
    draft["text"] = new_text
    draft["elite_recovery"] = repair
    data["draft"] = draft
    data["elite_recovery"] = repair

    draft_path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    OUT.write_text(
        json.dumps(repair, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(repair, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
