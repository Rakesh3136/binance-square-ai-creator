from pathlib import Path

P=Path('src/multi_agent_creator.py')
text=P.read_text(encoding='utf-8')
old='WRITING: Normal target 180-500 characters; hard maximum 750. First line creates curiosity. Use 2-5 short mobile-friendly lines. Sound conversational, not like a financial report. Do not automatically provide TP/SL/entry calls.'
new='''WRITING: Normal target 220-650 characters; hard maximum 750. First line must create curiosity or urgency without fake hype. Use 3-6 short mobile-friendly lines. Sound like a sharp human crypto creator, not a financial report. Rotate formats across market movers, breaking news, macro/news reactions, new listings, volume/volatility anomalies, TradingView technical setups, breakout/fakeout, comparison, education, creator-call outcome and follow-up stories. For a technical setup, include only live-data-derived support/resistance and, when the chart structure supports it, a measured target and invalidation/SL level; label them as chart-derived levels, never as guarantees. For a creator-call outcome, distinguish clearly between what the other creator said and what our own account said. Never claim "I told you" unless our own published record proves it.'''
if old in text:
    text=text.replace(old,new)
old2='STYLE ROTATION: Do not reuse the same opening cadence, editorial_style, or paragraph structure as the immediately previous post. Prefer visibly different structures such as CHOICE, CHART CHALLENGE, COIN VS COIN, DATA SURPRISE, BREAKOUT/FAKEOUT, NEWS REACTION, LIQUIDATION STORY, TOP MOVERS, quick observation, or mini-story.'
new2='''STYLE ROTATION: Do not reuse the same opening cadence, editorial_style, or paragraph structure as the immediately previous post. Prefer visibly different structures such as BREAKING NEWS + MARKET IMPACT, TOP GAINER/LOSER, VOLUME SURGE, NEW LISTING WATCH, CHART BREAKOUT, TARGET MAP, BREAKOUT/FAKEOUT, NEWS + CHART, COIN VS COIN, DATA SURPRISE, LIQUIDATION STORY, CREATOR CALL OUTCOME, FOLLOW-UP/UPDATE, or a short educational mini-story.'''
if old2 in text:
    text=text.replace(old2,new2)
P.write_text(text,encoding='utf-8')
print({'status':'PATCHED','path':str(P),'changed':old in text or old2 in text})
