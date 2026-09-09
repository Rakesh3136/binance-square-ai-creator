"""Hard publication integrity gate for Creator 5.8.

The gate may perform deterministic, evidence-preserving repairs: selected news
headline insertion, unsupported news-cashtag removal, and last-mile hook
deduplication. Market facts and numbers are never silently rewritten.
"""
from __future__ import annotations
import json,re,os
from pathlib import Path
from datetime import datetime,timezone,timedelta
ROOT=Path(__file__).resolve().parents[1]
MARKET=ROOT/'data/live/market_snapshot.json'; NEWS=ROOT/'data/live/news_snapshot.json'; PREFLIGHT=ROOT/'data/live/editorial_preflight.json'; CONTEXT=ROOT/'data/live/publication_context.json'; REPORT_DIR=ROOT/'data/reports'; OUT=ROOT/'data/live/content_integrity_gate.json'; PUBLICATIONS=ROOT/'analytics/publication_log.jsonl'
GENERIC_HOOKS={"fresh check","quick market check","the headline is only half the story","this is the crypto story i'm watching right now"}
NEWS_REQUIRED_WORDS={'source:','reported','announced','according to','news'}
MAX_HOOK_SIMILARITY=.68

def load(p,default=None):
    try:
        x=json.loads(Path(p).read_text(encoding='utf-8')); return x if isinstance(x,type(default or {})) else ({} if default is None else default)
    except Exception:return {} if default is None else default

def resolve_report():
    explicit=os.getenv('DRAFT_PATH','').strip()
    if explicit:
        p=Path(explicit)
        if not p.exists():raise SystemExit(f'DRAFT_PATH does not exist: {explicit}')
        return p
    rs=sorted(REPORT_DIR.glob('*-multi-agent.json'),key=lambda p:p.stat().st_mtime,reverse=True); return rs[0] if rs else None

def symbol_of(s):
    s=re.sub(r'USDT$','',str(s or '').upper().replace('$','').replace('BINANCE:','')).strip(); return s if re.fullmatch(r'[A-Z0-9]{1,15}',s) else ''

def find_market_item(market,symbol):
    target=symbol+'USDT'
    for group in ('top_content_signals','top_gainers','top_losers','highest_volume','new_listing_market'):
        for x in market.get(group) or []:
            if isinstance(x,dict) and str(x.get('symbol','')).upper()==target:return x
    return None

def extract_primary_move(text,symbol):
    m=re.search(r'\$'+re.escape(symbol)+r'[^\n%]{0,120}([+-]\d+(?:\.\d+)?)%',text.upper()); return float(m.group(1)) if m else None

def recent_hooks():
    hooks=[]
    if not PUBLICATIONS.exists():return hooks
    cutoff=datetime.now(timezone.utc)-timedelta(hours=36)
    for line in PUBLICATIONS.read_text(encoding='utf-8').splitlines()[-80:]:
        try:
            r=json.loads(line);dt=datetime.fromisoformat(str(r.get('published_at','')).replace('Z','+00:00'))
            if dt<cutoff:continue
            h=str(r.get('hook') or '').strip().lower()
            if h:hooks.append(re.sub(r'\s+',' ',h))
        except Exception:pass
    return hooks

def similarity(a,b):
    wa=set(re.findall(r'[a-z0-9$]+',a.lower())); wb=set(re.findall(r'[a-z0-9$]+',b.lower())); return len(wa&wb)/max(1,len(wa|wb))

def authorized_news_assets(context,selected):
    allowed={symbol_of(context.get('symbol') or selected.get('symbol'))}
    for v in context.get('headline_assets') or []:
        s=symbol_of(v)
        if s:allowed.add(s)
    return {x for x in allowed if x}

def remove_unsupported_news_cashtags(text,allowed):
    tags=sorted({m.group(1).upper() for m in re.finditer(r'\$([A-Z][A-Z0-9]{0,14})\b',text.upper()) if m.group(1).upper() not in allowed})
    if not tags:return text,[]
    cleaned=re.sub(r'\$([A-Z][A-Z0-9]{0,14})\b',lambda m:m.group(0) if m.group(1).upper() in allowed else '',text,flags=re.I)
    cleaned=re.sub(r' {2,}',' ',cleaned); cleaned=re.sub(r' +([,.!?])',r'\1',cleaned); cleaned=re.sub(r'\n[ \t]+\n','\n\n',cleaned); return cleaned.strip(),tags

