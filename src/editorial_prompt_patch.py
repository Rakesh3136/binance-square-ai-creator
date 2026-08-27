from pathlib import Path
P=Path('src/multi_agent_creator.py')
text=P.read_text(encoding='utf-8')
replacements={
'WRITING: Normal target 180-500 characters; hard maximum 750. First line creates curiosity. Use 2-5 short mobile-friendly lines. Sound conversational, not like a financial report. Do not automatically provide TP/SL/entry calls.':'WRITING: Normal target 220-650 characters; hard maximum 750. First line must create curiosity or urgency without fake hype. Use 3-6 short mobile-friendly lines. Sound like a sharp human crypto creator. Rotate market movers, breaking news, macro, new listings, volume anomalies, TradingView technical setups, breakout/fakeout, comparison, education, creator-call outcomes and follow-ups. For chart-driven stories, include live-data-derived support/resistance and, when justified, a measured target and invalidation/SL. Label levels as scenarios, never guarantees.',
'STYLE ROTATION: Do not reuse the same opening cadence, editorial_style, or paragraph structure as the immediately previous post. Prefer visibly different structures such as CHOICE, CHART CHALLENGE, COIN VS COIN, DATA SURPRISE, BREAKOUT/FAKEOUT, NEWS REACTION, LIQUIDATION STORY, TOP MOVERS, quick observation, or mini-story.':'STYLE ROTATION: Do not reuse the same opening cadence or structure. Rotate BREAKING NEWS + MARKET IMPACT, TOP GAINER/LOSER, VOLUME SURGE, NEW LISTING WATCH, CHART BREAKOUT, TARGET MAP, BREAKOUT/FAKEOUT, NEWS + CHART, COIN VS COIN, DATA SURPRISE, LIQUIDATION STORY, CREATOR CALL OUTCOME, FOLLOW-UP/UPDATE and education.'}
for old,new in replacements.items():
    if old in text: text=text.replace(old,new)
asset_rule='''SELECTED ASSET LOCK: The selected editorial opportunity is authoritative. Use its exact primary symbol unless the research proves that the opportunity is invalid. Never silently switch to another coin. The final draft symbol, chart symbol, cashtag and discussed market must all refer to the same primary asset. If the selected opportunity is a chart-first lane, do not produce a text-only generic market recap.'''
if 'SELECTED ASSET LOCK:' not in text:
    marker='VISUAL-FIRST: For a single-asset market story, prefer a REAL Binance 1h candlestick chart. Use only real OHLCV-derived levels/patterns. Never invent a pattern or level.'
    if marker in text: text=text.replace(marker,marker+'\n\n'+asset_rule)
P.write_text(text,encoding='utf-8')
print({'status':'EDITORIAL_DIRECTOR_PATCH_READY'})
