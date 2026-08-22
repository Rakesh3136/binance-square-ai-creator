import json
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from google import genai

MODEL=os.getenv("GEMINI_MODEL","gemini-3.6-flash"); TOPIC=os.getenv("TOPIC","").strip()
OUTPUT_DIR=Path("data/reports"); LIVE_SNAPSHOT=Path("data/live/market_snapshot.json"); NEWS_SNAPSHOT=Path("data/live/news_snapshot.json"); PREFLIGHT=Path("data/live/editorial_preflight.json"); STRATEGY_MEMORY=Path("analytics/strategy_memory.json"); CREATOR_PATTERNS=Path("data/intelligence/creator_patterns.json")
OUTPUT_DIR.mkdir(parents=True,exist_ok=True)
SYSTEM=r'''You are the senior editorial intelligence of an original HUMAN crypto creator on Binance Square.
Use public creator research only as pattern intelligence. Never copy another creator's sentences, distinctive phrasing, identity, branding or posts. Do not claim to know Binance's hidden recommendation algorithm. Treat observed patterns as hypotheses and validate them against our own performance.

GOAL: maximize genuine attention, useful interaction, follower growth and eligible monetization opportunities without spam, fake engagement, fabricated facts or guaranteed returns.

CREATOR-INTELLIGENCE RULES
- Study multiple archetypes: news flash, technical/chart, data/on-chain, educational, community/opinion, macro and movers.
- Prefer patterns supported by multiple examples over one viral outlier.
- Optimize for replies and follower conversion, not views alone.
- Use creator research to choose hook, format, length, question style and visual approach; keep the actual post original.
- If our own performance data contradicts a public pattern, prefer our evidence.

VISUAL-FIRST
For a single-asset market story, prefer a REAL Binance 1h candlestick chart. It is part of the hook, not decoration. Use only real OHLCV-derived support/resistance, breakout/breakdown, retest, volume, EMA or verified patterns. Never invent a pattern or level and never ask an image model to draw fake candles.

WRITING
- Normal target: 180-500 characters; hard maximum 750 unless genuinely necessary for breaking news.
- First line must create curiosity before explaining numbers.
- 2-5 short mobile-friendly lines. One main idea.
- Sound conversational, not like a financial report.
- Avoid filler such as "notable factor", "clear shift", "overhead liquidity", "market participants", "key takeaway", "this suggests".
- Do not automatically provide TP/SL/entry calls.
- For technical content use levels-to-watch, confirmation and invalidation only when supported by real candles.

INTERACTION
End with exactly ONE low-friction question. It must be answerable in under five seconds. Good examples: "Breakout or fakeout?", "Would you wait for the retest?", "Which one wins: A or B?", "Bullish continuation or pullback first?" Avoid generic "What do you think?" and never beg for likes/follows.

MONETIZATION
When a tradeable asset is discussed, naturally include its relevant $CASHTAG. Prefer a real chart widget downstream when available. Never promise earnings or returns.

FACTS
Never invent prices, volume, OHLC, news, quotes, listing dates, CPI/Fed statements, sources or URLs. Separate observation from inference.

QUALITY GATE
Rewrite anything repetitive, generic, overlong, unsupported, overly signal-like, or lacking a useful visual for a single-coin technical story.

Return ONLY valid JSON with research, critique, draft and visual_plan fields. visual_plan.type must be one of candlestick_chart, market_bar_chart, market_comparison, market_range_chart, news_timeline, text_card, none.'''

def call_creator(client,prompt):
    for attempt in range(2):
        try:
            r=client.interactions.create(model=MODEL,input=prompt,system_instruction=SYSTEM); text=(r.output_text or '').strip()
            if not text: raise RuntimeError('Gemini returned an empty response')
            return text
        except Exception as exc:
            if '429' not in str(exc) or attempt==1: raise
            print('Gemini rate limit reached; waiting 25s...'); time.sleep(25)
    raise RuntimeError('Gemini request failed')

def load(path):
    if not path.exists(): return {}
    return json.loads(path.read_text(encoding='utf-8'))

def parse_json(text):
    text=text.strip()
    if text.startswith('```'):
        text=re.sub(r'^```(?:json)?\s*','',text); text=re.sub(r'\s*```$','',text)
    value=json.loads(text)
    if not isinstance(value,dict): raise RuntimeError('Gemini returned non-object JSON')
    return value

def main():
    key=os.getenv('GEMINI_API_KEY')
    if not key: raise RuntimeError('GEMINI_API_KEY is missing')
    client=genai.Client(api_key=key)
    live=load(LIVE_SNAPSHOT); news=load(NEWS_SNAPSHOT); preflight=load(PREFLIGHT); memory=load(STRATEGY_MEMORY); creator_patterns=load(CREATOR_PATTERNS)
    selected=preflight.get('selected_opportunity') or {}; engagement=preflight.get('engagement_strategy') or {}; instruction=TOPIC or selected.get('instruction') or 'Choose the strongest evidence-based opportunity across all supplied market and news lanes.'
    prompt=("EDITORIAL LANE:\n"+instruction+"\n\nOUR ENGAGEMENT STRATEGY:\n"+json.dumps(engagement,ensure_ascii=False,indent=2)+"\n\nPUBLIC CREATOR PATTERNS (use only as hypotheses):\n"+json.dumps(creator_patterns,ensure_ascii=False,indent=2)+"\n\nPREFLIGHT:\n"+json.dumps(preflight,ensure_ascii=False,indent=2)+"\n\nLIVE MARKET:\n"+json.dumps(live,ensure_ascii=False,indent=2)+"\n\nNEWS:\n"+json.dumps(news,ensure_ascii=False,indent=2)+"\n\nOUR STRATEGY MEMORY:\n"+json.dumps(memory,ensure_ascii=False,indent=2)+"\n\nCreate ONE original short visual-first post. Public creator patterns must influence structure only, never wording or identity.")
    result=parse_json(call_creator(client,prompt)); research=result.get('research') or {}; critique=result.get('critique') or {}; draft=result.get('draft') or {}; visual=result.get('visual_plan') or {}
    draft['publication_status']='DRAFT_ONLY_NOT_PUBLISHED'; allowed={'candlestick_chart','market_bar_chart','market_comparison','market_range_chart','news_timeline','text_card','none'}
    if visual.get('type') not in allowed: visual['type']='none'
    report={'generated_at':datetime.now(timezone.utc).isoformat(),'model':MODEL,'topic_instruction':instruction,'selected_editorial_lane':selected,'engagement_strategy':engagement,'creator_intelligence':creator_patterns,'live_market_snapshot':live,'news_discovery_snapshot':news,'strategy_memory':memory,'research':research,'critique':critique,'draft':draft,'visual_plan':visual,'status':'DRAFT_ONLY_NOT_PUBLISHED','gemini_requests_used':1}
    slug=''.join(c.lower() if c.isalnum() else '-' for c in str(TOPIC or research.get('strongest_signal') or selected.get('category') or 'market-opportunity')).strip('-')[:80] or 'market-opportunity'
    output=OUTPUT_DIR/f'{slug}-multi-agent.json'; output.write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding='utf-8')
    print(json.dumps({'status':'DRAFT_ONLY_NOT_PUBLISHED','report':str(output),'quality_score':draft.get('quality_score',0),'editorial_style':draft.get('editorial_style',''),'visual_requested':visual.get('use_visual',False),'visual_type':visual.get('type','none'),'creator_intelligence_samples':creator_patterns.get('sample_count',0)},indent=2))

if __name__=='__main__': main()
