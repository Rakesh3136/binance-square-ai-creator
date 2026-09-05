"""Creator 6.5 identity + anti-repetition authority.

Keeps the existing workflow entrypoint while adding stronger cooldowns,
creative fingerprints, structure/CTA rotation, learned preferences, and a
hard TradingView-only asset rule. It never invents an asset or factual claim.
"""
from __future__ import annotations
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
LOG=ROOT/'analytics/publication_log.jsonl'
RANKING=ROOT/'data/live/opportunity_ranking_6.json'
PREF=ROOT/'data/live/editorial_preflight.json'
FEEDBACK=ROOT/'data/intelligence/performance_feedback.json'
OUT=ROOT/'data/live/creator_identity_6.json'
STOP={'the','a','an','and','or','to','of','in','on','for','with','is','are','this','that','it','as','at','from','by','now','just','will','what','would','you','your'}
HOOKS=['event_first','data_first','level_first','question_first','contrarian','explanation','scenario','lesson','outcome','statement']
CTAS=['stance','confirmation','forced_choice','reasoning','trade_action','prediction','watchlist','lesson']
STRUCTURES=['event_context_impact','signal_evidence_test','level_scenarios','data_comparison','lesson_example','outcome_next_test','question_context','macro_chain','watchlist','thesis_update']

def load(p):
    try:
        x=json.loads(p.read_text(encoding='utf-8')); return x if isinstance(x,dict) else {}
    except Exception:return {}

def norm(v): return re.sub(r'[^a-z0-9$]+',' ',str(v or '').lower()).strip()

def fp(v):
    return ' '.join(x for x in norm(v).split() if x not in STOP and not re.fullmatch(r'\$?[0-9]+(?:\.[0-9]+)?%?',x))[:8]

def hook_family(v):
    s=norm(v)
    if any(x in s for x in ('breaking','announced','launch','approval','listed','just in')): return 'event_first'
    if any(x in s for x in ('volume','open interest','funding','liquidation','flow','data')): return 'data_first'
    if any(x in s for x in ('support','resistance','level','breakout','breakdown')): return 'level_first'
    if '?' in str(v or '') or any(x in s for x in ('would you','which side','bullish','bearish')): return 'question_first'
    if any(x in s for x in ('why','because','reason','means')): return 'explanation'
    if any(x in s for x in ('if ','unless','could','scenario')): return 'scenario'
    if any(x in s for x in ('lesson','learn','mistake','guide')): return 'lesson'
    if any(x in s for x in ('worked','failed','result','outcome','update')): return 'outcome'
    if any(x in s for x in ('risk','fade','trap','crowded','overextended')): return 'contrarian'
    return 'statement'

def cta_family(v):
    s=norm(v)
    if any(x in s for x in ('bullish','bearish','wait','long','short')): return 'stance'
    if any(x in s for x in ('confirm','break','hold','reclaim','reject')): return 'confirmation'
    if any(x in s for x in ('which','pick','choose')): return 'forced_choice'
    if any(x in s for x in ('why','what would','how would')): return 'reasoning'
    if any(x in s for x in ('buy','sell','entry','enter','exit')): return 'trade_action'
    if any(x in s for x in ('where','target','next level')): return 'prediction'
    if any(x in s for x in ('watch','monitor','keep an eye')): return 'watchlist'
    return 'lesson'

def symbol(c):
    raw=c.get('symbol') or ((c.get('symbols') or [''])[0])
    s=str(raw or '').upper().replace('$','').strip()
    return s[:-4] if s.endswith('USDT') else s

def history():
    if not LOG.exists(): return []
    out=[]
    for line in LOG.read_text(encoding='utf-8').splitlines()[-120:]:
        try:
            x=json.loads(line)
            if isinstance(x,dict) and x.get('status')=='PUBLISHED_AUTONOMOUSLY': out.append(x)
        except Exception: pass
    return out

