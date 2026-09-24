"""Deterministic editorial scorer. No external model/API dependency."""
from __future__ import annotations
import json,re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
PREFLIGHT=ROOT/'data/live/editorial_preflight.json'; CONTEXT=ROOT/'data/live/publication_context.json'; OUT=ROOT/'data/live/script_scorecard_4.json'
REPORTS=ROOT/'data/reports'
GENERIC=('fresh check','quick market check','the headline is only half the story','here is what matters','here’s what matters','this is the crypto story')
BAD=('use verified current data','generate a post','write a post','you are the editor','placeholder','insert data','fill in')
CTA=('what do you think','thoughts?','who agrees','comment below','like and follow','what are your thoughts')
def load(p):
    try:
        x=json.loads(p.read_text(encoding='utf-8')) if p.exists() else {}
        return x if isinstance(x,dict) else {}
    except Exception:return {}
def words(s):return re.findall(r"\b[\w$%.-]+\b",str(s or ''))
def symbol(ctx):return str(ctx.get('symbol') or ctx.get('selected_lane_symbol') or '').upper().replace('USDT','').replace('$','').strip()
def extract_strings(x,out=None):
    out=[] if out is None else out
    if isinstance(x,dict):
        for k,v in x.items():
            if isinstance(v,str) and len(v.strip())>=55 and k.lower() in {'script','draft','content','body','post','text','caption','article','generated_text','normalized_text','final_text'}:out.append(v.strip())
            else:extract_strings(v,out)
    elif isinstance(x,list):
        for v in x:extract_strings(v,out)
    return out
def latest_drafts():
    vals=[]
    for p in sorted(REPORTS.glob('*.json'),key=lambda p:p.stat().st_mtime,reverse=True)[:20]:
        try:vals.extend(extract_strings(json.loads(p.read_text(encoding='utf-8'))))
        except Exception:pass
    return vals
def local_draft(ctx):
    s=symbol(ctx); price=ctx.get('last_price') or ctx.get('price'); change=ctx.get('price_change_percent'); vol=ctx.get('quote_volume_usdt') or ctx.get('quote_volume'); direction=str(ctx.get('direction') or ctx.get('flow_side') or '').upper(); setup=ctx.get('trade_setup') or {}; trigger=setup.get('trigger'); invalid=setup.get('invalidation');
    parts=[f"$${s}".replace('$$','$')+" is the asset to watch from the current evidence."]
    if price is not None:parts.append(f"Price is around {price}, with the latest move at {change}% and quoted volume near {vol} USDT.")
    if direction and trigger is not None and invalid is not None:parts.append(f"The conditional {direction} case only activates at {trigger}; it is invalidated at {invalid}.")
    parts.append("The useful question is whether fresh volume and price reaction confirm the setup rather than chasing the move.")
    parts.append("What would make you confirm, reject, or wait on this setup?")
    return '\n\n'.join(parts)
def score(t):
    low=t.lower(); w=len(words(t)); q=t.count('?'); b={'attention':0,'usefulness':0,'interaction':0,'evidence':0,'originality':0,'safety':0,'story':0,'conversation':0}; hook=t.splitlines()[0] if t else ''
    b['attention']=min(22,2+(7 if 7<=len(hook.split())<=22 else 0)+(5 if any(x in low for x in ['but','because','instead','however','while','catch']) else 0)+(2 if len(t.splitlines())>=4 else 0))
    b['usefulness']=min(22,7+(6 if any(x in low for x in ['support','resistance','volume','catalyst','liquidation','target','invalidation','level','evidence','flow','reaction']) else 0)+(5 if w>=80 else 3 if w>=55 else 0)+(4 if any(x in low for x in ['watch','confirm','invalidate','retest','reaction']) else 0))
    specific=any(x in low for x in ['which','bullish or bearish','breakout or fakeout','confirm','reject','wait'])
    b['interaction']=min(18,2+(10 if q==1 else 0)+(6 if specific else 0)); b['conversation']=min(12,(6 if q==1 else 0)+(4 if specific else 0)+(2 if any(x in low for x in ['choose','which','would you']) else 0))
    b['evidence']=min(14,5+(5 if any(x in low for x in ['data','volume','price','chart','reported','source']) else 0)+(4 if re.search(r'\$?\d+(?:\.\d+)?%?',t) else 0))
    b['originality']=min(10,4+(4 if not low.startswith(('bitcoin is','the crypto market','today')) else 0)+(2 if not any(g in hook.lower() for g in GENERIC) else 0)); b['story']=min(12,3+(4 if any(x in low for x in ['because','why now','catalyst','instead','but','while']) else 0)+(3 if w>=75 else 0)+(2 if len(t.splitlines())>=5 else 0)); b['safety']=0 if any(x in low for x in ['guaranteed','risk-free','100% certain','will 10x','will 20x','easy profit','cannot lose']) else 5
    if any(x in low for x in CTA):b['conversation']=max(0,b['conversation']-6);b['interaction']=max(0,b['interaction']-5)
    return min(100,sum(b.values())),b
def complete(t,ctx):
    low=t.lower();s=symbol(ctx);r=[]
    if s and not re.search(r'\$'+re.escape(s)+r'\b',t,re.I):r.append('missing_primary_cashtag')
    if len(words(t))<55:r.append('too_short_to_be_a_finished_story')
    if len(words(t))>180:r.append('too_long_for_short_mobile_post')
    if t.count('?')!=1:r.append('must_have_exactly_one_question')
    if len(t.splitlines())<3:r.append('needs_mobile_paragraph_structure')
    if any(x in low for x in BAD):r.append('instruction_like_candidate')
    if any(x in low for x in CTA):r.append('generic_engagement_bait')
    return r
def main():
    p=load(PREFLIGHT);ctx=load(CONTEXT);ctx={**(p.get('selected_opportunity') or {}),**ctx};candidates=p.get('candidate_scripts_4') or []
    raw=[c.get('script','') if isinstance(c,dict) else str(c) for c in candidates if c]
    raw += latest_drafts()
    if not raw:raw=[local_draft(ctx)]
    seen=[];scored=[]
    for t in raw:
        t=str(t).strip()
        if not t or t in seen:continue
        seen.append(t);total,b=score(t);miss=complete(t,ctx);eligible=not miss and b['safety']>0
        if miss:total=max(0,total-25)
        scored.append({'index':len(scored),'script':t,'total':total,'breakdown':b,'completeness_failures':miss,'eligible':eligible,'word_count':len(words(t))})
    scored.sort(key=lambda x:(x['eligible'],x['total']),reverse=True);winner=next((x for x in scored if x['eligible']),None)
    result={'version':'5.8-local','format':(p.get('script_director_4') or {}).get('format',''),'story_engine':ctx.get('story_engine',''),'candidate_count':len(scored),'winner':winner,'candidates':scored,'minimum_publish_score':72,'evidence_gate':True,'external_model_required':False,'policy':['Local deterministic fallback is authoritative when no model output exists.','Reject instruction-like and generic engagement bait.','Require primary cashtag and one specific question for trade/editorial drafts.']}
    OUT.parent.mkdir(parents=True,exist_ok=True);OUT.write_text(json.dumps(result,indent=2,ensure_ascii=False),encoding='utf-8');p['script_scorecard_4']=result;PREFLIGHT.write_text(json.dumps(p,indent=2,ensure_ascii=False),encoding='utf-8');print(json.dumps({'status':'OK','version':'5.8-local','winner_score':winner['total'] if winner else 0,'candidates':len(scored),'winner_eligible':bool(winner)},indent=2))
if __name__=='__main__':main()
