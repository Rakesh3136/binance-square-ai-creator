"""Creator 4.0 story-specific writing policy.
Produces candidate hooks and a structured brief consumed by the existing Gemini writer.
"""
import json,re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
PREFLIGHT=ROOT/'data/live/editorial_preflight.json'; OUT=ROOT/'data/live/script_director_4.json'
HOOKS={
'BREAKING NEWS + MARKET IMPACT':['🚨 This just changed the setup for ${symbol}.','The headline is important. The market reaction is more interesting.','Crypto traders are watching ${symbol} for one reason right now:'],
'NEWS + CHART':['The headline is only half the story. Look at ${symbol} on the chart.','${symbol} has the news. Now the chart has to confirm it.','Here is the level on ${symbol} that matters after today’s headline:'],
'TRADINGVIEW CHART CHALLENGE':['📊 Chart challenge: what happens next for ${symbol}?','${symbol} is testing a level worth watching.','The ${symbol} chart is getting interesting at this exact zone:'],
'TOP MOVERS':['🚀 ${symbol} just made a move traders cannot ignore.','${symbol} is moving fast — but the first candle is not the whole story.','Everyone can see the pump on ${symbol}. The question is what comes next.'],
'DATA SURPRISE':['The number on ${symbol} that caught my attention:','One data point makes today’s ${symbol} move more interesting:','Most people are watching price. I’m watching this number on ${symbol}:'],
'LIQUIDATION STORY':['⚠️ ${symbol} just experienced a move violent enough to change the short-term setup.','That ${symbol} flush was not a normal candle.','${symbol} just forced traders to rethink the next move.'],
'NEW LISTING WATCH':['🆕 New listing watch: here is what matters on ${symbol}.','A new market is live — but the first move can be deceptive.','${symbol} is getting fresh attention. Here are the levels I’m watching.'],
'MACRO + MARKET IMPACT':['🌎 The macro headline is hitting crypto. Here is what matters next.','One macro development could change the tone across crypto today.','Before chasing the move, watch how crypto reacts to this macro signal.'],
'CREATOR CALL OUTCOME':['👀 Remember this ${symbol} call? Let’s check what actually happened.','Follow-up: the ${symbol} setup moved. Here is the result.','A creator flagged ${symbol}. Now we can judge the call with actual price data.'],
'EDUCATION FROM LIVE CHART':['🧠 Quick lesson from the ${symbol} chart:','Here is a simple way to read what ${symbol} is doing right now.','A live ${symbol} chart can teach us something useful here:'],
'COIN VS COIN':['⚔️ ${a} vs ${b}: which chart looks stronger right now?','Two coins, one question: which setup has the cleaner structure?','The interesting comparison today is ${a} against ${b}.'],
'FOLLOW-UP / UPDATE':['🔄 Update on ${symbol}: the market has moved since our last look.','We flagged ${symbol}. Now the thesis needs an update.','New data changes the picture for ${symbol}. Here is what matters now.']}

def main():
 p=json.loads(PREFLIGHT.read_text(encoding='utf-8')) if PREFLIGHT.exists() else {}
 brief=p.get('content_director_4') or {}; fmt=brief.get('recommended_format','TOP MOVERS'); story=brief.get('primary_story') or {}; sym=str(story.get('symbol') or '').upper(); sym=re.sub(r'USDT$','',sym)
 templates=HOOKS.get(fmt,HOOKS['TOP MOVERS'])
 candidates=[x.replace('${symbol}',f'${sym}') for x in templates]
 directive={
  'version':'4.0','format':fmt,'primary_symbol':sym,'hook_candidates':candidates,
  'writing_contract':['Choose the strongest hook, not the safest hook.','Explain the concrete event/data before giving interpretation.','Use short mobile-first paragraphs, but allow enough room for substance.','For technical posts, synchronize every quoted level with the TradingView chart.','Use conditional language for targets/upside; never promise profit or a 10x/20x outcome.','Include exactly one easy question that invites a real answer.','Do not beg for follows/likes and do not manufacture urgency.','Do not copy other creators; learn only from broad structural patterns.','If a fact cannot be verified from supplied data, omit it.'],
  'script_structure':'HOOK → WHAT HAPPENED → WHY IT MATTERS → EVIDENCE/CHART → WHAT TO WATCH → ONE QUESTION',
  'style_rotation':'Prefer a different opening and structure from the recent post. Avoid generic market-recap language.'}
 OUT.parent.mkdir(parents=True,exist_ok=True); OUT.write_text(json.dumps(directive,indent=2,ensure_ascii=False),encoding='utf-8')
 p['script_director_4']=directive; p['content_director_instruction']=str(p.get('content_director_instruction',''))+' Writer 4.0 must use script_director_4.json and select the strongest hook candidate.'
 PREFLIGHT.write_text(json.dumps(p,indent=2,ensure_ascii=False),encoding='utf-8')
 print(json.dumps({'status':'OK','format':fmt,'symbol':sym,'hooks':len(candidates)},indent=2))
if __name__=='__main__': main()
