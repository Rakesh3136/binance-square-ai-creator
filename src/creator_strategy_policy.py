"""Executable creator-strategy policy for NIC generation and repetition control."""
from __future__ import annotations
import hashlib, json, re
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLAYBOOK = ROOT / "data/intelligence/creator_strategy_playbook.json"
PUBLICATION_LOG = ROOT / "analytics/publication_log.jsonl"

def normalize(text: str) -> str:
    return " ".join(re.sub(r"[^a-z0-9 ]", " ", str(text).lower()).split())

def fingerprint(text: str) -> str:
    return hashlib.sha256(normalize(text).encode("utf-8")).hexdigest()

def load_playbook(path: Path = PLAYBOOK) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Creator strategy playbook unavailable or invalid: {exc}") from exc
    if data.get("schema_version") != 1 or not isinstance(data.get("generation_policy"), dict):
        raise RuntimeError("Creator strategy playbook schema is unsupported")
    return data

def recent_posts(path: Path = PUBLICATION_LOG) -> list[dict]:
    if not path.exists():
        return []
    out = []
    for line in path.read_text(encoding="utf-8").splitlines()[-12:]:
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            out.append(row)
    return out

def prepare_context(context: dict, playbook: dict | None = None) -> dict:
    """Pass a versioned policy to the writer without imposing a fixed post template."""
    policy = playbook or load_playbook()
    context = dict(context)
    context["creator_strategy"] = {
        "schema_version": policy["schema_version"],
        "playbook_sha256": hashlib.sha256(json.dumps(policy, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest(),
        "generation_policy": policy["generation_policy"],
        "mechanisms": [item["mechanism"] for item in policy.get("learn_these_success_mechanisms", [])],
        "reward_regimes": policy.get("reward_regimes", []),
    }
    # A story type chosen by current-cycle editorial evidence remains authoritative.
    # This policy explicitly avoids overriding it with a global or coin-specific template.
    return context

def apply_policy(result: dict, context: dict, playbook: dict | None = None,
                 history: list[dict] | None = None) -> dict:
    policy = playbook or load_playbook()
    draft = result.get("draft") if isinstance(result.get("draft"), dict) else {}
    post = str(draft.get("post") or draft.get("text") or "").strip()
    if not post:
        raise RuntimeError("Creator strategy gate: generated post is empty")
    normalized = normalize(post)
    if len(normalized.split()) < 25:
        raise RuntimeError("Creator strategy gate: post is too short to demonstrate a complete thesis")
    blocks = [x.strip() for x in re.split(r"\n\s*\n", post) if x.strip()]
    hook = normalize(blocks[0]) if blocks else ""
    prior = history if history is not None else recent_posts()
    exact_hook_matches = 0
    duplicate_sentence_matches = 0
    sentences = {normalize(x) for x in re.split(r"(?<=[.!?])\s+", post) if len(normalize(x).split()) >= 7}
    for row in prior:
        old_text = str(row.get("text") or row.get("post") or row.get("content") or "")
        old_blocks = [x.strip() for x in re.split(r"\n\s*\n", old_text) if x.strip()]
        if old_blocks and normalize(old_blocks[0]) == hook and hook:
            exact_hook_matches += 1
        old_sentences = {normalize(x) for x in re.split(r"(?<=[.!?])\s+", old_text) if len(normalize(x).split()) >= 7}
        duplicate_sentence_matches += len(sentences & old_sentences)
    if exact_hook_matches or duplicate_sentence_matches >= 2:
        raise RuntimeError(
            "Creator strategy gate: repetitive draft rejected "
            f"(exact_hook_matches={exact_hook_matches}, repeated_sentences={duplicate_sentence_matches})"
        )
    strategy = context.get("creator_strategy") or prepare_context(context, policy)["creator_strategy"]
    digest = strategy.get("playbook_sha256") or hashlib.sha256(
        json.dumps(policy, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()
    draft["creator_strategy_version"] = f"schema-{policy['schema_version']}:{digest[:12]}"
    draft["creator_strategy_mechanisms"] = strategy.get("mechanisms", [])
    draft["originality_gate"] = {
        "status": "PASS",
        "recent_posts_checked": len(prior),
        "exact_hook_matches": exact_hook_matches,
        "repeated_sentences": duplicate_sentence_matches,
    }
    draft["post_hypothesis"] = {
        "unit": "post",
        "hypothesis_id": str((context.get("preflight") or {}).get("engagement_strategy", {}).get("experiment_id") or "UNASSIGNED"),
        "format": str((context.get("preflight") or {}).get("engagement_strategy", {}).get("content_format") or draft.get("editorial_style") or "NIC_NATIVE"),
        "reward_attribution_policy": "creator-period rewards are not post-level attribution",
        "owner_reported_rewards_are_unverified": True,
    }
    result["draft"] = draft
    result["creator_strategy"] = {
        "status": "CONSUMED_BY_GENERATOR",
        "playbook_schema_version": policy["schema_version"],
        "playbook_sha256": digest,
        "mechanisms_available": strategy.get("mechanisms", []),
        "fixed_template_forced": False,
        "originality_gate": "PASS",
        "checked_at_utc": datetime.now(timezone.utc).isoformat(),
    }
    return result
