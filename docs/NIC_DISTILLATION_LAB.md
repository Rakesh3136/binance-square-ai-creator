# NIC Distillation Lab: operating contract

The Distillation Lab prepares reviewed examples for a future student-model training run. It does not fine-tune a model, trade, or publish content.

## Input files

Place one JSON object per line in either:
- `data/live/nic_distillation_teacher_examples.jsonl`
- `data/live/nic_distillation_reviewed_examples.jsonl`

Required fields:
- `example_id`, `task_type`, `input`, `teacher_target`, `created_at` (timezone-aware ISO-8601)
- `review_status`: `VERIFIED`, `REVIEWED`, or `CONFIRMED`
- `label`: one of the supported labels in `src/nic_distillation_lab.py`
- `evidence_refs`: at least one reference containing a URL or source ID, a SHA-256/excerpt hash, and timezone-aware `observed_at`
- `source_group`: stable group for the underlying post, forecast, market episode, or source document

Forecast-outcome examples additionally require `forecast_id` and `outcome_status=TERMINAL_VERIFIED`. The student's input must contain only information available at decision time; the terminal outcome belongs in the teacher target/label, never the input. Creator-reward examples require a canonical post ID and verified paid/reward evidence. Views, likes, and impressions are not revenue labels.

## Run and review

Run the GitHub Actions workflow **NIC Distillation Dataset Activation** manually after reviewed examples are added. It also runs weekly and when the lab or input ledgers change. Download artifact `nic-distillation-dataset-audit`; inspect the report's accepted/rejected counts, reasons, source-group split, and dataset hash.

No invented or synthetic example should be marked verified. Keep raw source evidence and reviewer records traceable. Teacher targets should be concise, evidence-backed answer/decision summaries—not private chain-of-thought.

## Promotion criteria

The current builder requires at least 100 verified examples before training is eligible and at least 25 held-out examples before promotion can be considered. These are minimum gates, not a guarantee of statistical power. Promotion also requires human review, baseline comparison, chronological forecast evaluation after fees/slippage, and a model-specific benchmark. Small datasets remain blocked. A separate fine-tuning job and model registry/promotion mechanism must be implemented before actual student training is possible.

Automatic Binance Square publication and trade authorization remain disabled.
