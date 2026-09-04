"""Creator 5.7 candidate scorer: attention, usefulness and conversation quality."""
from __future__ import annotations
import json,re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
PREFLIGHT=ROOT/'data/live/editorial_preflight.json'; CONTEXT=ROOT/'data/live/publication_context.json'; OUT=ROOT/'data/live/script_scorecard_4.json'
GENERIC_OPENERS=('fresh check','quick market check','the headline is only half the story','here is what matters','here’s what matters','the next reaction matters','this is the crypto story')
GENERIC_CTA=('what do you think','thoughts?','who agrees','comment below','like and follow','what are your thoughts')
INSTRUCTION_PHRASES=('use verified current data','explain what matters next','generate a post','write a post','you are the editor','after generating','placeholder','insert data','fill in')
def load(p):
    try:
        x=json.loads(p.read_text(encoding='utf-8')); return x if isinstance(x,dict) else {}
    except Exception:return {}
def words(s):return re.findall(r"\b[\w$%.-]+\b",str(s or ''))
def score(s,fmt,context):
    t=str(s or '').strip(); low=t.lower(); w=len(words(t)); pts={'attention':0,'usefulness':0,'interaction':0,'evidence':0,'originality':0,'safety':0,'story':0,'conversation':0}
    hook=t.splitlines()[0].strip() if t else ''
    pts['attention']=min(22,(8 if any(x in hook for x in ['🚨','🔥','👀','📊','⚠️','🚀','🆕','💥']) else 2)+(7 if len(hook.split())>=7 and len(hook.split())<=22 else 2)+(5 if any(x in low for x in ['but','because','instead','however','while','the catch','surprise']) else 0)+(2 if len(t.splitlines())>=4 else 0))
    pts['usefulness']=min(22,7+(6 if any(x in low for x in ['support','resistance','volume','catalyst','liquidation','target','invalidation','level','evidence','flow','reaction']) else 0)+(5 if w>=80 else 3 if w>=55 else 0)+(4 if any(x in low for x in ['watch','confirm','invalidat','retest','reaction']) else 0))
    qmarks=t.count('?')
    specific_q=any(x in low for x in ['which','choose','a/b','bullish or bearish','breakout or fakeout','chase, fade, or wait','chase, pullback, or wait','agree or disagree','confirmed, mixed, or failed','opportunity or noise'])
    pts['interaction']=min(18,2+(10 if qmarks==1 else 0)+(6 if specific_q else 0))
    pts['conversation']=min(12,(6 if qmarks==1 else 0)+(4 if specific_q else 0)+(2 if any(x in low for x in ['agree','choose','which','would you','what would']) else 0))
    pts['evidence']=min(14,5+(5 if any(x in low for x in ['according','data','volume','chart','price','news','reported','source','announced']) else 0)+(4 if re.search(r'\$\d|\d+(?:\.\d+)?%|\$[A-Z]{2,}',t) else 0))
    pts['originality']=min(10,4+(4 if not low.startswith(('bitcoin is','the crypto market','today','fresh check','quick market check')) else 0)+(2 if not any(g in hook for g in GENERIC_OPENERS) else 0))
    pts['story']=min(12,3+(4 if any(x in low for x in ['because','why now','catalyst','instead','but','while','the catch','here’s the twist','here is the twist']) else 0)+(3 if w>=75 else 0)+(2 if len(t.splitlines())>=5 else 0))
    risky=any(x in low for x in ['guaranteed','risk-free','100% certain','will 10x','will 20x','easy profit','cannot lose'])
    pts['safety']=0 if risky else 5
    generic_q=any(x in low for x in GENERIC_CTA)
    if generic_q: pts['conversation']=max(0,pts['conversation']-6); pts['interaction']=max(0,pts['interaction']-5)
    instruction_like=any(x in low for x in INSTRUCTION_PHRASES)
    if instruction_like: pts['attention']=max(0,pts['attention']-5); pts['usefulness']=max(0,pts['usefulness']-8)
    if qmarks!=1: pts['interaction']=max(0,pts['interaction']-6)
    total=min(100,sum(pts.values()))
    return {'total':total,'breakdown':pts,'risk_flag':risky,'instruction_like':instruction_like,'generic_cta':generic_q,'word_count':w,'question_count':qmarks}
