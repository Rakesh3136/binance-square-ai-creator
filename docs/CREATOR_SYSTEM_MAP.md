# Binance Square AI Creator — Single Orchestrator System Map

## Purpose

The repository uses one autonomous Creator workflow. Older Creator generations remain as Python capability modules and persistent memory, but they no longer run as independent scheduled workflows.

The canonical publisher is `.github/workflows/autonomous-market-creator.yml`. It is the only scheduled publishing workflow and the only workflow with an autonomous Binance Square publishing path.

## Human-like creator loop

The workflow wakes frequently to observe the market and audience, but waking is **not** a requirement to publish.

`Observe → Research → Rank opportunities → Decide → Create → Quality check → Publish or Wait → Measure → Learn → Experiment → Improve → Observe again`

The Creator can wait when there is no strong story, pivot to a better opportunity, research when evidence is weak, or publish quickly when a time-sensitive opportunity is strong enough.

There is no hard "post every 3 hours" rule. Any cadence interval is a decision heartbeat only; the adaptive cadence and final production gates remain authoritative.

## Capability layers inside the one orchestrator

| Layer | Responsibility | Executed by the master workflow |
|---|---|---|
| Creator 7.x | Outcome learning, causal strategy, adaptive experiments, growth portfolio | Yes |
| Creator 8.0 | Monetization intelligence | Yes |
| Creator 9.0 | Autonomous reasoning/brain | Yes |
| Creator 10.0 | Reliability and recovery | Yes |
| Creator 10.1 | Root-cause repair | Yes |
| Creator 11.0 | Continuous improvement | Yes |
| Creator 12.0 | Bounded controlled experiments | Yes |
| Creator 13.0 | Self model | Yes |
| Creator 14.0 | World model | Yes |
| Creator 15.0 | Opportunity hunting | Yes |
| Creator 16.0 | Counterfactual decision analysis | Yes |
| Creator 17.0 | Active research | Yes |
| Creator 18.0 | Evidence-based value allocation | Yes |
| Creator 19.0 | Self-improvement planning | Yes |
| Creator 20.0 | Publication truth verification | Yes |
| Creator 21.0 | Human-level editorial intelligence | Yes |
| Creator 22.x | Audience, hook/format and draft intelligence | Yes |

## Canonical execution order

1. Refresh market, news and core intelligence.
2. Collect verified outcomes and update strategy memory.
3. Run reasoning, reliability, experiments, research, opportunity and improvement modules.
4. Run publication-truth and audience/editorial intelligence.
5. Build the current opportunity set and apply human-like adaptive cadence.
6. **WAIT** when the opportunity is weak or the system is not ready.
7. When authorized to publish, freeze the opportunity and create the content package.
8. Apply factual/content integrity, visual validation, and final production gates.
9. Publish through the single official Binance Square publisher path.
10. Record the result, refresh publication truth and feed measured outcomes back into future decisions.

## Safety boundaries

The Creator does not trade, withdraw funds, transfer funds, fabricate metrics, manufacture engagement, guarantee returns, bypass quality gates, or blindly rewrite source code.

Self-engineering is an optional guarded manual capability in the master workflow. It is not an independent scheduled workflow.

## Workflow topology

There is intentionally one file under `.github/workflows/`:

`autonomous-market-creator.yml`

Legacy scheduled workflow files for Creators 4.1, 7.2–9.0, 10.0–19.0, 20.0–22.x, performance learning, duplicate publishing, optimization, manual dispatching, and the separate control plane were consolidated or removed.

The Python implementations and historical state artifacts were retained so the Creator's learning memory is not discarded.
