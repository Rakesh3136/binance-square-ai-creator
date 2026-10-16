# NIC verified Write-to-Earn reward evidence

NIC may use a reward as a creator-learning label only when it is linked to one exact canonical Binance Square post and the evidence record is independently auditable.

## Required event fields

- `event_id`: stable, unique reward event identifier.
- `canonical_post_id`: exact numeric Square post ID; a general account notification is not enough.
- `reward_amount_usdc`: positive numeric reward amount.
- `currency`: `USDC`.
- `verified`: boolean `true`, paired with `reward_status=PAID_VERIFIED` or `REWARD_VERIFIED`.
- `observed_at` and `verified_at`: timezone-aware ISO-8601 timestamps.
- `evidence_refs`: at least one object with `source_id` or `url`, a 64-character SHA-256/excerpt hash, and timezone-aware `observed_at`.

Example structure (illustrative schema only; it is not a real reward record):

```json
{
  "event_id": "replace-with-real-event-id",
  "canonical_post_id": "replace-with-exact-post-id",
  "observed_at": "2026-10-16T10:00:00+00:00",
  "verified_at": "2026-10-16T10:05:00+00:00",
  "reward_amount_usdc": 0.201,
  "currency": "USDC",
  "verified": true,
  "reward_status": "PAID_VERIFIED",
  "source": "user-provided-reward-export",
  "evidence_refs": [
    {
      "source_id": "replace-with-source-row-or-private-evidence-reference",
      "sha256": "64-character-lowercase-sha256-of-the-evidence",
      "observed_at": "2026-10-16T10:05:00+00:00"
    }
  ]
}
```

Do not copy the example into production data or mark it verified without the original evidence. A screenshot/export can be retained privately; the event can store its hash and a non-sensitive evidence reference. If a reward cannot be linked to an exact post, preserve it as unattributed and do not use it to rank content formats.

Views, likes, and engagement remain separate observational metrics. This gate does not prove that a post caused a reward, train a model, authorize trading, or enable publishing.
