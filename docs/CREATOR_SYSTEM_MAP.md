# Binance Square AI Creator — Unified System Map

## Purpose

The repository contains multiple Creator generations. They are treated as capability layers, not separate products.

The production publisher remains the authoritative execution path. The new Control Plane coordinates state from the existing layers and makes one safety-aware control decision.

## Canonical flow

Research & Market → Opportunity/World Model → Counterfactual Decision → Content Creation → Existing Quality Gates → Publication → Outcome Measurement → Experiment Learning → Self-Improvement → next cycle

## Capability map

| Layer | Responsibility | State consumed by Control Plane |
|---|---|---|
| Creator 7.0 | Production content/publishing brain and gates | `creator_7_0_brain_state.json` |
| Creator 10.0 | Reliability/recovery | `creator_10_0_recovery_state.json` |
| Creator 10.1 | Root-cause repair | `creator_10_1_repair_state.json` |
| Creator 11.0 | Continuous improvement decisions | `creator_11_0_improvement_state.json` |
| Creator 12.0 | Bounded controlled experiments | `creator_12_0_active_experiment.json` |
| Creator 13.0 | Synthetic/self model | `creator_13_0_self_state.json` |
| Creator 14.0 | World model | `creator_14_0_world_model.json` |
| Creator 15.0 | Opportunity hunting/ranking | `creator_15_0_opportunity_board.json` |
| Creator 16.0 | Counterfactual decisions | `creator_16_0_decision_board.json` |
| Creator 17.0 | Active research | `creator_17_0_research_state.json` |
| Creator 18.0 | Evidence-based value allocation | `creator_18_0_value_allocation.json` |
| Creator 19.0 | Self-improvement planning | `creator_19_0_improvement_board.json` |

## Control Plane

`src/creator_control_plane.py` reads the capability state and writes:

- `data/live/creator_control_plane.json`
- `data/intelligence/creator_control_plane_report.json`

The workflow `.github/workflows/creator-control-plane.yml` runs every 3 hours and on manual dispatch.

## Safety model

The Control Plane does not publish directly, trade, withdraw funds, bypass editorial/factual/visual gates, fabricate outcomes, infer revenue from engagement, or rewrite source code automatically.

Creator 12.0 already enforces bounded experiments and explicitly prohibits invented data and gate bypasses. Creator 19.0 similarly records proposed improvements without blind self-modification. The Control Plane preserves those constraints.

## Cleanup policy

Do **not** delete the older Creator workflows yet. They remain available while the Control Plane is observed. Once the unified architecture is verified in real Actions runs, redundant scheduled writers can be consolidated safely in a separate cleanup change.
