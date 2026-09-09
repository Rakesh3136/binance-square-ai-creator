import json
import os
import re
from google import genai
from datetime import datetime, timezone
from pathlib import Path

MODEL = os.getenv("GEMINI_MODEL", "gemini-3.6-flash")
TOPIC = os.getenv("TOPIC", "").strip()
OUTPUT_DIR = Path("data/reports")
LIVE_SNAPSHOT = Path("data/live/market_snapshot.json")
NEWS_SNAPSHOT = Path("data/live/news_snapshot.json")
PREFLIGHT = Path("data/live/editorial_preflight.json")
CREATOR_BRAIN = Path("data/live/creator_brain_decision.json")
PUBLICATION_CONTEXT = Path("data/live/publication_context.json")
STRATEGY_MEMORY = Path("analytics/strategy_memory.json")
CREATOR_PATTERNS = Path("data/intelligence/creator_patterns.json")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

SYSTEM = r'''You are the senior editorial intelligence of an original HUMAN crypto creator on Binance Square.
Your job is not to summarize a market feed. Your job is to turn verified evidence into one memorable, useful idea that a reader would not get from a generic crypto headline.

NON-NEGOTIABLE PLATFORM PRINCIPLES:
- Binance's public CreatorPad guidance emphasizes creativity/originality, professionalism/depth, relevance, visuals/trading tools that add information, truthful evidence, and authentic engagement. It explicitly warns against repetitive, low-effort, copied, entirely AI-generated, or decorative content.
- Never imitate another creator, reuse distinctive wording, or manufacture engagement.
- Treat public platform guidance as constraints and hypotheses, never as knowledge of a hidden ranking formula.

AUTHORING STANDARD:
1. Start with a concrete observation, tension, contradiction, surprising relationship, or decision. Never start with generic ticker+percentage language unless the percentage itself is the non-obvious evidence.
2. State the strongest verified evidence early. Use 1-3 specific facts, not a data dump.
3. Explain the causal/mechanical link: FACT -> WHY IT HAPPENS / WHAT IT CHANGES -> MARKET IMPLICATION.
4. Add one genuine counterpoint, uncertainty, or failure condition. Do not pretend confidence is certainty.
5. Give the reader a practical payoff: a level, metric, comparison, test, mental model, or observable signal they can reuse.
6. End with exactly ONE story-specific question. Never generic engagement bait.
7. Every paragraph must add information. Delete repetition, filler, slogans, template transitions, and empty hype.
8. The post must remain valuable if the reader ignores the ticker; therefore the insight must be about a relationship, mechanism, anomaly, catalyst transmission, valuation/supply/liquidity behavior, or testable market condition.
9. Write like an experienced human analyst/newsroom creator: precise verbs, mixed sentence lengths, natural punctuation, occasional understated personality. Do not sound like a corporate research memo or AI checklist.
10. Prefer a sharp 450-850 character finished short post when evidence supports it. Hard maximum 900 characters.

ANTI-SLOP PHRASES TO AVOID:
"the next reaction matters", "the interesting part starts after the headline", "this is interesting", "watch what traders do", "fresh check", "quick market check", "here is what matters", "here's what matters", "the market is watching", "now watch", "bull case:", "bear case:" unless truly necessary. Avoid emoji-led generic hooks.

NEWS MODE:
Use the actual verified event as context but do not simply rewrite the headline. Add a non-obvious mechanism or implication. Attribution must be natural and supported. The news event must connect to the asset or market through supplied evidence.

TECHNICAL MODE:
The chart is evidence. Use only supplied OHLCV-derived levels/patterns. Explain why the level matters. No invented targets, stops or patterns.

COMPARISON MODE:
Explain the relationship between assets. Never treat a secondary asset as part of a catalyst unless evidence supports it.

FACTS:
Never invent prices, volumes, sources, quotes, flows, liquidations, listings, ETF activity, whale behavior, targets or outcomes. Hypotheses must be clearly conditional.

VISUALS:
A visual must add information. Prefer truthful charts/tables/data cards over decorative logos or synthetic imagery.

OUTPUT:
Return ONLY valid JSON with research, critique, draft and visual_plan. The draft.post must be finished publication copy, not instructions.'''

