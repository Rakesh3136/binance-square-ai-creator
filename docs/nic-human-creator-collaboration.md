# NIC Human Creator Collaboration Gate

## Why this exists

Binance Square's published CreatorPad guidance values original ideas, research depth, relevance and authentic engagement. It warns that entirely AI-generated content can be de-boosted. This component does not try to disguise AI authorship or fabricate a human voice.

## What it does

1. Reads the exact current draft.
2. Writes `data/live/nic_human_creator_brief.json` with the draft hash, asset and review prompts.
3. Reads `data/live/nic_human_creator_input.json`.
4. Requires a substantive human thesis, an original insight, evidence actually reviewed, explicit approval and an attestation.
5. Blocks if the input does not refer to the exact draft hash. Approval for an older draft cannot approve a regenerated draft.

## Input contract

The file `data/live/nic_human_creator_input.json` must be prepared by a human reviewer for the exact draft hash in the brief:

```json
{
  "draft_sha256": "COPY_THE_EXACT_HASH_FROM_THE_BRIEF",
  "human_thesis": "Write your own reasoned thesis in at least 30 characters.",
  "original_insight": "Write the specific insight you personally identified in at least 30 characters.",
  "evidence_reviewed": "Describe the chart/source/evidence you actually reviewed.",
  "approved_for_publication": true,
  "author_attestation": "I reviewed the evidence and authored the editorial contribution"
}
```

These fields must reflect genuine review; do not invent personal trading history, results or experience.

## Important deployment limitation

This is a strict gate, not a complete pause-and-resume publishing workflow. When human input is missing or stale, it produces a valid BLOCKED decision. Before enabling this as the default production requirement, NIC needs a two-stage workflow that preserves the exact pending draft, lets a human review it after generation, and resumes publication only for that same approved draft while revalidating market/chart freshness. Do not bypass the gate just to increase post volume.
