from pathlib import Path

P = Path("src/multi_agent_creator.py")
text = P.read_text(encoding="utf-8")

replacements = {
    "VISUAL-FIRST: For a single-asset market story, prefer a REAL Binance 1h candlestick chart. Use only real OHLCV-derived levels/patterns. Never invent a pattern or level.": "TRADINGVIEW-ONLY VISUAL: For every single-asset market story, the publication MUST include an official TradingView 1H candlestick chart for the exact primary Binance symbol. Use only real chart data and data-supported annotations. Never substitute a homemade, Binance-only, generated, placeholder, or text-only chart. If TradingView cannot be rendered or verified, do not publish.",
    "WRITING: Normal target 180-500 characters; hard maximum 750. First line creates curiosity. Use 2-5 short mobile-friendly lines. Sound conversational, not like a financial report. Do not automatically provide TP/SL/entry calls.": "WRITING: Normal target 300-700 characters; hard maximum 900 when the evidence genuinely needs more context. Start with a strong, specific hook tied to the actual market move or event. Explain WHY it matters, what the chart/news is showing, and what traders should watch next. For technical setups, include current price, support, resistance, and when directly supported by live OHLCV, TP1/target and invalidation/SL. Label levels as chart-derived scenarios, never guarantees. Use natural cashtags and avoid repetitive sentence patterns.",
    "STYLE ROTATION: Do not reuse the same opening cadence, editorial_style, or paragraph structure as the immediately previous post. Prefer visibly different structures such as CHOICE, CHART CHALLENGE, COIN VS COIN, DATA SURPRISE, BREAKOUT/FAKEOUT, NEWS REACTION, LIQUIDATION STORY, TOP MOVERS, quick observation, or mini-story.": "STYLE ROTATION: Never reuse the same opening, cadence, structure, emoji pattern, or question framing in consecutive posts. Rotate BREAKING NEWS + MARKET IMPACT, TOP GAINER/LOSER, VOLUME SURGE, NEW LISTING WATCH, TRADINGVIEW CHART BREAKDOWN, BREAKOUT/FAKEOUT, TARGET MAP, NEWS + CHART, COIN VS COIN, DATA SURPRISE, LIQUIDATION STORY, CREATOR CALL OUTCOME, FOLLOW-UP/UPDATE and education. Choose the format that best matches the evidence instead of mechanically repeating one experiment.",
}

for old, new in replacements.items():
    if old in text:
        text = text.replace(old, new)

rules = (
    "\n\nRESEARCH COVERAGE: The supplied NEWS snapshot is a first-class research input, not a fallback. "
    "Before choosing the post, compare current crypto headlines, official macro/regulatory announcements, market movers, "
    "volume anomalies, new listings and technical setups. Prefer a news post when a material, recent, verified story has "
    "stronger attention potential; use NEWS + CHART when the story materially affects a tradeable asset. Never invent or "
    "exaggerate news.\n\n"
    "TECHNICAL LEVELS: For a technical/chart post, the final draft MUST use the live technical enrichment values when supplied: "
    "current price, support, resistance, TP1/target and invalidation/SL. The chart visual must display those same values. "
    "Never manufacture levels. If the data does not justify a target or stop, say so rather than inventing one.\n\n"
    "CALL-OUT FOLLOW-UP: When a prior creator signal/call is available in the research inputs, the AI may create an original "
    "outcome post only when the subsequent price move is verified from fresh market data. State the measured result; never "
    "falsely claim that we told users to buy and never guarantee future returns. Avoid 10x/20x certainty claims; such scenarios "
    "must be explicitly speculative.\n"
)

marker = "Return ONLY valid JSON with research, critique, draft and visual_plan fields.'''
"
if "RESEARCH COVERAGE:" not in text:
    if marker not in text:
        raise RuntimeError("Editorial system prompt marker not found; refusing unsafe patch")
    text = text.replace(marker, rules + marker)

P.write_text(text, encoding="utf-8")
print({"status": "EDITORIAL_DIRECTOR_PATCH_APPLIED"})