SCOUT_SYSTEM = r'''You are a crypto research strategist supporting a human creator. Do not write the final post yet.
Given only the supplied market, news, research and performance evidence, identify the strongest original editorial opportunities.
For each thesis, explicitly state: observation, evidence, non-obvious interpretation, mechanism/causal chain, contradiction or risk, what would confirm it, and why a reader would care.
Reject any thesis that is only "coin moved X%", a copied headline, generic bullish/bearish commentary, or unsupported speculation.
Prefer anomalies, cross-asset relationships, catalyst transmission, supply/liquidity behavior, valuation gaps, undercoverage, data-vs-narrative contradictions, follow-up accountability, or a simple reusable mental model.
Return ONLY JSON: {"theses":[...],"recommended_thesis_index":0}.'''


def load(path):
    if not path.exists(): return {}
    try:
        value=json.loads(path.read_text(encoding='utf-8'))
        return value if isinstance(value,dict) else {}
    except Exception:return {}

def normalize_object(value,fallback_key='text'):
    if isinstance(value,dict): return value
    if isinstance(value,str): return {fallback_key:value}
    return {}

def normalize_draft(value):
    draft=normalize_object(value); draft.setdefault('text',''); draft.setdefault('quality_score',0); draft.setdefault('editorial_style','normalized'); return draft

def normalize_visual(value):
    if isinstance(value,dict):
        value.setdefault('use_visual',value.get('type') not in (None,'none')); return value
    if isinstance(value,str): return {'type':value,'use_visual':value!='none'}
    return {'type':'none','use_visual':False}

def parse_json(text):
    text=text.strip()
    if text.startswith('```'):
        text=re.sub(r'^```(?:json)?\s*','',text); text=re.sub(r'\s*```$','',text)
    value=json.loads(text)
    if not isinstance(value,dict): raise RuntimeError('Gemini returned non-object JSON')
    return value

def safe_slug_value(value):
    if isinstance(value,(str,int,float)): return str(value)
    if isinstance(value,dict):
        for key in ('symbol','topic','name','title','value'):
            candidate=value.get(key)
            if isinstance(candidate,(str,int,float)) and str(candidate).strip(): return str(candidate)
    return ''

def all_market_items(market):
    items=[]
    for group in ('top_content_signals','top_gainers','top_losers','highest_volume','new_listing_market'):
        for item in market.get(group) or []:
            if isinstance(item,dict) and item.get('symbol'): items.append(item)
    return items

def find_item(market,symbol):
    target=str(symbol or '').upper().replace('USDT','')
    for item in all_market_items(market):
        candidate=str(item.get('symbol','')).upper().replace('USDT','')
        if candidate==target:return item
    return next((x for x in all_market_items(market) if x.get('candles_1h')),None)

def fmt_money(value):
    if value>=1_000_000_000:return f'${value/1_000_000_000:.1f}B'
    if value>=1_000_000:return f'${value/1_000_000:.1f}M'
    if value>=1_000:return f'${value/1_000:.0f}K'
    return f'${value:.0f}'

def local_market_fallback(live,preflight,memory):
    selected=preflight.get('selected_opportunity') or {}; item=find_item(live,selected.get('symbol'))
    if not item:return None
    symbol=str(item.get('symbol','')).upper().replace('USDT','')
    def num(key,default=0.0):
        try:return float(item.get(key) or default)
        except Exception:return default
    move=num('price_change_percent'); price=num('last_price'); volume=num('quote_volume_usdt') or num('quote_volume'); intraday=num('intraday_range_percent'); signal=num('content_signal_score')
    candles=item.get('candles_1h') or []; highs=[]; lows=[]
    for c in candles[-24:]:
        try:
            if isinstance(c,(list,tuple)) and len(c)>=4: highs.append(float(c[2])); lows.append(float(c[3]))
            elif isinstance(c,dict): highs.append(float(c.get('high'))); lows.append(float(c.get('low')))
        except Exception: pass
    resistance=max(highs) if highs else None; support=min(lows) if lows else None
    ptxt=f'${price:.8g}' if price else 'the latest verified level'; vtxt=fmt_money(volume)+' spot volume' if volume else 'live spot data'
    hook=f'${symbol} is moving, but the useful signal is whether the move changes the market structure.'
    body=f'Price is around {ptxt}, {move:+.1f}% on the current snapshot, with {vtxt}. The 1H range is {intraday:.1f}%, so the move is meaningful only if it can hold after the initial impulse.'
    if support is not None and resistance is not None: body+=f' Recent 1H extremes: ${support:.8g} to ${resistance:.8g}.'
    q=f'What would you require next on ${symbol} before treating this move as confirmed?'
    post='\n\n'.join([hook,body,f'Confirmation means buyers keep control without immediately losing the recent range; failure would be a rejection back through support. {"Attention score is %.0f."%signal if signal else ""}'.strip(),q])
    return {'research':{'summary':'Verified live-market fallback.','strongest_signal':symbol,'source_mode':'local_fallback','opportunity_score':float(selected.get('adjusted_score') or selected.get('raw_score') or 80)},'critique':{'summary':'Evidence-preserving fallback used only when Gemini is unavailable.','reason':'gemini_unavailable'},'draft':{'post':post[:880],'text':post[:880],'hook':hook,'discussion_question':q,'quality_score':86,'editorial_style':'verified_market_observation','generation_mode':'LOCAL_FALLBACK','symbol':symbol},'visual_plan':{'type':'candlestick_chart','use_visual':bool(candles),'provider':'TradingView','timeframe':'1H','data_points':[{'symbol':symbol}],'purpose':'Show the actual price range used in the post.'}}

