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

## Pending-draft preservation added

When the human contribution gate blocks, the workflow now creates `data/live/nic_pending_human_review.json` and uploads a seven-day artifact containing the exact draft, its text/file SHA-256 hashes, review brief, and available market/chart context. The package verifier rejects a changed draft, mismatched approval hash, missing approval, or incomplete human contribution. This makes the blocked draft recoverable instead of leaving only a gate result in the run log.

## Important deployment limitation

This is still not a complete pause-and-resume publisher. The pending artifact preserves the draft and review context, but the manual resume workflow must still retrieve that artifact, validate the human approval, rerun every applicable market/chart/editorial/publication gate, and publish only if the approved text remains byte-for-byte unchanged. The current implementation does not claim that a reviewed artifact can publish, and no production publishing behavior is enabled by this branch. Do not bypass the gate just to increase post volume.
