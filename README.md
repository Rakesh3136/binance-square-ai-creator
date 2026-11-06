# Binance Square AI Creator

An autonomous content system for researching crypto topics, creating original Binance Square content, publishing through approved APIs, measuring performance, and improving its strategy.

## Task-scoped specialist runtime

NIC chat uses one orchestrator that can create up to two temporary, model-backed
specialists for a request when delegation adds value. The available specialties
cover research, reward analysis, publication/performance auditing, creator
strategy, editorial coaching, and fact checking. Workers are created only for
the current task, receive a role-specific allowlist of bounded read-only tools,
return findings to the orchestrator, and do not respond to the user directly.

The former synthetic 300-node mesh has been retired: those nodes were generated
labels with deterministic hash weights, not 300 independent model-backed workers.
NIC now favors measurable task completion over a permanent agent count. Specialist
creation is bounded, tool access is least-privilege, and publication remains
restricted to the existing publisher and quality gates.

## Safety

- Never store API keys, secrets, passwords, seed phrases, or private keys in this repository.
- Content automation must not perform trading, withdrawals, transfers, or market manipulation.
- Verify market-sensitive claims before publication.
- Earnings are not guaranteed.

## Planned pipeline

Research → Trend Scoring → Analysis → Fact Check → Content Creation → Quality Control → Publishing → Analytics → Learning

## Current stage

Project foundation. API credentials and automation services will be added later through secure environment variables/secrets.
