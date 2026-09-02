from pathlib import Path
P=Path('src/multi_agent_creator.py');text=P.read_text(encoding='utf-8')
replacements={
"WRITING: Normal target 300-700 characters; hard maximum 900 when the evidence genuinely needs more context. Start with a strong, specific hook tied to the actual market move or event. Explain WHY it matters, what the chart/news is showing, and what traders should watch next. For technical setups, include current price, support, resistance, and when directly supported by live OHLCV, TP1/target and invalidation/SL. Label levels as chart-derived scenarios, never guarantees. Use natural cashtags and avoid repetitive sentence patterns.":"WRITING: Write like a sharp human newsroom/trader, not a template generator. Normal target 450-900 characters; use more only when a real news story needs context. Structure: STOP-SCROLL HOOK -> VERIFIED EVENT/OBSERVATION -> WHY NOW -> EVIDENCE -> MARKET IMPACT -> WHAT THE CHART SAYS -> BULL/BEAR SCENARIOS -> NEXT WATCH -> ONE SPECIFIC QUESTION. If fresh news is selected, the first 1-2 lines MUST communicate the actual event and source context; never open with a generic price recap. Separate FACT from INTERPRETATION. Use varied sentence length, natural transitions, precise numbers, and mobile-friendly paragraphs. For technical setups, include current price/support/resistance and only data-supported target/invalidation. Levels are scenarios, never guarantees. Avoid repetitive emoji, canned phrases and generic 'what do you think?' questions.",
"STYLE ROTATION: Never reuse the same opening, cadence, structure, emoji pattern, or question framing in consecutive posts. Rotate BREAKING NEWS + MARKET IMPACT, TOP GAINER/LOSER, VOLUME SURGE, NEW LISTING WATCH, TRADINGVIEW CHART BREAKDOWN, BREAKOUT/FAKEOUT, TARGET MAP, NEWS + CHART, COIN VS COIN, DATA SURPRISE, LIQUIDATION STORY, CREATOR CALL OUTCOME, FOLLOW-UP/UPDATE and education. Choose the format that best matches the evidence instead of mechanically repeating one experiment.":"STYLE ROTATION: Treat each post as a new story. Never reuse the same hook, cadence, paragraph order, emoji pattern, question, or opening phrase within the recent-post memory. Rotate newsroom BREAKING NEWS, macro reaction, news+chart, top mover, volume anomaly, liquidation, new listing, technical challenge, comparison, creator-call outcome, follow-up and education. The strongest story wins; do not force every cycle into a coin-price recap.",
}
for old,new in replacements.items():
    if old not in text:raise RuntimeError(f'Expected editorial prompt fragment not found: {old[:60]}')
    text=text.replace(old,new)
rules="""

NEWSROOM WRITING: When selected_opportunity contains news_title/news_source, this is a NEWS STORY. Lead with the actual verified event, naturally attribute the source, explain why it matters now, then connect it to market reaction. Do not write 'the headline is only half the story' or any equivalent canned opener. Do not merely paraphrase the headline; add verified context and interpretation. If the story is macro (for example gold/silver), explain the macro driver and compare the relevant assets when evidence supports it.

VISUAL STORYBOARD: The attached image must be useful, not decorative. For a news/comparison story with two relevant assets, request a two-panel official TradingView image with one clean chart per asset. For gold/silver use OANDA:XAUUSD and OANDA:XAGUSD. For crypto use the exact relevant Binance symbols. No custom panels, maps, technical boxes or overlays may cover candles. Never fabricate a chart.

ARTICLE-STYLE POST: The post should read like a compact news article in the Square feed: strong headline-like first line, 2-5 short paragraphs, evidence, interpretation, market implications, scenarios and one specific question. It may be long enough to tell the story; do not compress a real breaking event into a two-line price recap.

FACT DISCIPLINE: Never invent sources, quotes, numbers, prices, volume, targets, creator calls or outcomes. If a source is only a discovery lead, do not present unverified claims as fact. Never promise profit or guaranteed 10x/20x returns.
"""
if 'NEWSROOM WRITING:' not in text:
    needle="Return ONLY valid JSON with research, critique, draft and visual_plan fields."
    marker=needle+(chr(39)*3)
    if marker not in text:raise RuntimeError('Editorial system prompt closing marker not found')
    text=text.replace(marker,needle+rules+(chr(39)*3),1)
P.write_text(text,encoding='utf-8');print({'status':'EDITORIAL_DIRECTOR_PATCH_APPLIED','version':'4.2-newsroom'})
