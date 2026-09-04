"""Creator 6.1 candidate-generation brief.
The model receives the market-wide story decision and must write materially
 different finished posts without overriding the selected story or asset.
"""
from __future__ import annotations
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; PREFLIGHT=ROOT/'data/live/editorial_preflight.json'; NEWS=ROOT/'data/live/news_snapshot.json'; CONTEXT=ROOT/'data/live/publication_context.json'
def load(p):
    try:
        x=json.loads(p.read_text(encoding='utf-8')); return x if isinstance(x,dict) else {}
    except Exception:return {}
def main():
    p=load(PREFLIGHT); d=p.get('content_director_4') or {}; s=p.get('script_director_4') or {}; news=load(NEWS); ctx=load(CONTEXT)
    fmt=str(d.get('recommended_format') or 'TOP MOVERS'); sym=str(ctx.get('symbol') or s.get('primary_symbol') or (d.get('primary_story') or {}).get('symbol','')).upper().replace('USDT','').replace('$','').strip(); selected=p.get('selected_opportunity') or {}; story=d.get('primary_story') or {}; narrative=str(d.get('narrative_engine') or s.get('narrative_engine') or 'what_to_watch'); archetype=str(s.get('creator_archetype') or 'conversational'); hooks=s.get('hook_candidates') or []
    if not sym: raise SystemExit('Candidate generation: authoritative asset missing')
    news_context=[]
    for article in (news.get('articles') or [])[:12]:
        if isinstance(article,dict): news_context.append({'title':article.get('title'),'source':article.get('source'),'url':article.get('url'),'published_at':article.get('published_at'),'summary':str(article.get('summary') or '')[:500],'symbols':article.get('symbols') or [],'news_score':article.get('news_score')})
    primary_news=bool(selected.get('news_title') or ctx.get('news_title'))
    prompt={'version':'6.1','symbol':sym,'format':fmt,'narrative_engine':narrative,'creator_archetype':archetype,'authoritative_context':ctx,'primary_story':story,'selected_opportunity':selected,'fresh_news':news_context[:12],'instruction':f'''You are the senior editor of a serious, high-energy Binance Square crypto creator covering the WHOLE crypto market. The executive director has already selected the single story and frozen the primary asset ${sym}. Your job is to create five materially different finished posts about THAT story. Never substitute another asset, invent a new story, or turn the post into a generic market recap.

SELECTED FORMAT: {fmt}
NARRATIVE ENGINE: {narrative}
CREATOR ARCHETYPE: {archetype}
PRIMARY NEWS STORY PRESENT: {str(primary_news).lower()}

Generate 5 complete candidates. Make them materially different in opening, information order, rhythm, angle and interaction mechanism. Candidate roles: (1) strongest selected format, (2) evidence/data angle, (3) conversational trader angle, (4) counterpoint/risk angle, (5) concise high-energy angle. Do not merely rewrite the same post five times. Do not start more than one candidate with the ticker or a percentage move.

If PRIMARY NEWS STORY PRESENT is true, this is a NEWS STORY: state the verified event and source naturally, explain why it matters now, then connect it to the supplied market evidence. Do not replace it with a price-only recap. If it is false, do NOT manufacture a news angle; stay faithful to the selected technical, mover, macro, education, comparison, listing, outcome or follow-up story.

Use the selected format as the dominant structure. For technical/chart stories, make TradingView evidence central. For movers, explain what makes the move notable and what would confirm/fail it. For volume/data stories, connect measurements rather than listing numbers. For macro, explain the transmission path into crypto. For comparison, give both assets a legitimate case. For education, teach one reusable principle from the supplied live evidence. For creator-call outcomes, separate the original public call from our measured result and never rewrite history. For follow-ups, clearly state what changed since the prior thesis.

Every candidate must be a finished Binance Square post, never an outline, prompt, briefing or placeholder. It must contain concrete supplied evidence, a clear why-now angle, interpretation, what-to-watch next, and exactly ONE question at the end. The question must be specific and low-friction: A/B, bullish/bearish/wait, breakout/fakeout, chase/pullback/wait, agree/disagree, or a precise evidence question. Never use generic 'What do you think?', 'Thoughts?', 'Comment below', 'Like and follow', or empty engagement bait.

At least two candidates must use non-question hooks such as a surprising fact, contrast, mini-story, myth-vs-data or open loop. At least one must use an A/B decision. At least one must teach or explain a reusable idea. At least one must present a legitimate counterpoint.

Use ONLY supplied verified evidence. Never invent prices, volume, sources, headlines, targets, stops, creator calls, outcomes, liquidations, whale activity, listings, ETF flows or macro facts. If evidence for a target/SL is missing, omit it. 10x/20x language is conditional only and must not imply guaranteed returns. Never promise profit, certainty or virality.

Use short mobile-first paragraphs and varied sentence rhythm. Use at most two emojis and only if they genuinely help. Avoid repetitive 'fresh check', 'quick market check', 'the next reaction matters' and ticker-plus-percentage openings. Do not force bull/bear blocks unless the selected story benefits from scenarios.

After the five candidates, score each on stop-scroll strength, evidence density, usefulness, originality, conversation quality, mobile readability, format fidelity and risk discipline. Select the strongest candidate and rewrite it once WITHOUT adding any new fact.''','selection_criteria':['story fidelity','stop-scroll strength','specificity','evidence density','usefulness','conversation quality','originality','mobile readability','scenario clarity','risk discipline','format fidelity','news fidelity','finished-post completeness'],'hook_candidates':hooks}
    p['candidate_generation_4']=prompt; PREFLIGHT.write_text(json.dumps(p,indent=2,ensure_ascii=False),encoding='utf-8'); print(json.dumps({'status':'OK','version':'6.1','format':fmt,'symbol':sym,'narrative_engine':narrative,'creator_archetype':archetype,'candidate_count':5,'primary_news':primary_news},indent=2))
if __name__=='__main__':main()
