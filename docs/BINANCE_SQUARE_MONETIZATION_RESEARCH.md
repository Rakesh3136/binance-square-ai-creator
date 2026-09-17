# Binance Square Monetization Research

## Purpose

This document separates first-party Binance monetization rules from public creator observations. The creator should learn reusable patterns, not copy creators, wording, identities, or unverifiable earnings claims.

## 1. First-party Write-to-Earn mechanics

Source: Binance Square Write-to-Earn FAQ and current Write-to-Earn program page.

- A market post needs a usable attribution bridge: a primary coin cashtag or verified trading widget.
- A qualified reader must click through and trade directly after the attribution interaction for the trade to be associated with the creator.
- The program describes a one-minute attribution window after the click.
- The creator's own trading activity does not earn commission.
- Referral-user trades, API trades, fee-free pairs, market-maker/broker activity, stablecoin-to-stablecoin conversions, and abnormal/fraudulent activity are excluded by the program rules.
- The base commission rate is 20% of the qualifying trading-fee commission allocated by the program. The published bonus tiers are 30% total for ranks 31-100 and up to 50% total for ranks 1-30.
- The reward period is Monday-Sunday UTC, with USDC payout by the following Thursday and a 0.1 USDC minimum weekly payout threshold.
- Supported content can include short posts, articles, videos, Lives/chats and other eligible Square formats described by the program.

## 2. What public creators repeatedly emphasize

Public Binance Square creator advice is treated as benchmark evidence, not as independently verified earnings data.

Repeated themes across public creator posts include:

1. **Timeliness and intent** — publish around live market attention, gainers/losers, breaking developments, or a clear decision point rather than generic evergreen filler.
2. **Proof and context** — use relevant candlestick charts, trading widgets, verified trade cards, or other genuine evidence when available.
3. **Clear thesis** — lead with the conclusion or decision point, then explain the mechanism and the evidence.
4. **Relevant cashtags** — keep attribution tightly tied to the assets actually discussed. More tags do not automatically improve monetization.
5. **Actionable reader value** — give the reader a concrete thing to watch, confirm, compare, or invalidate.
6. **Human voice** — concise conversational language, a recognizable point of view, and specific market reasoning are repeatedly favored over sterile summaries.
7. **Consistency without spam** — strong creators discuss trending topics while avoiding repetitive copy-paste posts, fake engagement, and meaningless promotional questions.

### Earnings evidence quality

Some public creators publish self-reported weekly earnings or ranking claims. Those claims are **not independently verified here** and are therefore never used as revenue facts or forecasts for this creator.

## 3. CreatorPad opportunity layer

CreatorPad is separate from ordinary Write-to-Earn attribution. Binance uses it for campaigns/tasks with specific requirements such as hashtags, mentions, minimum length, posting formats, livestream conditions, or other campaign-specific tasks.

The AI should therefore:

- monitor verified active campaign requirements when first-party data is available;
- treat each campaign as a separate contract;
- never claim campaign eligibility, reward amount, completion, or payout without verification;
- never manufacture hashtags, mentions, traffic, or task completion;
- treat expired campaigns only as historical evidence of campaign structure.

## 4. Architecture application

The repository now treats monetization as a **quality-and-attribution contract**, not a promise of revenue.

### Decision priority

`signal/evidence quality`
→ `timeliness/reader intent`
→ `clear mechanism`
→ `relevant cashtag/widget`
→ `proof visual`
→ `original human editorial judgment`
→ `specific question`
→ `verified outcome follow-up`

Monetization cannot override safety, editorial quality, or market-data integrity.

### Signal-first integration

For technical and capital-flow setups, the preferred package is:

- conditional LONG/SHORT direction;
- trigger/confirmation;
- TP1/TP2 only when evidence supports them;
- invalidation/SL;
- confidence;
- matching TradingView visual;
- primary cashtag;
- one useful reader question.

None of these fields may be invented merely to make a post monetizable.

### Learning loop

Verified publication IDs, Square metrics, prediction outcomes and explicitly verified revenue are fed back into the existing learning/revenue engines. Missing revenue or attribution stays missing; the system does not infer money from views, likes, comments, or follower growth.

## 5. Operating rule

The goal is not to make every post earn. The goal is to maximize the proportion of **genuinely useful, timely, attributable, trustworthy posts** that have a legitimate path to qualified reader actions while preserving safety and authenticity.

A post can be monetization-ready and still earn zero. That is a valid outcome and becomes training data rather than a reason to fabricate success.
