# NIC Trade Outcome & Counterfactual Journal

This journal keeps three questions separate:

1. **Outcome:** did a documented trade resolve as a verified win, verified loss, breakeven, or remain unresolved?
2. **Prediction quality:** was the thesis supported by evidence available when it was published?
3. **Learning status:** has the evaluated case been incorporated into measured strategy evaluation?

## Safety and evidence rules

- An outcome other than `unresolved` requires one or more traceable `outcome_evidence` references.
- A claim of profitability alone is not sufficient evidence to mark a trade as a verified win.
- Do not infer realized P&L from a target price or later market movement.
- Keep `prediction_quality` independent from `outcome`; a lucky outcome can still have a weak thesis.
- `learning_status=incorporated` requires a resolved outcome and an assessed prediction quality.
- The JSONL log is append-only. Corrections are new events with the same `trade_id`; the latest event is the current view.

## Initial ETH and QNT examples

The ETH short (entry 2,581; stop 2,596.5) and QNT long-term idea (entry mentioned 100.9 USDT) should initially be recorded as `unresolved`, `not_assessed`, and `pending` until timestamped entry/exit or price-path evidence is attached. The QNT $10,000 target is a stated thesis target, not proof of a realized outcome.

## Module API

- `append_record(record, path=...)` validates and appends one event.
- `read_latest(path=...)` returns the latest event per trade ID.
- `summary(path=...)` reports outcomes, thesis quality, and learning status separately.

Run tests with:

```bash
python -m unittest tests.test_trade_outcome_journal
```

**Integration status:** this module is deliberately isolated until the authoritative counterfactual gate and the production workflow's existing evaluation hooks are confirmed. It must not be treated as active production learning merely because the module exists.