def repair_missing_headline(data,draft,text,title,report):
    if not title or title.lower() in text.lower():return text,False
    lines=[line.strip() for line in text.splitlines() if line.strip()]
    if not lines:return text,False
    repaired=lines[0]+'\n\nSource: '+title+'\n\n'+'\n\n'.join(lines[1:])
    draft['post']=repaired; draft['text']=repaired; draft['news_headline_integrity_repair']={'status':'REPAIRED','headline':title,'verified_headline_inserted_verbatim':True,'body_rewritten':False,'repaired_at':datetime.now(timezone.utc).isoformat()}
    data['draft']=draft; data['news_headline_integrity_repair']=draft['news_headline_integrity_repair']
    Path(report).write_text(json.dumps(data,indent=2,ensure_ascii=False),encoding='utf-8')
    return repaired,True

def hook_quality(hook,symbol,headline):
    words=re.findall(r'\b[\w$%-]+\b',hook)
    low=hook.lower()
    if not (8<=len(words)<=24 and 45<=len(hook)<=180):return False
    if hook.endswith(('...','…',':','-')):return False
    if low in GENERIC_HOOKS:return False
    if any(x in low for x in ('what do you think','thoughts?','bullish or bearish','agree or disagree')):return False
    if headline and similarity(hook,headline)>=MAX_HOOK_SIMILARITY:return False
    if symbol and symbol.lower() not in low:return False
    return True

def deterministic_hook_repair(symbol,headline,body,recent):
    low_head=headline.lower()
    low_body=body.lower()
    candidates=[]
    if 'stablecoin' in low_head or 'stablecoin' in low_body:
        candidates += [
            f"The bigger ${symbol} signal is whether stablecoin use is becoming a real consumer behavior shift.",
            f"For ${symbol}, the key issue is the behavior shift behind this stablecoin story.",
            f"The ${symbol} angle is the consumer behavior change behind the stablecoin headline.",
        ]
    if 'wallet' in low_head or 'wallet' in low_body:
        candidates += [
            f"The ${symbol} angle is whether wallet behavior is shifting beyond the usual crypto audience.",
            f"For ${symbol}, wallet adoption matters more than repeating the headline itself.",
        ]
    candidates += [
        f"The bigger ${symbol} signal is the market behavior implied by this headline, not the headline itself.",
        f"For ${symbol}, the useful signal is the underlying behavior change behind this story.",
        f"The ${symbol} story is more about behavior than the headline that triggered the reaction.",
    ]
    for c in candidates:
        c=re.sub(r'\s+',' ',c).strip()
        if hook_quality(c,symbol,headline) and not any(similarity(c,h)>=MAX_HOOK_SIMILARITY for h in recent):
            return c
    return ''

