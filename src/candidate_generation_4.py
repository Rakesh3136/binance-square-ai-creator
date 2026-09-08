"""Creator 6.2 candidate-generation brief with Superhuman Creator Core."""
from __future__ import annotations
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; PREFLIGHT=ROOT/'data/live/editorial_preflight.json'; NEWS=ROOT/'data/live/news_snapshot.json'; CONTEXT=ROOT/'data/live/publication_context.json'; CORE=ROOT/'data/live/superhuman_creator_core.json'
def load(p):
    try:
        x=json.loads(p.read_text(encoding='utf-8')); return x if isinstance(x,dict) else {}
    except Exception:return {}
def main():
    p=load(PREFLIGHT); d=p.get('content_director_4') or {}; s=p.get('script_director_4') or {}; news=load(NEWS); ctx=load(CONTEXT); core=load(CORE)
    fmt=str(d.get('recommended_format') or 'TOP MOVERS'); sym=str(ctx.get('symbol') or s.get('primary_symbol') or (d.get('primary_story') or {}).get('symbol','')).upper().replace('USDT','').replace('$','').strip(); selected=p.get('selected_opportunity') or {}; story=d.get('primary_story') or {}; narrative=str(d.get('narrative_engine') or s.get('narrative_engine') or 'what_to_watch'); archetype=str(s.get('creator_archetype') or 'conversational'); hooks=s.get('hook_candidates') or []
    if not sym: raise SystemExit('Candidate generation: authoritative asset missing')
    news_context=[]
    for article in (news.get('articles') or [])[:12]:
        if isinstance(article,dict): news_context.append({'title':article.get('title'),'source':article.get('source'),'url':article.get('url'),'published_at':article.get('published_at'),'summary':str(article.get('summary') or '')[:500],'symbols':article.get('symbols') or [],'news_score':article.get('news_score')})
    primary_news=bool(selected.get('news_title') or ctx.get('news_title'))
    directives='\n'.join('- '+str(x) for x in (core.get('generation_directives') or []))
    redteam='\n'.join('- '+str(x) for x in (core.get('red_team_questions') or []))
    standard=json.dumps(core.get('minimum_publish_standard') or {},ensure_ascii=False)
    prompt={'version':'6.2','superhuman_core_version':core.get('version','1.0'),'symbol':sym,'format':fmt,'narrative_engine':narrative,'creator_archetype':archetype,'authoritative_context':ctx,'primary_story':story,'selected_opportunity':selected,'fresh_news':news_context[:12],'instruction':f'''You are the senior editor of a world-class, high-energy Binance Square crypto creator. The executive director has selected the single story and frozen the primary asset ${sym}. You must create exceptional reader value, not merely complete a publishing task.

SUPERHUMAN CREATOR CORE DIRECTIVES:\n{directives}\n
RED-TEAM BEFORE SELECTION:\n{redteam}\n
MINIMUM TARGET STANDARD: {standard}

Create 5 genuinely different finished candidates about THAT story. Roles: strongest selected format; evidence/data angle; conversational trader angle; counterpoint/risk angle; concise high-energy angle. Do not average them into generic prose. Select the strongest candidate, then rewrite it once for clarity and impact without adding facts.

SELECTED FORMAT: {fmt}
NARRATIVE ENGINE: {narrative}
CREATOR ARCHETYPE: {archetype}
PRIMARY NEWS STORY PRESENT: {str(primary_news).lower()}

If news is present, state the verified event and source naturally, explain why it matters now, then connect it to supplied market evidence. If news is absent, never manufacture a news angle. Stay faithful to the selected technical, mover, macro, education, comparison, listing, outcome or follow-up story.

Every candidate must be a complete mobile-first Binance Square post with concrete supplied evidence, a clear why-now thesis, interpretation, what-to-watch next, and exactly ONE specific question at the end. Never use generic engagement bait. At least two candidates must use non-question hooks; at least one A/B decision; at least one reusable educational insight; at least one legitimate counterpoint.

Use ONLY supplied verified evidence. Never invent prices, volume, sources, headlines, targets, stops, whale activity, liquidations, listings, ETF flows, macro facts, creator calls or outcomes. Conditional upside language must never imply guaranteed returns. Avoid generic ticker-plus-percentage openings, filler, excessive emojis and repetitive AI phrasing. A post that could be written about almost any coin is a failure.

Before selecting the winner, aggressively red-team all five. Reject anything obvious, generic, unsupported, templated, repetitive, low-value or dependent on fake urgency. The final winner should teach the reader something, reveal a useful implication, or frame a decision better than a basic market recap.''','selection_criteria':['stop_scroll_strength','evidence_density','specificity','reader_value','originality','why_now clarity','usefulness','conversation_quality','mobile_readability','format_fidelity','risk_discipline','anti_genericity','anti_ai_templating'] ,'hook_candidates':hooks}
    p['candidate_generation_4']=prompt; PREFLIGHT.write_text(json.dumps(p,indent=2,ensure_ascii=False),encoding='utf-8'); print(json.dumps({'status':'OK','version':'6.2','superhuman_core':'1.0','format':fmt,'symbol':sym,'candidate_count':5,'primary_news':primary_news},indent=2))
if __name__=='__main__':main()
