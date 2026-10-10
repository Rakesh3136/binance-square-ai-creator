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

## Two-stage resume-and-publish workflow

The manual workflow `.github/workflows/nic-human-review-approval-validation.yml` now implements the second stage:

1. Select the original Actions run ID and copy the exact draft SHA-256 from its pending-review artifact.
2. Enter your own thesis, original insight, evidence reviewed, explicit approval, and exact author attestation.
3. The workflow downloads the original draft plus runtime gate context and rejects a missing, changed, or hash-mismatched draft.
4. Market snapshot and, when required, visual-decision evidence must be no more than 15 minutes old.
5. NIC reruns the final editorial, originality, visual, timing, evidence-integrity, production, and human-contribution gates.
6. Any valid no-publication result stops the job before the publisher. If a rewriter changes the reviewed draft, the exact file/text checks fail and human review is required again.
7. Only when all gates pass does the workflow build the final payload and call the Binance Square publisher using the configured repository secret.

The normal autonomous workflow now uploads the complete `data/live/` runtime context with the exact draft so the resume workflow does not accidentally use stale checked-in gate reports. The artifact is retained for seven days; the 15-minute evidence freshness requirement means older drafts must be regenerated and reviewed again.

This implementation is intentionally fail-closed. CI can verify the review package, gate ordering and safety checks, but it cannot prove a real Binance Square publication without a fresh approved artifact and the configured publisher credentials. Do not mark production publishing as verified until an explicitly approved end-to-end run returns a confirmed post result.
