"""Creator 4.2 story-specific writing contract."""
from __future__ import annotations
import json,re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
PREFLIGHT=ROOT/'data/live/editorial_preflight.json'; OUT=ROOT/'data/live/script_director_4.json'
HOOKS={
'BREAKING NEWS + MARKET IMPACT':['🚨 The headline changed the backdrop. ${symbol} is where the market reaction gets interesting.','The news is only half the story — ${symbol} has to confirm it on price.','⚠️ New information is hitting crypto. Here is what ${symbol} is doing with it.'],
'NEWS + CHART':['📰 The headline is only half the story. Look at ${symbol} on the chart.','${symbol} has the catalyst. Now price has to confirm it.','The level on ${symbol} that matters after the latest headline:'],
'TRADINGVIEW CHART CHALLENGE':['📊 Chart challenge: what happens next for ${symbol}?','${symbol} is testing a level worth watching — here is why.','The ${symbol} chart is getting interesting at this exact zone:'],
'TOP MOVERS':['🔥 ${symbol} just made a move traders cannot ignore — but can it hold?','${symbol} is moving fast. The second move may matter more than the first.','Everyone can see ${symbol} moving. The real question is what happens next.'],
'DATA SURPRISE':['🔎 The ${symbol} number that caught my attention:','Most people are watching price. I’m watching this number on ${symbol}:','One data point makes today’s ${symbol} move much more interesting:'],
'LIQUIDATION STORY':['⚠️ ${symbol} just printed a move violent enough to change the short-term setup.','That ${symbol} flush was not a normal candle. Here is what I’m watching next.','${symbol} just forced traders to rethink the next move.'],
'NEW LISTING WATCH':['🆕 New listing watch: here is what matters on ${symbol}.','A new market is live — but the first move can be deceptive.','${symbol} is getting fresh attention. Here are the levels I’m watching.'],
'MACRO + MARKET IMPACT':['🌎 The macro headline is hitting crypto. Here is what matters for ${symbol}.','One macro development could change the tone around ${symbol}.','Before chasing ${symbol}, watch how price reacts to the macro signal.'],
'CREATOR CALL OUTCOME':['👀 A creator flagged ${symbol}. Now the market can tell us what happened.','Follow-up: the ${symbol} setup moved. Here is the measured result.','The original ${symbol} call is now testable with fresh price data.'],
'EDUCATION FROM LIVE CHART':['🧠 Quick lesson from the ${symbol} chart:','Here is a simple way to read what ${symbol} is doing right now.','A live ${symbol} chart can teach us something useful here:'],
'COIN VS COIN':['⚔️ ${a} vs ${b}: which chart has the cleaner setup?','Two coins, one question: which structure is stronger?','The interesting comparison today is ${a} against ${b}.'],
'FOLLOW-UP / UPDATE':['🔄 Update on ${symbol}: the market has moved since our last look.','We flagged ${symbol}. Now the thesis needs an update.','New data changes the picture for ${symbol}. Here is what matters now.']}

def main():
    p=json.loads(PREFLIGHT.read_text(encoding='utf-8')) if PREFLIGHT.exists() else {}; d=p.get('content_director_4') or {}; selected=p.get('selected_opportunity') or {}
    fmt=str(d.get('recommended_format') or 'TOP MOVERS').upper(); sym=re.sub(r'USDT$','',str(selected.get('symbol') or d.get('primary_story',{}).get('symbol') or '').upper())
    if not re.fullmatch(r'[A-Z0-9]{2,15}',sym):raise SystemExit('Script Director: authoritative selected symbol is missing or invalid')
    candidates=[x.replace('${symbol}',f'${sym}') for x in HOOKS.get(fmt,HOOKS['TOP MOVERS'])]
    directive={'version':'4.2','format':fmt,'primary_symbol':sym,'hook_candidates':candidates,'writing_contract':['Write a complete post: hook → what happened → why it matters → evidence → chart/levels → bull case and bear case → what to watch → one question.','Sound like a sharp human market observer, not a press release. Use contractions and varied sentence length.','Lead with the most interesting verified fact. Do not bury the hook under generic introductions.','Use concrete numbers only when present in the supplied evidence.','For technical posts, synchronize support, resistance, trigger, targets and invalidation with the verified chart/data.','Targets and stops are scenarios, never guarantees. Never state that a coin will definitely pump, moon, or 10x/20x.','If a public creator call is used, distinguish their original call from our measured follow-up and include attribution context.','A 10x/20x idea must be framed as a conditional scenario and explain the required market-cap/price conditions when data permits.','Use exactly one natural question. Avoid generic “what do you think?” unless it contains a specific choice.','Never fabricate news, sources, creator calls, prices, targets, engagement or outcomes.','Do not imitate another creator; learn only from aggregate performance patterns.'],'script_structure':'HOOK → EVENT/OBSERVATION → WHY NOW → EVIDENCE → TRADINGVIEW/LEVELS → BULL/BEAR → NEXT WATCH → ONE QUESTION','style_rotation':['newsroom','analyst','conversational','contrarian','high-energy'],'mobile_rules':['Short paragraphs','No wall of text','Put key levels on separate lines when useful','Avoid repetitive emoji patterns','Keep enough detail to be useful without filler']}
    OUT.parent.mkdir(parents=True,exist_ok=True); OUT.write_text(json.dumps(directive,indent=2,ensure_ascii=False),encoding='utf-8'); p['script_director_4']=directive; PREFLIGHT.write_text(json.dumps(p,indent=2,ensure_ascii=False),encoding='utf-8')
    print(json.dumps({'status':'OK','version':'4.2','format':fmt,'symbol':sym,'hooks':len(candidates)},indent=2))
if __name__=='__main__':main()
