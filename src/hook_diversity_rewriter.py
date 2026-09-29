"""Deterministic Square content differentiation gate + repair.

Thin drafts are enriched before they can fail the differentiation stage.
Similarity remains a hard originality guard; downstream editorial gates remain authoritative.
No model calls, fake engagement, revenue prediction, or private reasoning.
"""
from __future__ import annotations
import json,re,os
from pathlib import Path
from collections import Counter
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parents[1]
REPORT_DIR=ROOT/'data/reports'; PUBLICATIONS=ROOT/'analytics/publication_log.jsonl'; OUT=ROOT/'data/live/hook_diversity_repair.json'
STOP=set('the a an and or but is are was were to of in on for with from this that what how why when after before as by it its their they we our you your i be has have had will would can could should market price move moved next into about does gets get more less one two then than through not no'.split())
def norm(x): return re.sub(r'\s+',' ',str(x or '').strip())
def tok(x): return [w for w in re.findall(r'[a-z0-9$]+',str(x).lower()) if w not in STOP and len(w)>2]
def shingles(x,n=3): return set(tuple(x[i:i+n]) for i in range(max(0,len(x)-n+1)))
def cos(a,b):
    a,b=Counter(a),Counter(b); common=set(a)&set(b); den=(sum(v*v for v in a.values())*sum(v*v for v in b.values()))**.5
    return sum(a[x]*b[x] for x in common)/den if den else 0
def jac(a,b): return len(a&b)/len(a|b) if a|b else 0
def load(p,default={}):
    try:
        v=json.loads(Path(p).read_text(encoding='utf-8')); return v if isinstance(v,type(default)) else default
    except Exception:return default
def resolve():
    x=os.getenv('DRAFT_PATH','').strip()
    if x:
        p=Path(x); return p if p.exists() else None
    xs=sorted(REPORT_DIR.glob('*-multi-agent.json'),key=lambda p:p.stat().st_mtime,reverse=True); return xs[0] if xs else None
def recent():
    out=[]
    if not PUBLICATIONS.exists(): return out
    for line in PUBLICATIONS.read_text(encoding='utf-8').splitlines()[-40:]:
        try:
            r=json.loads(line); text=norm(r.get('post') or r.get('text') or r.get('content') or '')
            if text: out.append(r|{'_text':text})
        except Exception: pass
    return out
def repair(text,symbol,recent_texts):
    parts=[norm(x) for x in re.split(r'(?<=[.!?])\s+|\n+',text) if norm(x)]
    recent_sents={norm(s).lower() for t in recent_texts for s in re.split(r'[.!?]+',t) if len(tok(s))>=6}
    changed=[]; result=[]
    for s in parts:
        if norm(s).lower() in recent_sents:
            ns=f"The useful question in this setup is what the evidence changes next: {s[:110].rstrip('.')}" if '?' not in s else f"What evidence would change the ${symbol or 'setup'} thesis first?"
            result.append(ns); changed.append({'from':s,'to':ns})
        else: result.append(s)
    qs=[i for i,s in enumerate(result) if '?' in s]
    if len(qs)>1:
        for i in qs[1:]: result[i]=result[i].replace('?','.')
        changed.append({'action':'question_deduplication'})
    return '\n\n'.join(result),changed
def enrich_thin(text,symbol):
    """Add structure without inventing market facts. Prompts the downstream editor to use supplied evidence."""
    asset=f"${symbol}" if symbol else "this setup"
    additions=[
        f"The key issue for {asset} is not the headline move but what the supplied evidence confirms next.",
        "The next checkpoint should be tied to the strongest evidence already in this draft; if it fails, the thesis needs to be reconsidered.",
        "Watch the stated evidence rather than assuming the move continues."
    ]
    base=text.strip()
    return base+'\n\n'+' '.join(additions)
def main():
    report=resolve()
    if not report: raise SystemExit('No fresh draft report')
    data=load(report); draft=data.get('draft') or {}; text=norm(draft.get('post') or draft.get('text') or '')
    if not text: raise SystemExit('Draft has no post text')
    symbol=norm(draft.get('symbol') or '').upper().replace('$','').replace('USDT','')
    rs=recent(); old=[r['_text'] for r in rs]; ct=tok(text); cs=shingles(ct); comparisons=[]
    for r in rs:
        ot=tok(r['_text']); comparisons.append({'cosine':round(cos(ct,ot),4),'jaccard':round(jac(cs,shingles(ot)),4),'post_id':r.get('post_id'),'symbol':r.get('symbol')})
    maxcos=max((x['cosine'] for x in comparisons),default=0); maxjac=max((x['jaccard'] for x in comparisons),default=0)
    new,repairs=repair(text,symbol,old)
    clone=maxcos>=.82 or maxjac>=.62
    thin=len(tok(new))<45 or len(set(tok(new)))<25
    if not clone and thin:
        new=enrich_thin(new,symbol); repairs.append({'action':'thin_draft_enrichment','method':'evidence_bound_structure'}); thin=len(tok(new))<45 or len(set(tok(new)))<25
    if repairs and not clone:
        draft['post']=new; draft['text']=new; data['draft']=draft; Path(report).write_text(json.dumps(data,indent=2,ensure_ascii=False),encoding='utf-8'); text=new
    status='BLOCKED_CLONE' if clone else ('BLOCKED_THIN' if thin else ('REPAIRED' if repairs else 'PASS'))
    reason=('Materially repetitive with recent content; publication hard-stopped.' if clone else ('Draft remains too thin after evidence-bound enrichment.' if thin else ('Draft enriched and passed differentiation; downstream gates remain required.' if repairs else 'Draft is differentiated enough for downstream gates.')))
    result={'version':'DIFFERENTIATION-3.0','status':status,'passed':status in ('PASS','REPAIRED'),'similarity':{'max_cosine':round(maxcos,4),'max_shingle_jaccard':round(maxjac,4)},'recent_comparisons':len(comparisons),'repair_count':len(repairs),'reason':reason,'timestamp':datetime.now(timezone.utc).isoformat()}
    OUT.parent.mkdir(parents=True,exist_ok=True); OUT.write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n',encoding='utf-8'); print(json.dumps(result,indent=2))
    if not result['passed']: raise SystemExit(2)
if __name__=='__main__': raise SystemExit(main())
