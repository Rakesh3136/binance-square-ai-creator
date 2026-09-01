"""Creator 4.1 story-specific writing policy.
The authoritative symbol comes from editorial preflight, preventing malformed
'$.' hooks and asset drift between content selection and publishing.
"""
import json,re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
PREFLIGHT=ROOT/'data/live/editorial_preflight.json'; OUT=ROOT/'data/live/script_director_4.json'
HOOKS={
'BREAKING NEWS + MARKET IMPACT':['🚨 The headline changed the backdrop. ${symbol} is where the market reaction gets interesting.','The news is one part of the story. ${symbol} has to confirm it on price.','⚠️ New information is hitting crypto — here is what ${symbol} is doing with it.'],
'NEWS + CHART':['The headline is only half the story. Look at ${symbol} on the chart.','${symbol} has the news. Now the chart has to confirm it.','Here is the level on ${symbol} that matters after the latest headline:'],
'TRADINGVIEW CHART CHALLENGE':['📊 Chart challenge: what happens next for ${symbol}?','${symbol} is testing a level worth watching.','The ${symbol} chart is getting interesting at this exact zone:'],
'TOP MOVERS':['🚀 ${symbol} just made a move traders cannot ignore.','${symbol} is moving fast — but the first candle is not the whole story.','Everyone can see the move on ${symbol}. The question is what comes next.'],
'DATA SURPRISE':['The number on ${symbol} that caught my attention:','Most people are watching price. I’m watching this number on ${symbol}:','🔎 One data point makes today’s ${symbol} move much more interesting:'],
'LIQUIDATION STORY':['⚠️ ${symbol} just printed a move violent enough to change the short-term setup.','That ${symbol} flush was not a normal candle.','${symbol} just forced traders to rethink the next move.'],
'NEW LISTING WATCH':['🆕 New listing watch: here is what matters on ${symbol}.','A new market is live — but the first move can be deceptive.','${symbol} is getting fresh attention. Here are the levels I’m watching.'],
'MACRO + MARKET IMPACT':['🌎 The macro headline is hitting crypto. Here is what matters for ${symbol}.','One macro development could change the tone around ${symbol}.','Before chasing ${symbol}, watch how price reacts to the macro signal.'],
'CREATOR CALL OUTCOME':['👀 A creator flagged ${symbol}. Now the market can tell us what happened.','Follow-up: the ${symbol} setup moved. Here is the measured result.','The original ${symbol} call is now testable with fresh price data.'],
'EDUCATION FROM LIVE CHART':['🧠 Quick lesson from the ${symbol} chart:','Here is a simple way to read what ${symbol} is doing right now.','A live ${symbol} chart can teach us something useful here:'],
'COIN VS COIN':['⚔️ ${a} vs ${b}: which chart looks stronger right now?','Two coins, one question: which setup has the cleaner structure?','The interesting comparison today is ${a} against ${b}.'],
'FOLLOW-UP / UPDATE':['🔄 Update on ${symbol}: the market has moved since our last look.','We flagged ${symbol}. Now the thesis needs an update.','New data changes the picture for ${symbol}. Here is what matters now.']}

def main():
 p=json.loads(PREFLIGHT.read_text(encoding='utf-8')) if PREFLIGHT.exists() else {}
 selected=p.get('selected_opportunity') or {}; director=p.get('content_director_4') or {}
 fmt=str(director.get('recommended_format') or ((p.get('engagement_strategy') or {}).get('experiment') or {}).get('format') or 'TOP MOVERS').upper()
 sym=re.sub(r'USDT$','',str(selected.get('symbol') or selected.get('topic') or director.get('primary_story',{}).get('symbol') or '').upper())
 if not re.fullmatch(r'[A-Z0-9]{2,15}',sym): raise SystemExit('Script Director: authoritative selected symbol is missing or invalid')
 templates=HOOKS.get(fmt,HOOKS['TOP MOVERS']); candidates=[x.replace('${symbol}',f'${sym}') for x in templates]
 directive={
  'version':'4.1','format':fmt,'primary_symbol':sym,'hook_candidates':candidates,
  'writing_contract':[
   'Write a complete post, not a slogan: hook → event/data → why it matters → evidence/chart → bull/bear scenario → what to watch → one question.',
   'Use the authoritative selected symbol everywhere; never produce a bare dollar sign or substitute another asset.',
   'Use short mobile-first paragraphs with enough substance to be useful.',
   'For technical posts, synchronize every quoted level with the TradingView chart.',
   'Targets, stop/invalidation and upside are conditional scenarios only; never promise profit or 10x/20x returns.',
   'Use a concrete number, level, event or observation in the opening whenever evidence supports it.',
   'Include exactly one easy question that invites a real answer.',
   'Rotate cadence, emoji usage and structure based on recent performance; never imitate another creator.',
   'If evidence is missing, omit the claim instead of filling the gap.'
  ],
  'script_structure':'HOOK → WHAT HAPPENED → WHY IT MATTERS → EVIDENCE/CHART → BULL/BEAR SCENARIO → WHAT TO WATCH → ONE QUESTION',
  'style_rotation':'Avoid generic market-recap openings and avoid repeating the immediately previous style.'
 }
 OUT.parent.mkdir(parents=True,exist_ok=True); OUT.write_text(json.dumps(directive,indent=2,ensure_ascii=False),encoding='utf-8')
 p['script_director_4']=directive; p['content_director_instruction']=str(p.get('content_director_instruction',''))+f' Script Director 4.1 is locked to ${sym}.'
 PREFLIGHT.write_text(json.dumps(p,indent=2,ensure_ascii=False),encoding='utf-8')
 print(json.dumps({'status':'OK','version':'4.1','format':fmt,'symbol':sym,'hooks':len(candidates)},indent=2))
if __name__=='__main__':main()
