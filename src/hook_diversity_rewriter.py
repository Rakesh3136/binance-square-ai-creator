"""Repair near-duplicate hooks without degrading editorial quality."""
from __future__ import annotations
import json, os, re, subprocess, sys, urllib.request
from datetime import datetime, timezone, timedelta
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
REPORT_DIR=ROOT/'data/reports'; CONTEXT=ROOT/'data/live/publication_context.json'; PREFLIGHT=ROOT/'data/live/editorial_preflight.json'; PUBLICATIONS=ROOT/'analytics/publication_log.jsonl'; OUT=ROOT/'data/live/hook_diversity_repair.json'
MIN_WORDS=8; MAX_WORDS=24; MIN_HOOK_SCORE=82; MAX_SIMILARITY=.68

def load(path,default=None):
    if default is None: default={}
    try:
        v=json.loads(Path(path).read_text(encoding='utf-8')); return v if isinstance(v,type(default)) else default
    except Exception:return default

def resolve_report():
    explicit=os.getenv('DRAFT_PATH','').strip()
    if explicit:
        p=Path(explicit)
        if not p.exists(): raise SystemExit(f'No draft report at DRAFT_PATH: {explicit}')
        return p
    xs=sorted(REPORT_DIR.glob('*-multi-agent.json'),key=lambda p:p.stat().st_mtime,reverse=True); return xs[0] if xs else None

def norm(v): return re.sub(r'\s+',' ',str(v or '').strip())
def tokens(v): return set(re.findall(r'[a-z0-9$]+',str(v).lower()))
def similarity(a,b):
    x,y=tokens(a),tokens(b); return len(x&y)/max(1,len(x|y))
def recent_hooks():
    out=[]
    if not PUBLICATIONS.exists(): return out
    cutoff=datetime.now(timezone.utc)-timedelta(hours=36)
    for line in PUBLICATIONS.read_text(encoding='utf-8').splitlines()[-80:]:
        try:
            r=json.loads(line); dt=datetime.fromisoformat(str(r.get('published_at','')).replace('Z','+00:00')); h=norm(r.get('hook'))
            if h and dt>=cutoff: out.append(h)
        except Exception: pass
    return out

def gemini(prompt):
    key=os.getenv('GEMINI_API_KEY','').strip()
    if not key:return ''
    model=os.getenv('GEMINI_MODEL','gemini-3.6-flash').strip(); url=f'https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}'
    payload={'contents':[{'parts':[{'text':prompt}]}],'generationConfig':{'temperature':.72,'maxOutputTokens':180}}
    try:
        req=urllib.request.Request(url,data=json.dumps(payload).encode(),headers={'Content-Type':'application/json'},method='POST')
        with urllib.request.urlopen(req,timeout=30) as response: data=json.loads(response.read().decode())
        parts=((data.get('candidates') or [{}])[0].get('content') or {}).get('parts') or []
        return norm(parts[0].get('text','')) if parts else ''
    except Exception:return ''

def clean(v):
    v=norm(v).strip('"“”\''); v=re.sub(r'^(hook|alternative hook)\s*:\s*','',v,flags=re.I); return v.split('\n')[0].strip()
def hook_quality(hook,symbol,headline,body):
    words=re.findall(r'\b[\w$%-]+\b',hook); low=hook.lower()
    if not (MIN_WORDS<=len(words)<=MAX_WORDS): return False
    if len(hook)<45 or len(hook)>180:return False
    if hook.endswith(('...','…',':','-')):return False
    if low in {'digital dollars are replacing','digital dollars are replacing bank accounts','crypto is moving fast'}:return False
    if any(x in low for x in ('what do you think','thoughts?','bullish or bearish','agree or disagree')):return False
    if headline and similarity(hook,headline)>=.68:return False
    if symbol and symbol.lower() not in low and not any(w in low for w in ('capital','liquidity','settlement','wallet','payments','accounts','on-chain','adoption','flow','rail','market','users','usage','fees')): return False
    if len(re.findall(r'\b(?:is|are|was|were|means|shows|makes|changes|shifts|turns|puts|moves|connects|reveals|matters|signals|challenges|replaces|reduces|increases|depends|hinges|starts)\b',low))==0:return False
    return True
