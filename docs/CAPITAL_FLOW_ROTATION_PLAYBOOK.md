# Capital Flow & Rotation Playbook — Creator 23.0

## Objective

The creator should not merely ask “what coin moved?” It should estimate where risk appetite is rotating and which assets are becoming stronger or weaker relative to BTC/ETH/BNB. The system then turns that evidence into conditional story opportunities.

The engine is deliberately probabilistic. It does **not** observe wallet-level capital flows and must not describe its proxy signals as literal proof that money is moving into a coin.

## Evidence stack

For BTC, ETH, BNB and a liquid Binance USDT universe, Creator 23.0 studies:

- 1h, 4h, 12h and 1d OHLCV structure.
- EMA trend alignment and RSI.
- Multi-window returns and ATR volatility.
- Volume acceleration.
- Spot taker-buy share as a directional flow proxy.
- Futures open-interest change as a positioning proxy.
- Funding rate as a crowding/positioning proxy.
- Futures taker buy/sell ratio and global long/short account ratio when available.
- Relative strength versus BTC.
- Recent breakout/support/resistance structure.
- Liquidity and data-quality conditions.

Binance's derivatives market-data APIs expose klines and open-interest history, while funding and positioning endpoints provide additional observable derivatives signals. These are inputs, not certainty about future price direction.

## Regime model

The market regime is classified as:

- `RISK_ON`: BTC trend and flow proxies are both positive.
- `RISK_OFF`: BTC trend and flow proxies are both negative.
- `MIXED`: evidence conflicts or lacks alignment.

The regime is a context variable, not a trade signal by itself.

## Rotation logic

An altcoin can become a **relative-strength leader** when its multi-timeframe returns exceed BTC while its trend/flow stack also improves. A laggard is one that materially underperforms BTC.

A BTC weakness event does **not** automatically imply that another coin will pump. The creator must require independent confirmation such as:

`relative strength + spot buy pressure + acceptable positioning + trend alignment + liquidity`.

For downside setups, the mirror logic applies: persistent underperformance plus bearish multi-timeframe structure and flow/positioning confirmation are required.

## Conditional setup model

The engine may produce `LONG`, `SHORT`, or `WAIT`.

A setup requires:

- multi-timeframe trend alignment,
- directional flow-proxy confirmation,
- adequate liquidity,
- confidence above the configured threshold,
- no direct contradiction from relative strength.

Trigger, invalidation, TP1 and TP2 are derived from current ATR and recent structure. They are **model levels**. They are never presented as guaranteed outcomes.

`WAIT` is the correct output whenever evidence conflicts, data is incomplete, or liquidity is weak.

## Content format

When the flow engine finds a strong conditional setup, the creator should produce:

1. The BTC/ETH/BNB regime.
2. The selected asset's relative strength or weakness.
3. The specific evidence stack behind the divergence.
4. A conditional LONG/SHORT setup only when qualified.
5. Trigger, invalidation and model TP1/TP2.
6. The exact condition that would make the thesis wrong.
7. One useful reader question.

The post should not say “this coin will pump,” “this coin will dump,” or use certainty language. It should say what the current evidence supports and what needs to happen next.

## Monetization alignment

Relevant coin cashtags and Binance trading widgets can make content attributable for eligible Binance Square monetization programs. Current Binance guidance says Write to Earn can reward eligible creators when readers click a coin cashtag or trading widget and complete a qualified trade. It also states that spam/low-quality content is excluded and that CreatorPad submissions must have required tags in the first publication version. The creator must therefore optimize for **useful, original analysis**, not click farming.

## Research integrity

The engine must preserve these epistemic labels:

- `VERIFIED_FACT`
- `DERIVED_OBSERVATION`
- `INTERPRETATION`
- `HYPOTHESIS`
- `UNKNOWN`

No component may convert a derived flow proxy into a claim of certainty.