def completeness(s,context):
    t=str(s or '').strip(); low=t.lower(); reasons=[]; symbol=str(context.get('symbol') or '').upper()
    if symbol and not re.search(r'\$'+re.escape(symbol)+r'\b',t,re.I): reasons.append('missing_primary_cashtag')
    if len(words(t))<55: reasons.append('too_short_to_be_a_finished_story')
    if len(words(t))>180: reasons.append('too_long_for_short_mobile_post')
    title=str(context.get('news_title') or '').strip()
    if title and not any(x in low for x in [w.lower() for w in re.findall(r"[A-Za-z0-9$%.-]{4,}",title)[:4]]): reasons.append('news_story_not_grounded_in_selected_event')
    if title and not any(x in low for x in ['source','reported','according','said','announced','per ']): reasons.append('news_source_context_missing')
    if str(context.get('story_engine','')).upper() in {'TECHNICAL_SETUP','DATA_SURPRISE','MOMENTUM_DISCOVERY'} and not any(x in low for x in ['price','volume','chart','support','resistance','range','data','breakout']): reasons.append('market_evidence_missing')
    if any(x in low for x in INSTRUCTION_PHRASES): reasons.append('instruction_like_candidate')
    if any(x in low for x in GENERIC_CTA): reasons.append('generic_engagement_bait')
    if t.count('?')!=1: reasons.append('must_have_exactly_one_question')
    if len(t.splitlines())<3: reasons.append('needs_mobile_paragraph_structure')
    return reasons
def main():
    p=load(PREFLIGHT); ctx=load(CONTEXT); brief=p.get('script_director_4') or {}; fmt=brief.get('format',''); candidates=p.get('candidate_scripts_4') or []
    if not candidates:
        candidates=[{'hook':h,'script':h+'\n\nUse verified current data and explain what matters next.\n\nWhat are you watching?'} for h in brief.get('hook_candidates',[])]
    scored=[]
    for i,c in enumerate(candidates):
        txt=c.get('script') if isinstance(c,dict) else str(c); r=score(txt,fmt,ctx); missing=completeness(txt,ctx); r['completeness_failures']=missing; r['eligible']=not missing and not r['risk_flag'];
        if missing:r['total']=max(0,r['total']-25)
        scored.append({'index':i,'script':txt,**r})
    scored.sort(key=lambda x:(x['eligible'],x['total']),reverse=True); winner=next((x for x in scored if x['eligible']),None)
    result={'version':'5.7','format':fmt,'story_engine':ctx.get('story_engine',''),'candidate_count':len(scored),'winner':winner,'candidates':scored,'minimum_publish_score':72,'evidence_gate':True,'policy':['Prefer specific curiosity and conversation over generic hype.','Reject instruction-like or placeholder drafts.','Reject generic engagement bait.','Require the frozen primary cashtag and exactly one specific question.','For news, require grounding in the selected event and source context.','Use performance data as an experiment, not knowledge of a private platform algorithm.']}
    OUT.parent.mkdir(parents=True,exist_ok=True); OUT.write_text(json.dumps(result,indent=2,ensure_ascii=False),encoding='utf-8'); p['script_scorecard_4']=result; PREFLIGHT.write_text(json.dumps(p,indent=2,ensure_ascii=False),encoding='utf-8'); print(json.dumps({'status':'OK','version':'5.7','winner_score':winner['total'] if winner else 0,'candidates':len(scored),'winner_eligible':bool(winner)},indent=2))
if __name__=='__main__':main()