def main():
    report=resolve_report()
    if not report:raise SystemExit('No fresh draft report')
    data=load(report); draft=data.get('draft') or {}; text=str(draft.get('post') or draft.get('text') or '').strip(); pre=load(PREFLIGHT); selected=pre.get('selected_opportunity') or {}; context=load(CONTEXT); market=load(MARKET)
    sym=symbol_of(context.get('symbol') or selected.get('symbol') or selected.get('topic') or draft.get('symbol')); failures=[]; warnings=[]; repaired=[]
    if not text:failures.append('empty_post')
    if not sym:failures.append('missing_primary_symbol')
    selected_news=bool(context.get('news_title') or selected.get('news_title'))
    allowed_assets=authorized_news_assets(context,selected) if selected_news else {sym}
    if selected_news and text:
        text,repaired=remove_unsupported_news_cashtags(text,allowed_assets)
        if repaired:
            draft['post']=text; draft['text']=text; draft['integrity_repaired_cashtags']=repaired; data['draft']=draft; data['integrity_last_mile_repair']=True; data['integrity_repaired_at']=datetime.now(timezone.utc).isoformat(); Path(report).write_text(json.dumps(data,indent=2,ensure_ascii=False),encoding='utf-8')
        title=str(context.get('news_title') or selected.get('news_title') or '').strip()
        text,headline_repaired=repair_missing_headline(data,draft,text,title,report)
        if headline_repaired:
            draft=load(report).get('draft') or draft
    if text.count('?')!=1:failures.append('question_count_must_equal_one')
    lines=[x.strip() for x in text.splitlines() if x.strip()]
    hook=lines[0] if lines else ''
    if any(g in hook.lower() for g in GENERIC_HOOKS):failures.append('generic_repetitive_hook')
    if selected_news:
        title=str(context.get('news_title') or selected.get('news_title') or '').strip()
        if title and title.lower() not in text.lower():failures.append('selected_news_headline_not_present')
        if not any(k in text.lower() for k in NEWS_REQUIRED_WORDS):warnings.append('news_source_context_not_explicit')
    cashtags={m.group(1).upper() for m in re.finditer(r'\$([A-Z][A-Z0-9]{0,14})\b',text.upper())}; foreign=sorted(x for x in cashtags if x not in allowed_assets)
    if selected_news and foreign:failures.append('foreign_cashtag_not_supported_by_story:'+','.join(foreign))
    item=find_market_item(market,sym) if sym else None
    if item and sym:
        market_move=float(item.get('price_change_percent') or 0); claimed=extract_primary_move(text,sym)
        if claimed is not None:
            delta=abs(claimed-market_move)
            if delta>5.0:failures.append('market_move_mismatch:claimed='+format(claimed,'.4g')+',snapshot='+format(market_move,'.4g')+',delta='+format(delta,'.4g'))
            elif delta>2.0:warnings.append('market_move_near_mismatch:claimed='+format(claimed,'.4g')+',snapshot='+format(market_move,'.4g'))
        if float(item.get('last_price') or 0)<=0:failures.append('invalid_authoritative_market_price')
    elif sym:failures.append('authoritative_market_item_missing')
    recent=recent_hooks(); near=[]
    if hook:
        for h in recent:
            sim=similarity(hook,h)
            if sim>=MAX_HOOK_SIMILARITY:near.append((round(sim,2),h))
    if near:
        title=str(context.get('news_title') or selected.get('news_title') or '').strip()
        body='\n'.join(lines[1:])
        replacement=deterministic_hook_repair(sym,title,body,recent)
        if replacement:
            original_hook=hook; lines[0]=replacement; text='\n\n'.join(lines)
            draft=load(report).get('draft') or draft
            draft['post']=text; draft['text']=text
            repair={'status':'REPAIRED','original_hook':original_hook,'new_hook':replacement,'previous_matches':near[:5],'max_recent_similarity':max((similarity(replacement,h) for h in recent),default=0.0),'verified_headline_preserved':bool(title and title.lower() in text.lower()) if title else True,'repaired_at':datetime.now(timezone.utc).isoformat()}
            draft['integrity_hook_repair']=repair; data['draft']=draft; data['integrity_hook_repair']=repair; Path(report).write_text(json.dumps(data,indent=2,ensure_ascii=False),encoding='utf-8')
            hook=replacement; near=[(round(similarity(hook,h),2),h) for h in recent if similarity(hook,h)>=MAX_HOOK_SIMILARITY]
    if near:
        failures.append('hook_too_similar_to_recent_post')
    if hook and any(hook==h.lower() for h in recent):failures.append('duplicate_hook')
    low_value_phrases=('move is strong enough to watch','confirmation matters more than chasing it','which signal are you watching next')
    if sum(1 for p in low_value_phrases if p in text.lower())>=2:failures.append('low_information_fallback_copy')
    result={'version':'5.8','generated_at':datetime.now(timezone.utc).isoformat(),'draft_path':str(report),'publish':not failures,'symbol':sym,'selected_news':selected_news,'authorized_news_assets':sorted(allowed_assets),'repaired_cashtags':repaired,'failures':failures,'warnings':warnings,'hook_similarity_matches':near[:5],'authoritative_price_change':float(item.get('price_change_percent') or 0) if item else None,'claimed_price_change':extract_primary_move(text,sym) if sym else None,'policy':['Only explicitly headline-supported assets may receive additional news cashtags.','Unsupported cashtags may be removed at the last mile.','Numerical/factual claims are never silently rewritten.','Never publish contradictory market figures.','News-selected posts must retain the actual headline verbatim.','One real question per post.','Repeated hooks are repaired deterministically when a safe evidence-preserving alternative exists.']}
    OUT.parent.mkdir(parents=True,exist_ok=True); OUT.write_text(json.dumps(result,indent=2,ensure_ascii=False),encoding='utf-8'); print(json.dumps(result,indent=2,ensure_ascii=False))
    if failures:raise SystemExit(1)
if __name__=='__main__':raise SystemExit(main())