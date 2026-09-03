"""Creator 4.2 candidate-generation brief.
The actual model call remains in the existing creator backend; this module supplies
its richer editorial contract and candidate diversity requirements.
"""
from __future__ import annotations
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; PREFLIGHT=ROOT/'data/live/editorial_preflight.json'; NEWS=ROOT/'data/live/news_snapshot.json'

def load(p):
    try:return json.loads(p.read_text(encoding='utf-8'))
    except Exception:return {}

def main():
    p=load(PREFLIGHT); d=p.get('content_director_4') or {}; s=p.get('script_director_4') or {}; news=load(NEWS)
    fmt=d.get('recommended_format','TOP MOVERS'); sym=s.get('primary_symbol') or (d.get('primary_story') or {}).get('symbol','')
    hooks=s.get('hook_candidates') or []
    selected=p.get('selected_opportunity') or {}
    news_context=[]
    if selected.get('news_title'):
        news_context.append({'title':selected.get('news_title'),'source':selected.get('news_source'),'url':selected.get('news_url'),'published_at':selected.get('news_published_at'),'score':selected.get('news_score'),'primary':True})
    for article in (news.get('articles') or [])[:12]:
        if isinstance(article,dict):
            news_context.append({'title':article.get('title'),'source':article.get('source'),'url':article.get('url'),'published_at':article.get('published_at'),'summary':str(article.get('summary') or '')[:500],'symbols':article.get('symbols') or [],'news_score':article.get('news_score')})
    prompt={'version':'4.2','symbol':sym,'format':fmt,'selected_opportunity':selected,'fresh_news':news_context[:12],'instruction':f'''You are the senior editor of a serious but high-energy Binance Square crypto creator. Primary asset: ${sym}. Format: {fmt}.
Generate 5 genuinely different COMPLETE posts, not five rewrites of one template. Use these voices: (1) newsroom/breaking, (2) sharp technical analyst, (3) conversational trader, (4) contrarian/counterpoint, (5) concise high-energy. Make the candidates materially different in opening, information order, sentence rhythm and interaction mechanism. Do not start more than one candidate with the asset ticker or a percentage move.
If fresh_news contains a primary story, the post MUST be a real NEWS story: lead with the verified event, name the source naturally, explain why it matters now, then connect the event to price/market impact. Do NOT replace the headline with a generic "${sym} moved X%" recap. Never invent details beyond the supplied article.
Each candidate must have: a stop-scroll opening; the verified event/observation; why it matters now; concrete evidence; TradingView-based technical context when applicable; conditional bull and bear scenarios; what to watch next; exactly one natural question. Keep paragraphs mobile-first. At least two candidates must use a non-question hook such as a surprising fact, contrast, mini-story, myth-vs-data, or open loop. At least one candidate should invite a simple A/B decision. At least one should teach one concrete market-reading idea. At least one should use a concise counterpoint.
Use ONLY supplied verified evidence. Never invent a headline, source, price, volume, target, stop, creator call or outcome. If evidence for a target/SL is missing, omit it. Never promise profit or claim a coin WILL pump/moon/10x/20x. For 10x/20x discussions, make the scenario conditional and explain the required price/market-cap conditions when data is available.
If a public creator signal is supplied, clearly separate their original call from our measured outcome and attribute it; never claim we predicted their move. Do not imitate creators. Optimize for usefulness, curiosity and conversation rather than empty hype. The goal is a reader response such as a choice, disagreement, follow-up, or request for evidence—not a generic acknowledgement.
After generating the five candidates, score each on hook strength, evidence density, usefulness, originality, conversation quality, mobile readability and risk discipline. Select the strongest and rewrite it once without adding new facts.
Hook ideas (do not copy mechanically): {json.dumps(hooks,ensure_ascii=False)}''','selection_criteria':['stop-scroll strength','specificity','evidence density','usefulness','conversation quality','originality','mobile readability','scenario clarity','risk discipline','format diversity','news fidelity']}
    p['candidate_generation_4']=prompt; PREFLIGHT.write_text(json.dumps(p,indent=2,ensure_ascii=False),encoding='utf-8'); print(json.dumps({'status':'OK','version':'4.2','format':fmt,'symbol':sym,'candidate_count':5,'news_candidates':len(news_context)},indent=2))
if __name__=='__main__':main()