def pref_bonus(feedback,cat):
    best=0.0
    for key in ('winning_categories','preferred_categories','best_categories'):
        v=feedback.get(key)
        if isinstance(v,dict):
            try: best=max(best,min(6.0,max(0.0,float(v.get(cat,0))*.2)))
            except Exception: pass
        elif isinstance(v,list) and cat in [str(x).lower() for x in v]: best=max(best,2.0)
    return round(best,2)

def main():
    ranking=load(RANKING); pref=load(PREF); feedback=load(FEEDBACK); rows=history(); recent=rows[-24:]
    syms=[str(x.get('symbol') or '').upper() for x in recent if x.get('symbol')]
    cats=[str(x.get('content_category') or '').lower() for x in recent]
    fmts=[str(x.get('format') or '').lower() for x in recent]
    hooks=[hook_family(x.get('hook')) for x in recent]; ctas=[cta_family(x.get('discussion_question')) for x in recent]
    structs=[str(x.get('structure') or '') for x in recent]
    hfp=[fp(x.get('hook')) for x in recent if fp(x.get('hook'))]; tfp=[fp(x.get('topic')) for x in recent if fp(x.get('topic'))]; qfp=[fp(x.get('discussion_question')) for x in recent if fp(x.get('discussion_question'))]
    sc=Counter(syms); cc=Counter(cats); hc=Counter(hooks); qc=Counter(ctas); stc=Counter(structs)
    old=pref.get('selected_opportunity') or {}; manual=bool(pref.get('manual_topic')) or bool(old.get('manual_topic')); protected=str(old.get('category') or '').lower() in {'creator_signal_outcome','follow_up'}
    scored=[]
    for raw in ranking.get('top_candidates') or []:
        if not isinstance(raw,dict): continue
        c=dict(raw); s=symbol(c); cat=str(c.get('lane') or c.get('category') or '').lower(); title=str(c.get('title') or c.get('news_title') or ''); base=float(c.get('ranker_score') or c.get('score') or 0); n=0.0; why=[]
        if s and sc[s]:
            p=min(32.0,12.0*sc[s])
            if title and any(k in norm(title) for k in ('breaking','hack','exploit','approval','listing','launch')): p*=.35
            n-=p; why.append(f'asset_repeat:-{round(p,2)}')
        if cat and cc[cat]: n-=min(16.0,4.0*cc[cat]); why.append(f'category_repeat:-{min(16.0,4.0*cc[cat]):g}')
        if cats and cat==cats[-1]: n-=8; why.append('consecutive_lane:-8')
        if fmts and fmts[-1]=='article' and cat in {'breaking_news','news_market_impact','news_and_macro'}: n-=6; why.append('article_rhythm_repeat:-6')
        titlefp=fp(title)
        if titlefp and titlefp in tfp: n-=14; why.append('topic_fingerprint_repeat:-14')
        if title and not s: n-=45; why.append('no_chart_asset:-45')
        if cat in {'breaking_news','news_market_impact'} and title: n+=3; why.append('fresh_event:+3')
        b=pref_bonus(feedback,cat)
        if b: n+=b; why.append(f'learned_preference:+{b}')
        c['identity_score']=round(base+n,2); c['identity_adjustments']=why; scored.append(c)
    scored.sort(key=lambda x:float(x.get('identity_score') or 0),reverse=True)
    if manual or protected: chosen=dict(old); reason='Manual topic or protected creator follow-up/outcome retained.'
    elif scored:
        chosen=dict(scored[0]); reason='Creator 6.5 selected the strongest evidence-backed opportunity after cooldowns and learned preferences.'
        if chosen.get('title') and not symbol(chosen):
            alt=next((x for x in scored[1:] if symbol(x)),None)
            if not alt: raise SystemExit('No chartable opportunity available for TradingView-only publication policy')
            chosen=dict(alt); reason+=' No-chart news candidate skipped.'
        if chosen.get('title'):
            chosen.update(category='breaking_news' if float(chosen.get('score') or 0)>=70 else 'news_and_macro',news_title=chosen.get('title'),news_url=chosen.get('url'),news_source=chosen.get('source'),news_published_at=chosen.get('published_at'),news_score=float(chosen.get('score') or 0),symbol=symbol(chosen))
        else: chosen.update(category=chosen.get('lane') or 'top_mover',symbol=symbol(chosen))
        chosen.update(reason=reason,ranker_score=float(chosen.get('ranker_score') or chosen.get('score') or 0))
    next_hook=min(HOOKS,key=lambda x:(hc[x],HOOKS.index(x))); next_cta=min(CTAS,key=lambda x:(qc[x],CTAS.index(x))); next_structure=min(STRUCTURES,key=lambda x:(stc[x],STRUCTURES.index(x)))
    rotation={'version':'6.5','window_posts':len(recent),'cooldown_assets':list(dict.fromkeys(syms[:10])),'cooldown_categories':list(dict.fromkeys(cats[-6:])),'avoid_hook_families':[x for x,_ in hc.most_common()],'avoid_cta_families':[x for x,_ in qc.most_common()],'avoid_structures':[x for x,_ in stc.most_common() if x],'avoid_formats':list(dict.fromkeys(fmts[-4:])),'avoid_exact_fingerprints':(hfp[-10:]+qfp[-10:])[-16:],'avoid_topic_fingerprints':tfp[-12:],'next_hook_family':next_hook,'next_cta_family':next_cta,'next_structure':next_structure,'rules':['Do not reuse recent opening rhythm or sentence skeleton.','Do not reuse exact or near-exact hook/CTA fingerprints.','Do not repeat ticker-plus-percentage openings unless that is genuinely the strongest verified framing.','Rotate hook, structure, CTA and format independently.','Material breaking news can override asset/category cooldown, but never evidence or integrity rules.','TradingView is the only chart source and must match the selected asset/story.','Never use BTC as an arbitrary proxy.','End with one concrete interaction question; never generic filler.']}
    instruction=(f'Creator 6.5 identity: preferred hook={next_hook}; structure={next_structure}; CTA={next_cta}. '
                 'Make the post materially different from recent posts in opening rhythm, structure and question. '
                 'Avoid recent fingerprints and ticker-plus-percentage templates. Preserve evidence and selected-story authority. '
                 'Write mobile-first: strong first two lines, one central insight, supporting evidence, one specific question. '
                 'TradingView only; chart must match the selected asset/story; never use BTC as an arbitrary proxy.')
    chosen['instruction']=instruction; chosen['identity_rotation']=rotation; pref['selected_opportunity']=chosen; pref['content_director_instruction']=instruction
    pref['creator_identity_6']={'version':'6.5','generated_at':datetime.now(timezone.utc).isoformat(),'selection_reason':reason,'rotation':rotation,'recent_history_count':len(rows),'recent_symbols':syms,'recent_categories':cats,'recent_formats':fmts,'recent_hook_families':hooks,'recent_cta_families':ctas,'recent_structures':structs}
    OUT.parent.mkdir(parents=True,exist_ok=True); OUT.write_text(json.dumps({'version':'6.5','generated_at':datetime.now(timezone.utc).isoformat(),'selected':chosen,'rotation':rotation,'top_candidates':scored[:20]},indent=2,ensure_ascii=False),encoding='utf-8'); PREF.write_text(json.dumps(pref,indent=2,ensure_ascii=False),encoding='utf-8')
    print(json.dumps({'status':'OK','version':'6.5','selected_category':chosen.get('category'),'selected_symbol':chosen.get('symbol'),'selected_news':chosen.get('news_title'),'recent_posts':len(rows),'next_hook_family':next_hook,'next_structure':next_structure,'next_cta_family':next_cta,'rotation_active':True,'tradingview_only':True},indent=2,ensure_ascii=False))

if __name__=='__main__': main()