def local_news_fallback(news):
    articles=[x for x in (news.get('articles') or []) if isinstance(x,dict) and str(x.get('title') or '').strip()]
    if not articles:return None
    article=sorted(articles,key=lambda x:(float(x.get('news_score') or 0),str(x.get('published_at') or '')),reverse=True)[0]
    title=str(article.get('title') or '').strip(); source=str(article.get('source') or '').strip(); symbols=article.get('symbols') or []; symbol=str(symbols[0] if symbols else '').upper().replace('USDT','')
    hook=(f'${symbol}: ' if symbol else '')+title
    q=f'What evidence would make this catalyst look durable rather than temporary for ${symbol}?' if symbol else 'What evidence would make this catalyst look durable rather than temporary?'
    post='\n\n'.join([hook,f'Source: {source}' if source else 'Source: verified news feed','The useful test is not the headline itself but whether the reported event changes measurable behavior already visible in the supplied data.',q])
    return {'research':{'summary':'Fresh verified headline selected from news snapshot.','source_mode':'local_news_fallback','strongest_signal':symbol or 'macro','opportunity_score':90},'critique':{'summary':'News fallback preserves supplied event and source without adding claims.'},'draft':{'post':post[:880],'text':post[:880],'hook':hook,'discussion_question':q,'quality_score':86,'editorial_style':'fallback_newsroom','generation_mode':'LOCAL_FALLBACK','symbol':symbol},'visual_plan':{'type':'news_timeline','use_visual':True,'provider':'verified_news'}}

def call_creator(client,prompt,system_instruction=SYSTEM):
    response=client.interactions.create(model=MODEL,input=prompt,system_instruction=system_instruction)
    text=(response.output_text or '').strip()
    if not text: raise RuntimeError('Gemini returned an empty response')
    return text

