"""Repair near-duplicate hooks without weakening the hard integrity gate.

If the finished draft's first line is too similar to a recent publication, this
module creates a materially different hook while preserving the verified body,
news headline, numbers and facts. It uses Gemini only when available; a
conservative deterministic fallback is used otherwise.
"""
from __future__ import annotations
import json, os, re, urllib.request, urllib.error
from datetime import datetime, timezone, timedelta
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
REPORT_DIR=ROOT/'data/reports'; CONTEXT=ROOT/'data/live/publication_context.json'; PREFLIGHT=ROOT/'data/live/editorial_preflight.json'; PUBLICATIONS=ROOT/'analytics/publication_log.jsonl'; OUT=ROOT/'data/live/hook_diversity_repair.json'

def load(p, default=None):
    if default is None: default={}
    try:
        x=json.loads(Path(p).read_text(encoding='utf-8')); return x if isinstance(x,type(default)) else default
    except Exception: return default

def latest_report():
    rs=sorted(REPORT_DIR.glob('*-multi-agent.json'),key=lambda p:p.stat().st_mtime,reverse=True)
    return rs[0] if rs else None

def norm(s): return re.sub(r'\s+',' ',str(s or '').strip())
def tokens(s): return set(re.findall(r'[a-z0-9$]+',str(s).lower()))
def similarity(a,b):
    a,b=tokens(a),tokens(b); return len(a&b)/max(1,len(a|b))
def recent_hooks():
    out=[]
    if not PUBLICATIONS.exists(): return out
    cutoff=datetime.now(timezone.utc)-timedelta(hours=36)
    for line in PUBLICATIONS.read_text(encoding='utf-8').splitlines()[-80:]:
        try:
            r=json.loads(line); dt=datetime.fromisoformat(str(r.get('published_at','')).replace('Z','+00:00'))
            h=norm(r.get('hook'))
            if h and dt>=cutoff: out.append(h)
        except Exception: pass
    return out

def gemini(prompt):
    key=os.getenv('GEMINI_API_KEY','').strip()
    if not key: return ''
    model=os.getenv('GEMINI_MODEL','gemini-3.6-flash').strip()
    url=f'https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}'
    payload={'contents':[{'parts':[{'text':prompt}]}],'generationConfig':{'temperature':0.85,'maxOutputTokens':180}}
    req=urllib.request.Request(url,data=json.dumps(payload).encode(),headers={'Content-Type':'application/json'},method='POST')
    try:
        with urllib.request.urlopen(req,timeout=30) as r: data=json.loads(r.read().decode())
        return norm((((data.get('candidates') or [{}])[0].get('content') or {}).get('parts') or [{}])[0].get('text','')))
    except Exception: return ''

def clean_candidate(s):
    s=norm(s).strip('"“”\'')
    s=re.sub(r'^(hook|alternative hook)\s*:\s*','',s,flags=re.I)
    return s.split('\n')[0].strip()

def fallback(symbol, body, recent):
    b=norm(body)
    clues=[]
    for sentence in re.split(r'(?<=[.!?])\s+',b):
        low=sentence.lower()
        if len(sentence)>=35 and not low.startswith(('source:','🚨')) and '?' not in sentence:
            clues.append(sentence)
    if clues:
        words=clues[0].split(); insight=' '.join(words[:18]).rstrip('.,:;')
        candidate=f"The useful signal in ${symbol} is the evidence behind the move: {insight}."
    else:
        candidate=f"For ${symbol}, the next decision matters more than repeating the latest headline."
    if any(similarity(candidate,h)>=0.68 for h in recent):
        candidate=f"A better read on ${symbol} starts with what the current evidence actually supports."
    return candidate

def main():
    report=latest_report()
    if not report: raise SystemExit('No fresh draft report')
    data=load(report); draft=data.get('draft') or {}; text=norm(draft.get('post') or draft.get('text'))
    if not text: raise SystemExit('Draft has no post text')
    lines=[x.strip() for x in str(draft.get('post') or draft.get('text')).splitlines() if x.strip()]
    hook=lines[0] if lines else ''
    recent=recent_hooks(); near=[(round(similarity(hook,h),2),h) for h in recent if similarity(hook,h)>=0.68]
    if not near:
        OUT.write_text(json.dumps({'status':'NOT_NEEDED','original_hook':hook,'matches':[]},indent=2,ensure_ascii=False),encoding='utf-8'); print(json.dumps({'status':'NOT_NEEDED','hook':hook})); return
    context=load(CONTEXT); pre=load(PREFLIGHT); selected=pre.get('selected_opportunity') or {}
    symbol=str(context.get('symbol') or selected.get('symbol') or draft.get('symbol') or '').upper().replace('$','').replace('USDT','').strip()
    headline=norm(context.get('news_title') or selected.get('news_title') or draft.get('news_title'))
    body='\n'.join(lines[1:])
    prompt=f'''You are the final hook editor for a high-quality Binance Square crypto post.
The current hook is too similar to a recent post. Replace ONLY the first line with a genuinely different semantic angle.
Primary asset: ${symbol}
Verified news headline that MUST remain elsewhere in the post verbatim: {headline}
Current body (DO NOT rewrite it):\n{body[:6500]}
Recent hooks to avoid:\n{json.dumps([h for _,h in near[:8]],ensure_ascii=False)}
Rules: use only facts already present in the supplied body/headline; do not add numbers, events, predictions, targets, sentiment claims, whale activity or urgency. Do not repeat the headline. Do not start with the ticker plus a percentage. Do not use generic hooks such as "fresh check" or "quick market check". Make the hook 12-24 words, specific to the evidence or implication in this post, and clearly different in wording and structure from every recent hook. Return ONLY the new hook, one line.'''
    candidate=clean_candidate(gemini(prompt))
    if not candidate: candidate=fallback(symbol,body,recent)
    if not candidate or any(similarity(candidate,h)>=0.68 for h in recent):
        candidate=fallback(symbol,body,recent)
    if any(similarity(candidate,h)>=0.68 for h in recent):
        OUT.write_text(json.dumps({'status':'REPAIR_FAILED','original_hook':hook,'candidate':candidate,'matches':near[:5]},indent=2,ensure_ascii=False),encoding='utf-8'); raise SystemExit('Could not produce a sufficiently distinct hook')
    lines[0]=candidate
    new_text='\n\n'.join(lines)
    draft['post']=new_text; draft['text']=new_text; draft['hook_diversity_repair']={'status':'REPAIRED','original_hook':hook,'new_hook':candidate,'max_recent_similarity':max((similarity(candidate,h) for h in recent),default=0.0),'verified_body_preserved':True,'headline_preserved':headline.lower() in new_text.lower() if headline else True}
    data['draft']=draft; data['hook_diversity_repair']=draft['hook_diversity_repair']
    Path(report).write_text(json.dumps(data,indent=2,ensure_ascii=False),encoding='utf-8')
    OUT.write_text(json.dumps({'status':'REPAIRED','original_hook':hook,'new_hook':candidate,'blocked_matches':near[:5],'max_recent_similarity':draft['hook_diversity_repair']['max_recent_similarity'],'report':str(report)},indent=2,ensure_ascii=False),encoding='utf-8')
    print(json.dumps({'status':'REPAIRED','original_hook':hook,'new_hook':candidate,'max_recent_similarity':draft['hook_diversity_repair']['max_recent_similarity']},ensure_ascii=False))

if __name__=='__main__': main()
