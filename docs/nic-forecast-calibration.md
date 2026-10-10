# NIC Forecast Calibration

This module adds probability calibration metrics to the NIC learning foundation. It is separate from the trade outcome journal and is not wired into production publishing yet.

## Required record

Each forecast needs a unique `forecast_id`, symbol, `probability_up` between 0 and 1, and a resolution label (`up`, `down`, or `unresolved`). A resolved forecast must include traceable `resolution_evidence`. Forecast horizon and strategy labels should be supplied so incompatible populations are not mixed.

## Metrics

- **Brier score:** mean squared error between the predicted probability of an upward outcome and the observed binary outcome; lower is better.
- **Calibration bins:** compares mean predicted probability with observed upward frequency in probability bands.
- **Unresolved forecasts:** reported separately and excluded from the score.

## Guardrails

- Never score unresolved forecasts as losses, wins, or zeros.
- Never resolve a forecast without evidence.
- Do not compare incompatible horizons or resolution definitions.
- A good calibration score does not itself prove positive returns, useful entries, causality, or future success.
- The ETH and QNT examples must not receive invented probability values or be included in calibration until original probabilities, resolution rules, and outcome evidence are available.

## Test

```bash
python tests/test_forecast_calibration.py
```
