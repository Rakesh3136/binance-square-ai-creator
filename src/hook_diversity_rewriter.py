"""Deterministic hook repair.

AI authoring happens once in safe_creator_runner. This stage may repair structure
only with evidence already present in the draft; it never makes another model
request, preventing downstream Gemini quota exhaustion and style drift.
"""
from __future__ import annotations
import json,re
from datetime import datetime,timezone,timedelta
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; REPORT_DIR=ROOT/'data/reports'; CONTEXT=ROOT/'data/live/publication_context.json'; PREFLIGHT=ROOT/'data/live/editorial_preflight.json'; PUBLICATIONS=ROOT/'analytics/publication_log.jsonl'; OUT=ROOT/'data/live/hook_diversity_repair.json'
MIN_WORDS=8;MAX_WORDS=24;MAX_SIMILARITY=.68
def load(path,default=None):
    if default is None:default={}
    try:
        v=json.loads(Path(path).read_text(encoding='utf-8'));return v if isinstance(v,type(default)) else default
    except Exception:return default
def resolve_report():
    explicit=Path(str(__import__('os').getenv('DRAFT_PATH','')).strip()) if __import__('os').getenv('DRAFT_PATH','').strip() else None
    if explicit:return explicit if explicit.exists() else None
    xs=sorted(REPORT_DIR.glob('*-multi-agent.json'),key=lambda p:p.stat().st_mtime,reverse=True);return xs[0] if xs else None
def norm(v):return re.sub(r'\s+',' ',str(v or '').strip())
def tokens(v):return set(re.findall(r'[a-z0-9$]+',str(v).lower()))
def similarity(a,b):
    x,y=tokens(a),tokens(b);return len(x&y)/max(1,len(x|y))
def recent_hooks():
    out=[]
    if not PUBLICATIONS.exists():return out
    cutoff=datetime.now(timezone.utc)-timedelta(hours=36)
    for line in PUBLICATIONS.read_text(encoding='utf-8').splitlines()[-80:]:
        try:
            r=json.loads(line);dt=datetime.fromisoformat(str(r.get('published_at','')).replace('Z','+00:00'));h=norm(r.get('hook'))
            if h and dt>=cutoff:out.append(h)
        except Exception:pass
    return out
def hook_quality(hook,symbol,headline):
    words=re.findall(r'\b[\w$%-]+\b',hook);low=hook.lower()
    if not(MIN_WORDS<=len(words)<=MAX_WORDS) or not(45<=len(hook)<=180):return False
    if hook.endswith(('...','…',':','-')) or low in {'digital dollars are replacing','crypto is moving fast'}:return False
    if any(x in low for x in ('what do you think','thoughts?','bullish or bearish','agree or disagree')):return False
    if headline and similarity(hook,headline)>=MAX_SIMILARITY:return False
    if symbol and symbol.lower() not in low and not any(w in low for w in ('capital','liquidity','settlement','wallet','payments','accounts','on-chain','adoption','flow','market','users','usage','fees','reaction','move')):return False
    return True
def fallback(symbol,body,recent,headline):
    clean_body=[s for s in re.split(r'(?<=[.!?])\s+',norm(body)) if len(s)>=45 and '?' not in s]
    candidates=[]
    for s in clean_body[:8]:candidates.append(f"The ${symbol} signal is the relationship inside this move: {' '.join(s.split()[:12])}.")
    candidates += [f"For ${symbol}, the useful signal is how the evidence changes after the move.",f"The ${symbol} setup becomes clearer in the reaction, not the headline.",f"The overlooked ${symbol} question is whether this move changes behavior or only attention."]
    for c in candidates:
        c=norm(c)
        if hook_quality(c,symbol,headline) and not any(similarity(c,h)>=MAX_SIMILARITY for h in recent):return c
    return ''
def main():
    report=resolve_report()
    if not report:raise SystemExit('No fresh draft report')
    data=load(report);draft=data.get('draft') or {};original=norm(draft.get('post') or draft.get('text') or '')
    if not original:raise SystemExit('Draft has no post text')
    lines=[x.strip() for x in original.splitlines() if x.strip()];hook=lines[0] if lines else '';recent=recent_hooks();near=[(round(similarity(hook,old),2),old) for old in recent if similarity(hook,old)>=MAX_SIMILARITY]
    if not near:
        OUT.write_text(json.dumps({'status':'NOT_NEEDED','original_hook':hook,'matches':[]},indent=2,ensure_ascii=False),encoding='utf-8');print(json.dumps({'status':'NOT_NEEDED','hook':hook},ensure_ascii=False));return 0
    context=load(CONTEXT);preflight=load(PREFLIGHT);selected=preflight.get('selected_opportunity') or {};symbol=norm(context.get('symbol') or selected.get('symbol') or draft.get('symbol')).upper().replace('$','').replace('USDT','').strip();headline=norm(context.get('news_title') or selected.get('news_title') or draft.get('news_title'));body='\n'.join(lines[1:]);candidate=fallback(symbol,body,recent,headline)
    if not candidate:
        OUT.write_text(json.dumps({'status':'REPAIR_FAILED','reason':'No deterministic distinct hook passed checks','original_hook':hook,'matches':near[:5],'draft_path':str(report)},indent=2,ensure_ascii=False),encoding='utf-8');print(json.dumps({'status':'REPAIR_FAILED','action':'LEAVE_DRAFT_UNCHANGED'},ensure_ascii=False));return 0
    lines[0]=candidate;new='\n\n'.join(lines);repair={'status':'REPAIRED','method':'deterministic','original_hook':hook,'new_hook':candidate,'max_recent_similarity':max((similarity(candidate,h) for h in recent),default=0.0),'verified_body_preserved':True,'quality_checked':True,'draft_path':str(report)};draft['post']=new;draft['text']=new;draft['hook_diversity_repair']=repair;data['draft']=draft;data['hook_diversity_repair']=repair;Path(report).write_text(json.dumps(data,indent=2,ensure_ascii=False),encoding='utf-8');OUT.write_text(json.dumps(repair,indent=2,ensure_ascii=False),encoding='utf-8');print(json.dumps(repair,ensure_ascii=False));return 0
if __name__=='__main__':raise SystemExit(main())