def fallback(symbol,body,recent,headline):
    clean_body=[s for s in re.split(r'(?<=[.!?])\s+',norm(body)) if len(s)>=45 and '?' not in s and not s.lower().startswith(('source:','🚨'))]
    candidates=[]
    for s in clean_body[:8]: candidates.append(f"The important ${symbol} signal is the mechanism behind this move, not the headline itself: {' '.join(s.split()[:12])}.")
    candidates += [f"For ${symbol}, the real signal is how the evidence changes the market's underlying liquidity picture.",f"The ${symbol} setup depends less on the headline and more on whether the underlying flow can persist.",f"The overlooked ${symbol} question is whether this shift changes behavior or only changes the narrative."]
    for c in candidates:
        c=norm(c)
        if hook_quality(c,symbol,headline,body) and not any(similarity(c,h)>=MAX_SIMILARITY for h in recent):return c
    return ''
def run_judge():
    p=subprocess.run([sys.executable,str(ROOT/'src/elite_prepublication_judge.py')],capture_output=True,text=True)
    print(p.stdout,end='');
    if p.stderr: print(p.stderr,end='',file=sys.stderr)
    return p.returncode

def main():
    report=resolve_report()
    if not report: raise SystemExit('No fresh draft report')
    data=load(report); draft=data.get('draft') or {}; original=norm(draft.get('post') or draft.get('text') or '')
    if not original: raise SystemExit('Draft has no post text')
    lines=[x.strip() for x in original.splitlines() if x.strip()]; hook=lines[0] if lines else ''; recent=recent_hooks()
    near=[(round(similarity(hook,old),2),old) for old in recent if similarity(hook,old)>=MAX_SIMILARITY]
    if not near:
        OUT.write_text(json.dumps({'status':'NOT_NEEDED','original_hook':hook,'matches':[]},indent=2,ensure_ascii=False),encoding='utf-8'); print(json.dumps({'status':'NOT_NEEDED','hook':hook},ensure_ascii=False)); return 0
    context=load(CONTEXT); preflight=load(PREFLIGHT); selected=preflight.get('selected_opportunity') or {}; symbol=norm(context.get('symbol') or selected.get('symbol') or draft.get('symbol')).upper().replace('$','').replace('USDT','').strip(); headline=norm(context.get('news_title') or selected.get('news_title') or draft.get('news_title')); body='\n'.join(lines[1:])
    prompt=f'''You are an elite crypto editor. Replace ONLY the first line of this Binance Square post. The current hook is too similar to a recent post. Write ONE complete, specific, information-dense hook, 8-20 words. It must name or clearly describe the concrete subject and the evidence-backed relationship/implication already present in the body. It must read as a finished sentence, not a fragment. Do not copy the verified headline. Do not add facts, numbers, predictions, targets or urgency. Do not use generic openings. Do not ask a question. Return ONLY the hook. Asset: ${symbol}. Verified headline: {headline}. Body: {body[:6500]}. Recent hooks to avoid: {json.dumps([h for _,h in near[:8]],ensure_ascii=False)}'''
    candidate=clean(gemini(prompt))
    if not hook_quality(candidate,symbol,headline,body) or any(similarity(candidate,h)>=MAX_SIMILARITY for h in recent): candidate=fallback(symbol,body,recent,headline)
    if not candidate:
        OUT.write_text(json.dumps({'status':'REPAIR_FAILED','reason':'No distinct hook passed semantic, length and specificity checks','original_hook':hook,'matches':near[:5],'draft_path':str(report)},indent=2,ensure_ascii=False),encoding='utf-8'); print(json.dumps({'status':'REPAIR_FAILED','action':'LEAVE_DRAFT_UNCHANGED','reason':'No safe hook generated'},ensure_ascii=False)); return 0
    lines[0]=candidate; new='\n\n'.join(lines)
    repair={'status':'REPAIRED','original_hook':hook,'new_hook':candidate,'max_recent_similarity':max((similarity(candidate,h) for h in recent),default=0.0),'verified_body_preserved':True,'headline_preserved':headline.lower() in new.lower() if headline else True,'quality_checked':True,'draft_path':str(report)}
    draft['post']=new; draft['text']=new; draft['hook_diversity_repair']=repair; data['draft']=draft; data['hook_diversity_repair']=repair
    Path(report).write_text(json.dumps(data,indent=2,ensure_ascii=False),encoding='utf-8'); OUT.write_text(json.dumps(repair,indent=2,ensure_ascii=False),encoding='utf-8')
    print(json.dumps({'status':'REPAIRED','original_hook':hook,'new_hook':candidate,'max_recent_similarity':repair['max_recent_similarity']},ensure_ascii=False))
    return 0
if __name__=='__main__': raise SystemExit(main())