def main():
    live=load(LIVE_SNAPSHOT); news=load(NEWS_SNAPSHOT); preflight=load(PREFLIGHT); memory=load(STRATEGY_MEMORY); creator_patterns=load(CREATOR_PATTERNS); creator_brain=load(CREATOR_BRAIN); publication_context=load(PUBLICATION_CONTEXT); selected=preflight.get('selected_opportunity') or {}
    if os.getenv('LOCAL_FALLBACK','').lower()=='true':
        result=local_market_fallback(live,preflight,memory) or local_news_fallback(news)
        if not result: raise RuntimeError('Local fallback found neither a usable market opportunity nor a news article')
        generation_mode='LOCAL_FALLBACK'; scout={}
    else:
        key=os.getenv('GEMINI_API_KEY')
        if not key: raise RuntimeError('GEMINI_API_KEY is missing')
        client=genai.Client(api_key=key)
        engagement=preflight.get('engagement_strategy') or {}; instruction=TOPIC or selected.get('instruction') or 'Choose the strongest evidence-based opportunity across all supplied market and news lanes.'
        research_bundle=json.dumps({'creator_brain':creator_brain,'publication_context':publication_context,'preflight':preflight,'live_market':live,'news':news,'strategy_memory':memory,'creator_patterns':creator_patterns},ensure_ascii=False,indent=2)
        scout_prompt=('RESEARCH SCOUT BRIEF\n'+instruction+'\n\n'+research_bundle+'\n\nGenerate 5 materially different theses from the evidence. Rank them by information advantage, evidence strength, reader utility, non-obviousness, and visual information value. One thesis should challenge the obvious narrative; one should expose a mechanism; one should offer a reusable mental model. Return only JSON.')
        scout=parse_json(call_creator(client,scout_prompt,SCOUT_SYSTEM))
        theses=scout.get('theses') or []
        final_prompt=(
            'FINAL AUTHORING BRIEF — use the research scout below as internal editorial intelligence. Do not mention the scout or its process in the post.\n\n'
            'AUTHENTICITY REQUIREMENT: the final copy must sound like a specific human creator who has actually looked at the evidence, not like an AI summary.\n'
            'DECIDE FIRST: which thesis has the largest reader information gain? Write that one. If none has enough evidence, return a structured WAIT draft rather than generic market filler.\n'
            'QUALITY TEST BEFORE RETURNING: Can a reader point to the exact fact that supports the insight? Is there a clear why-now? Is there a non-obvious interpretation? Is the mechanism understandable? Is there a counterpoint or invalidation? Does the final question arise naturally from the story? Would the post still be meaningful if the ticker were changed? If any answer is no, rewrite.\n\n'
            'RESEARCH SCOUT:\n'+json.dumps(scout,ensure_ascii=False,indent=2)+'\n\n'
            'AUTHORITATIVE STORY DECISION:\n'+json.dumps(creator_brain,ensure_ascii=False,indent=2)+'\n\n'
            'PUBLICATION CONTRACT:\n'+json.dumps(publication_context,ensure_ascii=False,indent=2)+'\n\n'
            'EDITORIAL LANE:\n'+instruction+'\n\n'
            'ENGAGEMENT STRATEGY:\n'+json.dumps(engagement,ensure_ascii=False,indent=2)+'\n\n'
            'LIVE MARKET:\n'+json.dumps(live,ensure_ascii=False,indent=2)+'\n\nNEWS:\n'+json.dumps(news,ensure_ascii=False,indent=2)+'\n\n'
            'STRATEGY MEMORY:\n'+json.dumps(memory,ensure_ascii=False,indent=2)+'\n\n'
            'Write ONE finished Binance Square post. Preserve verified asset/headline/chart constraints. Do not copy the verified headline verbatim as the hook unless the event itself is the unique insight. Use no more than two emojis and only when natural.'
        )
        result=parse_json(call_creator(client,final_prompt,SYSTEM)); generation_mode='GEMINI_2PASS'
    research=normalize_object(result.get('research'),'summary'); critique=normalize_object(result.get('critique'),'summary'); draft=normalize_draft(result.get('draft')); visual=normalize_visual(result.get('visual_plan'))
    draft['experiment_id']=(preflight.get('engagement_strategy') or {}).get('experiment_id') or preflight.get('recommended_experiment') or 'A'
    draft['experiment_format']=((preflight.get('engagement_strategy') or {}).get('experiment') or {}).get('format')
    draft['symbol']=publication_context.get('symbol') or selected.get('symbol') or research.get('strongest_signal') or ''
    draft['content_category']=selected.get('category') or selected.get('reason') or 'market_opportunity'; draft['publication_status']='DRAFT_ONLY_NOT_PUBLISHED'; draft['generation_mode']=generation_mode
    if not draft.get('post') and draft.get('text'): draft['post']=str(draft['text']).strip()
    allowed={'candlestick_chart','market_bar_chart','market_comparison','market_range_chart','news_timeline','text_card','none'}
    if visual.get('type') not in allowed: visual={'type':'none','use_visual':False}
    report={'generated_at':datetime.now(timezone.utc).isoformat(),'model':MODEL,'topic_instruction':TOPIC or selected.get('instruction',''),'selected_editorial_lane':selected,'engagement_strategy':preflight.get('engagement_strategy') or {},'creator_intelligence':creator_patterns,'live_market_snapshot':live,'news_discovery_snapshot':news,'strategy_memory':memory,'research':research,'critique':critique,'draft':draft,'visual_plan':visual,'status':'DRAFT_ONLY_NOT_PUBLISHED','creator_brain':creator_brain,'publication_context':publication_context,'generation_mode':generation_mode,'gemini_requests_used':2 if generation_mode=='GEMINI_2PASS' else 0,'research_scout':scout}
    slug_source=TOPIC or safe_slug_value(research.get('strongest_signal')) or safe_slug_value(selected.get('category')) or 'market-opportunity'; slug=''.join(c.lower() if c.isalnum() else '-' for c in slug_source).strip('-')[:80] or 'market-opportunity'
    output=OUTPUT_DIR/f'{slug}-multi-agent.json'; output.write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding='utf-8')
    print(json.dumps({'status':'DRAFT_ONLY_NOT_PUBLISHED','report':str(output),'quality_score':draft.get('quality_score',0),'editorial_style':draft.get('editorial_style',''),'generation_mode':generation_mode,'visual_requested':visual.get('use_visual',False),'visual_type':visual.get('type','none'),'gemini_requests_used':2 if generation_mode=='GEMINI_2PASS' else 0},indent=2))
if __name__=='__main__':main()
