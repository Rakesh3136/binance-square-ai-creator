# NIC Agent Assistant and Model Teaching Plan

## Product direction

NIC should evolve from a scheduled content script into a tool-using assistant with explicit roles, task plans, provenance-aware memory, evaluations, and human-controlled side effects. It should support a conversational founder-partner workflow as well as crypto research and original content drafting.

## Suggested architecture

1. **Conversation/task intake:** turn the user's request into a typed task with goal, constraints, expected output, and required evidence.
2. **Planner/orchestrator:** break tasks into research, analysis, critique, drafting, and verification subtasks. Keep a task ledger and resumable status.
3. **Role agents:** market researcher, creator analyst, trade critic, writer, quality reviewer, founder partner. Roles receive least-privilege tools and have no publishing authority.
4. **Tool adapters:** read-only public web/market-data tools and repository/files tools with typed schemas, timeouts, provenance and retry limits.
5. **Evidence memory:** source URL, capture time, factual observation, interpretation, confidence, expiry/freshness, evaluation result and correction history. Memory is not automatically truth.
6. **Evaluator:** unit tests, citation checks, factual consistency, duplicate detection, chart-symbol matching, out-of-sample forecast scoring, and human preference tests.
7. **Action gateway:** publishing and any financial side effects remain separate, explicitly authorized capabilities. The agent core cannot grant itself these permissions.
8. **Provider adapter:** NIC-native baseline first; optional authorized Claude API calls behind a feature flag and budget cap. No API secret in source or logs.

## Claude 5.5: use as a teacher or service, not an unauthorized copy target

First verify the exact available Claude model/API ID in Anthropic's official model documentation. If the user has authorized API access and the relevant terms permit the intended use, Claude can serve as an external critic/teacher for a small, curated set of examples: generate rubric scores, explain observable writing strengths, suggest counterarguments, and draft synthetic training examples. Save prompt/version, model ID, date, source provenance, cost and human approval. Evaluate the resulting NIC system against held-out examples and the existing NIC-native baseline.

Do not scrape or mass-query Claude to reconstruct hidden reasoning, clone proprietary weights, or assume API output can be used for model training without checking applicable terms. Prefer using Claude as an optional runtime service or using permitted synthetic examples to improve NIC's explicit rubrics, retrieval, tools and tests. Do not train on private chain-of-thought; use concise rationales, evidence, answers and rubric labels instead.

## Initial validation sequence

- Benchmark 30–50 representative tasks: crypto market explanation, trader pain-point clustering, creator-style analysis, long-term project evidence checklist, draft rewrite, chart/source mismatch detection, and founder idea validation.
- Compare NIC-native baseline against an authorized Claude-assisted variant on accuracy, citation fidelity, usefulness, originality, latency and cost.
- Use blinded scoring and a held-out set; preserve failure cases. If the Claude-assisted variant does not improve the target metrics enough to justify cost, do not adopt it.
- Only after the evaluation passes, wire a provider adapter. Keep all external actions disabled until separate policy tests and explicit owner approval.

## Current scope of the code in this PR

The new core is a typed planning/provenance contract and safety boundary. It does not call Claude, execute tools, publish posts, trade, or claim autonomous learning. Those capabilities require separately reviewed adapters, credentials, evaluation results and explicit activation.
